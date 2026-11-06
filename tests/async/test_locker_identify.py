"""Exercise locker stat routing and the actual item lore renderer."""
from pathlib import Path
import re
import subprocess
import tempfile

from _paths import extract_function

ROOT = Path(__file__).resolve().parents[2]
service = (ROOT / 'src/item/locker_identify.c').read_text()
service = re.sub(r'^#include.*\n', '', service, flags=re.M)
locker = (ROOT / 'src/item/storage_lockers.c').read_text()
stat = locker.split('if (cmd == CMD_STAT && !IS_TRUSTED(ch))',1)[1].split('StorageLocker *pLocker',1)[0]
assert 'locker_identify(ch, tmp_object, cost)' in stat
assert 'locker_identify_receipt(ch)' in stat and 'locker_identify_replay' not in stat
assert 'CharWait' not in stat and 'do_lore' not in stat and 'SUB_MONEY' not in stat
lore = (ROOT / 'src/cmd/actnew.c').read_text()
normal = lore.split('void do_lore(',1)[1].split('static void render_item_lore(',1)[0]
assert 'lore_item(ch, obj);\n\tCharWait(ch, lore_lag());' in normal
assert 'static int lore_lag()\n{\n\treturn 3;\n}' in lore
captured = lore.split('std::string item_lore_description(',1)[1].split('const char *MAKE_FORMAT',1)[0]
assert 'CharWait' not in captured and 'send_to_char' not in captured

(ROOT / 'bin').mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(dir=ROOT / 'bin') as temp:
    temp = Path(temp)
    cpp = temp / 'locker.cpp'
    binary = temp / 'locker'

    # Execute the entire room special and production argument parser. Item
    # lookup, identification and attribute display are observable boundaries;
    # unrelated locker operations must never run in these dispatch cases.
    interp = (ROOT / 'src/cmd/interp.c').read_text()
    routing_prefix = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "cmd/interp.h"
#include "item/storage_lockers.h"
#include <cassert>
#include <cstdlib>
#include <iostream>
#include <string>
std::string output;
int attributes, identifies, receipts, lookups, prices, locker_lookups;
int configured_cost = 100;
obj_data item = {};
void logit(const char *,const char *,...) { std::abort(); }
int locker_exit_room(P_char,int room) { return room; }
StorageLocker *locker_current(P_char) { ++locker_lookups; return nullptr; }
bool locker_handle_leave(P_char,StorageLocker *,int,int) { std::abort(); }
int locker_handle_save_hook(P_char,int) { std::abort(); }
void locker_handle_postsave(P_char,StorageLocker *,int) { std::abort(); }
int locker_grantcmd(P_char,char *) { std::abort(); }
int locker_equipcmd(P_char,char *) { std::abort(); }
int locker_opencmd(P_char,char *) { std::abort(); }
int locker_closecmd(P_char,char *) { std::abort(); }
void display_no_mem(P_char) { std::abort(); }
void send_to_char(const char *text,P_char) { output += text; }
void do_attributes(P_char,char *,int cmd) { assert(cmd == CMD_STAT); ++attributes; }
int generic_find(const char *name,int type,P_char,P_char *ch,P_obj *obj) {
 assert(type == FIND_OBJ_INV); ++lookups;
 *ch = nullptr; *obj = !strcmp(name,"sword") ? &item : nullptr; return 0;
}
int get_property(const char *name,int fallback) {
 assert(!strcmp(name,"locker.stat.cost") && fallback == 100);
 ++prices; return configured_cost;
}
void locker_identify(P_char,P_obj obj,int cost) {
 assert(obj == &item && cost == configured_cost); ++identifies;
}
void locker_identify_receipt(P_char) { ++receipts; }
'''
    routing_main = r'''
int main() {
 char_data ch = {}; ch.player.level = 30;
 auto stat = [&](const char *text,int consumed) {
  char arg[MAX_INPUT_LENGTH]; strcpy(arg,text); output.clear();
  assert(storage_locker(0,&ch,CMD_STAT,arg) == consumed);
 };
 for (const char *arg : {"", "   ", "\t", " \t  "}) {
  int before = attributes;
  stat(arg,TRUE);
  assert(attributes == before + 1 && output.empty());
  assert(!identifies && !receipts && !lookups && !prices && !locker_lookups);
 }
 stat("sword",TRUE);
 assert(identifies == 1 && lookups == 1 && prices == 1 && attributes == 4);
 configured_cost = 275;
 stat("  SWORD ",TRUE);
 assert(identifies == 2 && lookups == 2 && prices == 2 && output.empty());
 for (const char *arg : {"receipt", "  ReCeIpT \t"}) {
  int before = receipts;
  stat(arg,TRUE);
  assert(receipts == before + 1 && identifies == 2 && lookups == 2 && prices == 2);
 }
 stat("missing",TRUE);
 assert(output.find("what item should i tell you more about?") != std::string::npos);
 assert(identifies == 2 && receipts == 2 && lookups == 3 && prices == 3);

 // Trusted staff fall through to their usual stat command. Mortal mode uses
 // the same locker routing as an ordinary player, including explicit items.
 ch.player.level = MAXLVLMORTAL + 1;
 for (const char *arg : {"", "sword", "receipt"}) stat(arg,FALSE);
 assert(attributes == 4 && identifies == 2 && receipts == 2 && lookups == 3 && prices == 3);
 assert(locker_lookups == 3);
 SET_BIT(ch.specials.act,PLR_MORTAL);
 stat("\t ",TRUE);
 assert(attributes == 5 && identifies == 2 && receipts == 2 && lookups == 3 && prices == 3);
 stat("sword",TRUE); stat("receipt",TRUE);
 assert(identifies == 3 && receipts == 3 && lookups == 4 && prices == 4);
 assert(locker_lookups == 3);
 std::cout << "locker stat routing: bare/whitespace, item/cost, receipt, missing item and staff pass\n";
}
'''
    parser = '\n'.join(extract_function('cmd/interp.c', signature) for signature in (
        'int search_block(', 'int fill_word(', 'char *one_argument(',
    ))
    fill_words = re.search(r'^const char \*fill_words\[\].*;', interp, re.M).group()
    cpp.write_text(routing_prefix + fill_words + '\n' +
                   extract_function('core/utility.c', 'int strn_cmp(') + '\n' + parser + '\n' +
                   extract_function('item/storage_lockers.c',
                                    'int storage_locker(int room, P_char ch, int cmd, char *arg)\n{') +
                   routing_main)
    subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-no-pie',
                    '-Isrc', str(cpp), '-o', str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)

    # Compile the actual lore renderer with real object layouts/constants. Only
    # presentation tables and networking are stubbed, so item variants exercise
    # the same capture implementation used by the paid service.
    render_start = lore.index('static void render_item_lore(')
    render_end = lore.index('const char *MAKE_FORMAT', render_start)
    render_prefix = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/objmisc.h"
#include "net/comm.h"
#include <cassert>
#include <cstdarg>
#include <iostream>
int checked_snprintf_at(const char *,int,char *out,size_t size,const char *format,...) {
 va_list args; va_start(args,format); int result=vsnprintf(out,size,format,args); va_end(args); return result; }
const char *item_types[]={"type"}, *spells[]={"spell"}, *apply_types[]={"attribute"};
const flagDef extra_bits[]={{}}, affected1_bits[]={{}}, affected2_bits[]={{}},
 affected3_bits[]={{}}, affected4_bits[]={{}}, affected5_bits[]={{}};
std::string sent;
void send_to_char(const char *text,P_char) { sent+=text; }
void sprinttype(int,const char **,char *text) { strcpy(text,"type"); }
void sprintbitde(ulong,const flagDef[],char *text) { strcpy(text,"ability"); }
bool ac_can_see_obj(P_char,P_obj,int) { return true; }
int itemvalue(P_obj) { return 42; }
char *get_str_zone(P_obj) { static char zone[]="Test Zone"; return zone; }
void act(const char *text,int,P_char,P_obj obj,void *,int) {
 std::string line=text;
 auto pos=line.find("$p"); if(pos!=std::string::npos) line.replace(pos,2,obj->short_description);
 sent+=line+"\r\n";
}
'''
    render_main = r'''
int main() {
 char_data ch={}; ch.player.level=50;
 obj_data obj={}; char name[]="a test item"; obj.short_description=name; obj.weight=5;
 for(int type : {ITEM_WEAPON,ITEM_ARMOR,ITEM_TOTEM,ITEM_POTION,ITEM_WAND}) {
  obj.type=type; obj.value[0]=TOTEM_LESS_ANIM|TOTEM_GR_SPIR;
  obj.value[1]=3; obj.value[2]=4; obj.value[3]=1; obj.bitvector=1;
  obj.affected[0].location=APPLY_STR; obj.affected[0].modifier=2;
  sent.clear(); lore_item(&ch,&obj); std::string normal=sent;
  sent.clear(); auto snapshot=item_lore_description(&ch,&obj);
  assert(sent.empty()); assert(snapshot=="This item is from the zone: Test Zone\n"+normal);
  if(type==ITEM_WEAPON) assert(snapshot.find("3D4")!=std::string::npos);
  if(type==ITEM_TOTEM) assert(snapshot.find("Greater Spiritual")!=std::string::npos);
 }
 ch.player.level=49; obj.extra_flags=ITEM_NOIDENTIFY;
 auto denied=item_lore_description(&ch,&obj);
 assert(denied.find("can't recall")!=std::string::npos);
 assert(item_lore_description(nullptr,&obj).empty());
 std::cout << "actual lore capture matches ordinary rendering for weapon, armor, totem, potion and wand\n";
}
'''
    cpp.write_text(render_prefix + lore[lore.index('static int lore_unidentified_level()'):lore.index('std::string lore_facts(')] + lore[render_start:render_end] + render_main)
    subprocess.run(['g++','-std=c++20','-Wall','-Wextra','-Werror','-Isrc',
                    str(cpp),'-o',str(binary)],cwd=ROOT,check=True)
    subprocess.run([str(binary)],check=True)
