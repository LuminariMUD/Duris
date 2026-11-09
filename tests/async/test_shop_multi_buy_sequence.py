#!/usr/bin/env python3
"""Execute produced-purchase staging and final settlement with delayed authority.

The production shop functions and weight calculations run unchanged. The worker
boundary is controlled here; repository and socket journeys qualify the real
ownership paths separately.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, HARNESS_STUBS

SHOP = (SRC / 'economy/shop.c').read_text()
HANDLER = (SRC / 'world/handler.c').read_text()

def function(source, signature):
    start = source.rindex(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

PRELUDE = r"""
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "net/comm.h"
#include "world/object_template.h"
#include "economy/shop.h"
#include "economy/currency_transaction.h"
#include "economy/currency_value.h"
#include "item/item_movement_transaction.h"
#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

P_obj object_list = nullptr;
static room_data room{};
P_room world = &room;
extern const int top_of_world = 0;
int top_of_objt = 1;
static index_data indexes[2]{};
P_index obj_index = indexes;
static shop_data shop{};
shop_data *shop_index = &shop;
int number_of_shops = 1;
static object_template bag_template{};
static char_data buyer{}, keeper{};
static descriptor_data descriptor{};
static pc_only_data pc{};
static npc_only_data npc{};
static obj_data stock{}, bag{};
static int clone_weight, fail_clone_after, clones, charges, refunds, keeper_credits, submissions;
static int grants, completions;
static unsigned clone_flags;
static bool accept_submission, payment_commits;
static std::string output;
static uint64_t next_uid = 1000;
static std::vector<P_obj> held;
static item_movement_completion_fn grant_done;
static std::vector<uint8_t> grant_context;
static int64_t purse(P_char ch) {
    return GET_COPPER(ch) + 10LL*GET_SILVER(ch) + 100LL*GET_GOLD(ch) + 1000LL*GET_PLATINUM(ch);
}
static void money(P_char ch, int64_t value) {
    const auto coins=currency_canonical_value(value);
    for (size_t i=0; i<4; ++i) ch->points.cash[i]=static_cast<int>(coins.amount[i]);
}
const object_template *find_object_template(int vnum) { return vnum==600 ? &bag_template : nullptr; }
int real_room(int) { return 0; }
void send_to_char(const char *message, P_char) { output += message; }
void do_tell(P_char, char *, int) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
int writeShopKeeper(P_char, int) { return 1; }
void ADD_MONEY(P_char ch, int amount) {
    if (ch==&buyer) ++refunds;
    else ++keeper_credits;
    money(ch,purse(ch)+amount);
}
int SUB_MONEY(P_char ch, int amount, int) { money(ch,purse(ch)-amount); return 0; }
char *coin_stringv(int amount, int) { static char text[32]; snprintf(text,sizeof(text),"%d coins",amount); return text; }
int checked_substitute_strings(char *result, size_t size, const char *, const char *const *, size_t) { return snprintf(result,size,"paid"); }
P_obj read_object(int, int) {
    if (fail_clone_after>=0 && clones>=fail_clone_after) return nullptr;
    ++clones;
    auto *object=new obj_data{};
    object->obj_uid=next_uid++; object->R_num=0; object->type=ITEM_FOOD; object->loc_p=LOC_NOWHERE;
    object->weight=clone_weight; object->short_description=const_cast<char *>("a ration");
    object->extra_flags=clone_flags;
    object->next=object_list; object_list=object;
    return object;
}
void extract_obj(P_obj object, int) {
    P_obj *link=&object_list;
    while (*link && *link!=object) link=&(*link)->next;
    assert(*link==object); *link=object->next;
    delete object;
}
bool obj_to_char(P_obj object, P_char ch) { object->loc_p=LOC_CARRIED; object->loc.carrying=ch; return true; }
void obj_from_char(P_obj object) { object->loc_p=LOC_NOWHERE; object->loc.carrying=nullptr; }
void obj_to_obj(P_obj object, P_obj container) {
    object->loc_p=LOC_INSIDE; object->loc.inside=container;
    object->next_content=container->contains; container->contains=object;
    ++grants;
}
bool currency_transaction_submit_wallet_value(P_char ch, int64_t amount, currency_reason_type,
    int64_t, critical_source_site, critical_deadline_class, currency_completion_fn done,
    const void *context, size_t context_size) {
    assert(amount<0);
    if (payment_commits) { money(ch,purse(ch)+amount); ++charges; }
    if (done) done(ch,payment_commits,{},0,static_cast<const uint8_t *>(context),context_size);
    return true;
}
bool item_creation_grant_submit_batch_to_player(P_char, P_obj const *objects, size_t count,
    P_char, P_obj, item_movement_completion_fn done, const void *context, size_t size) {
    ++submissions;
    if (!accept_submission) return false;
    held.assign(objects,objects+count); grant_done=done;
    grant_context.assign(static_cast<const uint8_t *>(context),static_cast<const uint8_t *>(context)+size);
    return true;
}
"""

WEIGHT = '\n'.join(function(HANDLER, signature) for signature in (
    'static const object_template *container_prototype(',
    'static int container_weight_reduction_pct(',
    'static int sum_direct_contents_weight(',
    'static int calculated_container_weight(',
    'int container_total_weight(',
))
start = SHOP.index('struct produced_purchase_batch')
end = SHOP.index('void lore_item(', start)
STATE = SHOP[start:end]
FUNCTIONS = '\n'.join(function(SHOP, signature) for signature in (
    'static P_obj shop_trade_find_object(', 'static P_char shop_trade_find_keeper(',
    'static bool shop_trade_container_accepts(', 'static bool shop_purchase_count(',
    'static int64_t shop_wallet_value(', 'static void shop_purchase_report(',
    'static void shop_creation_refund(', 'static void shop_discard_produced(',
    'static bool shop_stage_produced(', 'static void shop_produced_completion(',
    'static void shop_creation_grant_completion(', 'static void shop_creation_payment_completion(',
    'static bool shop_begin_produced(',
))
FORWARDS = ""
DRIVER = r"""
static void reset(int balance=100000, int capacity=100000) {
    while (object_list && object_list!=&stock) extract_obj(object_list,FALSE);
    produced_purchase_batches.clear();
    buyer={};keeper={};pc={};npc={};bag={};stock={};room={};shop={};descriptor={};
    buyer.only.pc=&pc;pc.pid=42; buyer.in_room=0;
    buyer.desc=&descriptor;descriptor.character=&buyer;
    SET_BIT(buyer.specials.act,PLR_SMARTPROMPT);
    keeper.only.npc=&npc;keeper.specials.act=ACT_ISNPC;keeper.in_room=0;
    room.people=&keeper;shop.keeper=0;shop.in_room=100;
    indexes[0].virtual_number=500;indexes[1].virtual_number=600;
    stock.obj_uid=100;stock.R_num=0;stock.type=ITEM_FOOD;
    stock.loc_p=LOC_CARRIED;stock.loc.carrying=&keeper;
    bag.obj_uid=700;bag.R_num=1;bag.type=ITEM_CONTAINER;bag.value[0]=capacity;
    bag.loc_p=LOC_CARRIED;bag.loc.carrying=&buyer;bag_template.weight=0;
    stock.next=&bag;object_list=&stock;
    clone_weight=1;fail_clone_after=-1;clones=charges=refunds=keeper_credits=submissions=grants=completions=0;
    accept_submission=payment_commits=true;output.clear();held.clear();
    clone_flags=0;
    money(&buyer,balance);money(&keeper,0);
}
static void finish(bool committed) {
    ++completions;
    if (committed) for (auto object:held) obj_to_obj(object,&bag);
    grant_done(&buyer,committed,{},committed ? 0 : ESTALE,grant_context.data(),grant_context.size());
}
int main() {
    {
        for (int count:{1,2,12,13,20,50}) {
            reset();
            assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,count,10));
            assert(submissions==1 && charges==1 && held.size()==static_cast<size_t>(count));
            assert(grants==0 && output.find("You now have")==std::string::npos);
            assert(bag.contains==nullptr && bag.weight==0);
            finish(true);
            assert(descriptor.prompt_mode);
            assert(grants==count && completions==1 && keeper_credits==1);
            assert(purse(&buyer)==100000-count*10 && purse(&keeper)==count*10);
            assert(produced_purchase_batches.empty());
            if (count>1) assert(output.find("Purchase complete:")!=std::string::npos);
        }
        reset(70);assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(held.size()==7);finish(true);assert(purse(&buyer)==0 && purse(&keeper)==70);
        reset(1000,3);assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(held.size()==3);finish(true);assert(purse(&buyer)==970);
        reset(0);assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(charges==0 && submissions==0 && object_list==&stock);
        reset(1000,3);obj_data existing{};existing.weight=1;bag.contains=&existing;
        assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(held.size()==2 && bag.contains==&existing);finish(true);
        reset();bag.type=ITEM_TREASURE;
        assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(charges==0 && submissions==0 && object_list==&stock);
        for (unsigned restricted : {ITEM_NODROP, ITEM_ARTIFACT}) {
            reset();clone_flags=restricted;
            assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
            assert(charges==0 && submissions==0 && object_list==&stock);
        }
        reset();assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,50,0));
        finish(true);assert(charges==0 && purse(&buyer)==100000 && purse(&keeper)==0);
        assert(output.find("for no charge.")!=std::string::npos);
        reset();assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        finish(false);assert(purse(&buyer)==100000 && purse(&keeper)==0 && refunds==1 && grants==0);
        assert(descriptor.prompt_mode);
        assert(object_list==&stock && produced_purchase_batches.empty());
        reset();accept_submission=false;
        assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(purse(&buyer)==100000 && purse(&keeper)==0 && object_list==&stock);
        reset();fail_clone_after=5;
        assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(charges==0 && submissions==0 && object_list==&stock && bag.contains==nullptr);
        reset();SET_BIT(bag.value[1],CONT_CLOSED);
        assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
        assert(charges==0 && submissions==0 && object_list==&stock);
        reset();clone_weight=0;
        assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,50,10));assert(held.size()==50);finish(true);
        reset(1000,3);bag_template.weight=-2;bag.weight=-2;
        assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));assert(held.size()==5);finish(true);
        reset(1000,3);bag.value[4]=50;
        assert(shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));assert(held.size()==5);finish(true);
        reset();GET_PLATINUM(&buyer)=INT_MAX;
        assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,50,INT_MAX/2));
        assert(charges==0 && submissions==0 && object_list==&stock);
    }
    reset();payment_commits=false;
    assert(!shop_begin_produced(&buyer,&keeper,&stock,&bag,0,20,10));
    assert(charges==0 && refunds==0 && object_list==&stock);
    int count=0;
    for (const char *valid:{"1","2","20","50"}) assert(shop_purchase_count(valid,&count));
    for (const char *invalid:{"0","-1","51","1.5","1tail","9999999999999999999999"}) assert(!shop_purchase_count(invalid,&count));
    reset();
}
"""

(ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='shop-batch-',dir=ROOT / 'bin/tests') as temporary:
    source=Path(temporary)/'shop_batch.cpp'
    binary=Path(temporary)/'shop_batch'
    source.write_text(PRELUDE + WEIGHT + STATE + FORWARDS + FUNCTIONS + DRIVER)
    subprocess.run(['g++','-std=c++20','-g','-O1','-Wall','-Wextra','-Werror',
                    '-Wno-unused-function','-ffunction-sections','-fdata-sections',
                    '-fsanitize=address,undefined','-Isrc',str(source),str(HARNESS_STUBS),
                    '-Wl,--gc-sections','-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],cwd=ROOT,check=True)
print('[PASS] produced purchases stage, charge and complete once for 1/2/12/13/20/50 roots')
