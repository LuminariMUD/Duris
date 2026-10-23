// Actual boon completion, award preparation/publication and epic balance mutation.
// SQL outcomes, unrelated reward kinds and bonus/achievement services are adapters.
#include "core/utils.h"
#include "core/prototypes.h"
#include "magic/spells.h"
#include "world/epic.h"
#include "world/epic_bonus.h"
#include "world/epic_transaction.h"
#include "world/achievements.h"
#include "world/difficulty.h"
#include "economy/boon.h"
#include "economy/boon_reward_transaction.h"
#include "economy/boon_shop_transaction.h"
#include "economy/currency_transaction.h"
#include "economy/nexus_stones.h"
#include "flatfile/flatfile_boon_repository.h"
#include "persistence/persistence_mode.h"
#include "persistence/persistence_checkpoint.h"
#include "guild/artifact_guild_transaction.h"
#include <cassert>
#include <cerrno>
#include <limits>
#include <sys/random.h>
#include <cstdarg>
#include <string>
#include <vector>
#include <filesystem>

P_room world = nullptr;
zone_data *zone_table = nullptr;
P_index mob_index = nullptr;
Skill skills[MAX_SKILLS] = {};
long new_exp_table[MAXLVL + 2] = {};
int errand_notch = 100000;
extern const attr_names_struct attr_names[MAX_ATTRIBUTES] = { { "", "" }, { "str", "strength" } };
static bool fail_id = false, refuse_history = false;
extern "C" ssize_t __real_getrandom(void *, size_t, unsigned int);
extern "C" ssize_t __wrap_getrandom(void *buf, size_t size, unsigned int flags)
{
	if (fail_id)
	{
		errno = EIO;
		return -1;
	}
	return __real_getrandom(buf, size, flags);
}
static char_data actor = {};
static pc_only_data pc = {};
static affected_type gain_tag = {};
static std::string feedback;
static std::vector<std::string> retained_alerts;
void persistence_alert(int, const char *, const char *, const char *, const char *,
		       const char *reason, const char *, ...)
{
	retained_alerts.emplace_back(reason);
}
static std::vector<critical_command> commands;
static int artifact_awards = 0, dirty = 0, experience = 0;
static std::string flat_root;
static bool online = true, fail_acknowledgement = false;
static int nested_submissions = 0;
static bool admissions_open = true;
static bool shop_completion = false;

bool divine_boon_legacy_admissions_allowed()
{
	return admissions_open;
}

float get_property(const char *, double fallback)
{
	return fallback;
}
int get_property(const char *, int fallback)
{
	return fallback;
}
double difficulty_multiplier(difficulty_dial)
{
	return 1.0;
}
bool has_epic_task(P_char)
{
	return false;
}
int check_nexus_bonus(P_char, int value, int)
{
	return value;
}
float get_epic_bonus(P_char, int)
{
	return 0;
}
void epic_bonus_record_gain(P_char, int, int) {}
void epiclog(int, const char *, ...) {}
void epic_free_level(P_char) {}
void epic_choose_new_epic_task(P_char)
{
	std::abort();
}
affected_type *get_spell_from_char(P_char, int, void *, int)
{
	return &gain_tag;
}
affected_type *apply_achievement(P_char, int)
{
	std::abort();
}
bool gameplay_read_state_add_completed_zone(gameplay_read_state *, int32_t)
{
	std::abort();
}
void send_to_char(const char *text, P_char)
{
	feedback += text;
}
void send_to_char_f(P_char, const char *format, ...)
{
	char text[1024];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	feedback += text;
}
P_char find_player_by_pid(int pid)
{
	return online && pid == 42 ? &actor : nullptr;
}
void mark_player_dirty_components(int, player_component_mask_t)
{
	++dirty;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	command.accepted_at_usec = commands.size() + 1;
	assert(critical_command_normalize(&command));
	commands.push_back(std::move(command));
	return refuse_history ? critical_submit_result::unavailable :
				critical_submit_result::accepted;
}
bool artifact_guild_transaction_submit(P_char, const critical_operation_id &, int amount, int type)
{
	assert(amount == 4 && type == EPIC_BOON);
	++artifact_awards;
	while (nested_submissions > 0)
	{
		--nested_submissions;
		assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	}
	if (fail_acknowledgement)
	{
		fail_acknowledgement = false;
		std::filesystem::rename(flat_root + "/domains", flat_root + "/unavailable");
	}
	return true;
}
persistence_mode persistence_mode_get()
{
	return flat_root.empty() ? PERSISTENCE_MODE_MARIADB_PRIMARY :
				   PERSISTENCE_MODE_FLATFILE_PRIMARY;
}
const char *persistence_mode_flatfile_root()
{
	return flat_root.empty() ? nullptr : flat_root.c_str();
}
int gain_exp(P_char, P_char, int amount, int)
{
	experience += amount;
	return amount;
}
bool currency_transaction_submit_bank_reward(P_char, int64_t, currency_reason_type, int64_t,
					     critical_source_site, critical_deadline_class,
					     currency_completion_fn, const void *, size_t)
{
	std::abort();
}
struct cash_boon_context
{
	int boon_id;
	int cash;
};
static void cash_boon_committed(P_char, bool, const currency_command_result &, unsigned int,
				const uint8_t *, size_t)
{
	std::abort();
}
void advance_level(P_char)
{
	std::abort();
}
void affect_to_char_with_messages(P_char, affected_type *, const char *, const char *)
{
	std::abort();
}
char affect_total(P_char, int)
{
	assert(shop_completion);
	return 0;
}
P_obj read_object(int, int)
{
	std::abort();
}
void obj_to_char(P_obj, P_char)
{
	std::abort();
}

// EPIC_AWARD_FUNCTIONS
// BOON_PUBLICATION

static void reset_actor(int level, int64_t epics)
{
	boon_reward_transaction_reset_for_tests();
	actor = {};
	pc = {};
	gain_tag = {};
	actor.only.pc = &pc;
	pc.pid = 42;
	pc.epics = epics;
	actor.player.name = const_cast<char *>("Boonfixture");
	actor.player.level = level;
	actor.player.racewar = RACEWAR_GOOD;
	actor.in_room = NOWHERE;
	SET_POS(&actor, POS_STANDING + STAT_NORMAL);
	fail_id = refuse_history = false;
	feedback.clear();
	retained_alerts.clear();
	commands.clear();
	artifact_awards = dirty = experience = 0;
	online = true;
	fail_acknowledgement = false;
	nested_submissions = 0;
	admissions_open = true;
}

static void publication_case(int level, int type, int failure)
{
	reset_actor(level, failure == 2 ? std::numeric_limits<int64_t>::max() : 100);
	const auto initial = pc.epics;
	assert(boon_reward_transaction_submit(&actor, nullptr, 1, BOPT_LEVEL));
	assert(commands.size() == 1 && boon_reward_transaction_health_copy().pending == 1);
	admissions_open = false;
	assert(!boon_reward_transaction_submit(&actor, nullptr, 1, BOPT_LEVEL));
	assert(commands.size() == 1); // Closing admission preserves the accepted completion.
	const auto parent = commands.front().operation_id;
	boon_reward_result result = {};
	result.pid = 42;
	result.entry_count = 1;
	result.entries[0].boon_id = 7;
	result.entries[0].type = type;
	result.entries[0].flags = BOON_RESULT_COMPLETED;
	result.entries[0].bonus = 4;
	std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
	assert(boon_reward_command_encode_result(result, &bytes));
	critical_completion completion = {};
	completion.operation_id = parent;
	completion.outcome = critical_apply_outcome::applied;
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	fail_id = failure == 1;
	refuse_history = failure == 3;
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(feedback.find("completed boon # 7") != std::string::npos);
	assert(boon_reward_transaction_health_copy().pending == 0 &&
	       boon_reward_transaction_health_copy().committed == 1);
	const bool rewarded = type == BTYPE_EPIC && failure != 1 && failure != 2;
	assert(pc.epics == initial + (rewarded ? 4 : 0));
	assert(pc.epic_revision == (rewarded ? 1 : 0));
	assert(artifact_awards == rewarded && dirty == rewarded);
	assert(experience == (type == BTYPE_EXP ? 4 : 0));
	assert((feedback.find("You have gained 4 epic points") != std::string::npos) == rewarded);
	if (type == BTYPE_EPIC && !rewarded)
	{
		assert(feedback.find("No epic points were awarded") != std::string::npos);
		assert(feedback.find("must be level") == std::string::npos);
	}
	else
		assert(feedback.find("No epic points were awarded") == std::string::npos);
	// Completion stays consumed even after a failed award becomes possible again.
	const auto prior_messages = feedback;
	const auto prior_commands = commands.size();
	fail_id = refuse_history = false;
	completion.outcome = critical_apply_outcome::already_applied;
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(feedback == prior_messages && commands.size() == prior_commands);
	assert(pc.epics == initial + (rewarded ? 4 : 0) && artifact_awards == rewarded);
}

static void flat_publication_case(const std::string &root, int ordering, bool fail_ack)
{
	reset_actor(20, 100);
	flat_root = root;
	std::filesystem::create_directories(flat_root + "/domains");
	std::filesystem::permissions(flat_root, std::filesystem::perms::owner_all);
	std::filesystem::permissions(flat_root + "/domains", std::filesystem::perms::owner_all);
	flatfile_boon_definition definition;
	definition.id = 7;
	definition.type = BTYPE_EPIC;
	definition.option = BOPT_LEVEL;
	definition.criteria = 20;
	definition.bonus = 4;
	definition.active = true;
	definition.author = "test";
	std::string error;
	assert(flatfile_boon_establish(flat_root, { definition }, &error) ==
	       flatfile_boon_result::ok);
	assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	const auto command = commands.front();
	const auto applied = flatfile_boon_repository_apply(flat_root, command);
	assert(applied.outcome == critical_apply_outcome::applied);
	admissions_open = false;
	assert(!boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	critical_completion completion = {};
	completion.operation_id = command.operation_id;
	completion.outcome = applied.outcome;
	completion.result_size = applied.result_size;
	completion.result_payload = applied.result_payload;
	fail_acknowledgement = fail_ack;
	if (ordering == 0)
	{
		// Login sees the durable receipt while the live completion is outstanding.
		boon_reward_transaction_player_ready(&actor);
		assert(pc.epics == 104 && artifact_awards == 1);
	}
	else if (ordering == 1)
		online = false; // Completion drains while the player is disconnected.
	else if (ordering == 2)
		boon_reward_transaction_reset_for_tests(); // Recovery after a process restart.
	boon_reward_transaction_handle_completions(&completion, 1);
	online = true;
	if (ordering != 0)
		boon_reward_transaction_player_ready(&actor);

	const bool known = ordering != 2;
	assert(pc.epics == (known ? 104 : 100) && artifact_awards == known && dirty == known);
	if (fail_ack && known)
		std::filesystem::rename(flat_root + "/unavailable", flat_root + "/domains");
	const auto messages = feedback;
	for (int repeat = 0; repeat < 2; ++repeat)
	{
		boon_reward_transaction_player_ready(&actor);
		completion.outcome = critical_apply_outcome::already_applied;
		boon_reward_transaction_handle_completions(&completion, 1);
	}
	assert(pc.epics == (known ? 104 : 100) && artifact_awards == known && dirty == known);
	if (known)
	{
		assert(feedback == messages &&
		       feedback.find("completed boon # 7") != std::string::npos);
		assert(boon_reward_transaction_health_copy().pending == 0);
	}
	else
	{
		assert(feedback.find("retained for staff reconciliation") != std::string::npos);
		assert(feedback.find("completed boon # 7") == std::string::npos);
	}
	// No old receipt is acknowledged without a saved recipient watermark.
	flatfile_boon_pending_reward reward;
	assert(flatfile_boon_find_pending_reward(flat_root, 42, &reward, &error) ==
	       flatfile_boon_result::ok);
	critical_outbox_record outbox = {};
	outbox.destination = 8;
	outbox.event_type = 1;
	outbox.payload_version = 1;
	outbox.payload.assign(applied.result_payload.begin(),
			      applied.result_payload.begin() + applied.result_size);
	assert(boon_reward_transaction_outbox_delivery(outbox, nullptr) ==
	       critical_outbox_delivery_result::terminal_failure);

	if (known)
	{
		boon_reward_transaction_reset_for_tests();
		boon_reward_transaction_player_ready(&actor);
		assert(pc.epics == 104 && artifact_awards == 1 && dirty == 1);
		assert(feedback.find("retained for staff reconciliation") != std::string::npos);
		assert(flatfile_boon_find_pending_reward(flat_root, 42, &reward, &error) ==
		       flatfile_boon_result::ok);
	}

	flat_root.clear();
}

static void multiple_offline_rewards(const std::string &root)
{
	reset_actor(20, 100);
	flat_root = root;
	std::filesystem::create_directories(root + "/domains");
	std::filesystem::permissions(root, std::filesystem::perms::owner_all);
	std::filesystem::permissions(root + "/domains", std::filesystem::perms::owner_all);
	flatfile_boon_definition definition;
	definition.id = 7;
	definition.type = BTYPE_EPIC;
	definition.option = BOPT_LEVEL;
	definition.criteria = 20;
	definition.bonus = 4;
	definition.active = true;
	definition.repeat = true;
	definition.author = "test";
	std::string error;
	assert(flatfile_boon_establish(root, { definition }, &error) == flatfile_boon_result::ok);
	online = false;
	for (int index = 0; index < 2; ++index)
	{
		assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
		const auto command = commands.back();
		const auto applied = flatfile_boon_repository_apply(root, command);
		assert(applied.outcome == critical_apply_outcome::applied);
		critical_completion completion{};
		completion.operation_id = command.operation_id;
		completion.outcome = applied.outcome;
		completion.result_size = applied.result_size;
		completion.result_payload = applied.result_payload;
		boon_reward_transaction_handle_completions(&completion, 1);
	}
	admissions_open = false;
	online = true;
	boon_reward_transaction_player_ready(&actor);
	assert(pc.epics == 108 && artifact_awards == 2);
	boon_reward_transaction_player_ready(&actor);
	assert(pc.epics == 108 && artifact_awards == 2);
	flat_root.clear();
}
static void sql_offline_rewards()
{
	flat_root.clear();
	for (int type : { BTYPE_EPIC, BTYPE_EXP })
	{
		reset_actor(20, 100);
		online = false;
		std::vector<critical_completion> completions;
		for (int index = 0; index < 2; ++index)
		{
			assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
			boon_reward_result result{};
			result.pid = 42;
			result.entry_count = 1;
			result.entries[0].boon_id = 7;
			result.entries[0].type = type;
			result.entries[0].flags = BOON_RESULT_COMPLETED;
			result.entries[0].bonus = 4;
			std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
			assert(boon_reward_command_encode_result(result, &bytes));
			critical_completion completion{};
			completion.operation_id = commands.back().operation_id;
			completion.outcome = critical_apply_outcome::applied;
			completion.result_size = bytes.size();
			std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
			boon_reward_transaction_handle_completions(&completion, 1);
			completions.push_back(completion);
		}
		assert(pc.epics == 100 && experience == 0 &&
		       boon_reward_transaction_health_copy().pending == 2);
		admissions_open = false;
		online = true;
		boon_reward_transaction_player_ready(&actor);
		assert(pc.epics == (type == BTYPE_EPIC ? 108 : 100));
		assert(experience == (type == BTYPE_EXP ? 8 : 0));
		assert(boon_reward_transaction_health_copy().pending == 0);
		boon_reward_transaction_player_ready(&actor);
		boon_reward_transaction_handle_completions(completions.data(), completions.size());
		assert(pc.epics == (type == BTYPE_EPIC ? 108 : 100));
		assert(experience == (type == BTYPE_EXP ? 8 : 0));
	}
}

static void ordered_offline_rewards()
{
	reset_actor(20, 100);
	flat_root.clear();
	online = false;
	std::vector<critical_completion> completed;
	for (int i = 0; i < 32; ++i)
	{
		assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
		boon_reward_result result{};
		result.pid = 42;
		result.entry_count = 1;
		result.entries[0].boon_id = 100 + i;
		result.entries[0].type = BTYPE_EXP;
		result.entries[0].bonus = 1;
		result.entries[0].flags = BOON_RESULT_COMPLETED;
		std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
		assert(boon_reward_command_encode_result(result, &bytes));
		critical_completion completion{};
		completion.operation_id = commands.back().operation_id;
		completion.outcome = critical_apply_outcome::applied;
		completion.result_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
		completed.push_back(completion);
	}
	std::reverse(completed.begin(), completed.end());
	boon_reward_transaction_handle_completions(completed.data(), completed.size());
	online = true;
	boon_reward_transaction_player_ready(&actor);
	size_t previous = 0;
	for (int id = 131; id >= 100; --id)
	{
		const auto position = feedback.find("completed boon # " + std::to_string(id));
		assert(position != std::string::npos && (id == 131 || position > previous));
		previous = position;
	}
	assert(experience == 32 && boon_reward_transaction_health_copy().pending == 0);
}

static void checkpoint_free_offline(const std::string &root)
{
	for (bool flat : { false, true })
		for (int type : { BTYPE_POINT, BTYPE_STATS, -1, -2 })
		{
			reset_actor(20, 100);
			flat_root.clear();
			if (flat)
			{
				flat_root = root + "/" + std::to_string(type);
				std::filesystem::create_directories(flat_root + "/domains");
				std::filesystem::permissions(flat_root,
							     std::filesystem::perms::owner_all);
				std::filesystem::permissions(flat_root + "/domains",
							     std::filesystem::perms::owner_all);
				flatfile_boon_definition definition;
				definition.id = 7;
				definition.type = type >= 0 ? type : BTYPE_EPIC;
				definition.option = BOPT_LEVEL;
				definition.criteria = type >= 0 ? 20 : 99;
				definition.bonus = 4;
				definition.active = true;
				definition.author = "test";
				std::string error;
				assert(flatfile_boon_establish(flat_root, { definition }, &error) ==
				       flatfile_boon_result::ok);
			}
			assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
			critical_completion completion{};
			completion.operation_id = commands.back().operation_id;
			completion.outcome = critical_apply_outcome::applied;
			if (flat)
			{
				const auto applied =
					flatfile_boon_repository_apply(flat_root, commands.back());
				assert(applied.outcome == critical_apply_outcome::applied);
				completion.result_size = applied.result_size;
				completion.result_payload = applied.result_payload;
			}
			else
			{
				boon_reward_result result{};
				result.pid = 42;
				result.entry_count = type == -2 ? 0 : 1;
				if (result.entry_count)
				{
					result.entries[0].boon_id = 7;
					result.entries[0].type = type < 0 ? BTYPE_EXP : type;
					result.entries[0].flags = type < 0 ? BOON_RESULT_PROGRESS :
									     BOON_RESULT_COMPLETED;
				}
				std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
				assert(boon_reward_command_encode_result(result, &bytes));
				completion.result_size = bytes.size();
				std::copy(bytes.begin(), bytes.end(),
					  completion.result_payload.begin());
			}
			online = false;
			boon_reward_transaction_handle_completions(&completion, 1);
			assert(boon_reward_transaction_health_copy().pending == 0 &&
			       pc.epics == 100 && experience == 0);
			if (flat)
			{
				std::string error;
				flatfile_boon_pending_reward reward;
				assert(flatfile_boon_find_pending_reward(flat_root, 42, &reward,
									 &error) ==
				       flatfile_boon_result::not_found);
				if (type >= 0)
				{
					flatfile_boon_player_projection saved;
					assert(flatfile_boon_load_player(flat_root, 42, &saved,
									 &error) ==
					       flatfile_boon_result::ok);
					assert((type == BTYPE_POINT ? saved.points : saved.stats) ==
					       4);
				}
			}
		}
	flat_root.clear();
}

static void checkpoint_free_online_ack_failure(const std::string &root,
					       bool recipient_online = true)
{
	reset_actor(20, 100);
	flat_root = root;
	std::filesystem::create_directories(root + "/domains");
	std::filesystem::permissions(root, std::filesystem::perms::owner_all);
	std::filesystem::permissions(root + "/domains", std::filesystem::perms::owner_all);
	flatfile_boon_definition definition;
	definition.id = 7;
	definition.type = BTYPE_POINT;
	definition.option = BOPT_LEVEL;
	definition.criteria = 20;
	definition.bonus = 4;
	definition.active = true;
	definition.author = "test";
	std::string error;
	assert(flatfile_boon_establish(root, { definition }, &error) == flatfile_boon_result::ok);
	assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	const auto applied = flatfile_boon_repository_apply(root, commands.back());
	assert(applied.outcome == critical_apply_outcome::applied);
	critical_completion completion{};
	completion.operation_id = commands.back().operation_id;
	completion.outcome = applied.outcome;
	completion.result_size = applied.result_size;
	completion.result_payload = applied.result_payload;
	online = recipient_online;
	std::filesystem::rename(root + "/domains", root + "/unavailable");
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(boon_reward_transaction_health_copy().pending == 1);
	assert(std::find(retained_alerts.begin(), retained_alerts.end(),
			 "checkpoint_free_ack_retained") != retained_alerts.end());
	const auto messages = feedback;
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(feedback == messages && boon_reward_transaction_health_copy().pending == 1);
	std::filesystem::rename(root + "/unavailable", root + "/domains");
	online = true;
	boon_reward_transaction_player_ready(&actor);
	assert(feedback == messages && boon_reward_transaction_health_copy().pending == 0);
	flatfile_boon_pending_reward reward;
	assert(flatfile_boon_find_pending_reward(root, 42, &reward, &error) ==
	       flatfile_boon_result::not_found);
	flat_root.clear();
}

static void checkpoint_free_outbox()
{
	for (int type : { BTYPE_POINT, BTYPE_STATS, BTYPE_EXP })
	{
		boon_reward_result result{};
		result.pid = 42;
		result.entry_count = 1;
		result.entries[0].boon_id = 7;
		result.entries[0].flags = BOON_RESULT_COMPLETED;
		result.entries[0].type = type;
		std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
		assert(boon_reward_command_encode_result(result, &bytes));
		critical_outbox_record record{};
		record.destination = 8;
		record.event_type = 1;
		record.payload_version = 1;
		record.payload.assign(bytes.begin(), bytes.end());
		assert(boon_reward_transaction_outbox_delivery(record, nullptr) ==
		       (type == BTYPE_EXP ? critical_outbox_delivery_result::terminal_failure :
					    critical_outbox_delivery_result::delivered));
	}
	for (unsigned count : { 0U, 1U })
	{
		boon_reward_result result{};
		result.pid = 42;
		result.entry_count = count;
		if (count)
		{
			result.entries[0].boon_id = 7;
			result.entries[0].type = BTYPE_EXP;
			result.entries[0].flags = BOON_RESULT_PROGRESS;
		}
		std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
		assert(boon_reward_command_encode_result(result, &bytes));
		critical_outbox_record record{};
		record.destination = 8;
		record.event_type = 1;
		record.payload_version = 1;
		record.payload.assign(bytes.begin(), bytes.end());
		assert(boon_reward_transaction_outbox_delivery(record, nullptr) ==
		       critical_outbox_delivery_result::delivered);
	}
}

static void flat_published_admission_capacity()
{
	reset_actor(20, 100);
	flat_root = "retained-flat-publication-fixture";
	boon_reward_result result{};
	result.pid = 42;
	result.entry_count = 1;
	result.entries[0].boon_id = 7;
	result.entries[0].type = BTYPE_EPIC;
	result.entries[0].flags = BOON_RESULT_COMPLETED;
	result.entries[0].bonus = 4;
	std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
	assert(boon_reward_command_encode_result(result, &bytes));
	for (size_t i = 0; i < 1100; ++i)
	{
		assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
		critical_completion completion{};
		completion.operation_id = commands.back().operation_id;
		completion.outcome = critical_apply_outcome::applied;
		completion.result_size = bytes.size();
		std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
		boon_reward_transaction_handle_completions(&completion, 1);
		boon_reward_transaction_handle_completions(&completion, 1);
	}
	assert(pc.epics == 4500 && boon_reward_transaction_health_copy().pending == 0);
	// Real outstanding work still obeys the existing admission ceiling.
	for (size_t i = 0; i < BOON_REWARD_PENDING_MAX; ++i)
		assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	assert(!boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	assert(boon_reward_transaction_health_copy().pending == BOON_REWARD_PENDING_MAX);
	flat_root.clear();
}

static void nested_publication_case()
{
	reset_actor(20, 100);
	assert(boon_reward_transaction_submit(&actor, nullptr, 0, BOPT_LEVEL));
	boon_reward_result result = {};
	result.pid = 42;
	result.entry_count = 1;
	result.entries[0].boon_id = 7;
	result.entries[0].type = BTYPE_EPIC;
	result.entries[0].flags = BOON_RESULT_COMPLETED;
	result.entries[0].bonus = 4;
	std::array<uint8_t, BOON_REWARD_RESULT_BYTES> bytes;
	assert(boon_reward_command_encode_result(result, &bytes));
	critical_completion completion = {};
	completion.operation_id = commands.front().operation_id;
	completion.outcome = critical_apply_outcome::applied;
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	nested_submissions = 128; // Award-side level-ups can submit more boon operations.
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(boon_reward_transaction_health_copy().pending == 128);
	const auto messages = feedback;
	boon_reward_transaction_handle_completions(&completion, 1);
	assert(pc.epics == 104 && artifact_awards == 1 && feedback == messages);
	assert(boon_reward_transaction_health_copy().pending == 128);
}

static void legacy_shop_admission_case()
{
	reset_actor(20, 100);
	boon_shop_transaction_reset_for_tests();
	flat_root = "shop-admission-fixture";
	admissions_open = false;
	assert(!boon_shop_transaction_submit(&actor, 0) && commands.empty());
	admissions_open = true;
	assert(boon_shop_transaction_submit(&actor, 0) && commands.size() == 1);
	admissions_open = false;
	assert(!boon_shop_transaction_submit(&actor, 0) && commands.size() == 1);
	const boon_shop_result result = { 42, 0, 51, 1, 1 };
	std::array<uint8_t, BOON_SHOP_RESULT_BYTES> bytes;
	assert(boon_shop_command_encode_result(result, &bytes));
	critical_completion completion = {};
	completion.operation_id = commands.front().operation_id;
	completion.outcome = critical_apply_outcome::applied;
	completion.result_size = bytes.size();
	std::copy(bytes.begin(), bytes.end(), completion.result_payload.begin());
	shop_completion = true;
	boon_shop_transaction_handle_completions(&completion, 1);
	shop_completion = false;
	assert(actor.base_stats.Str == 51 &&
	       feedback.find("strength rises to 51") != std::string::npos);
	const auto prior = feedback;
	boon_shop_transaction_handle_completions(&completion, 1);
	assert(feedback == prior);
	flat_root.clear();
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	for (int level : { 1, 29, 30, 49, 50, 56 })
		for (int failure : { 0, 1, 2, 3 })
		{
			publication_case(level, BTYPE_EPIC, failure);
			publication_case(level, BTYPE_EXP, failure);
		}
	for (int ordering : { 0, 1, 2, 3 })
		for (bool fail_ack : { false, true })
			flat_publication_case(std::string(argv[1]) + "/" +
						      std::to_string(ordering) +
						      (fail_ack ? "-fail" : "-ok"),
					      ordering, fail_ack);
	multiple_offline_rewards(std::string(argv[1]) + "/multiple");
	sql_offline_rewards();
	ordered_offline_rewards();
	checkpoint_free_offline(std::string(argv[1]) + "/checkpoint-free");
	checkpoint_free_outbox();
	checkpoint_free_online_ack_failure(std::string(argv[1]) + "/online-ack-failure");
	checkpoint_free_online_ack_failure(std::string(argv[1]) + "/offline-ack-failure", false);
	flat_published_admission_capacity();
	nested_publication_case();
	legacy_shop_admission_case();
	puts("PASS boon rewards: all-level awards, admission closure, accepted shop/reward delivery, reconnect, retries and nested submissions");
}
