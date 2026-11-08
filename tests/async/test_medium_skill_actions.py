#!/usr/bin/env python3
"""Execute #715 command decision boundaries using the production handler blocks."""
import re
import subprocess

from _paths import ROOT, extract_function
from _source_contract import strip_comments


def handler(signature):
    return strip_comments(extract_function("actoff.c", signature))


def between(text, start, end):
    return text[text.index(start):text.index(end, text.index(start))]


breath = between(handler("void do_dragon_breath("), "int select_chance =", "if (((select_chance")
lance = between(handler("void lance_charge("), "if (dir != -1 && CAN_GO", "if (IS_OP_GOLEM")
retreat = handler("void do_retreat(")
expedited = re.search(r"if \((expdr[^)]*)\)", retreat).group(1)
tackle = handler("void do_tackle(")
sturdy = between(tackle, "if ((has_innate(vict", "\n\t{")
sturdy = sturdy[sturdy.index("(") + 1:].strip()[:-1]
learning = []
for name, skill in (("void rush(", "SKILL_RUSH"), ("void rescue(", "SKILL_RESCUE")):
    body = handler(name)
    statement = re.search(r"notch_skill\(ch, " + skill + r".*?;", body, re.S).group()
    condition = re.search(r"if \((number\(1, 100\) > GET_CHAR_SKILL\(ch, " + skill + r"\))\)", body).group(1)
    learning.append("bool miss_" + skill + "(Char *ch) {" + statement + "return " + condition + ";}")
roundkick = handler("bool roundkick(")
assert roundkick.count("CharWait(victim,") == 1
assert "CharWait(victim, roundkick_target_lag())" in roundkick
assert "SET_POS(victim, POS_KNEELING + GET_STAT(victim))" in roundkick
lance_source = handler("void lance_charge(")
assert re.search(r"if \(!do_simple_move\(ch, dir, 0\)\)\s*return;", lance_source)
assert re.search(r"void do_dragon_breath\(.*?char name\[MAX_INPUT_LENGTH\] = \{\};", strip_comments(handler("void do_dragon_breath(")), re.S)
assert "centaur, quadruped or drider" in extract_function("actoff.c", "std::string tackle_facts(")
rush_body = handler("void rush(")
rush_free_attack = between(rush_body[rush_body.rindex("if (GET_OPPONENT(ch))"):], "if (GET_OPPONENT(ch))", "\n\t}\n")
rescue_body = handler("void rescue(")
rescue_cleave = between(rescue_body, "if (!rescue_all && GET_CHAR_SKILL(ch, SKILL_CLEAVE))", 'send_to_char("&+WBanzai!')
stab = handler("bool single_stab(")
awareness = between(stab, "if (((IS_AFFECTED", "\n\t{")[4:-1]
assert stab.index("dam = backstab_noticed_damage") < stab.index("dam = critical_stab_damage")

cpp = r'''#include <algorithm>
#include <cassert>
#include <cstdio>
struct Char { int skills[3]{}; int race=0, size=1, innate=0, flags=0; bool recent=false; int in_room=0; };
struct Exit { int to_room=0; bool wall=false, allowed=true; };
struct Room { Exit *dir_option[4]{}; } world[1];
constexpr int NUM_EXITS=4, SKILL_DRAGON_BREATH=0, SKILL_RUSH=1, SKILL_RESCUE=2;
constexpr int RACE_QUADRUPED=10, INNATE_HORSE_BODY=1, INNATE_SPIDER_BODY=2;
constexpr int AFF_AWARE=1, AFF_SKILL_AWARE=2, AFF_KNOCKED_OUT=4, SKILL_BACKSTAB=3;
int rev_dir[4]={2,3,0,1};
#define GET_CHAR_SKILL(ch, skill) ((ch)->skills[skill])
#define GET_RACE(ch) ((ch)->race)
#define GET_POS(ch) 0
#define IS_AFFECTED(ch, flag) ((ch)->flags & flag)
#define EXIT(ch, dir) (world[(ch)->in_room].dir_option[dir])
#define CAN_GO(ch, dir) (EXIT(ch, dir) && EXIT(ch, dir)->allowed)
int BOUNDED(int lo,int value,int hi) { return std::clamp(value,lo,hi); }
int get_property(const char *,int value) { return value; }
bool learned;
int roll, draws, notches;
bool notch_skill(Char *,int,float) { ++notches; return learned; }
int number(int lo,int hi) { ++draws; return std::clamp(roll,lo,hi); }
bool has_innate(Char *ch,int flag) { return ch->innate & flag; }
int get_takedown_size(Char *ch) { return ch->size; }
bool affected_by_spell(Char *ch,int) { return ch->recent; }
bool check_wall(int room,int dir) { assert(dir>=0 && dir<NUM_EXITS); return world[room].dir_option[dir]->wall; }
bool can_enter_room(Char *,int,int) { return true; }
'''
cpp += "int selection(Char *ch) {" + breath + "return select_chance;}\n"
cpp += "int continued(Char *ch,int dir) { int continue_dir=-1, i, available_exits=0, choice;" + lance + "return continue_dir;}\n"
cpp += "bool new_direction(int expdr) { return " + expedited + ";}\n"
cpp += "bool sturdy_target(Char *ch,Char *vict) { return " + sturdy + ";}\n"
cpp += "bool penalized(Char *victim,bool crit) {return " + awareness + ";}\n"
cpp += "\n".join(learning)
cpp += r'''

constexpr int PRIMARY_WEAPON=0, SKILL_CLEAVE=2;
struct attack_continuation {};
struct continuation_result { bool go; bool can_continue() const { return go; } };
int alive_checks, freed_uses;
attack_continuation begin_attack_continuation(Char *,Char *) { return {}; }
continuation_result check_attack_continuation(attack_continuation) { return {alive_checks-->0}; }
Char *opponent;
void *equipment_of(Char *) { return nullptr; }
void hit_char(Char *,Char *,void *) { ++freed_uses; }
void stop_fighting(Char *) { ++freed_uses; }
void set_fighting(Char *,Char *) { ++freed_uses; }
int cleaves;
bool cleave(Char *,Char *) { ++cleaves; return true; }
#define hit(a,b,c) (hit_char(a,b,nullptr))
#define GET_OPPONENT(ch) opponent
#undef GET_CHAR_SKILL
#define GET_CHAR_SKILL(ch, skill) ((ch)->skills[skill])
struct WithEquipment : Char { void *equipment[1]{}; };
'''
cpp += "void rush_free(WithEquipment *ch,WithEquipment *victim) {" + rush_free_attack + "}\n"
cpp += "void rescue_cleave(WithEquipment *ch,WithEquipment *t_ch,bool rescue_all) {" + rescue_cleave + "++freed_uses;}\n"
cpp += r'''
int main() {
    Char actor, target;
    for (int rating : {1,19,20,50,100}) assert(new_direction(rating));
    assert(!new_direction(0));
    actor.skills[0]=10; assert(selection(&actor)==9);
    actor.skills[0]=100; assert(selection(&actor)==95);
    for (bool gains : {false,true}) {
        learned=gains; actor.skills[1]=actor.skills[2]=50; notches=draws=0;
        roll=50; assert(!miss_SKILL_RUSH(&actor)); assert(!miss_SKILL_RESCUE(&actor));
        roll=51; assert(miss_SKILL_RUSH(&actor)); assert(miss_SKILL_RESCUE(&actor));
        assert(notches==4 && draws==4);
    }
    target.race=RACE_QUADRUPED; assert(sturdy_target(&actor,&target));
    actor.size=2; assert(!sturdy_target(&actor,&target));
    actor.size=1; target.race=0; assert(!sturdy_target(&actor,&target));
    target.innate=INNATE_HORSE_BODY; assert(sturdy_target(&actor,&target));
    Exit exits[4]; for(int i=0;i<4;++i) world[0].dir_option[i]=&exits[i];
    exits[0].wall=true; exits[1].wall=true; exits[3].allowed=false;
    roll=0; assert(continued(&actor,-1)==2); // each candidate's wall, including an in-room charge
    assert(continued(&actor,0)==-1); // the sole clear exit is the reverse direction
    exits[1].wall=false; assert(continued(&actor,0)==1);
    exits[0].wall=false; assert(continued(&actor,0)==0); // continue straight when possible
    WithEquipment rusher, rushed; opponent=&rushed;
    alive_checks=0; freed_uses=0; rush_free(&rusher,&rushed); assert(freed_uses==1); // rusher died to the free attack
    alive_checks=1; freed_uses=0; rush_free(&rusher,&rushed); assert(freed_uses==3); // set_fighting ended it
    alive_checks=2; freed_uses=0; rush_free(&rusher,&rushed); assert(freed_uses==4);
    rusher.skills[SKILL_CLEAVE]=50;
    alive_checks=0; freed_uses=cleaves=0; rescue_cleave(&rusher,&rushed,false); assert(cleaves==1 && freed_uses==0);
    alive_checks=1; freed_uses=cleaves=0; rescue_cleave(&rusher,&rushed,false); assert(cleaves==1 && freed_uses==1);
    target.flags=AFF_AWARE; assert(!penalized(&target,true)); assert(penalized(&target,false));
    target.recent=true; assert(penalized(&target,true));
    std::puts("PASS #715 skill actions: selection, retreat ratings, exit walls/reversal, learning, tackle and critical awareness");
}
'''
out = ROOT / "bin/tests/medium-skill-actions"
out.mkdir(parents=True, exist_ok=True)
path, binary = out / "harness.cpp", out / "harness"
path.write_text(cpp)
subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-fsanitize=address,undefined",
                "-fno-sanitize-recover=all", "-fno-pie", "-no-pie", str(path), "-o", str(binary)], check=True)
subprocess.run([str(binary)], check=True, timeout=30)
