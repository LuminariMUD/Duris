// Real reward calculation, live application, child codec and transaction lifetime.
// Only boot state, artifact storage, SQL/writer admission and engine messaging are
// fixture boundaries. No reward formula is supplied by the fixture.
#include "guild/artifact_guild_state.c"
#include "guild/artifact_guild_transaction.h"
#include "world/zone_touch_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include <cassert>
#include <cstdio>
#include <map>
#include <string>
#include <vector>

static constexpr time_t NOW = 1791900000;
extern "C" time_t time(time_t *out)
{
	if (out)
		*out = NOW;
	return NOW;
}
static constexpr int64_t FEED_CAP = NOW + ARTIFACT_BLOOD_DAYS * SECS_PER_REAL_DAY;
struct row
{
	int64_t timer;
	int32_t soul = -1;
	int64_t bind = 0;
	int owner = 42;
};
static std::map<int, row> rows;
static std::vector<std::pair<int, row>> snapshots;
static std::vector<std::pair<unsigned long, unsigned long>> guild_snapshots;
static std::vector<critical_command> commands;
static std::vector<std::string> feedback;
static critical_submit_result admission = critical_submit_result::accepted;
static bool recent_frag = false;
static double difficulty = 1;
index_data indexes[2] = {};
P_index obj_index = indexes;
char guild_default_titles[ASC_NUM_RANKS][ASC_MAX_STR_RANK] = {};
float get_property(const char *, double value)
{
	return value;
}
int get_property(const char *, int value)
{
	return value;
}
int check_nexus_bonus(P_char, int amount, int)
{
	return amount;
}
bool affected_by_spell(P_char, int tag)
{
	return tag == TAG_PLR_RECENT_FRAG && recent_frag;
}
double difficulty_multiplier(difficulty_dial)
{
	return difficulty;
}
bool persistence_mode_requires_mysql()
{
	return true;
}
bool artifact_feed_state(int vnum, int64_t *timer, int32_t *owner, int64_t *bind)
{
	auto found = rows.find(vnum);
	if (found == rows.end())
		return false;
	*timer = found->second.timer;
	*owner = found->second.soul;
	*bind = found->second.bind;
	return true;
}
void artifact_feed_set_timer(int vnum, time_t timer)
{
	assert(rows.count(vnum));
	rows[vnum].timer = timer;
	snapshots.emplace_back(vnum, rows.at(vnum));
}
void artifact_feed_published(int vnum, time_t before, time_t timer)
{
	if (rows.count(vnum) && rows[vnum].timer == before)
		artifact_feed_set_timer(vnum, timer);
}
size_t artifact_save_pulse(bool)
{
	return 0;
}
void artifact_report_unsaved() {}
bool sql_save_guild(Guild *guild)
{
	guild_snapshots.emplace_back(guild->get_prestige(), guild->get_construction());
	return true;
}
// Kingdom persistence is covered by the snapshot fixture; this fixture has no realms.
void kingdom_guild_save_completed(int, const std::shared_ptr<sql_write_receipt> &) {}
static std::vector<P_char> online;
P_char find_player_by_pid(int pid)
{
	for (P_char ch : online)
		if (GET_PID(ch) == pid)
			return ch;
	return nullptr;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
static size_t stone_consumed = 0, stone_feedback = 0;
void epic_publish_zone_touch(const zone_touch_result &) {}
void epic_finish_stone_touch(const zone_touch_result &)
{
	++stone_consumed;
}
void epic_publish_stone_award(P_char, const zone_touch_result &, size_t)
{
	++stone_feedback;
}
bool redis_invalidate_epic_zones()
{
	return true;
}
void send_to_char(const char *text, P_char)
{
	feedback.emplace_back(text);
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	if (admission != critical_submit_result::accepted)
	{
		errno = admission == critical_submit_result::overloaded ? ENOSPC : ESHUTDOWN;
		return admission;
	}
	commands.push_back(std::move(command));
	return admission;
}
bool critical_command_coordinator_drain(uint64_t)
{
	return true;
}
critical_coordinator_health critical_command_coordinator_health_copy()
{
	return {};
}

static void reset()
{
	artifact_guild_transaction_reset_for_tests();
	rows.clear();
	snapshots.clear();
	guild_snapshots.clear();
	commands.clear();
	feedback.clear();
	admission = critical_submit_result::accepted;
	recent_frag = false;
	difficulty = 1;
#if LEGACY_HYDRATION
	hydrated = true;
	guild_revisions.emplace(7, 0);
	guild_revisions.emplace(8, 0);
#endif
}
static critical_operation_id award(P_char ch, int amount = 4, int type = EPIC_BOON)
{
	critical_operation_id parent = {};
	assert(critical_operation_id_generate(&parent));
	assert(artifact_guild_transaction_submit(ch, parent, amount, type));
	return parent;
}
static void complete(const critical_command &command)
{
	artifact_guild_payload payload = {};
	assert(artifact_guild_command_decode_payload(command, &payload));
	artifact_guild_result result = {};
	result.guild_id = payload.guild_id;
#if !LEGACY_HYDRATION
	result.prestige = payload.prestige_after;
	result.construction = payload.construction_after;
#endif
	result.artifact_count = payload.artifact_count;
	for (size_t i = 0; i < result.artifact_count; ++i)
		result.artifacts[i] = { payload.artifacts[i].vnum, payload.artifacts[i].timer,
					payload.artifacts[i].bind_owner_pid,
					payload.artifacts[i].bind_timer, i + 1 };
	std::array<uint8_t, ARTIFACT_GUILD_RESULT_BYTES> bytes;
	assert(artifact_guild_command_encode_result(result, &bytes));
	critical_completion completion = {};
	completion.operation_id = command.operation_id;
	completion.outcome = critical_apply_outcome::applied;
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	artifact_guild_transaction_handle_completions(&completion, 1);
	artifact_guild_transaction_handle_completions(&completion, 1); // duplicate delivery
}

// Issue #67 acceptance cases use real capture, application and history admission.
// No canonical UID is established for the conflicting vnum: neither copy may
// feed, but the unrelated artifact and independently eligible guild must survive.
static int identity_contract(bool duplicate)
{
	reset();
	char_data actor = {}, member = {}, last = {};
	pc_only_data pc = {}, pc2 = {}, pc3 = {};
	actor.only.pc = &pc;
	member.only.pc = &pc2;
	last.only.pc = &pc3;
	pc.pid = 42;
	pc2.pid = 43;
	pc3.pid = 44;
	char name[] = "Identity fixture";
	auto *guild = new Guild(name, RACEWAR_GOOD, 7, 95, 0, 0, 0);
	group_list group[3] = { { &actor, &group[1] }, { &member, &group[2] }, { &last, nullptr } };
	for (P_char ch : { &actor, &member, &last })
	{
		ch->player.level = 51;
		ch->in_room = 1;
		ch->group = group;
		ch->specials.guild = guild;
	}
	obj_data first = {}, copy = {}, unrelated = {};
	indexes[0].virtual_number = 42001;
	indexes[1].virtual_number = 42002;
	first.obj_uid = 101;
	copy.obj_uid = 102;
	unrelated.obj_uid = 103;
	unrelated.R_num = 1;
	for (P_obj object : { &first, &copy, &unrelated })
	{
		object->extra_flags = ITEM_ARTIFACT;
		object->loc_p = LOC_WORN;
		object->loc.wearing = &actor;
	}
	actor.equipment[0] = &first;
	actor.equipment[1] = &unrelated;
	if (duplicate)
		actor.equipment[2] = &copy;
	else
	{
		copy.loc.wearing = &member;
		member.equipment[0] = &copy;
	}
	online = { &actor, &member, &last };
	rows[42001] = { NOW + 100, -1, 0, duplicate ? 42 : 43 };
	rows[42002] = { NOW + 200 };
	critical_operation_id parent = {};
	assert(critical_operation_id_generate(&parent));
	const bool submitted = artifact_guild_transaction_submit(&actor, parent, 4, EPIC_BOON);
	const bool isolated = submitted && rows.at(42001).timer == NOW + 100 &&
			      rows.at(42002).timer == NOW + 3800 && guild->get_prestige() == 105 &&
			      guild->get_construction() == 1 && snapshots.size() == 1 &&
			      guild_snapshots.size() == 1 && commands.size() == 1;
	printf("%s identity contract: submitted=%d conflicted_feed=%lld unrelated_feed=%lld "
	       "prestige=%lu construction=%lu\n",
	       duplicate ? "duplicate" : "cross-player", submitted,
	       static_cast<long long>(rows.at(42001).timer - NOW - 100),
	       static_cast<long long>(rows.at(42002).timer - NOW - 200), guild->get_prestige(),
	       guild->get_construction());
	// Reserve 2 for a completed but unmet contract; harness failures stay fatal.
	return isolated ? 0 : 2;
}

int main(int argc, char **argv)
{
	if (argc == 2)
	{
		assert(std::string(argv[1]) == "duplicate" ||
		       std::string(argv[1]) == "cross-player");
		return identity_contract(std::string(argv[1]) == "duplicate");
	}
	char_data ch = {}, second = {}, third = {};
	pc_only_data pc = {}, pc2 = {}, pc3 = {};
	ch.only.pc = &pc;
	second.only.pc = &pc2;
	third.only.pc = &pc3;
	pc.pid = 42;
	pc2.pid = 43;
	pc3.pid = 44;
	ch.player.level = second.player.level = third.player.level = 51;
	obj_data artifact = {};
	artifact.extra_flags = ITEM_ARTIFACT;
	artifact.R_num = 0;
	indexes[0].virtual_number = 42001;
	ch.equipment[0] = &artifact;

	reset();
	rows[42001] = { NOW + 100 };
	for (int i = 1; i <= 3; ++i)
	{
		award(&ch);
		assert(rows.at(42001).timer == NOW + 100 + i * 3600);
		assert(snapshots.size() == static_cast<size_t>(i));
	}
	assert(commands.size() == 3);
	const auto messages = feedback.size();
	rows.at(42001).owner = 77;
	rows.at(42001).soul = 88;
	rows.at(42001).timer = NOW + 50;
	for (const auto &command : commands)
		complete(command);
	assert(rows.at(42001).owner == 77 && rows.at(42001).soul == 88 &&
	       rows.at(42001).timer == NOW + 50);
	assert(feedback.size() == messages && snapshots.size() == 3);
	puts("PASS uncapped burst visible before completion; late/duplicate delivery preserves newer state and feedback");

	reset();
	rows[42001] = { FEED_CAP - 30 };
	const auto parent = award(&ch);
	assert(rows.at(42001).timer == FEED_CAP);
	assert(artifact_guild_transaction_submit(&ch, parent, 4, EPIC_BOON));
	assert(snapshots.size() == 1 && commands.size() == 1 && feedback.size() == 1);
	award(&ch);
	assert(rows.at(42001).timer == FEED_CAP && commands.size() == 2);
	rows.at(42001).timer = FEED_CAP + 200;
	award(&ch);
	assert(rows.at(42001).timer == FEED_CAP);
	rows.erase(42001);
	for (const auto &command : commands)
		complete(command);
	assert(rows.empty());
	rows[42001] = { NOW + 10, 44, 17, 44 };
	for (const auto &command : commands)
		complete(command);
	assert(rows.at(42001).timer == NOW + 10 && rows.at(42001).soul == 44);
	puts("PASS at/below/above cap, pending identity attachment, removal and recreation");

	reset();
	char name[] = "Fixture";
	// Guild destruction means in-game deletion; fixture objects live to process exit.
	auto *guild = new Guild(name, RACEWAR_GOOD, 7, 85, 0, 0, 0);
	group_list group[3] = { { &ch, &group[1] }, { &second, &group[2] }, { &third, nullptr } };
	for (auto *actor : { &ch, &second, &third })
	{
		actor->group = group;
		actor->in_room = 1;
		actor->specials.guild = guild;
	}
	rows[42001] = { NOW + 100 };
	size_t n = 0;
	for (auto *actor : { &ch, &second, &third })
	{
		award(actor);
		++n;
		assert(guild->get_prestige() == 85 + n * 10);
		assert(guild->get_construction() == (n >= 2 ? 1u : 0u));
		assert(guild_snapshots.back().first == guild->get_prestige());
		assert(guild_snapshots.back().second == guild->get_construction());
	}
	assert(snapshots.size() == 1); // worn artifact and guild eligibility are independent
	guild->sub_prestige(50);
	guild->set_construction(7);
	for (const auto &command : commands)
		complete(command);
	assert(guild->get_prestige() == 65 && guild->get_construction() == 7);
	auto *other = new Guild(name, RACEWAR_GOOD, 8, 90, 0, 0, 0);
	third.specials.guild = other;
	const auto count = commands.size();
	award(&third); // insufficient same-guild group
	assert(commands.size() == count && other->get_prestige() == 90);
	// A complete group in a different guild changes only its own totals.
	const auto first_guild_prestige = guild->get_prestige();
	ch.specials.guild = second.specials.guild = other;
	award(&third);
	assert(other->get_prestige() == 100 && other->get_construction() == 1);
	assert(guild->get_prestige() == first_guild_prestige);
	ch.specials.guild = second.specials.guild = third.specials.guild = nullptr;
	puts("PASS multiple same-guild participants, cumulative construction, mixed rewards and later spending");

	reset();
	rows[42001] = { NOW + 100, 99 };
	award(&ch, 4, EPIC_PVP);
	assert(commands.empty());
	rows.at(42001).soul = 42;
	award(&ch, 4, EPIC_PVP);
	assert(rows.at(42001).timer == NOW + 100 + 28800);
	rows.at(42001).soul = -1;
	recent_frag = true;
	difficulty = 2;
	award(&ch);
	assert(rows.at(42001).timer == NOW + 100 + 28800 + 10800);
	ch.player.level = 62;
	const auto before = commands.size();
	award(&ch);
	assert(commands.size() == before);
	ch.player.level = 51;
	ch.equipment[0] = nullptr;
	award(&ch);
	assert(commands.size() == before);
	ch.equipment[0] = &artifact;
	puts("PASS trusted/unworn and PvP soul eligibility; source, difficulty and recent-frag modifiers");

	reset();
	rows[42001] = { NOW + 100 };
	ch.specials.guild = second.specials.guild = third.specials.guild = guild;
	critical_operation_id bad_parent = {};
	assert(critical_operation_id_generate(&bad_parent));
	const auto prestige = guild->get_prestige();
	assert(!artifact_guild_transaction_submit(&ch, bad_parent, INT_MAX, EPIC_BOON));
	assert(guild->get_prestige() == prestige && rows.at(42001).timer == NOW + 100 &&
	       commands.empty());
	ch.specials.guild = second.specials.guild = third.specials.guild = nullptr;
#if !LEGACY_HYDRATION
	admission = critical_submit_result::overloaded;
	award(&ch);
	assert(rows.at(42001).timer == NOW + 3700 && commands.empty());
	assert(artifact_guild_transaction_health_copy().pending == 1);
	admission = critical_submit_result::accepted;
	artifact_guild_transaction_pulse();
	assert(commands.size() == 1 && rows.at(42001).timer == NOW + 3700);
	complete(commands.front());
	assert(artifact_guild_transaction_health_copy().pending == 0);
	reset();
	rows[42001] = { FEED_CAP };
	for (size_t i = 0; i < ARTIFACT_GUILD_PENDING_MAX + 1; ++i)
		award(&ch);
	const auto health = artifact_guild_transaction_health_copy();
	assert(health.pending == ARTIFACT_GUILD_PENDING_MAX && health.history_lost == 1);
	assert(health.live_applied == ARTIFACT_GUILD_PENDING_MAX + 1);
	assert(feedback.size() == ARTIFACT_GUILD_PENDING_MAX + 1 &&
	       rows.at(42001).timer == FEED_CAP);

	// Real stone publication reaches real artifact capture/application. The
	// coordinator fixture retains no completed IDs: the source's own guards must
	// prevent duplicate completion/reconnect from granting anything again.
	reset();
	zone_touch_transaction_reset_for_tests();
	online = { &ch };
	obj_data second_artifact = artifact;
	second_artifact.R_num = 1;
	indexes[1].virtual_number = 42002;
	second.equipment[0] = &second_artifact;
	rows[42001] = { NOW + 100 };
	rows[42002] = { NOW + 200 };
	zone_touch_payload touch = {};
	touch.zone_number = 77;
	touch.toucher_pid = 42;
	touch.group_size = 2;
	touch.participant_pids[0] = 42;
	touch.participant_pids[1] = 43;
	touch.stone_uid = 99;
	touch.awards[0] = { 4, 77, 0 };
	touch.awards[1] = { 8, 0, 0 };
	assert(zone_touch_transaction_submit(touch));
	const critical_command parent_stone = commands.back();
	zone_touch_result touch_result(touch);
	std::array<uint8_t, ZONE_TOUCH_RESULT_BYTES> touch_bytes;
	assert(zone_touch_command_encode_result(touch_result, &touch_bytes));
	critical_completion touch_completion = {};
	touch_completion.operation_id = parent_stone.operation_id;
	touch_completion.outcome = critical_apply_outcome::applied;
	touch_completion.result_size = touch_bytes.size();
	std::copy(touch_bytes.begin(), touch_bytes.end(), touch_completion.result_payload.begin());
	zone_touch_transaction_handle_completions(&touch_completion, 1);
	assert(stone_consumed == 1 && stone_feedback == 1);
	assert(rows.at(42001).timer == NOW + 14500 && rows.at(42002).timer == NOW + 200);
	assert(snapshots.size() == 1 && commands.size() == 2);
	complete(commands.back());
	assert(artifact_guild_transaction_health_copy().pending == 0);
	zone_touch_transaction_handle_completions(&touch_completion, 1);
	zone_touch_transaction_player_ready(&ch);
	assert(snapshots.size() == 1 && stone_feedback == 1);
	online.push_back(&second);
	zone_touch_transaction_player_ready(&second);
	assert(rows.at(42002).timer == NOW + 29000 && snapshots.size() == 2);
	critical_command epic_award;
	assert(zone_touch_award_command(parent_stone, 1, &epic_award));
	artifact_guild_payload history;
	assert(artifact_guild_command_decode_payload(commands.back(), &history));
	assert(history.parent_operation_id.bytes == epic_award.operation_id.bytes);
	complete(commands.back());
	zone_touch_transaction_handle_completions(&touch_completion, 1);
	zone_touch_transaction_player_ready(&second);
	assert(snapshots.size() == 2 && stone_feedback == 2 && pc.epics == 4 && pc2.epics == 8);
	assert(artifact_guild_transaction_health_copy().live_applied == 2);
	assert(zone_touch_transaction_submit(touch));
	touch_completion.operation_id = commands.back().operation_id;
	touch_result.recovered_claim = true;
	assert(zone_touch_command_encode_result(touch_result, &touch_bytes));
	std::copy(touch_bytes.begin(), touch_bytes.end(), touch_completion.result_payload.begin());
	zone_touch_transaction_handle_completions(&touch_completion, 1);
	zone_touch_transaction_player_ready(&second);
	assert(stone_consumed == 2 && stone_feedback == 2 && snapshots.size() == 2);
	puts("PASS actual stone producer: offline return, derived parent identity, duplicate completion and recovered claim");
#endif
	puts("PASS invalid combined arithmetic is atomic; history refusal/retry and exhaustion do not undo live rewards");
}
