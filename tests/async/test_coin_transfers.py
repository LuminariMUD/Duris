#!/usr/bin/env python3
"""Execute real coin debit/publication/recipient/refund paths under ASan/UBSan."""

from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, rel

def function(signature):
    return extract_function("actobj.c", signature) + "\n"

HARNESS = r'''
#include "currency_test_support.h"
#include "net/comm.h"
#include "classes/necromancy.h"
#include "item/storage_lockers.h"
#include <algorithm>
#include <cstdio>
#include <cstring>
bool locker_container_access_allowed(P_char, P_obj) { return true; }
static bool refuse_audit;
LockerMovementAudit::LockerMovementAudit(P_char, P_obj, P_obj, P_obj, const char *) { m_ready = !refuse_audit; }
LockerMovementAudit::~LockerMovementAudit() {}
void LockerMovementAudit::Commit() {}

const char *coins_to_string(int,int,int,int,const char *) { return "coins"; }


const int top_of_world = 1;
const char *coin_names[] = {"copper","silver","gold","platinum"};
static std::vector<P_char> characters;
static P_obj destination = nullptr;
static obj_data created = {};
static bool allocation_fails = false, placement_fails = false;
static int placed = 0, extracted = 0, announcements = 0;
static std::string feedback;

P_char find_character_by_runtime_id(uint64_t id)
{
    for (auto ch : characters) if (ch->runtime_id == id) return ch;
    return nullptr;
}
P_obj find_live_item_uid(uint64_t id)
{
    return destination && destination->obj_uid == id ? destination : nullptr;
}
void send_to_char(const char *text, P_char) { feedback += text; }
void act(const char *text, int, P_char, P_obj, void *, int type)
{
    if (type == TO_CHAR) feedback += text;
}
void wizlog(int,const char *,...) {}
int char_light(P_char) { return 0; }
int room_light(int,int) { return 0; }
void writeSavedItem(P_obj) { order.push_back("storage"); }
void writeCorpse(P_obj) { order.push_back("corpse"); }
P_obj create_money(int c,int s,int g,int p)
{
    if (allocation_fails) return nullptr;
    created = {};
    created.type = ITEM_MONEY;
    created.value[0]=c; created.value[1]=s; created.value[2]=g; created.value[3]=p;
    return &created;
}
void add_coins(P_obj pile,int c,int s,int g,int p)
{
    pile->value[0]+=c; pile->value[1]+=s; pile->value[2]+=g; pile->value[3]+=p;
}
void extract_obj(P_obj,int = FALSE) { ++extracted; }
void obj_to_char(P_obj obj,P_char ch) { obj->loc_p=LOC_CARRIED;obj->loc.carrying=ch; }
void obj_to_room(P_obj obj,int room)
{
    obj->loc_p=LOC_ROOM; obj->loc.room=room; ++placed;
}
bool put(P_char,P_obj obj,P_obj container,int,bool * = nullptr)
{
    if (placement_fails) return false;
    obj->loc_p=LOC_INSIDE;obj->loc.inside=container;container->contains=obj; ++placed;
    return true;
}
''' + function("enum class coin_debit_action") + ";\n" + \
    function("struct coin_debit_context") + ";\n" + \
    function("struct coin_give_credit_context") + r''';
constexpr uint8_t COIN_DEBIT_ACCIDENTAL = 1U << 0, COIN_DEBIT_ALL = 1U << 1;
void announce_coin_give(P_char,P_char recipient,const coin_give_credit_context &context)
{
    ++announcements;
    assert(recipient->points.cash[context.coin_type] >= context.amount);
    order.push_back("give");
}
''' + "".join(function(signature) for signature in (
    "static bool change_nonpersistent_coins(", "static bool credit_coins(",
    "int64_t coin_debit_value(", "void refund_committed_coin_debit(",
    "bool coin_put_destination_available(", "void coin_give_credit_completion(",
    "bool begin_coin_give_credit(", "void finish_coin_put_publication(",
    "bool publish_transient_coin_put(", "bool publish_pc_corpse_coin_put(",
    "bool publish_coin_put(", "void publish_coin_drop(",
    "void coin_debit_completion(", "bool submit_coin_debit(",
)) + r'''
static void reset()
{
    currency_transaction_reset_for_tests();
    order.clear(); feedback.clear(); characters.clear();
    destination=nullptr;allocation_fails=placement_fails=refuse_audit=false;
    placed=extracted=announcements=dirty=alerts=0;
    invalid_account=nullptr;
}
static void purse(P_char ch, std::array<int64_t,4> coins)
{
    for (size_t i=0;i<4;++i) ch->points.cash[i]=static_cast<int>(coins[i]);
}
static coin_debit_context payment(P_char sender,P_char recipient,coin_debit_action action)
{
    sender->in_room=0;sender->runtime_id=100;
    recipient->in_room=0;recipient->runtime_id=200;
    characters={sender,recipient};
    coin_debit_context context={};
    context.amount={0,0,10,0};context.room=0;context.action=action;
    context.coin_type=2;context.target_runtime_id=200;context.container_uid=300;
    return context;
}
static void actor_kind(player &actor,int kind)
{
    if(kind==1) actor.ch.specials.act |= ACT_ISNPC;
    if(kind==2) actor.pc.pid=0;
}
int main()
{
    room_data rooms[2]={}; world=rooms;
    // All real callers share a four-count debit: PC, NPC and no-PID fallback.
    for(int kind=0;kind<3;++kind)
    for(auto action:{coin_debit_action::drop,coin_debit_action::put,coin_debit_action::give})
    {
        reset();player sender(44),recipient(46);actor_kind(sender,kind);
        purse(&sender.ch,{3,12,40,2});
        auto context=payment(&sender.ch,&recipient.ch,action);
        obj_data bag={};bag.obj_uid=300;bag.type=ITEM_CONTAINER;
        obj_to_char(&bag,&sender.ch);destination=&bag;
        for(int remaining=30;remaining>=0;remaining-=10)
        {
            assert(submit_coin_debit(&sender.ch,context));
            assert((wallet(&sender.ch)==std::array<int64_t,4>{3,12,remaining,2}));
        }
        assert(kind!=0 || sender.pc.wallet_revision==4);
        if(action==coin_debit_action::give) {
            assert((wallet(&recipient.ch)==std::array<int64_t,4>{0,0,40,0}));
            assert(announcements==4 && recipient.pc.wallet_revision==4);
            assert(order[0]=="save:44" || kind!=0);
        } else if(action==coin_debit_action::put) {
            assert(bag.contains && bag.contains->value[2]==40);
        } else assert(placed==4 && created.value[2]==10);
    }
    // A refused audit for an existing pile restores the debited wallet once.
    {
        reset(); player sender(44),recipient(46);
        auto context=payment(&sender.ch,&recipient.ch,coin_debit_action::put);
        purse(&sender.ch,{0,0,40,0});
        obj_data bag={},pile={};bag.obj_uid=300;bag.type=ITEM_CONTAINER;
        pile.type=ITEM_MONEY;pile.value[2]=7;bag.contains=&pile;
        obj_to_char(&bag,&sender.ch);destination=&bag;refuse_audit=true;
        assert(submit_coin_debit(&sender.ch,context));
        assert(GET_GOLD(&sender.ch)==40 && pile.value[2]==7 && placed==0);
        assert(feedback.find("restor")!=std::string::npos);
    }
    // NPC recipient, self give, and staff no-debit credit.
    reset();player sender(44),recipient(46);
    recipient.ch.specials.act|=ACT_ISNPC;
    auto context=payment(&sender.ch,&recipient.ch,coin_debit_action::give);
    purse(&sender.ch,{0,0,40,0});
    assert(submit_coin_debit(&sender.ch,context));
    assert(GET_GOLD(&sender.ch)==30 && GET_GOLD(&recipient.ch)==10);
    assert(begin_coin_give_credit(&sender.ch,&recipient.ch,context,false));
    assert(GET_GOLD(&sender.ch)==30 && GET_GOLD(&recipient.ch)==20);
    context.target_runtime_id=sender.ch.runtime_id;
    assert(submit_coin_debit(&sender.ch,context));
    assert(GET_GOLD(&sender.ch)==30);

    // Mixed/all coins and values beyond an aggregate int remain exact.
    for(int kind=0;kind<3;++kind)
    {
        reset();player actor(44),other(46);actor_kind(actor,kind);
        auto all=payment(&actor.ch,&other.ch,coin_debit_action::drop);
        all.amount={3,12,17,3000000};all.flags=COIN_DEBIT_ALL;
        purse(&actor.ch,{3,12,17,3000000});
        assert(submit_coin_debit(&actor.ch,all));
        assert((wallet(&actor.ch)==std::array<int64_t,4>{0,0,0,0}));
        for(size_t i=0;i<4;++i) assert(created.value[i]==all.amount[i]);
    }
    // PC and NPC overflow, missing recipient and invalid identity each refund once.
    for(int failure=0;failure<5;++failure)
    {
        reset();player giver(44),target(46);
        auto give=payment(&giver.ch,&target.ch,coin_debit_action::give);
        purse(&giver.ch,{3,12,40,2});
        if(failure<2) GET_GOLD(&target.ch)=INT_MAX;
        if(failure==1) target.ch.specials.act|=ACT_ISNPC;
        if(failure==2) characters.pop_back();
        if(failure==3) invalid_account=&target.ch;
        if(failure==4) target.pc.pid=0;
        const auto before=wallet(&target.ch);
        assert(submit_coin_debit(&giver.ch,give));
        assert((wallet(&giver.ch)==std::array<int64_t,4>{3,12,40,2}));
        assert(wallet(&target.ch)==before && announcements==0);
        assert(giver.pc.wallet_revision==2 && target.pc.wallet_revision==0 && dirty==2);
        assert(feedback.find("restor")!=std::string::npos && alerts==0);
    }
    reset();player staff(44),full_recipient(46);
    auto minted=payment(&staff.ch,&full_recipient.ch,coin_debit_action::give);
    GET_GOLD(&full_recipient.ch)=INT_MAX;
    assert(begin_coin_give_credit(&staff.ch,&full_recipient.ch,minted,false));
    assert(GET_GOLD(&staff.ch)==0 && staff.pc.wallet_revision==0 && !announcements);
    assert(feedback.find("nothing changed")!=std::string::npos);
    // All put/drop failure boundaries restore the exact mixed debit.
    for(int kind=0;kind<3;++kind)
    for(int failure=0;failure<7;++failure)
    {
        reset();player actor(44),other(46);actor_kind(actor,kind);
        auto request=payment(&actor.ch,&other.ch,coin_debit_action::put);
        request.amount={3,12,17,0};purse(&actor.ch,{8,20,40,2});
        obj_data bag={},old={};bag.type=ITEM_CONTAINER;bag.obj_uid=300;
        obj_to_char(&bag,&actor.ch);destination=&bag;
        if(failure==0) destination=nullptr;
        if(failure==1) bag.value[1]|=CONT_CLOSED;
        if(failure==2) {old.type=ITEM_MONEY;old.value[2]=INT_MAX;bag.contains=&old;}
        if(failure==3) allocation_fails=true;
        if(failure==4) placement_fails=true;
        if(failure==5) request.room=1;
        if(failure==6) {request.action=coin_debit_action::drop;allocation_fails=true;}
        assert(submit_coin_debit(&actor.ch,request));
        assert((wallet(&actor.ch)==std::array<int64_t,4>{8,20,40,2}));
        assert(placed==0 && announcements==0 && alerts==0);
        assert(feedback.find("You put")==std::string::npos && feedback.find("You drop")==std::string::npos);
        assert(kind!=0 || actor.pc.wallet_revision==2);
    }
    // Insufficient selected denomination does not spend the platinum instead.
    for(int kind=0;kind<3;++kind)
    {
        reset();player actor(44),other(46);actor_kind(actor,kind);
        auto request=payment(&actor.ch,&other.ch,coin_debit_action::give);
        purse(&actor.ch,{0,0,0,4});
        bool submitted=submit_coin_debit(&actor.ch,request);
        assert(submitted==(kind==0));
        assert((wallet(&actor.ch)==std::array<int64_t,4>{0,0,0,4}));
        assert(actor.pc.wallet_revision==0 && !announcements && !dirty);
    }
    // Reserved payment: the facade returns true but refuses; no publication.
    reset();player reserved(44),other(46);
    auto request=payment(&reserved.ch,&other.ch,coin_debit_action::drop);
    purse(&reserved.ch,{0,0,40,0});
    assert(currency_transaction_reserve_trade(&reserved.ch,-3500));
    assert(submit_coin_debit(&reserved.ch,request));
    assert(GET_GOLD(&reserved.ch)==40 && reserved.pc.wallet_revision==0 && placed==0);
    assert(feedback.find("did not commit")!=std::string::npos);
    // submit=false: invalid actor identity also never publishes.
    currency_transaction_release_trade(44);invalid_account=&reserved.ch;
    assert(!submit_coin_debit(&reserved.ch,request));
    assert(GET_GOLD(&reserved.ch)==40 && placed==0);

    // Persistent destinations retain sender-first ordering.
    for(int type:{ITEM_STORAGE,ITEM_CORPSE})
    {
        reset();player actor(44),other2(46);purse(&actor.ch,{0,0,40,0});
        auto put_request=payment(&actor.ch,&other2.ch,coin_debit_action::put);
        obj_data bag={};bag.obj_uid=300;bag.type=type;
        if(type==ITEM_CORPSE)bag.value[CORPSE_FLAGS]=PC_CORPSE;
        obj_to_char(&bag,&actor.ch);destination=&bag;
        assert(submit_coin_debit(&actor.ch,put_request));
        assert(order.size()==2 && order[0]=="save:44");
        assert(order[1]==(type==ITEM_CORPSE ? "corpse":"storage"));
    }
    // Refund refusal must be observable even when submission returns true.
    reset();player full(44);GET_GOLD(&full.ch)=INT_MAX;
    refund_committed_coin_debit(&full.ch,{0,0,10,0},0);
    assert(alerts==1 && full.pc.wallet_revision==0 && GET_GOLD(&full.ch)==INT_MAX);
    // A player wallet can never enter the direct-mutation fallback.
    assert(!change_nonpersistent_coins(&full.ch,{}));
    return 0;
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="coin-transfers-", dir=ROOT / "bin/tests") as temporary:
    source = Path(temporary) / "harness.cpp"
    binary = Path(temporary) / "harness"
    source.write_text(HARNESS)
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        "-Wno-unused-function", "-Wno-missing-field-initializers", "-g", "-O1",
        "-fsanitize=address,undefined", "-ffunction-sections", "-fdata-sections",
        "-Isrc", "-Itests/async", "-I/usr/include/mysql", str(source),
        rel("currency_transaction.c"), rel("currency_command.c"), rel("critical_command.c"),
        "-Wl,--gc-sections", "-lcrypto", "-o", str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
print("[PASS] exact PC/NPC give, put/drop, overflow/refusal/refunds and sender-first saves")
