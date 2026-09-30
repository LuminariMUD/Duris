#!/usr/bin/env python3
"""Execute the production account-menu character deletion with injected failures.

No live DB, account, or player data. The native harness compiles the production menu,
delete_character() and its memory release, the guild staging and account-list removal
against test doubles. On MariaDB the deletion is one writer job: the harness holds the
queued job, runs its statements in one staged transaction that can fail at any of them,
and replies on a later "pulse", while the session waits with its input held. It drives
selection, confirmation, cancel, refusal at every statement, retry, a session that closes
before the reply, and (flat-file build) the synchronous backend.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise AssertionError(signature)


account = (ROOT / 'src/account/account.c').read_text()
files = (ROOT / 'src/core/files.c').read_text()
guild = (ROOT / 'src/guild/assocs.c').read_text()
prototypes = (ROOT / 'src/core/prototypes.h').read_text()
# Menu loads must not instantiate inventory/pets before free_char().
request_builder = function(account, 'bool build_account_load_request(')
assert 'STATE(d) == CON_ACCT_DELETE_CHAR' in request_builder
assert 'request.include_items = false;' in request_builder
assert 'request.include_pets = false;' in request_builder

enum_start = prototypes.index('enum class character_delete_result')
enum_end = prototypes.index('};', enum_start) + 2
deletion_start = files.index('#ifndef _PFILE_\nnamespace\n{\n// What a deleted character')
deletion = files[deletion_start:files.index('void PurgeCorpseFile', deletion_start)]
bodies = '\n'.join([
    prototypes[enum_start:enum_end],
    '#ifndef __NO_MYSQL__\n' + function(guild, 'std::vector<std::string> Guild::statements_without_member(') + '\n#endif',
    function(guild, 'void Guild::forget_deleted_member('),
    function(account, 'void remove_char_from_list('),
    deletion,
    function(account, 'uint64_t wait_for_writer(P_desc d)'),
    function(account, 'P_desc writer_replied(uint64_t id)'),
    function(account, 'static void release_delete_character(P_desc d)\n'),
    function(account, 'static void finish_character_deletion('),
    function(account, 'void account_delete_char('),
    function(account, 'void account_delete_char_loaded('),
])
prelude = r'''
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <strings.h>
#include <cctype>
#include <cstdint>
#include <functional>
#include <string>
#include <vector>
#define TRUE 1
#define FALSE 0
#define USE_ACCOUNT
#define MAX_CHARS_PER_ACCOUNT 10
#define CON_DISPLAY_ACCT_MENU 1
#define CON_ACCT_DELETE_CHAR 2
#define CON_PLAYER_LOAD 3
#define PLAYER_LOAD_MODE_NONE 0
#define LOG_DEBUG 0
#define LOG_PLAYER 1
#define AVATAR 56
#define SEX_MALE 0
#define GET_NAME(ch) ((ch)->player.name)
#define GET_PID(ch) ((ch)->pid)
#define GET_LEVEL(ch) ((ch)->player.level)
#define GET_SEX(ch) ((ch)->sex)
#define GET_FRAGS(ch) ((ch)->frags)
#define GET_ASSOC(ch) ((ch)->assoc)
#define STATE(d) ((d)->state)
#define FREE(p) free(p)
#define SEND_TO_Q(text,d) ((d)->output += (text))
void checked_snprintf(char *out,size_t size,const char *format,...) {
    va_list args; va_start(args,format); vsnprintf(out,size,format,args); va_end(args);
}
std::string sql_format(const char *format,...) {
    char out[512]; va_list args; va_start(args,format); vsnprintf(out,sizeof out,format,args); va_end(args);
    return out;
}
struct member { char name[32]; member *next = nullptr; };
using P_member = member*;
struct Character;
using P_char = Character*;
class Guild {
public:
    member *members = nullptr;
    unsigned member_count = 0;
    struct { long frags=0, top_frags=0; char topfragger[32] = {}; } frags;
    unsigned get_id() const { return 7; }
    std::vector<std::string> statements_without_member(P_char);
    void forget_deleted_member(const char *, long);
};
struct acct_chars { char *charname; int pid; int last; acct_chars *next; };
struct Account { acct_chars *acct_character_list=nullptr; int num_chars=0; char *acct_name=nullptr; };
using P_acct = Account*;
struct Descriptor { Character *character=nullptr; Account *account=nullptr; int player_load_mode=7;
    int state=CON_ACCT_DELETE_CHAR, term_type=7; char host[8]="fixture"; std::string output;
    char *selected_char_name=nullptr; uint64_t writer_wait_id=0; bool prompt_mode=false;
    Descriptor *next=nullptr; };
using P_desc = Descriptor*;
struct Character { struct { char *name; int level; } player; int pid=1, sex=0, frags=7;
    Guild *assoc=nullptr; Descriptor *desc=nullptr; };
static P_desc descriptor_list = nullptr;
static int fail_stage=0, frees=0, menus=0, writes=0, audits=0, runtime_ships=0,
    ship_rows=0, loads=0, backend_calls=0, load_requests=0, forgotten=0, guild_rows=0;
static bool async_loads=false, durable_active=true;
static Guild fixture_guild;
Guild *get_guild_from_id(int id) { return id == 7 ? &fixture_guild : nullptr; }
namespace zone_story_quest_runtime {
bool erase_character(uint32_t, std::string *) { return true; }
}
void logit(int kind, const char*,...) { if(kind==LOG_PLAYER) { assert(!durable_active); ++audits; } }
void statuslog(int, const char *fmt,...) { if(strstr(fmt,"deleted")) { assert(!durable_active); ++audits; } }
void persistence_alert(int,const char*,const char*,const char*,const char*,const char*,const char*,...) {}
#ifdef __NO_MYSQL__
const char *persistence_mode_flatfile_root() { return "fixture"; }
enum class flatfile_character_delete_result { ok, already_deleted, io_error };
flatfile_character_delete_result flatfile_character_delete(const std::string&, int, const std::string&, std::string*) {
    ++backend_calls;
    if (fail_stage) return flatfile_character_delete_result::io_error;
    durable_active=false; return flatfile_character_delete_result::ok;
}
#else
// The writer: a queued job waits for the test's pulse, and runs its statements in one
// staged transaction that commits only when every statement succeeded.
struct MYSQL {};
using sql_row = std::vector<std::string>;
using sql_rows = std::vector<sql_row>;
static std::function<void()> pending;
static int stage=0;
static std::vector<std::string> executed;
unsigned int sql_execute(MYSQL *, const std::string &statement) {
    if (++stage == fail_stage) return 1146;
    executed.push_back(statement); return 0;
}
#define sql_read_work(...) queue_job(__VA_ARGS__)
bool queue_job(std::function<unsigned int(MYSQL*, sql_rows*)> work,
               std::function<void(bool, const sql_rows&)> done) {
    ++backend_calls; assert(!pending);
    pending = [work, done]() {
        MYSQL connection; sql_rows rows; stage = 0; executed.clear();
        const bool ok = work(&connection, &rows) == 0;
        if (ok) durable_active = false;
        done(ok, rows);
    };
    return true;
}
static void pulse() { assert(pending); auto job = pending; pending = nullptr; job(); }
std::string remove_all_locker_access_statement(const char *name) { return std::string("locker access ") + name; }
std::vector<std::string> remove_all_artifacts_sql(int) { return {"release artifacts", "mirror artifacts"}; }
std::string sql_delete_locker_statement(int, int) { return "delete locker"; }
std::string sql_delete_ship_statement(const char *) { return "delete ship"; }
// The guild is saved as it will be: without the member, its frags and top fragger.
std::vector<std::string> sql_save_guild_statements(Guild *g) {
    assert(!g->members && g->member_count==1 && g->frags.frags==0 && !g->frags.topfragger[0]);
    ++guild_rows; return {"guild row", "guild members"};
}
bool sql_delete_ship(const char *) { assert(!durable_active); ++ship_rows; return true; }
#endif
void artifacts_forget_deleted_character(int) { assert(!durable_active); ++forgotten; }
void player_revision_forget(int) { assert(!durable_active); ++forgotten; }
void sql_player_names_forget(int) { assert(!durable_active); ++forgotten; }
void delete_ship_runtime(const char*) { assert(!durable_active); ++runtime_ships; }
int write_account(P_acct) { ++writes; return 1; }
void free_char(P_char ch) { assert(!ch->desc); ++frees; free(ch->player.name); delete ch; }
void display_account_menu(P_desc d, char*) { assert(!d->character); assert(STATE(d)==CON_DISPLAY_ACCT_MENU); ++menus; }
void display_delete_character_list(P_desc) {}
size_t strlcpy(char *out,const char *s,size_t n) { snprintf(out,n,"%s",s); return strlen(s); }
char *str_dup(const char *s) { return strdup(s); }
void str_free(char *s) { free(s); }
// An asynchronous load parks the descriptor on its first call and hands the
// character over when account_delete_char_loaded() asks again.
P_char load_char_into_game(acct_chars *c,P_desc d) {
    if(async_loads && ++load_requests%2) { STATE(d)=CON_PLAYER_LOAD; return nullptr; }
    ++loads; auto ch=new Character; ch->player={strdup(c->charname),10}; ch->desc=d; ch->assoc=&fixture_guild; return ch; }
void remove_char_from_list(P_acct,const char*,bool=true);
void account_delete_char_loaded(P_desc);
'''
main = r'''
static void input(P_desc d,const char *s) { account_delete_char(d,const_cast<char*>(s)); }
static void reset(Account &a,Descriptor &d) {
    fail_stage=frees=menus=writes=audits=runtime_ships=ship_rows=loads=backend_calls=0;
    load_requests=forgotten=guild_rows=0; async_loads=false; durable_active=true;
    a.acct_character_list=(acct_chars*)calloc(1,sizeof(acct_chars));
    *a.acct_character_list={strdup("Fixture"),1,1,nullptr}; a.num_chars=1;
    d=Descriptor{}; d.account=&a; descriptor_list=&d;
    fixture_guild.members=new member; strcpy(fixture_guild.members->name,"Fixture");
    fixture_guild.member_count=1; fixture_guild.frags.frags=7;
    fixture_guild.frags.top_frags=7; strcpy(fixture_guild.frags.topfragger,"Fixture");
}
static void released(Descriptor &d) { assert(!d.character && frees==loads); assert(d.player_load_mode==0); assert(d.term_type==7); assert(menus>0); assert(!d.selected_char_name); assert(!d.writer_wait_id); }
static void kept(Account &a) {
    // Nothing of the character was forgotten: it stays listed, in its guild, and loadable.
    assert(a.num_chars==1 && !audits && !runtime_ships && !forgotten && !writes);
    assert(fixture_guild.member_count==1 && fixture_guild.frags.frags==7 && fixture_guild.members);
}
static void deleted(Account &a) {
    assert(!durable_active && audits==2 && runtime_ships==1 && forgotten==3);
    assert(!a.acct_character_list && a.num_chars==0 && !writes);
    assert(!fixture_guild.members && fixture_guild.member_count==0 && fixture_guild.frags.frags==0);
}
static void dispose(Account &a) {
    while(a.acct_character_list) {auto old=a.acct_character_list;a.acct_character_list=old->next;free(old->charname);free(old);}
    delete fixture_guild.members; fixture_guild.members=nullptr; descriptor_list=nullptr;
}
int main() {
    Account a; Descriptor d;
#ifndef __NO_MYSQL__
    // The job's statements: two tombstones, locker access, two artifact statements, two
    // guild statements, the locker, the ship and the player row.
    constexpr int statements = 10;
    for(int failure=1;failure<=statements;++failure) {
        reset(a,d); fail_stage=failure; input(&d,"1"); input(&d,"yes");
        // The session waits for the writer with the character it confirmed.
        assert(d.writer_wait_id && d.character && d.output.find("did not complete")==std::string::npos);
        pulse(); released(d); kept(a);
        assert(d.output.find("did not complete")!=std::string::npos);
        assert(d.output.find("successfully")==std::string::npos && !ship_rows);
        fail_stage=0; input(&d,"1"); input(&d,"yes"); pulse(); released(d);
        deleted(a); assert(ship_rows==1 && guild_rows==2 && executed.size()==statements);
        assert(d.output.find("successfully")!=std::string::npos);
        int calls=backend_calls; input(&d,"yes"); assert(backend_calls==calls && audits==2);
        dispose(a);
    }
    // A session that closes before the reply: the deletion still lands and memory lets
    // go of the character; nobody is told.
    {
        reset(a,d); input(&d,"1"); input(&d,"yes");
        P_char waiting = d.character; d.character = nullptr; waiting->desc = nullptr; free_char(waiting);
        descriptor_list = nullptr; pulse();
        assert(!durable_active && runtime_ships==1 && forgotten==3 && a.num_chars==1);
        assert(d.output.find("successfully")==std::string::npos && d.writer_wait_id);
        dispose(a);
    }
#else
    reset(a,d); fail_stage=1; input(&d,"1"); input(&d,"yes"); released(d); kept(a);
    fail_stage=0; input(&d,"1"); input(&d,"yes"); released(d); deleted(a); dispose(a);
#endif
    for(const char *cancel:{"no","0","back"}) {
        reset(a,d); input(&d,"1"); input(&d,cancel); released(d);
        assert(!backend_calls && !audits && durable_active); dispose(a);
    }
    reset(a,d); input(&d,"1"); input(&d,"1"); assert(frees==1 && loads==2); input(&d,"no"); released(d); dispose(a);
    // The load runs on the load worker: the menu waits, then asks for confirmation.
    reset(a,d); async_loads=true; input(&d,"1");
    assert(STATE(&d)==CON_PLAYER_LOAD && !d.character && !loads && d.selected_char_name);
    STATE(&d)=CON_ACCT_DELETE_CHAR; account_delete_char_loaded(&d);
    assert(d.character && loads==1 && !d.selected_char_name);
    input(&d,"yes");
#ifndef __NO_MYSQL__
    pulse();
#endif
    released(d); deleted(a); dispose(a);
    for(bool at_head:{false,true}) {
        reset(a,d);
        auto other=(acct_chars*)calloc(1,sizeof(acct_chars));
        *other={strdup("Other"),2,0,nullptr};
        if(at_head) a.acct_character_list->next=other;
        else {other->next=a.acct_character_list;a.acct_character_list=other;}
        a.num_chars=2; input(&d,"1"); input(&d,"yes");
#ifndef __NO_MYSQL__
        pulse();
#endif
        released(d);
        assert(a.num_chars==1 && a.acct_character_list==other && !other->next && !writes);
        dispose(a);
    }
    puts("PASS");
}
'''
build_root = ROOT / 'bin/tests'
build_root.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='account-delete-', dir=build_root) as directory:
    cpp = Path(directory) / 'runtime.cpp'
    cpp.write_text(prelude + bodies + main)
    for backend, flags in (('mariadb', []), ('flatfile', ['-D__NO_MYSQL__'])):
        exe = Path(directory) / f'runtime-{backend}'
        subprocess.run(['g++', '-std=c++20', '-g', '-fsanitize=address,undefined',
                        '-fno-omit-frame-pointer', *flags, str(cpp), '-o', str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
print('PASS: account deletion runtime refusal at every statement, release, publication, '
      'retry and closed-session scenarios on both backends')
