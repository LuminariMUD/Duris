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
#include "economy/currency_transaction.h"
#include "economy/nexus_stones.h"
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
static bool online = true;
static int nested_submissions = 0;
static bool admissions_open = true;

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
	return true;
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
	std::abort();
	return 0;
}
P_obj read_object(int, int)
{
	std::abort();
}
bool obj_to_char(P_obj, P_char)
{
	std::abort();
	return true;
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

static void sql_offline_rewards()
{
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

int main()
{
	for (int level : { 1, 29, 30, 49, 50, 56 })
		for (int failure : { 0, 1, 2, 3 })
		{
			publication_case(level, BTYPE_EPIC, failure);
			publication_case(level, BTYPE_EXP, failure);
		}
	sql_offline_rewards();
	ordered_offline_rewards();
	checkpoint_free_outbox();
	nested_publication_case();
	puts("PASS boon rewards: all-level awards, admission closure, accepted reward delivery, reconnect, retries and nested submissions");
}
