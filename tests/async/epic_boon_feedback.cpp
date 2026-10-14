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

P_room world = nullptr;
zone_data *zone_table = nullptr;
P_index mob_index = nullptr;
Skill skills[MAX_SKILLS] = {};
long new_exp_table[MAXLVL + 2] = {};
int errand_notch = 100000;
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
static std::vector<critical_command> commands;
static int artifact_awards = 0, dirty = 0, experience = 0;

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
	return pid == 42 ? &actor : nullptr;
}
void mark_player_dirty_components(int, player_component_mask_t)
{
	++dirty;
}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	commands.push_back(std::move(command));
	return refuse_history ? critical_submit_result::unavailable :
				critical_submit_result::accepted;
}
bool artifact_guild_transaction_submit(P_char, const critical_operation_id &, int amount, int type)
{
	assert(amount == 4 && type == EPIC_BOON);
	++artifact_awards;
	return true;
}
persistence_mode persistence_mode_get()
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
const char *persistence_mode_flatfile_root()
{
	return nullptr;
}
flatfile_boon_result flatfile_boon_acknowledge_reward(const std::string &,
						      const critical_operation_id &, std::string *)
{
	std::abort();
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

static void publication_case(int level, int type, int failure)
{
	boon_reward_transaction_reset_for_tests();
	actor = {};
	pc = {};
	gain_tag = {};
	actor.only.pc = &pc;
	pc.pid = 42;
	pc.epics = failure == 2 ? std::numeric_limits<int64_t>::max() : 100;
	const auto initial = pc.epics;
	actor.player.name = const_cast<char *>("Boonfixture");
	actor.player.level = level;
	actor.player.racewar = RACEWAR_GOOD;
	actor.in_room = NOWHERE;
	SET_POS(&actor, POS_STANDING + STAT_NORMAL);
	fail_id = refuse_history = false;
	feedback.clear();
	commands.clear();
	artifact_awards = dirty = experience = 0;
	assert(boon_reward_transaction_submit(&actor, nullptr, 1, BOPT_LEVEL));
	assert(commands.size() == 1 && boon_reward_transaction_health_copy().pending == 1);
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

int main()
{
	for (int level : { 1, 29, 30, 49, 50, 56 })
		for (int failure : { 0, 1, 2, 3 })
		{
			publication_case(level, BTYPE_EPIC, failure);
			publication_case(level, BTYPE_EXP, failure);
		}
	puts("PASS real boon completion -> all-level award result; ID/overflow failure, ledger refusal, non-epic rewards and replay");
}
