#!/usr/bin/env python3
"""Real slot procedure and wallet: refused results cannot award jackpot coupons."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, rel

HARNESS = r'''
#include "currency_test_support.h"
#include "core/prototypes.h"
#include "cmd/interp.h"
#include "net/comm.h"
#include <algorithm>
#include <unordered_set>

static index_data indices[3]{};
P_index obj_index = indices;
char *coin_names[] = {const_cast<char *>("copper"), const_cast<char *>("silver"),
                      const_cast<char *>("gold"), const_cast<char *>("platinum")};
static obj_data machine{}, coupons[2]{};
static std::unordered_set<P_obj> live;
static std::vector<int> wheels;
static size_t wheel_index;
static int unavailable, failed_delivery, saves;
static std::vector<uint64_t> saved_uids;
static int64_t saved_money;
static std::string output;
int number(int low, int high) {
    assert(wheel_index < wheels.size());
    int value = wheels[wheel_index++]; assert(value >= low && value <= high); return value;
}
int coin_type(char *) { return 3; }
int generic_find(const char *,int,P_char,P_char *,P_obj *object) { *object=&machine; return 1; }
void send_to_char(const char *text,P_char) { output+=text; }
void act(const char *text,int,P_char,P_obj,void *,int) { output+=text; }
void wizlog(int,const char *,...) {}
P_obj read_object(int vnum,int) {
    if(vnum==unavailable) return nullptr;
    assert(vnum==43 || vnum==44);
    auto *obj=&coupons[vnum-43]; *obj={}; obj->R_num=vnum-42;
    obj->obj_uid=1000+vnum; obj->loc_p=LOC_NOWHERE;
    live.insert(obj); return obj;
}
P_obj find_live_object(P_obj expected,uint64_t uid) {
    return live.count(expected) && expected->obj_uid==uid ? expected : nullptr;
}
void extract_obj(P_obj object,int) {
    assert(live.erase(object));
    if(OBJ_CARRIED(object)) {
        auto *link=&object->loc.carrying->carrying;
        while(*link!=object) { assert(*link); link=&(*link)->next_content; }
        *link=object->next_content;
    }
    object->loc_p=LOC_NOWHERE;
}
bool obj_to_char(P_obj object,P_char ch) {
    if(OBJ_VNUM(object)==failed_delivery) { extract_obj(object,0); return false; }
    object->next_content=ch->carrying; ch->carrying=object;
    object->loc_p=LOC_CARRIED; object->loc.carrying=ch; return true;
}
bool do_save_silent(P_char ch,int,player_save_pipeline_result *) {
    ++saves; saved_uids.clear();
    for(P_obj obj=ch->carrying;obj;obj=obj->next_content) saved_uids.push_back(obj->obj_uid);
    saved_money=GET_COPPER(ch)+10LL*GET_SILVER(ch)+100LL*GET_GOLD(ch)+1000LL*GET_PLATINUM(ch);
    return true;
}
int fill_word(char *) { return 0; }
'''

DRIVER = r'''
int main() {
    player buyer(44); room_data rooms[1]{}; world=rooms; buyer.ch.in_room=0;
    buyer.ch.player.name=const_cast<char *>("Gambler");
    indices[0].virtual_number=999; indices[1].virtual_number=43; indices[2].virtual_number=44;
    for(int failure : {1,2,3,4,5,0,6,7,8}) {
        currency_transaction_reset_for_tests();
        buyer.ch.carrying=nullptr; machine={}; machine.R_num=0;
        for(int i=0;i<8;++i) machine.value[i]=i+11;
        std::array<int,8> before; std::copy_n(machine.value,8,before.begin());
        GET_COPPER(&buyer.ch)=GET_SILVER(&buyer.ch)=GET_GOLD(&buyer.ch)=0;
        GET_PLATINUM(&buyer.ch)=10;
        live.clear(); output.clear(); saves=0; wheel_index=0;
        unavailable=failure==4 ? 43 : 0;
        failed_delivery=failure==5 ? 43 : 0;
        wheels={39,43,47,47,47,47,47,47,47,47,47,47};
        if(failure==1) assert(currency_transaction_reserve_chest(&buyer.ch));
        if(failure==2) GET_PLATINUM(&buyer.ch)=INT_MAX;
        if(failure==3) {
            wheels={1,11,70}; // A losing wager cannot spend a reserved payment.
            assert(currency_transaction_reserve_trade(&buyer.ch,-10000));
        }
        if(failure==6) wheels={1,11,70}; // Loss.
        if(failure==7) wheels={15,1,70}; // Break even.
        if(failure==8) wheels={1,1,1}; // 15:1 payout.
        auto revision=buyer.pc.wallet_revision;
        char wager[]="1 platinum machine";
        assert(slot_machine(&machine,&buyer.ch,CMD_PUT,wager));
        if(failure>=1 && failure<=5) {
            assert(buyer.pc.wallet_revision==revision);
            assert(GET_PLATINUM(&buyer.ch)==(failure==2 ? INT_MAX : 10));
            assert(!buyer.ch.carrying && live.empty() && saves==0);
            assert(std::equal(before.begin(),before.end(),machine.value));
            assert(output.find("You receive")==std::string::npos);
        } else {
            assert(machine.value[1]==before[1]+1000 && machine.value[2]==before[2]+1);
            if(failure==7) assert(buyer.pc.wallet_revision==revision && saves==0);
            else {
                assert(buyer.pc.wallet_revision==revision+1 && saves==1);
                assert(saved_money==(failure==0 ? 50009000 : failure==6 ? 9000 : 24000));
            }
            if(failure==0) {
                assert(live.size()==2 && saved_uids.size()==2);
                std::sort(saved_uids.begin(),saved_uids.end());
                assert((saved_uids==std::vector<uint64_t>{1043,1044}));
                do_save_silent(&buyer.ch,1);
                assert(saved_money==50009000 && live.size()==2);
            } else assert(live.empty());
        }
        while(!live.empty()) extract_obj(*live.begin(),0);
    }
    (void)last_committed; (void)last_error; (void)completion; (void)wallet;
    puts("slots: refused admission/application/delivery retain purse and counters; jackpot UIDs share one checkpoint");
}
'''

(ROOT / 'bin/tests').mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='slot-payment-', dir=ROOT / 'bin/tests') as temporary:
    cpp = Path(temporary) / 'slot.cpp'
    binary = Path(temporary) / 'slot'
    cpp.write_text(HARNESS + extract_function('interp.c', 'char *one_argument(') +
                   extract_function('specs.object.c', 'int slot_machine(') + DRIVER)
    subprocess.run([
        'g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
        '-Wno-missing-field-initializers', '-g', '-O1', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-pie', '-no-pie', '-ffunction-sections', '-fdata-sections',
        '-Isrc', '-Itests/async', '-I/usr/include/mysql', str(cpp),
        rel('currency_transaction.c'), rel('currency_command.c'), rel('critical_command.c'),
        '-Wl,--gc-sections', '-lcrypto', '-o', str(binary),
    ], cwd=ROOT, check=True)
    subprocess.run([str(binary)], cwd=ROOT, check=True, timeout=30)
