#!/usr/bin/env python3
"""Compare deferred output bytes with synchronous output using real prompt/renderers.

A production creation grant is held at the coordinator boundary, and the prompt with it;
its completion callback queues fixture text. Real prompt, ANSI, Telnet and WebSocket
serialization run against an in-memory transport.
"""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, SRC, extract_function


PRELUDE = r'''
#include "core/prototypes.h"
#include "player/output_preferences.h"
#include "core/utils.h"
#include "net/comm.h"
#include "net/mccp.h"
#include "net/websocket.h"
#include "core/json_utils.h"
#include "item/item_movement_transaction.h"
#include "item/item_ownership_runtime.h"
#include "persistence/persistence_checkpoint.h"
#include "player/player_load_items.h"
#include <algorithm>
#include <cassert>
#include <string>
#include <vector>
#include <cstring>
#include <gnutls/gnutls.h>

static bool custom_prompt = false;
ResolvedOutputProfile player_output_profile(P_char, OutputChannel channel, OutputPolicy policy) {
    OutputProfilePreferences choices;
    if (custom_prompt) choices.set_color(OutputChannel::Prompt, ATTR_FG(27));
    return resolve_output_profile({}, channel, policy, choices);
}
static critical_command submitted;
static const char *publication_message;
static bool publication_success;
P_char character_list = nullptr;
P_obj object_list = nullptr;
static index_data indexes[1]{};
P_index obj_index = indexes;
static room_data rooms[1]{};
P_room world = rooms;
int top_of_objt = 0;
extern const int top_of_world = 0;

static bool collector_busy;
bool collector_transaction_player_busy(P_char) { return collector_busy; }
bool collector_transaction_item_busy(uint64_t) { return false; }
bool collector_service_player_busy(P_char) { return false; }
void collector_catalog_cache_invalidate(void) {}
void extract_obj(P_obj, int) {}
void obj_from_char(P_obj) {}
void obj_to_char(P_obj object, P_char ch) { object->loc_p = LOC_CARRIED; object->loc.carrying = ch; }
void obj_to_obj(P_obj, P_obj) {}
void obj_to_room(P_obj, int) {}
void mark_player_dirty_components(int, player_component_mask_t) {}
P_char find_player_by_pid(int pid) { return character_list && GET_PID(character_list) == pid ? character_list : nullptr; }
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
    submitted = std::move(command);
    return critical_submit_result::accepted;
}
bool critical_command_coordinator_is_fenced(const critical_entity_key &, critical_operation_id *)
{
    return false;
}
static void publish(P_char actor, bool committed, const item_transfer_result &, unsigned,
                    const uint8_t *, size_t)
{
    assert(committed == publication_success);
    write_to_q(publication_message, &actor->desc->output, 1);
}
static std::string delivered;
static std::vector<std::string> frames;
static std::string ambient_bytes;
static int ga_count;
P_index mob_index = nullptr;
long sentbytes = 0;
void logit(const char *, const char *, ...) {}
void statuslog(int, const char *, ...) {}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
                       const char *, ...) {}
bool player_load_item_graph_materialize_creation(const item_transfer_payload &,
                                                 const item_transfer_result &,
                                                 std::vector<P_obj> *)
{
    return false;
}
void debug(const char *, ...) {}
int IS_MORPH(P_char) { return false; }
bool ac_can_see(P_char, P_char, bool) { return true; }
char *PERS(P_char, P_char, int, bool) { static char name[] = "someone"; return name; }
char *FirstWord(char *s) { return s; }
affected_type *get_ward_from_char(P_char) { return nullptr; }
void delete_doubledollar(char *) {}
void panic_corruption(const char *, const char *, ...) { abort(); }
void __free(void *p, const char *, int) { free(p); }
void format_to_snoopers(const char *in, char *out) { strcpy(out, in); }
void append_prompt(P_char, char *) {}
void write_to_pc_log(P_char, const char *, int) {}
void send_to_char(const char *text, P_char ch) { write_to_q(text, &ch->desc->output, 1); }
extern "C" ssize_t __wrap_write(int, const void *p, size_t n)
{
    std::string bytes((const char *)p, n);
    if (bytes == std::string("\xff\xf9", 2)) ++ga_count;
    delivered += bytes;
    return n;
}
extern "C" ssize_t gnutls_record_send(gnutls_session_t, const void *, size_t) { abort(); }
extern "C" const char *gnutls_strerror(int) { return "fixture"; }
int websocket_send_text(P_desc, const char *text) { frames.emplace_back(text); return 0; }
void write_to_q(const char *text, struct txt_q *q, const int)
{
    auto *block = (txt_block *)calloc(1, sizeof(txt_block));
    block->text = strdup(text);
    if (q->tail) q->tail->next = block; else q->head = block;
    q->tail = block;
}
'''

DRIVER = r'''
static std::string output_bytes(bool websocket)
{
    if (!websocket) return delivered;
    std::string bytes;
    for (const auto &frame : frames) bytes += frame;
    return bytes;
}
static std::string text_bytes(bool websocket, const char *text)
{
    if (!websocket) return text;
    char *escaped = json_escape_ansi_string(text);
    assert(escaped);
    std::string bytes = "{\"type\":\"text\",\"category\":\"info\",\"data\":\"";
    bytes += escaped;
    bytes += "\"}";
    free(escaped);
    return bytes;
}
static std::string run(bool delayed, bool websocket, int flags, bool two_line,
                       bool fighting, const char *message, bool ambient = false,
                       bool collector = false, bool switched = false, int auxiliary = 0)
{
    descriptor_data d{};
    char_data actor{}, body{}, enemy{};
    npc_only_data body_npc{};
    pc_only_data pc{};
    char *edit = nullptr;
    actor.only.pc = &pc;
    actor.desc = &d;
    actor.specials.act = flags;
    actor.specials.position = POS_STANDING | STAT_NORMAL;
    actor.points.hit = actor.points.max_hit = 100;
    actor.points.vitality = actor.points.max_vitality = 100;
    pc.screen_length = 24;
    pc.prompt = PROMPT_HIT | (two_line ? PROMPT_TWOLINE : 0);
    if (fighting) actor.specials.fighting = &enemy;
    if (switched)
    {
        body.only.npc = &body_npc;
        body.desc = &d;
        body.specials.act = ACT_ISNPC;
        body.specials.position = POS_STANDING | STAT_NORMAL;
        body.points.hit = body.points.max_hit = 100;
        body.points.vitality = body.points.max_vitality = 100;
        d.character = &body;
        d.original = &actor;
    }
    else
        d.character = &actor;
    d.prompt_mode = TRUE;
    d.websocket = websocket;
    delivered.clear(); frames.clear(); ambient_bytes.clear(); ga_count = 0;
    collector_busy = false;
    item_movement_transaction_reset_for_tests();
    item_ownership_runtime_reset();
    pc.pid = 42;
    character_list = &actor;
    obj_data item{};
    indexes[0].virtual_number = 100;
    item.obj_uid = 100;
    item.R_num = 0;
    // A grant takes a detached object; one lying in the room is refused at once.
    item.loc_p = delayed || message[0] == 'Y' ? LOC_NOWHERE : LOC_ROOM;
    object_list = &item;
    assert(item_ownership_runtime_hydrate_owner({item_owner_type::system, 0, 0}, 1));
    assert(item_ownership_runtime_hydrate_owner({item_owner_type::player, 42, 0}, 7));
    if (delayed)
    {
        publication_message = message;
        publication_success = message[0] == 'Y';
        if (collector)
            collector_busy = true;
        else
            assert(item_creation_grant_submit_to_player_with_completion(&actor, &item, &actor,
                                                                        publish, nullptr, 0));
        assert(collector_busy || item_movement_transaction_player_busy(&actor));
        if (auxiliary)
        {
            if (auxiliary == 1)
            {
                d.showstr_count = 2;
                d.showstr_page = 1;
            }
            else
                d.str = &edit;
            assert(process_output(&d) == 1);
            const auto bytes = output_bytes(websocket);
            assert(bytes.find(auxiliary == 1 ? "[Return to continue" : "] ") !=
                   std::string::npos);
            assert((websocket || ga_count == 1) && !d.prompt_mode);
            d.showstr_count = 0;
            d.str = nullptr;
            d.prompt_mode = TRUE;
            delivered.clear(); frames.clear(); ga_count = 0;
        }
        for (int pulse = 0; pulse < 6; ++pulse)
        {
            assert(process_output(&d) == 1);
            assert(delivered.empty() && frames.empty() && ga_count == 0);
        }
        if (ambient)
        {
            write_to_q("Someone says hello.\r\n", &d.output, 1);
            assert(process_output(&d) == 1);
            assert(output_bytes(websocket).find("Someone says hello.") != std::string::npos);
            assert(ga_count == 0 && !d.output.head);
            ambient_bytes = output_bytes(websocket);
            delivered.clear(); frames.clear();
        }
        if (collector)
        {
            collector_busy = false;
            write_to_q(message, &d.output, 1);
        }
        else
        {
            critical_completion completion{};
            completion.operation_id = submitted.operation_id;
            completion.outcome = publication_success ? critical_apply_outcome::applied :
                                                      critical_apply_outcome::terminal_failure;
            item_transfer_result result{100, 1, 4, 8, 2, 0};
            std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> encoded{};
            assert(item_transfer_command_encode_result(result, &encoded));
            completion.result_size = encoded.size();
            std::copy(encoded.begin(), encoded.end(), completion.result_payload.begin());
            item_movement_transaction_handle_completions(&completion, 1);
            assert(!item_movement_transaction_player_busy(&actor));
        }
    }
    else
    {
        if (message[0] != 'Y')
        {
            // A refused grant must keep the ordinary immediate prompt.
            assert(!item_creation_grant_submit_to_player_with_completion(&actor, &item, &actor,
                                                                         publish, nullptr, 0));
            assert(!item_movement_transaction_player_busy(&actor));
        }
        write_to_q(message, &d.output, 1);
    }
    assert(process_output(&d) == 1);
    assert(!d.output.head);
    const auto bytes = output_bytes(websocket);
    assert(bytes.find(message[0] == 'Y' ? "You get" : "Unable to pick up") != std::string::npos);
    const bool expect_prompt = !(flags & PLR_OLDSMARTP) || fighting;
    assert(ga_count == (!websocket && expect_prompt ? 1 : 0));
    if (expect_prompt && !(flags & PLR_SMARTPROMPT))
        assert(bytes.find("100h") > bytes.find(message[0] == 'Y' ? "You get" : "Unable to pick up"));
    assert(process_output(&d) == 1);
    assert(output_bytes(websocket) == bytes); // no duplicate completion prompt
    return bytes;
}
int main()
{
    for (bool ws : {false, true})
    for (bool compact : {false, true})
    for (unsigned smart : {0u, PLR_SMARTPROMPT, PLR_OLDSMARTP, PLR_SMARTPROMPT | PLR_OLDSMARTP})
    for (bool two : {false, true})
    for (bool fighting : {false, true})
    for (const char *message : {"You get item from bag.\r\n",
                               "You get sword from corpse.\r\nYou get shield from corpse.\r\n",
                               "You get item.\r\n", "Unable to pick up item.\r\n",
                               "Unable to pick up item from bag.\r\n",
                               "Unable to pick up sword and shield from corpse.\r\n"})
    {
        int flags = smart | (compact ? PLR_COMPACT : 0);
        const auto synchronous = run(false, ws, flags, two, fighting, message);
        assert(run(true, ws, flags, two, fighting, message) == synchronous);
        run(true, ws, flags, two, fighting, message, true);
        if (smart == PLR_SMARTPROMPT)
            assert(ambient_bytes == text_bytes(ws, "Someone says hello.\r\n"));
    }
    // A collector transaction in flight holds the prompt the same way.
    const auto synchronous = run(false, false, 0, false, false, "You get item.\r\n");
    assert(run(true, false, 0, false, false, "You get item.\r\n", false, true) ==
           synchronous);
    assert(run(true, false, 0, false, false, "You get item.\r\n", false, false, true) ==
           run(false, false, 0, false, false, "You get item.\r\n", false, false, true));
    run(true, false, 0, false, false, "You get item.\r\n", false, false, false, 1);
    run(true, false, 0, false, false, "You get item.\r\n", false, false, true, 2);
    custom_prompt = true;
    for(bool ws : {false, true})
    for(bool two : {false, true}) {
        const auto colored = run(false, ws, 0, two, false, "You get item.\r\n");
        assert(run(true, ws, 0, two, false, "You get item.\r\n") == colored);
    }
    puts("Deferred item/collector output, ambient bytes, auxiliary prompts, and switched descriptors passed");
}
'''


def main():
    build = ROOT / 'bin/tests'
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='item-prompts-', dir=build) as directory:
        source = Path(directory) / 'harness.cpp'
        binary = Path(directory) / 'harness'
        source.write_text('\n'.join([PRELUDE,
            extract_function('comm.c', 'int get_from_q(struct txt_q *queue, char *dest)'),
            extract_function('comm.c', 'int process_output(P_desc t)'), DRIVER]))
        subprocess.run(['g++', '-std=c++20', '-g', '-O1', '-ffunction-sections', '-fdata-sections',
                        '-fsanitize=address,undefined', '-Isrc', str(source),
                        *[str(SRC / name) for name in ['output_profiles.c', 'output_style.c', 'prompt.c', 'ansi.c', 'mccp.c', 'unicode.c', 'json_utils.c', 'safe_format.c',
                            'item_movement_transaction.c', 'item_ownership_runtime.c',
                            'item_transfer_command.c', 'critical_command.c',
                            'player_snapshot_capture.c', 'player_snapshot_codec.c']],
                        '-Wl,--gc-sections', '-Wl,--wrap=write', '-lz', '-lcrypto', '-lcjson', '-o', str(binary)],
                       cwd=ROOT, check=True, timeout=600)
        subprocess.run([str(binary)], check=True, timeout=30)


if __name__ == '__main__':
    main()
