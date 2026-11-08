#!/usr/bin/env python3
"""Production copyover save -> exec -> recover with the real runtime custody ledger.

The fixture has no clients. Worker drains are idle; unrelated player and
network services must not be called. NPC cases cover generated mobs and shop stock.
No database or running game is used.
"""
import ast
import os
from pathlib import Path
import subprocess
import tempfile
from _paths import HARNESS_STUBS, extract_function

ROOT = Path(__file__).resolve().parents[2]


def remove_function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[:start] + source[end:]


# Reuse only the small in-memory world fixture, without executing its test runner.
module = ast.parse((ROOT / "tests/async/test_world_recovery_pipeline.py").read_text())
support = next(ast.literal_eval(node.value) for node in module.body
               if isinstance(node, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "HARNESS" for t in node.targets))
support = support[:support.index("struct publish_gate")]
for signature in (
    "P_char copyover_restore_mob_from_buffer(",
    "void extract_char(",
    "P_obj unequip_char(",
    "void equip_char(",
    "void obj_to_char_at_end(",
    "char affect_total(",
    "bool sql_persistence_reconcile_world_recovery_items(",
    "bool item_ownership_runtime_hydrate_many_atomic(",
    "bool item_ownership_runtime_lookup(",
    "bool item_owner_identity_equal(",
    "bool item_owner_identity_valid(",
    "bool world_recovery_rehydrate_npc_items(",
    "int copyover_write_door_to_buffer(",
    "int copyover_write_zone_age_to_buffer(",
    "int singleton_shop_id(",
):
    support = remove_function(support, signature)

support = support.replace("bool fallback_fixture = false;", "bool fallback_fixture = false;\nbool restoring_npc_items = false;")
support = support.replace("void obj_to_room(P_obj object, int room)\n{", "void obj_to_room(P_obj object, int room)\n{\n    assert(!(restoring_npc_items && object->obj_uid>=910 && object->obj_uid<=914));")
support += '\nint curr_ingame_good = 0, curr_ingame_evil = 0;\n'
support += 'int max_ingame_good = 0, max_ingame_evil = 0;\n'
support += extract_function('nanny.c', 'void update_ingame_racewar(')

HARNESS = r'''
P_obj read_object_for_creation(int, int) { std::abort(); }
bool binary_case() { return std::string(getenv("COPYOVER_TEST_CASE")).starts_with("binary-"); }
bool npc_case() { const char *s=getenv("COPYOVER_TEST_CASE"); return !strcmp(s,"npc") || !strcmp(s,"shop") || !strcmp(s,"foreign-shop"); }
bool shop_case() { return npc_case() && strcmp(getenv("COPYOVER_TEST_CASE"),"npc"); }
int singleton_shop_id(P_char mob) { return mob && mob->only.npc ? mob->only.npc->shopkeeper_shop_id : -1; }

#include "classes/necromancy.h"
#include "persistence/locker_async.h"
#include "persistence/maintenance_scheduler.h"
#include "persistence/critical_command_coordinator.h"
#include "persistence/critical_outbox.h"
#include "player/player_save_pipeline.h"
#include "player/player_save_worker.h"
#include "redis/redis_world_runtime.h"
#include "player/player_load_pipeline.h"
#include "player/player_load_items.h"
#include "player/player_load_materialize.h"
#include "core/mm.h"
#include "telemetry/telemetry_runtime.h"
#include <unistd.h>
#include <cstdarg>
#include <sys/syscall.h>
#include <sys/file.h>
#include <netinet/in.h>
#include <sys/socket.h>

// The fixture's logit() writes nothing, so there is no log thread to flush before the exec.
void flush_log_writer(void) {}
bool pwipe_launch_allows_at(const char *, time_t) { std::abort(); }
void pwipe_launch_deny(descriptor_data *) { std::abort(); }

// This no-player custody fixture must never enter gameplay telemetry adapters.
// Its clock is unavailable, so the telemetry durability barrier is not entered.
bool telemetry_runtime_now(telemetry_monotonic_usec *, telemetry_utc_usec *) noexcept
{ return false; }
telemetry_runtime_outcome telemetry_runtime_flush_for_copyover(telemetry_monotonic_usec)
{ std::abort(); }
telemetry_handoff_result telemetry_runtime_game_handoff_copy(P_char) { std::abort(); }
telemetry_capture_result telemetry_runtime_game_session_resume(
    P_char, P_desc, const telemetry_session_handoff *) { std::abort(); }

P_desc descriptor_list = nullptr;
int RUNNING_PORT = 4000, mini_mode = 1, _copyover = 0, used_descs = 0;
int copyover_boot = 0;
struct mm_ds *dead_mob_pool = nullptr, *dead_pconly_pool = nullptr, *dead_desc_pool = nullptr;

bool sql_persistence_reconcile_world_recovery_items(const world_recovery_authority_item *,
    size_t, item_ownership_runtime_entry *, size_t) { std::abort(); }
bool world_recovery_rehydrate_npc_items(P_char const *, size_t) { std::abort(); }
bool item_creation_grant_batches_pending() { return false; }
void flush_pending_ship_saves() {}
bool drain_pending_ship_saves() { return true; }
int locker_async_drain(int) { return 1; }
bool artifact_guild_transaction_drain(uint64_t) { return true; }
void kingdom_flush_persistent_state() {}
void maintenance_scheduler_quiesce() {}
void maintenance_scheduler_resume() {}
bool maintenance_scheduler_drain(uint64_t) { return true; }
void critical_command_coordinator_quiesce() {}
void critical_command_coordinator_resume() {}
bool critical_command_coordinator_drain(uint64_t) { return true; }
void critical_outbox_quiesce() {}
void critical_outbox_resume() {}
bool critical_outbox_drain(uint64_t) { return true; }
void player_save_pipeline_quiesce() {}
void player_save_pipeline_resume() {}
bool player_save_pipeline_drain(uint64_t) { return true; }
bool redis_world_recovery_drain(uint64_t) { return true; }
bool redis_world_checkpoint_for_copyover(redis_copyover_checkpoint *) { std::abort(); }
int write_to_descriptor(P_desc, const char *) { assert(false); return -1; }
void redis_world_writer_release() {}
void redis_world_writer_reclaim_after_copyover() {}
bool return_from_staff_switch(P_desc) { std::abort(); }
int telnet_flush_output(P_desc) { std::abort(); }
P_ship get_ship_from_char(P_char) { std::abort(); }
P_ship find_ship_by_database_id(uint32_t) { std::abort(); }
bool persistence_flush_all_character_saves() { return true; }
bool persistence_log_drain(unsigned timeout_ms) { assert(timeout_ms == 3000); return true; }

// Empty-world boundaries: reaching these would make the fixture invalid.
void schedule_pc_events(P_char) { std::abort(); }
bool persistence_save_character_terminal(P_char, int) { std::abort(); }
bool persistence_save_character_terminal_database_acknowledged(P_char, int) { std::abort(); }
int websocket_send_text(P_desc, const char *) { std::abort(); }
int compress_end(P_desc, int) { std::abort(); }
void write_to_q(const char *, txt_q *, int) {
    assert(binary_case());
}
uint64_t persistence_observability_now_usec() { std::abort(); }
uint64_t player_load_pipeline_next_request_id() { std::abort(); }
bool player_load_pipeline_wait(player_load_request, player_load_result *, uint64_t) { std::abort(); }
bool player_load_pipeline_execute_sync(player_load_request, player_load_result *) { std::abort(); }
bool player_load_items_read_current(const player_load_result &) { std::abort(); }
bool persistence_writer_wait_idle(uint64_t) { std::abort(); }
bool player_load_materialize(P_char, const player_load_result &) { std::abort(); }
void player_load_pets_place(P_char) { std::abort(); }
void epic_bonus_hydrate(P_char) { std::abort(); }
void *_mm_get(mm_ds *, const char *, int) { std::abort(); }
unsigned mm_find_best_chunk(int, int, int) { std::abort(); }
mm_ds *mm_create(const char *, size_t, size_t, unsigned) { std::abort(); }
void mm_release(mm_ds *, void *) { std::abort(); }
void clear_char(P_char) { std::abort(); }
void free_char(P_char) { std::abort(); }
void nonblock(int) { std::abort(); }
void check_cp437(P_desc) { std::abort(); }
acct_entry *allocate_account() { std::abort(); }
void account_read(P_desc, const char *, account_read_done) { std::abort(); }
acct_entry *free_account(acct_entry *) { std::abort(); }
// This fixture restores into static NPCs and models its own item placement.
void extract_char(P_char) {}
P_obj unequip_char(P_char, int, bool) { std::abort(); }
static char_data npc_holder;
static npc_only_data npc_holder_data;
static char_data catalog_keeper;
static npc_only_data catalog_data;
bool char_to_room(P_char mob, int room, int) { mob->in_room=npc_case() ? 1 : room; return true; }
P_char read_mobile(int number, int mode) {
 assert((mode==REAL && number==0) || (mode==VIRTUAL && number==2000));
 npc_holder={}; npc_holder_data={}; npc_holder.only.npc=&npc_holder_data;
 npc_holder.specials.act=ACT_ISNPC; npc_holder_data.R_num=0; npc_holder_data.shopkeeper_shop_id=-1;
 npc_holder.player.name=const_cast<char *>("fixture NPC"); npc_holder.next=character_list; character_list=&npc_holder; return &npc_holder;
}
int setup_pet(P_char, P_char, int, int) { std::abort(); }
void add_follower(P_char, P_char) { std::abort(); }
static affected_type restored_skill_effect;
affected_type *affect_to_char(P_char mob, affected_type *effect) {
 assert(effect->loc2==1251 && effect->location==APPLY_SKILL_GRANT && effect->modifier==40);
 restored_skill_effect=*effect; mob->affected=&restored_skill_effect; return mob->affected;
}
char affect_total(P_char mob, int) { GET_MAX_HIT(mob)=5; GET_MAX_MANA(mob)=6; GET_MAX_VITALITY(mob)=7; return 0; }
void equip_char(P_char mob, P_obj object, int slot, int) {
 mob->equipment[slot]=object; object->loc_p=LOC_WORN; object->loc.wearing=mob;
 GET_MAX_HIT(mob)=5; GET_MAX_MANA(mob)=6; GET_MAX_VITALITY(mob)=7;
}
bool obj_to_char(P_obj object, P_char mob) {
 object->loc_p=LOC_CARRIED; object->loc.carrying=mob; object->next_content=mob->carrying; mob->carrying=object;
 return true;
}
void obj_to_char_at_end(P_obj object,P_char mob) { obj_to_char(object,mob); }
P_obj find_live_object(P_obj expected,uint64_t uid) {
 for(P_obj object=object_list;object;object=object->next) if(object==expected && object->obj_uid==uid) return object;
 return nullptr;
}
int bind_shopkeeper_calls = 0;
void bind_shopkeeper(P_char mob, int shop) { ++bind_shopkeeper_calls; mob->only.npc->shopkeeper_shop_id=shop; }

// Inject a concurrent publication at the actual kernel rename boundary.
extern "C" int renameat2(int from_directory,const char *from,int to_directory,const char *to,
    unsigned int flags) noexcept
{
    const char *scenario=getenv("COPYOVER_TEST_CASE");
    if (scenario && (!strcmp(scenario,"publish-race") || !strcmp(scenario,"claim-race")) && !strcmp(to,COPYOVER_FILE)) {
        const std::string competing=!strcmp(scenario,"claim-race") ? std::string(to)+".recovering" : to;
        FILE *other=fopen(competing.c_str(),"wb");
        assert(other && fwrite("replacement",11,1,other)==1 && fclose(other)==0);
    }
    if (scenario && !strcmp(scenario,"consume-race") && std::string(to).ends_with(".consuming/image")) {
        assert(!syscall(SYS_unlink,from));
        FILE *other=fopen(from,"wb");
        assert(other && fwrite("replacement",11,1,other)==1 && fclose(other)==0);
    }
    const int result = static_cast<int>(syscall(SYS_renameat2,from_directory,from,to_directory,to,flags));
    if (result == 0 && binary_case() &&
        !strcmp(to, "bin/server/dms") && flags == RENAME_EXCHANGE) {
        int publisher = open("bin/server", O_RDONLY | O_DIRECTORY);
        assert(publisher >= 0 && flock(publisher, LOCK_EX | LOCK_NB) < 0 && errno == EWOULDBLOCK);
        close(publisher);
        // Simulate an out-of-band publisher ignoring the lock at the old race point.
        assert(!rename("bin/server/racing", "bin/server/dms_new"));
    }
    return result;
}

bool binary_backup_race_injected = false;
void replace_binary_parent(int directory, const char *from, const char *to)
{
    if (strcmp(getenv("COPYOVER_TEST_CASE"), "binary-backup-race") ||
        strcmp(to, "bin/server/history/dms.copyover"))
        return;
    assert(!binary_backup_race_injected);
    binary_backup_race_injected = true;
    std::string source = from;
    if (directory != AT_FDCWD) {
        char link[64], parent[4096];
        snprintf(link, sizeof(link), "/proc/self/fd/%d", directory);
        const ssize_t size = readlink(link, parent, sizeof(parent));
        assert(size > 0 && size < static_cast<ssize_t>(sizeof(parent)));
        source = std::string(parent, size) + "/" + from;
        struct stat permissions = {};
        assert(!fstat(directory, &permissions) && (permissions.st_mode & 0777) == 0700);
        assert(fcntl(directory, F_GETFD) & FD_CLOEXEC);
    }
    // Replace an ancestor after the inode checks, at the final rename boundary.
    // A descriptor-relative rename must still publish the original runtime inode.
    const std::string parent = source.substr(0, source.find_last_of('/'));
    assert(!syscall(SYS_rename, parent.c_str(), (parent + ".moved").c_str()));
    assert(!mkdir(parent.c_str(), 0700));
    FILE *replacement = fopen(source.c_str(), "wb");
    assert(replacement && fwrite("unvalidated", 11, 1, replacement) == 1 && !fclose(replacement));
}

extern "C" int rename(const char *from, const char *to) noexcept
{
    replace_binary_parent(AT_FDCWD, from, to);
    return static_cast<int>(syscall(SYS_rename, from, to));
}

extern "C" int renameat(int from_directory, const char *from, int to_directory, const char *to) noexcept
{
    replace_binary_parent(from_directory, from, to);
    return static_cast<int>(syscall(SYS_renameat, from_directory, from, to_directory, to));
}

extern "C" int unlink(const char *path) noexcept {
    const char *scenario=getenv("COPYOVER_TEST_CASE");
    if(scenario && !strcmp(scenario,"consume-race") && std::string(path).ends_with(".recovering")) {
        assert(!syscall(SYS_unlink,path));
        FILE *other=fopen(path,"wb");
        assert(other && fwrite("replacement",11,1,other)==1 && fclose(other)==0);
    }
    return static_cast<int>(syscall(SYS_unlink,path));
}

// Exercise a real process replacement. Only the executable destination changes;
// the production save, publication, counting and recovery functions are intact.
extern "C" int fixture_execl(const char *path, const char *, ...) noexcept
{
    assert(strcmp(getenv("COPYOVER_TEST_CASE"),"publish-race") && strcmp(getenv("COPYOVER_TEST_CASE"),"claim-race") && "a competing publication must refuse before exec");
    assert(!std::strcmp(path, "bin/server/dms"));
    FILE *file = std::fopen(COPYOVER_FILE, "rb"); assert(file);
    copyover_header header = {};
    assert(std::fread(&header, sizeof(header), 1, file) == 1);
    const bool npc=npc_case();
    assert(header.version == COPYOVER_VERSION && header.num_objects == (npc ? 5 : 1));
    assert(!header.num_descriptors && header.num_mobs==(npc ? 1 : 0));
    std::fclose(file);
    if (binary_case() && strcmp(getenv("COPYOVER_TEST_CASE"), "binary-success")) {
        errno = ENOENT;
        return -1;
    }
    char executable[] = "/proc/self/exe", phase[] = "recover";
    char *args[] = {executable, phase, nullptr};
    execv(executable, args);
    std::abort();
}

item_ownership_runtime_entry custody(uint64_t uid)
{
    item_ownership_runtime_entry entry = {};
    entry.item_uid = uid;
    entry.root_item_uid = 900;
    entry.parent_item_uid = uid == 902 ? 901 : uid == 901 ? 900 : 0;
    entry.owner = {item_owner_type::room, 100, 0};
    entry.item_revision = uid;
    entry.owner_revision = !strcmp(getenv("COPYOVER_TEST_CASE"),"mixed-owner") ? uid-870 : 31;
    entry.vnum = 1000;
    entry.state = item_custody_state::active;
    return entry;
}

static int listener()
{
    int fd = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
    sockaddr_in address = {};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    assert(fd >= 0 && bind(fd, reinterpret_cast<sockaddr *>(&address), sizeof address) == 0);
    assert(listen(fd, 1) == 0);
    return fd;
}

int main(int argc, char **argv)
{
    rooms[0].number = 100; rooms[1].number = 200;
    object_indexes[0].virtual_number = 1000; mob_indexes[0].virtual_number=npc_case() ? 1255 : 2000;
    if (argc == 1) {
        P_obj corpse = read_object(1000, VIRTUAL);
        P_obj bag = read_object(1000, VIRTUAL);
        P_obj gloves = read_object(1000, VIRTUAL);
        corpse->obj_uid = 900; corpse->type = ITEM_CORPSE;
        corpse->name = str_dup("corpse snake");
        corpse->action_description = str_dup("a cavern snake");
        corpse->wear_flags = ITEM_TAKE;
        bag->obj_uid = 901; bag->type = ITEM_CONTAINER;
        gloves->obj_uid = 902; gloves->type = ITEM_ARMOR;
        gloves->name = str_dup("boreal hardwood gloves");
        gloves->wear_flags = ITEM_TAKE | ITEM_WEAR_HANDS;
        gloves->material = 3; gloves->weight = 3;
        gloves->affected[0].location = APPLY_HIT;
        gloves->affected[0].modifier = -5;
        obj_to_room(corpse, 0); obj_to_obj(bag, corpse); obj_to_obj(gloves, bag);
        for (uint64_t uid : {900, 901, 902})
            assert(item_ownership_runtime_hydrate(custody(uid)));
        std::vector<char> buffer(WORLD_RECOVERY_MAX_RECORD_BYTES);
        // A fuzzy snapshot carries the ordinary NPC corpse but leaves custody
        // to SQL at recovery. Native copyover preserves the live ledger below.
        const int fuzzy_size = world_recovery_write_object_to_buffer(corpse, 100, buffer.data(), buffer.size());
        assert(fuzzy_size > 0);
        world_recovery_object_record fuzzy_record{};
        std::vector<world_recovery_item_snapshot> fuzzy_items;
        assert(world_recovery_read_object_record(reinterpret_cast<const unsigned char *>(buffer.data()),
                                                  fuzzy_size, &fuzzy_record, &fuzzy_items));
        assert(fuzzy_record.room_vnum == 100 && fuzzy_items.size() == 3);
        for (const auto &item : fuzzy_items)
            assert(!(item.flags & WORLD_RECOVERY_ITEM_AUTHORITY_REQUIRED));

        if(npc_case()) {
            auto *mob=read_mobile(0,REAL); mob->in_room=0; mob->only.npc->idnum=42;
            static affected_type skill_effect{};
            skill_effect.type=1251; skill_effect.loc2=1251;
            skill_effect.location=APPLY_SKILL_GRANT; skill_effect.modifier=40;
            skill_effect.duration=30; mob->affected=&skill_effect;
            if(shop_case()) mob->only.npc->shopkeeper_shop_id=0;
            auto *carried=read_object(1000,VIRTUAL); carried->obj_uid=910; carried->extra_flags=ITEM_ARTIFACT;
            carried->value[0]=73; obj_to_char(carried,mob);
            auto *worn=read_object(1000,VIRTUAL); worn->obj_uid=911; worn->extra_flags=ITEM_ARTIFACT;
            worn->value[1]=74; equip_char(mob,worn,3,9);
            auto *bag=read_object(1000,VIRTUAL); bag->obj_uid=912; bag->type=ITEM_CONTAINER; obj_to_char(bag,mob);
            auto *nested=read_object(1000,VIRTUAL); nested->obj_uid=913; nested->extra_flags=ITEM_ARTIFACT;
            nested->value[2]=75; obj_to_obj(nested,bag);
            auto *money=read_object(1000,VIRTUAL); money->obj_uid=914; money->type=ITEM_MONEY; money->value[3]=9; obj_to_char(money,mob);
            mob->player.name=str_dup("generated fixture"); mob->player.short_descr=str_dup("a generated fixture");
            mob->player.long_descr=str_dup("A generated fixture stands here.");
            mob->only.npc->str_mask=STRUNG_KEYS|STRUNG_DESC1|STRUNG_DESC2;
            mob->player.level=61; mob->player.race=1; mob->player.sex=1; mob->player.size=2; mob->player.m_class=4;
            for(size_t index=0;index<10;++index) mob->base_stats[index]=90;
            mob->points.base_hit=300; mob->points.base_mana=200; mob->points.base_vitality=100;
            GET_MAX_HIT(mob)=333; GET_HIT(mob)=222; GET_MAX_MANA(mob)=211; GET_MANA(mob)=111;
            GET_MAX_VITALITY(mob)=123; GET_VITALITY(mob)=99;
        }
        const int plain = listener(), tls = listener();
        if (!strcmp(getenv("COPYOVER_TEST_CASE"),"publish-race") || !strcmp(getenv("COPYOVER_TEST_CASE"),"claim-race")) {
            assert(!copyover_save(plain,tls,-1));
            const std::string competing=!strcmp(getenv("COPYOVER_TEST_CASE"),"claim-race") ? std::string(COPYOVER_FILE)+".recovering" : COPYOVER_FILE;
            FILE *other=fopen(competing.c_str(),"rb"); char bytes[11];
            assert(other && fread(bytes,sizeof(bytes),1,other)==1 && fclose(other)==0);
            assert(!memcmp(bytes,"replacement",11) && object_list && item_ownership_runtime_size()==3);
            extract_obj(corpse,FALSE); item_ownership_runtime_reset();
            assert(!object_list);
            puts("[PASS] competing publication survives atomic publish refusal; live objects and custody remain");
            return 0;
        }
        if (binary_case() && strcmp(getenv("COPYOVER_TEST_CASE"), "binary-success")) {
            int pair[2];
            assert(!socketpair(AF_UNIX, SOCK_STREAM, 0, pair));
            descriptor_data tls_menu = {}, web_menu = {};
            tls_menu.descriptor = pair[0];
            tls_menu.connected = CON_DISPLAY_ACCT_MENU;
            tls_menu.sslses = reinterpret_cast<gnutls_session_t>(1);
            tls_menu.telnet_output_len = 1024 * 1024 - 16;
            tls_menu.next = &web_menu;
            web_menu.descriptor = pair[1];
            web_menu.connected = CON_DISPLAY_ACCT_MENU;
            web_menu.websocket = web_menu.ws_handshake_done = 1;
            web_menu.ws_output_len = 1024 * 1024 - 16;
            descriptor_list = &tls_menu;
            struct stat before = {}, after = {}, racing = {}, staged = {};
            assert(!stat("bin/server/dms", &before) && !stat("bin/server/racing", &racing));
            assert(!copyover_save(plain, tls, -1));
            assert(!stat("bin/server/dms", &after) && before.st_ino == after.st_ino);
            assert(binary_backup_race_injected ==
                   !strcmp(getenv("COPYOVER_TEST_CASE"), "binary-backup-race"));
            assert(!stat("bin/server/dms_new", &staged) && racing.st_ino == staged.st_ino);
            assert(access(COPYOVER_FILE, F_OK) < 0 && errno == ENOENT);
            assert(!tls_menu.write_failed && !web_menu.write_failed &&
                   !(fcntl(pair[0], F_GETFD) & FD_CLOEXEC) && !(fcntl(pair[1], F_GETFD) & FD_CLOEXEC));
            assert(tls_menu.telnet_output_len == 1024 * 1024 - 16 &&
                   web_menu.ws_output_len == 1024 * 1024 - 16);
            puts("[PASS] racing publication and backup paths preserved both binaries and congested menu sockets after failed exec");
            return 0;
        }
        copyover_save(plain, tls, -1);
        assert(false && "copyover_save failed before process replacement");
    }
    assert(argc == 2 && !std::strcmp(argv[1], "recover"));
    copyover_boot = 1;
    restoring_npc_items=true;
    assert(!object_list && item_ownership_runtime_size() == 0);
    // A newer in-memory custody revision must survive a rejected handoff;
    // all newly materialized objects must be rolled back atomically.
    FILE *file = std::fopen(COPYOVER_FILE, "rb"); assert(file);
    assert(std::fseek(file, sizeof(copyover_header) + 3 * sizeof(int), SEEK_SET) == 0);
    // Version 15 has a framed telemetry block even with zero descriptors.
    struct { char magic[4]; uint32_t version; uint32_t count; } telemetry_header{};
    assert(std::fread(&telemetry_header, sizeof(telemetry_header), 1, file) == 1);
    assert(std::memcmp(telemetry_header.magic, "TLMY", 4) == 0);
    assert(telemetry_header.version == 1 && telemetry_header.count == 0);
    uint32_t size = 0;
    assert(std::fread(&size, sizeof(size), 1, file) == 1);
    assert(size <= WORLD_RECOVERY_MAX_RECORD_BYTES);
    std::vector<char> buffer(size);
    assert(std::fread(buffer.data(), size, 1, file) == 1);
    std::fclose(file);
    auto newer = custody(902); ++newer.item_revision;
    assert(item_ownership_runtime_hydrate(newer));
    if (!strcmp(getenv("COPYOVER_TEST_CASE"),"newer-owner"))
        assert(item_ownership_runtime_hydrate_owner(newer.owner, 99));
    size_t consumed = 99;
    assert(!copyover_restore_obj_from_buffer(buffer.data(), buffer.size(), &consumed));
    assert(!object_list && consumed == 0 && item_ownership_runtime_size() == 1);
    item_ownership_runtime_entry retained = {};
    assert(item_ownership_runtime_lookup(902, &retained));
    assert(retained.item_revision == newer.item_revision);
    item_ownership_runtime_reset();
    assert(copyover_prepare_boot() == copyover_boot_result::ready);
    const auto *pinned = copyover_boot_evidence();
    assert(pinned && pinned->objects.size() == (npc_case() ? 5 : 1) && pinned->header.version == COPYOVER_VERSION);
    const std::string claimed = std::string(COPYOVER_FILE) + ".recovering";
    const std::string interrupted = claimed + ".consuming";
    assert(!mkdir(interrupted.c_str(),0700));
    copyover_boot_snapshot blocked;
    assert(copyover_read_file(claimed,&blocked)==copyover_boot_result::failed);
    assert(!rmdir(interrupted.c_str()));
    const char *scenario = getenv("COPYOVER_TEST_CASE");
    assert(scenario);
    const bool new_publication = !strcmp(scenario,"newer");
    const bool changed = !strcmp(scenario,"changed") || !strcmp(scenario,"consume-race");
    if (new_publication || !strcmp(scenario,"changed")) {
        FILE *replacement = std::fopen(new_publication ? COPYOVER_FILE : claimed.c_str(),"wb");
        assert(replacement && std::fwrite("replacement",11,1,replacement)==1 && std::fclose(replacement)==0);
        assert(copyover_prepare_boot() == copyover_boot_result::ready && copyover_boot_evidence() == pinned);
        assert(copyover_has_durable_shopkeepers());
    }
    const bool newer_owner = !strcmp(scenario,"newer-owner");
    const bool mixed_owner = !strcmp(scenario,"mixed-owner");
    if (newer_owner) assert(item_ownership_runtime_hydrate_owner(custody(900).owner, 99));
    if(shop_case()) {
        catalog_keeper.only.npc=&catalog_data; catalog_keeper.specials.act=ACT_ISNPC;
        catalog_data.shopkeeper_shop_id=!strcmp(scenario,"foreign-shop") ? 1 : 0;
        catalog_keeper.in_room=0; character_list=&catalog_keeper;
        P_obj roots[5]={};
        for(int i=0;i<5;++i) { roots[i]=read_object(1000,VIRTUAL); roots[i]->obj_uid=910+i; roots[i]->g_key=700+i; }
        roots[0]->extra_flags=ITEM_ARTIFACT; roots[0]->value[0]=73;
        roots[1]->extra_flags=ITEM_ARTIFACT; roots[1]->value[1]=74;
        roots[2]->type=ITEM_CONTAINER; roots[3]->extra_flags=ITEM_ARTIFACT; roots[3]->value[2]=75;
        roots[4]->type=ITEM_MONEY; roots[4]->value[3]=9;
        obj_to_char(roots[0],&catalog_keeper); equip_char(&catalog_keeper,roots[1],3,9);
        obj_to_char(roots[2],&catalog_keeper); obj_to_obj(roots[3],roots[2]); obj_to_char(roots[4],&catalog_keeper);
    }
    int telnet = 0, tls = 0, websocket = 0;
    if(!strcmp(scenario,"foreign-shop")) {
        assert(copyover_recover(&telnet,&tls,&websocket)==0);
        assert(catalog_keeper.carrying && catalog_keeper.equipment[3]);
        assert(catalog_keeper.equipment[3]->obj_uid==911 && catalog_keeper.equipment[3]->g_key==701);
        while(object_list) { P_obj root=object_list; while(OBJ_INSIDE(root)) root=root->loc.inside; extract_obj(root,FALSE); }
        str_free(npc_holder.player.name); str_free(npc_holder.player.short_descr); str_free(npc_holder.player.long_descr);
        item_ownership_runtime_reset();
        puts("[PASS] foreign-shop UID reuse refuses without replacing catalog stock");
        return 0;
    }
    assert(copyover_recover(&telnet, &tls, &websocket) == 1);
    if(npc_case()) assert(npc_holder.affected && npc_holder.affected->loc2==1251);
    assert(telnet >= 0 && tls >= 0 && telnet != tls && websocket == -1);
    close(telnet);
    close(tls);
    copyover_commit_boot();
    assert(copyover_recover(&telnet, &tls, &websocket) == 0);
    assert((access(COPYOVER_FILE, F_OK) == 0) == new_publication);
    assert((access(claimed.c_str(), F_OK) == 0) == changed);
    if (new_publication || changed) {
        FILE *retained_file = std::fopen(new_publication ? COPYOVER_FILE : claimed.c_str(),"rb");
        char retained_bytes[11];
        assert(retained_file && std::fread(retained_bytes,sizeof(retained_bytes),1,retained_file)==1);
        assert(!std::memcmp(retained_bytes,"replacement",11) && std::fclose(retained_file)==0);
    }
    P_obj corpse = nullptr;
    for (P_obj object = object_list; object; object = object->next)
        if (object->obj_uid == 900) corpse = object;
    assert(corpse && corpse->loc_p == LOC_ROOM && corpse->loc.room == 0);
    assert(!std::strcmp(corpse->action_description, "a cavern snake"));
    assert(corpse->wear_flags == ITEM_TAKE);
    P_obj bag = corpse->contains;
    assert(bag && bag->obj_uid == 901 && !bag->next_content && bag->loc.inside == corpse);
    P_obj gloves = bag->contains;
    assert(gloves && gloves->obj_uid == 902 && !gloves->next_content && gloves->loc.inside == bag);
    assert(!std::strcmp(gloves->name, "boreal hardwood gloves"));
    assert(gloves->wear_flags == (ITEM_TAKE | ITEM_WEAR_HANDS) && gloves->material == 3);
    assert(gloves->affected[0].location == APPLY_HIT && gloves->affected[0].modifier == -5);
    assert(gloves->weight == 3 && bag->weight == 3 && corpse->weight == 3);
    assert(item_ownership_runtime_size() == 3);
    for (uint64_t uid : {900, 901, 902}) {
        item_ownership_runtime_entry restored = {}, expected = custody(uid);
        assert(item_ownership_runtime_lookup(uid, &restored));
        assert(restored.item_uid == expected.item_uid && restored.vnum == expected.vnum);
        assert(restored.root_item_uid == expected.root_item_uid);
        assert(restored.parent_item_uid == expected.parent_item_uid);
        assert(item_owner_identity_equal(restored.owner, expected.owner));
        assert(restored.item_revision == expected.item_revision && restored.owner_revision == (newer_owner ? 99 : mixed_owner ? 32 : 31));
        assert(restored.state == item_custody_state::active);
    }

    if(npc_case()) {
        P_char inventory=shop_case() ? &catalog_keeper : &npc_holder;
        if(shop_case()) {
            assert(!npc_holder.carrying && !npc_holder.equipment[3]);
            int count=0;
            for(P_obj object=object_list;object;object=object->next) {
                ++count;
                if(object->obj_uid>=910 && object->obj_uid<=914) assert(object->g_key==long(object->obj_uid-210));
            }
            assert(count==8); // Five catalog items and three recovered corpse items.
        }
        assert(character_list==&npc_holder && npc_holder.in_room==1 && inventory->equipment[3] && inventory->equipment[3]->obj_uid==911);
        assert(inventory->equipment[3]->extra_flags & ITEM_ARTIFACT);
        assert(inventory->equipment[3]->value[1]==74);
        assert(GET_MAX_HIT(&npc_holder)==333 && GET_HIT(&npc_holder)==222 && GET_MAX_MANA(&npc_holder)==211 && GET_MANA(&npc_holder)==111 && GET_MAX_VITALITY(&npc_holder)==123 && GET_VITALITY(&npc_holder)==99);
        bool carried=false,nested=false,money=false;
        for(auto *root=inventory->carrying;root;root=root->next_content) {
            if(root->obj_uid==914) { money=true; assert(root->type==ITEM_MONEY && root->value[3]==9); }
            if(root->obj_uid==910) { carried=true; assert((root->extra_flags & ITEM_ARTIFACT) && root->value[0]==73); }
            if(root->obj_uid==912) { nested=true; assert(root->contains && root->contains->obj_uid==913 &&
                (root->contains->extra_flags & ITEM_ARTIFACT) && root->contains->value[2]==75); }
        }
        assert(carried && nested && money);
        extract_obj(inventory->equipment[3],FALSE); inventory->equipment[3]=nullptr;
        while(inventory->carrying) { auto *root=inventory->carrying; inventory->carrying=root->next_content; extract_obj(root,FALSE); }
        str_free(npc_holder.player.name); str_free(npc_holder.player.short_descr); str_free(npc_holder.player.long_descr);
        npc_holder.player.name=npc_holder.player.short_descr=npc_holder.player.long_descr=nullptr;
        character_list=nullptr;
    }
    extract_obj(corpse, FALSE);
    item_ownership_runtime_reset();
    assert(!object_list);
    assert(bind_shopkeeper_calls == (shop_case() ? 1 : 0));
    std::puts("[PASS] production copyover save/exec/recover preserves corpse, generated loot and live custody without SQL");
}
'''

output = ROOT / "bin/tests"
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="duris-copyover-custody-", dir=output) as temp:
    temp = Path(temp)
    source = temp / "fixture.cpp"
    source.write_text(support + HARNESS)
    common = ["g++", "-std=c++20", "-g", "-fsanitize=address,undefined",
              "-fno-omit-frame-pointer", "-fno-sanitize-recover=undefined", "-ffunction-sections", "-fdata-sections", "-Isrc", "-D__NO_MYSQL__"]
    subprocess.run(common + ["-Dexecl=fixture_execl", "-c", "src/persistence/copyover.c",
                            "-o", str(temp / "copyover.o")], cwd=ROOT, check=True)
    subprocess.run(common + [str(source), str(temp / "copyover.o"),
                   "src/world/world_recovery_pipeline.c", "src/world/world_recovery_codec.c", "src/world/generated_npc_state.c", "src/world/generated_npc_runtime.c",
                   "src/player/pet_restore_state.c", "src/combat/trap_legacy.c",
                            "src/item/item_ownership_runtime.c", "src/item/item_transfer_command.c",
                            "src/redis/redis_command_observability.c", str(HARNESS_STUBS), "-Wl,--gc-sections",
                            "-lz", "-pthread", "-lgnutls", "-lbsd", "-o", str(temp / "fixture")],
                   cwd=ROOT, check=True)
    for scenario in ("binary-backup-race", "binary-race", "binary-success", "shop", "foreign-shop", "npc", "consume-race", "claim-race", "normal", "newer", "changed", "publish-race", "newer-owner", "mixed-owner"):
        state = temp / scenario
        server = state / "bin/server"
        server.mkdir(parents=True)
        if scenario.startswith("binary-"):
            for name in ("dms", "dms_new", "racing"):
                binary = server / name
                binary.write_text(name)
                binary.chmod(0o755)
        subprocess.run([str(temp / "fixture")], cwd=state, check=True, timeout=60,
                       env=dict(os.environ, COPYOVER_TEST_CASE=scenario, COPYOVER_STATE_FILE="copyover.dat"))
        if scenario == "binary-success":
            assert (server / "dms").read_text() == "dms_new"
            assert (server / "history/dms.copyover").read_text() == "dms"
            assert (server / "dms_new").read_text() == "racing"
        if scenario.startswith("binary-") and scenario != "binary-backup-race":
            assert not list((server / "history").glob(".copyover.*"))
