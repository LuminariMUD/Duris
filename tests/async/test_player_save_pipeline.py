#!/usr/bin/env python3
"""Player saves go straight to the one writer; nothing is journaled."""

from _paths import SRC, rel, extract_function
import subprocess
import tempfile
from pathlib import Path
from _paths import HARNESS_STUBS


ROOT = Path(__file__).resolve().parents[2]
PIPELINE = (SRC / "player_save_pipeline.c").read_text()
HEADER = (SRC / "player_save_pipeline.h").read_text()
FILES = (SRC / "files.c").read_text()
ACTOTH = (SRC / "actoth.c").read_text()
CHECKPOINT = (SRC / "persistence_checkpoint.c").read_text()
EVENTS = (SRC / "new_events.c").read_text()
COMM = (SRC / "comm.c").read_text()
NANNY = (SRC / "nanny.c").read_text()


def section(text: str, start: str, end: str) -> str:
    """Extract a production function region for contract checks."""
    first = text.index(start)
    return text[first : text.index(end, first)]


HARNESS = r'''
#include "player/player_save_pipeline.h"
#include "net/gmcp.h"
#include "player/player_save_worker.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "combat/combat_outcome_command.h"
#include "persistence/persistence_observability.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "core/files.h"
#include "cmd/interp.h"
#include "guild/assocs.h"
#include "player/player_playtime.h"
#include "net/output_preference_codec.h"
#include <algorithm>
#include <type_traits>

#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdarg>
#include <cstdlib>
#include <filesystem>
#include <map>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

P_char character_list = nullptr;
static bool divine_pending = false;
static bool locker_ready = true;
bool locker_private_contents_durable(P_char) { return locker_ready; }
void divine_boon_runtime_pulse() {}
bool divine_boon_runtime_pending() { return divine_pending; }
static room_data rooms[1]{};
P_room world = rooms;
const char *command[] = {"\n"};
int IS_MORPH(P_char) { return false; }
int GET_CLASS(P_char, unsigned int) { return 0; }
void do_color_preferences(P_char, const char *) { assert(false); }
void show_toggles(P_char) { assert(false); }
void __free(void *memory, const char *, int) { (std::free)(memory); }
void gmcp_send_initial_state(P_char) { assert(false); }
char *skip_spaces(char *s) { while (*s == ' ') ++s; return s; }
char *one_argument(const char *s, char *out) {
    while (*s == ' ') ++s;
    while (*s && *s != ' ') *out++ = *s++;
    *out = 0; return const_cast<char *>(s);
}
std::string toggle_output;
void send_to_char(const char *message, P_char) { toggle_output += message; }
const std::array<struct race_names, 1> race_names_table{{{"Human", "Human", "Human", "H"}}};
const char *get_account_name_safe(P_char) { return "privacy-fixture"; }
const char *get_class_name(P_char, P_char) { return "Warrior"; }
bool get_equipment_list(P_char, char *buffer, int) { strcpy(buffer, "PENDING_EQUIPMENT"); return true; }
/* PRODUCTION_WEBINFO_AND_STATUS */
int alerts = 0;
std::string last_alert, last_log;
void logit(const char *, const char *format, ...)
{
    char line[512];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    last_log = line;
}

void collector_death_enrollment_saved(uint64_t, unsigned int) {}
void persistence_alert(int, const char *, const char *, const char *, const char *,
                       const char *, const char *format, ...)
{
    assert(!strstr(format, "%s")); // the production alert rejects string substitutions
    char line[512];
    va_list args;
    va_start(args, format);
    vsnprintf(line, sizeof(line), format, args);
    va_end(args);
    last_alert = line;
    ++alerts;
}

struct apply_state
{
    std::mutex mutex;
    std::condition_variable changed;
    std::vector<std::string> order;
    std::map<int, unsigned int> failures;
    std::map<int, player_snapshot> committed;
    bool hold = false;
    bool holding = false;
};
apply_state state;

player_save_apply_result player_snapshot_repository_apply_from_pool(const player_snapshot &snapshot,
                                                                    void *)
{
    std::unique_lock<std::mutex> lock(state.mutex);
    if (state.hold)
    {
        state.holding = true;
        state.changed.notify_all();
        state.changed.wait(lock, [] { return !state.hold; });
        state.holding = false;
    }
    state.order.push_back(std::to_string(snapshot.pid) + ":" + std::to_string(snapshot.revision));
    if (state.failures[snapshot.pid])
    {
        --state.failures[snapshot.pid];
        player_save_apply_result result{player_save_apply_outcome::terminal_failure, 0, 1264};
        strcpy(result.failed_field.data(), "base_str");
        result.rolled_back = true;
        return result;
    }
    state.committed[snapshot.pid] = snapshot;
    return {player_save_apply_outcome::applied, snapshot.revision, 0};
}

player_snapshot_capture_result player_snapshot_capture(P_char ch, player_revision_t revision,
                                                       player_component_mask_t components, int save_intent,
                                                       int, player_snapshot *snapshot)
{
    *snapshot = {};
    snapshot->schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
    snapshot->pid = GET_PID(ch);
    snapshot->revision = revision;
    snapshot->components = components;
    snapshot->wallet_revision = ch->only.pc->wallet_revision;
    capture_budget budget;
    if ((components & PLAYER_COMPONENT_STATUS) && !capture_status(ch, *snapshot, budget, save_intent))
        return player_snapshot_capture_result::limit_exceeded;
    snapshot->encoded_size_bound = budget.bytes;
    return player_snapshot_capture_result::ok;
}

struct player
{
    char_data ch = {};
    pc_only_data pc = {};
    explicit player(int pid)
    {
        ch.only.pc = &pc;
        pc.pid = pid;
    }
};

void hold_writer(bool hold)
{
    std::lock_guard<std::mutex> lock(state.mutex);
    state.hold = hold;
    state.changed.notify_all();
}

void wait_until_held()
{
    std::unique_lock<std::mutex> lock(state.mutex);
    state.changed.wait(lock, [] { return state.holding; });
}

std::vector<std::string> take_order()
{
    std::lock_guard<std::mutex> lock(state.mutex);
    std::vector<std::string> order;
    order.swap(state.order);
    return order;
}

int main()
{
    assert(player_save_pipeline_init());
    player alice(41), bob(42), carol(44);
    alice.ch.next = &bob.ch;
    bob.ch.next = &carol.ch;
    character_list = &alice.ch;
    assert(player_revision_hydrate(41, 7));
    assert(player_revision_hydrate(42, 0));
    assert(player_revision_hydrate(44, 0));

    // Nothing dirty, nothing captured.
    assert(player_save_pipeline_checkpoint_dirty(&alice.ch, 1, 3001) ==
           player_save_pipeline_result::unchanged);

    player_pending_trade_snapshot trade;
    trade.operation[0]=1;trade.command_hash[0]=2;trade.payment=-80;
    assert(player_save_pipeline_reserve_trade(41,trade));
    assert(!player_save_pipeline_reserve_trade(42,trade));
    player_save_pipeline_release_trade(42);
    // A queued save leaves its owner clean: the writer has it.
    hold_writer(true);
    assert(player_save_pipeline_request(&bob.ch, PLAYER_COMPONENT_SKILLS, 1, 3001) ==
           player_save_pipeline_result::queued);
    wait_until_held();
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    player_revision_snapshot revision = {};
    assert(player_revision_snapshot_copy(41, &revision));
    assert(revision.current_revision == 8 && revision.acknowledged_revision == 8);
    assert(!revision.unacknowledged_components);
    // Accepted is not written: `save` reports completion on the written revision.
    assert(revision.written_revision == 7);
    // A newer save queues behind what was queued after the owner's save, and replaces
    // the owner's save only when that is the last one queued.
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_AFFECTS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_SKILLS, 1, 3001) ==
           player_save_pipeline_result::coalesced);
    // Equipment and inventory are one item graph.
    assert(player_save_pipeline_mark(42, PLAYER_COMPONENT_INVENTORY));
    assert(player_revision_snapshot_copy(42, &revision));
    assert(revision.unacknowledged_components ==
           (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY));
    assert(player_save_pipeline_checkpoint_dirty(&bob.ch, 1, 3001) ==
           player_save_pipeline_result::queued);

    // A stalled writer fails the drain within its bound and admission resumes.
    assert(!player_save_pipeline_drain(20));
    assert(player_save_pipeline_health_copy().drain_failures == 1);
    assert(!player_save_pipeline_mark(41, PLAYER_COMPONENT_STATUS));
    player_save_pipeline_resume();
    assert(player_save_pipeline_mark(41, PLAYER_COMPONENT_STATUS));

    hold_writer(false);
    assert(persistence_writer_wait_idle(5000));
    // Bob's first save was being written; everything else in capture order.
    assert((take_order() == std::vector<std::string>{"42:1", "41:8", "44:1", "41:10", "42:2"}));
    player_save_pipeline_pulse();
    assert(player_revision_snapshot_copy(41, &revision) && revision.written_revision == 10);
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        assert(state.committed[41].pending_trade.operation==trade.operation);
        assert(state.committed[41].pending_trade.payment==-80);
        assert(!player_snapshot_trade_pending(state.committed[42]));
    }
    player_save_pipeline_release_trade(41);


    // A failed write is reported and its owner is dirty again.
    state.failures[44] = 1;
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_TIMERS, 1, 3001) ==
           player_save_pipeline_result::queued);
    assert(persistence_writer_wait_idle(5000));
    const int alerts_before = alerts;
    player_save_pipeline_pulse();
    assert(alerts == alerts_before + 1);
    assert(last_alert.find("ended=0 queued_revision=2 written_revision=1 rollback_confirmed=1") != std::string::npos);
    assert(last_log == "PLAYER SAVE FIELD: pid=44 revision=2 field=base_str");
    assert(player_revision_snapshot_copy(44, &revision));
    assert(revision.unacknowledged_components == PLAYER_COMPONENT_TIMERS);
    assert(revision.written_revision == 1);
    player_save_pipeline_health health = player_save_pipeline_health_copy();
    assert(health.write_failures == 1);
    assert(player_save_pipeline_checkpoint_dirty(&carol.ch, 1, 3001) ==
           player_save_pipeline_result::queued);

    assert(player_save_pipeline_drain(5000));
    assert((take_order() == std::vector<std::string>{"44:2", "44:3"}));

    // Ended sessions cannot be forgotten while a save or its completion is pending.
    player_save_pipeline_resume();
    divine_pending = true;
    assert(!player_save_pipeline_drain(100)); // An idle writer does not drain deferred Divine work.
    divine_pending = false;
    player_save_pipeline_resume();
    hold_writer(true);
    state.failures[44] = 2;
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    wait_until_held();
    assert(player_save_pipeline_request(&carol.ch, PLAYER_COMPONENT_TIMERS, 1, 3001) ==
           player_save_pipeline_result::queued);
    bob.ch.next = nullptr; // production extraction removes Carol from character_list
    player_save_pipeline_end_session(44);
    assert(player_save_pipeline_load_held(44));
    assert(player_revision_snapshot_copy(44, &revision));
    assert(!player_revision_hydrate(44, 3)); // previous persisted revision
    hold_writer(false);
    assert(persistence_writer_wait_idle(5000));
    // Completed SQL must still be reconciled on the game thread before admission.
    assert(player_save_pipeline_load_held(44));
    player_save_pipeline_end_session(44);
    assert(player_revision_snapshot_copy(44, &revision));
    player_save_pipeline_pulse();
    assert(!player_save_pipeline_load_held(44));
    assert(last_alert.find("ended=1 queued_revision=5 written_revision=3 rollback_confirmed=1") != std::string::npos);
    assert(!player_revision_snapshot_copy(44, &revision));
    assert(player_revision_hydrate(44, 3)); // relog uses the actual committed state

    // An online owner's dirty state survives even when no writer job is pending.
    player_save_pipeline_end_session(41);
    assert(player_revision_snapshot_copy(41, &revision));
    assert(revision.unacknowledged_components);
    // A save completed before logout is retired by extraction, including unsaved dirt.
    player_save_pipeline_end_session(44);
    assert(!player_revision_snapshot_copy(44, &revision));

    // A quest transition retains the full terminal capture through write
    // failures, holds reload, and publishes only after the history/status
    // after-image commits even if its actor has departed.
    player dave(45);
    dave.pc.quest_active = 1;
    dave.pc.quest_mob_vnum = 15001;
    dave.pc.quest_origin_room = 16633;
    dave.pc.quest_replacement_due = 1;
    dave.ch.next = character_list;
    character_list = &dave.ch;
    assert(player_revision_hydrate(45, 0));
    player_pending_world_quest quest{true,15001,30,9000,0,1800000000,"Dave",""};
    int quest_callbacks = 0;
    bool callback_was_offline = false;
    persistence_writer_quiesce();
    assert(!player_save_pipeline_submit_world_quest(&dave.ch, quest,
        [&](P_char, const player_pending_world_quest &) { ++quest_callbacks; return true; }));
    assert(!player_save_pipeline_world_quest_pending(45) && quest_callbacks == 0);
    persistence_writer_resume();
    state.failures[45] = 2;
    hold_writer(true);
    assert(player_save_pipeline_submit_world_quest(&dave.ch, quest,
        [&](P_char actor, const player_pending_world_quest &record) {
            ++quest_callbacks; callback_was_offline = !actor;
            assert(record.target == 15001);
            return true;
        }));
    wait_until_held();
    assert(player_save_pipeline_world_quest_pending(45) && dave.pc.quest_active == 1);
    assert(player_save_pipeline_request(&dave.ch, PLAYER_CHECKPOINT_COMPONENT_ALL,
                                        RENT_QUIT, 3001) == player_save_pipeline_result::queued);
    character_list = dave.ch.next;
    player_save_pipeline_end_session(45);
    assert(player_save_pipeline_load_held(45));
    hold_writer(false);
    assert(persistence_writer_wait_idle(5000));
    player_save_pipeline_pulse();
    assert(quest_callbacks == 0 && player_save_pipeline_world_quest_pending(45));
    const auto quest_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (player_save_pipeline_world_quest_pending(45) &&
           std::chrono::steady_clock::now() < quest_deadline) {
        player_save_pipeline_pulse();
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    assert(!player_save_pipeline_world_quest_pending(45) && quest_callbacks == 1 &&
           callback_was_offline && !player_save_pipeline_load_held(45));
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto &saved = state.committed.at(45);
        assert(saved.pending_world_quest.present && saved.pending_world_quest.target == 15001);
        assert(saved.quest_values[0] == 0 && saved.quest_values[1] == 0 &&
               saved.quest_values[5] == -1);
        for (const auto &row : saved.status_integers)
            if (row.field == player_status_field::quest_origin_room ||
                row.field == player_status_field::quest_replacement_due)
                assert(row.signed_value == 0 && row.unsigned_value == 0);
    }

    // A rewarded completion instead persists the active task as accomplished,
    // so a disconnect before reward publication can recover it on login.
    player erin(46);
    erin.pc.quest_active = 1;
    erin.pc.quest_mob_vnum = 15002;
    erin.pc.quest_started = 1234;
    erin.pc.quest_origin_room = 16633;
    erin.ch.next = character_list;
    character_list = &erin.ch;
    assert(player_revision_hydrate(46, 0));
    auto reward_quest = quest;
    reward_quest.target = 15002;
    reward_quest.awaiting_reward = true;
    reward_quest.reward = {260, 3, 400};
    player_item_snapshot reward_root{}, reward_child{}, reward_bonus{};
    reward_root.object_uid=9001; reward_root.vnum=1001;
    reward_root.parent_index=PLAYER_SNAPSHOT_NO_PARENT;
    reward_child.object_uid=9002; reward_child.vnum=1002; reward_child.parent_index=0;
    reward_bonus=reward_root; reward_bonus.object_uid=9003;
    reward_quest.reward_items={reward_root,reward_child,reward_bonus};
    reward_quest.reward_encoded_size=1024;
    int reward_callbacks = 0;
    // Detached quest rewards add item components to an otherwise status-only
    // request, so they must also wait for the private chest destination.
    locker_ready = false;
    assert(!player_save_pipeline_submit_world_quest(&erin.ch, reward_quest,
        [&](P_char, const player_pending_world_quest &) { ++reward_callbacks; return true; }));
    assert(!player_save_pipeline_world_quest_pending(46) && reward_callbacks == 0);
    assert(player_revision_snapshot_copy(46, &revision));
    assert(revision.unacknowledged_components == PLAYER_COMPONENT_STATUS);
    locker_ready = true;
    hold_writer(true);
    assert(player_save_pipeline_submit_world_quest(&erin.ch, reward_quest,
        [&](P_char actor, const player_pending_world_quest &record) {
            assert(actor == &erin.ch && record.awaiting_reward);
            return ++reward_callbacks > 1; // first live publication refuses
        }));
    wait_until_held();
    assert(erin.pc.quest_active == 1 && erin.pc.quest_accomplished == 0 &&
           reward_callbacks == 0);
    hold_writer(false);
    assert(persistence_writer_wait_idle(5000));
    player_save_pipeline_pulse();
    assert(reward_callbacks == 1 && player_save_pipeline_world_quest_pending(46) &&
           player_save_pipeline_load_held(46));
    // A save during refused publication still carries the detached reward.
    assert(player_save_pipeline_request(&erin.ch, PLAYER_COMPONENT_STATUS, RENT_CRASH, 3001) ==
           player_save_pipeline_result::queued);
    assert(persistence_writer_wait_idle(5000));
    player_save_pipeline_pulse();
    const auto publication_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(5);
    while (player_save_pipeline_world_quest_pending(46) &&
           std::chrono::steady_clock::now() < publication_deadline) {
        player_save_pipeline_pulse();
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    assert(reward_callbacks >= 2 && !player_save_pipeline_world_quest_pending(46));
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto &saved = state.committed.at(46);
        assert(saved.pending_world_quest.awaiting_reward && saved.quest_values[0] == 1 &&
               saved.quest_values[1] == 15002 &&
               saved.quest_values[3] == PLAYER_WORLD_QUEST_REWARD_PENDING &&
               saved.quest_values[4] == 1234 && saved.quest_values[8] == 260 &&
               saved.quest_values[9] == 3 && saved.quest_values[10] == 400);
        assert((saved.components & (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY)) ==
               (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY));
        assert(saved.items.size() == 3 && saved.items[0].object_uid == 9001 &&
               saved.items[1].object_uid == 9002 && saved.items[1].parent_index == 0 &&
               saved.items[2].object_uid == 9003 &&
               saved.items[2].parent_index == PLAYER_SNAPSHOT_NO_PARENT);
    }
    character_list = erin.ch.next;

    // An escrowed fee is only present in the committed after-image; fallback
    // keeps the exact captured denominations and revision.
    player frank(47);
    frank.pc.quest_active=1; frank.pc.quest_mob_vnum=15003;
    frank.pc.wallet_revision=10; GET_COPPER(&frank.ch)=100;
    frank.ch.next=character_list; character_list=&frank.ch;
    assert(player_revision_hydrate(47, 0));
    auto paid_quest=quest; paid_quest.target=15003; paid_quest.escrow_fee=67;
    int paid_callbacks=0;
    hold_writer(true);
    assert(player_save_pipeline_submit_world_quest(&frank.ch,paid_quest,
        [&](P_char actor,const player_pending_world_quest &) {
            assert(actor==&frank.ch); ++paid_callbacks; return true;
        }));
    wait_until_held();
    assert(GET_COPPER(&frank.ch)==100 && frank.pc.wallet_revision==10 && paid_callbacks==0);
    hold_writer(false); assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    assert(paid_callbacks==1);
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto &saved=state.committed.at(47);
        assert(saved.pending_world_quest.before_quest[0]==1 &&
               saved.pending_world_quest.before_quest[1]==15003 &&
               saved.pending_world_quest.before_wallet==(std::array<int64_t,4>{100,0,0,0}) &&
               saved.pending_world_quest.before_wallet_revision==10 && saved.wallet_revision==11);
        std::array<int64_t,4> after{};
        for (const auto &row : saved.status_integers)
            if (row.field>=player_status_field::copper && row.field<=player_status_field::platinum)
                after[static_cast<size_t>(row.field)-static_cast<size_t>(player_status_field::copper)] = row.signed_value;
        assert((after==std::array<int64_t,4>{3,3,0,0}));
    }
    character_list=frank.ch.next;

    // A later independent credit is captured even if the actor disconnects
    // before a refused quest save is retried.
    player grace(48);
    grace.pc.quest_active=1; grace.pc.quest_mob_vnum=15004;
    grace.pc.wallet_revision=20; GET_COPPER(&grace.ch)=100;
    grace.ch.next=character_list; character_list=&grace.ch;
    assert(player_revision_hydrate(48,0));
    auto offline_paid=quest; offline_paid.target=15004; offline_paid.escrow_fee=67;
    int offline_paid_callbacks=0;
    state.failures[48]=2; hold_writer(true);
    assert(player_save_pipeline_submit_world_quest(&grace.ch,offline_paid,
        [&](P_char actor,const player_pending_world_quest &) {
            assert(!actor); ++offline_paid_callbacks; return true;
        }));
    wait_until_held();
    GET_COPPER(&grace.ch)+=10; ++grace.pc.wallet_revision;
    assert(player_save_pipeline_request(&grace.ch,PLAYER_CHECKPOINT_COMPONENT_ALL,
                                        RENT_QUIT,3001)==player_save_pipeline_result::queued);
    character_list=grace.ch.next; player_save_pipeline_end_session(48);
    hold_writer(false); assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    const auto offline_deadline=std::chrono::steady_clock::now()+std::chrono::seconds(5);
    while (player_save_pipeline_world_quest_pending(48) &&
           std::chrono::steady_clock::now()<offline_deadline) {
        player_save_pipeline_pulse(); std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    assert(offline_paid_callbacks==1 && !player_save_pipeline_world_quest_pending(48));
    {
        std::lock_guard<std::mutex> lock(state.mutex);
        const auto &saved=state.committed.at(48);
        assert(saved.pending_world_quest.before_wallet==(std::array<int64_t,4>{110,0,0,0}) &&
               saved.pending_world_quest.before_wallet_revision==21 && saved.wallet_revision==22);
        std::array<int64_t,4> after{};
        for (const auto &row : saved.status_integers)
            if (row.field>=player_status_field::copper && row.field<=player_status_field::platinum)
                after[static_cast<size_t>(row.field)-static_cast<size_t>(player_status_field::copper)] = row.signed_value;
        assert((after==std::array<int64_t,4>{3,4,0,0}));
    }

    // A new/offline character is not in character_list yet; its baseline save still
    // needs a written acknowledgement and a revision entry for the session to use.
    player newcomer(99);
    assert(player_revision_hydrate(99, 0));
    assert(player_save_pipeline_terminal(&newcomer.ch, 1, 3001, 100) ==
           player_save_terminal_result::database_acknowledged);
    assert(player_revision_snapshot_copy(99, &revision) && revision.written_revision == 1);

    // A private destination must land before an item checkpoint can remove the
    // saved inventory source. Refusal retains the dirty graph for a later retry.
    player custody(49);
    assert(player_revision_hydrate(49, 0));
    locker_ready = false;
    assert(player_save_pipeline_request(&custody.ch, PLAYER_COMPONENT_INVENTORY,
                                        RENT_CRASH, 3001) == player_save_pipeline_result::capture_failed);
    assert(player_revision_snapshot_copy(49, &revision));
    assert(revision.unacknowledged_components ==
           (PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY));
    locker_ready = true;
    assert(player_save_pipeline_checkpoint_dirty(&custody.ch, RENT_CRASH, 3001) ==
           player_save_pipeline_result::queued);
    assert(persistence_writer_wait_idle(5000));
    player_save_pipeline_pulse();
    assert(state.committed.count(49) == 1);

    // Shutdown reports a save that failed after its last pulse: the writer was still on
    // it when the drain ran out, and the interrupt made it fail.
    player_save_pipeline_resume();
    hold_writer(true);
    state.failures[41] = 1;
    assert(player_save_pipeline_request(&alice.ch, PLAYER_COMPONENT_STATUS, 1, 3001) ==
           player_save_pipeline_result::queued);
    wait_until_held();
    const int alerts_at_shutdown = alerts;
    divine_pending = true;
    const auto left = player_save_pipeline_finish(persistence_observability_now_usec() + 20000,
                                                  [] { hold_writer(false); });
    assert(left.size() == 1 && left[0] == persistence_job_owner(persistence_job_kind::divine_boon, 1));
    divine_pending = false;
    assert(alerts == alerts_at_shutdown + 1);
    player_save_pipeline_reset_for_tests();

    // Real webinfo dispatcher, real status capture, codec, worker and completion
    // reconciliation. Only the database boundary injects delayed/failing writes.
    assert(player_save_pipeline_init());
    player a(201), b(202);
    a.ch.next = &b.ch; character_list = &a.ch;
    a.ch.in_room = b.ch.in_room = NOWHERE;
    assert(player_revision_hydrate(201, 0) && player_revision_hydrate(202, 0));
    auto toggle = [&](P_char ch, const char *setting) {
        char text[80]; strcpy(text, setting); toggle_output.clear();
        do_toggle(ch, text, 0); return toggle_output;
    };
    auto saved_on = [&](int pid) {
        std::lock_guard<std::mutex> lock(state.mutex);
        for (const auto &entry : state.committed[pid].status_integers)
            if (entry.field == player_status_field::action_flags_2)
                return ((entry.is_unsigned ? entry.unsigned_value : entry.signed_value) & PLR2_WEBINFO) != 0;
        return false;
    };
    a.ch.player.name = const_cast<char *>("Alice");
    b.ch.player.name = const_cast<char *>("Bob");
    auto capture_pending = [&](bool a_on, bool b_on) {
        combat_outcome_payload capture{};
        auto *killer = combat_outcome_add_participant(&capture, &a.ch, combat_participant_role::killer, true, true);
        auto *victim = combat_outcome_add_participant(&capture, &b.ch, combat_participant_role::victim, true, false);
        assert(killer->webinfo_at_capture == (a_on ? combat_webinfo::on : combat_webinfo::off));
        assert(victim->webinfo_at_capture == (b_on ? combat_webinfo::on : combat_webinfo::off));
        assert(killer->equipment.empty() == !a_on && victim->equipment.empty() == !b_on);
        assert(killer->log.empty() && victim->log.empty()); // Missing PlayerLogs are safe.
    };
    player_save_pipeline_quiesce();
    assert(toggle(&a.ch, "webinfo on").find("did not take effect") != std::string::npos);
    assert(!PLR2_FLAGGED(&a.ch, PLR2_WEBINFO));
    player_save_pipeline_resume();
    std::string oversized(PLAYER_SNAPSHOT_MAX_STRING_BYTES + 1, 'x');
    a.ch.player.description = oversized.data();
    assert(toggle(&a.ch, "webinfo on").find("did not take effect") != std::string::npos);
    assert(!PLR2_FLAGGED(&a.ch, PLR2_WEBINFO));
    a.ch.player.description = nullptr;
    hold_writer(true);
    assert(toggle(&a.ch, "webinfo on").find("save pending") != std::string::npos);
    wait_until_held();
    assert(PLR2_FLAGGED(&a.ch, PLR2_WEBINFO) && !saved_on(201));
    assert(player_revision_snapshot_copy(201, &revision) && revision.written_revision == 0);
    assert(toggle(&b.ch, "webinfo on").find("save pending") != std::string::npos);
    capture_pending(true, true);
    assert(toggle(&b.ch, "webinfo off").find("save pending") != std::string::npos);
    capture_pending(true, false);
    assert(player_save_pipeline_health_copy().coalesced >= 1);
    hold_writer(false); assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    assert(saved_on(201) && !saved_on(202));
    assert(player_revision_snapshot_copy(201, &revision) && revision.written_revision > 0);

    // An older off write fails after a newer on request. Completion cannot undo
    // the newer live decision; status stays dirty until a successful retry.
    state.failures[201] = 1; hold_writer(true);
    assert(toggle(&a.ch, "webinfo off").find("save pending") != std::string::npos);
    wait_until_held();
    assert(!PLR2_FLAGGED(&a.ch, PLR2_WEBINFO) && saved_on(201));
    capture_pending(false, false);
    assert(toggle(&a.ch, "webinfo on").find("save pending") != std::string::npos);
    hold_writer(false); assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    assert(PLR2_FLAGGED(&a.ch, PLR2_WEBINFO) && saved_on(201));
    assert(player_revision_snapshot_copy(201, &revision) && (revision.unacknowledged_components & PLAYER_COMPONENT_STATUS));
    assert(player_save_pipeline_checkpoint_dirty(&a.ch, RENT_CRASH, NOWHERE) == player_save_pipeline_result::queued);
    assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    assert(player_revision_snapshot_copy(201, &revision) && !revision.unacknowledged_components);
    auto committed_revision = revision.written_revision;

    // Successful disconnect/reconnect loads the committed setting. A failed final
    // save retires its session only after completion and reloads that same setting.
    character_list = &b.ch; player_save_pipeline_end_session(201);
    assert(!player_save_pipeline_load_held(201));
    assert(player_revision_hydrate(201, committed_revision));
    a.ch.specials.act2 = saved_on(201) ? PLR2_WEBINFO : 0;
    character_list = &a.ch;
    state.failures[201] = 2; hold_writer(true);
    assert(toggle(&a.ch, "webinfo off").find("save pending") != std::string::npos);
    wait_until_held();
    assert(player_save_pipeline_terminal(&a.ch, RENT_QUIT, NOWHERE, 1) == player_save_terminal_result::timed_out);
    character_list = &b.ch; player_save_pipeline_end_session(201);
    assert(player_save_pipeline_load_held(201));
    hold_writer(false); assert(persistence_writer_wait_idle(5000)); player_save_pipeline_pulse();
    assert(!player_save_pipeline_load_held(201) && saved_on(201));
    assert(player_revision_hydrate(201, committed_revision));
    assert(last_alert.find("ended=1") != std::string::npos);
    player_save_pipeline_reset_for_tests();
    character_list = nullptr;
    return 0;
}
'''


with tempfile.TemporaryDirectory(prefix="duris-player-save-pipeline-", dir=ROOT / "bin/tests") as temp_dir:
    source = Path(temp_dir) / "pipeline_test.cpp"
    binary = Path(temp_dir) / "pipeline_test"
    actoth = (SRC / "actoth.c").read_text()
    production = "#define TOG_OFF 0\n#define TOG_ON 1\n"
    production += "#define PLR_TOG(flag) plr_tog(PLR_FLAGS(ch), flag, arg)\n#define PLR2_TOG(flag) plr_tog(PLR2_FLAGS(ch), flag, arg)\n#define PLR3_TOG(flag) plr_tog(PLR3_FLAGS(ch), flag, arg)\n"
    production += actoth[actoth.index("static const char *toggles_list[]"):actoth.index("void do_more(")]
    for filename, signature in [("interp.c", "char *lohrr_chop("), ("interp.c", "bool is_abbrev("), ("interp.c", "int old_search_block("),
                                ("utility.c", "int yes_no("), ("utility.c", "int strn_cmp("),
                                ("actoth.c", "static const char *term_name("), ("actoth.c", "static int plr_tog("),
                                ("actoth.c", "void do_toggle(")]:
        production += "\n" + extract_function(filename, signature)
    capture = (SRC / "player_snapshot_capture.c").read_text()
    production += "\n" + capture[capture.index("struct capture_budget"):capture.index("template <typename T> bool add_index_value")]
    production += "\n" + extract_function("fight.c", "static combat_outcome_participant *combat_outcome_add_participant(")
    source.write_text(HARNESS.replace("/* PRODUCTION_WEBINFO_AND_STATUS */", production))
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wno-unused-parameter",
            "-pthread",
            "-Isrc",
            "-I/usr/include/mysql",
            str(source),
            rel("player_save_pipeline.c"),
            rel("player_save_worker.c"),
            rel("safe_format.c"),
            rel("player_snapshot_codec.c"),
            rel("player_revision_state.c"),
            rel("persistence_observability.c"),
            "-lmysqlclient",
            str(HARNESS_STUBS), "-o",
            str(binary),
        ],
        cwd=ROOT,
        check=True,
        capture_output=False,
        text=True,
    )
    subprocess.run([str(binary)], check=True, timeout=60)
print("[PASS] a queued save leaves its owner clean; a newer save replaces the queued one")
print("[PASS] a failed write is reported and marks its owner dirty again")
print("[PASS] ended sessions retire only after pending writes/completions; live dirt and new baselines survive")
print("[PASS] drain waits for the writer within its bound")
print("[PASS] shutdown reports a save that failed after the last pulse")
print("[PASS] real webinfo toggles capture live consent before delayed saves, coalesce, retry and reload committed settings")

free_character = section((SRC / "db.c").read_text(), "void free_char(P_char ch)", "void free_obj(")
assert "player_save_pipeline_end_session(GET_PID(ch));" in free_character

assert "PLAYER_SAVE_PIPELINE_MAX_BYTES" not in HEADER
assert "pending_append" not in PIPELINE and "durable_ready" not in PIPELINE
assert "dispatcher" not in PIPELINE
assert "player_save_journal_append" not in PIPELINE
checkpoint = section(
    PIPELINE,
    "player_save_pipeline_result player_save_pipeline_checkpoint_dirty",
    "player_save_pipeline_result player_save_pipeline_request",
)
assert checkpoint.index("player_revision_queue") < checkpoint.index("player_snapshot_capture")
for forbidden in ("player_save_journal_", "sql_", "redis_", "fopen", "open(", "write("):
    assert forbidden not in checkpoint
pulse = section(PIPELINE, "void player_save_pipeline_pulse", "void player_save_pipeline_quiesce")
assert "player_save_worker_pulse" in pulse
for forbidden in ("player_save_journal_", "sql_", "redis_", "fopen", "open(", "write("):
    assert forbidden not in pulse
print("[PASS] game-thread checkpoint and completion paths contain no external I/O")

write_character = section(FILES, "int writeCharacter(P_char ch", "character_delete_result forget_deleted_character(")
# Every MariaDB save, terminal ones too, is queued: no synchronous SQL is left in it.
branch = write_character.index("player_save_pipeline_request(")
assert "const bool queued_save = true;" in write_character[:branch]
for legacy in ("sql_save_player", "sql_update_money", "sql_save_locker"):
    assert legacy not in write_character, legacy
silent = section(ACTOTH, "bool do_save_silent(P_char ch", "void do_save(P_char")
assert silent.index("player_save_pipeline_is_nonterminal_type") < silent.index("fopen(tmp_buf")
assert silent.index("player_save_pipeline_request") < silent.index("writeCharacter(ch")
init_char = section(NANNY, "void init_char(P_char ch)", "int approve_mode")
assert "player_revision_hydrate(ch->only.pc->pid, 0)" in init_char
print("[PASS] ordinary direct and manual saves branch before legacy mutation and I/O")

mark = section(CHECKPOINT, "void mark_player_dirty_components(int pid", "int get_dirty_player_count(void)")
flush = section(CHECKPOINT, "void event_flush_dirty_players(", "\n}\n")
assert "player_save_pipeline_mark" in mark
assert "player_save_pipeline_checkpoint_dirty" in flush
for retired in ("redis_command", "redis_reconnect", "sql_save_player", "fork("):
    assert retired not in mark and retired not in flush
event_init = section(EVENTS, "void ne_init_events", "void zone_purge")
assert '"dirty-player-checkpoint", event_flush_dirty_players' in event_init
assert "nevent_periodic_policy::fixed_delay, true" in event_init
print("[PASS] autosave is local and the Redis dirty-save fork is retired")

assert "player_save_pipeline_init()" in COMM
assert "player_save_pipeline_pulse();" in COMM
assert "player_save_pipeline_finish(shutdown_writer_deadline_usec," in COMM
assert "player_save_pipeline_shutdown();" in section(
    (SRC / "player_save_pipeline.c").read_text(), "std::vector<persistence_job_owner> player_save_pipeline_finish(",
    "player_save_pipeline_health player_save_pipeline_health_copy(void)")
print("[PASS] the pipeline starts at boot and shutdown finishes it")

print("player save pipeline contracts passed")
