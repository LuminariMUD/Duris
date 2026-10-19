// Actual teacher command, purchase callback and epic balance transaction.
// Cash/save/display adapters observe charges and publication order. The full-server
// journey verifies the real HP rebuild, client packets and restart durability.
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "cmd/interp.h"
#include "magic/spells.h"
#include "classes/epic_skills.h"
#include "world/epic.h"
#include "world/epic_transaction.h"
#include "persistence/persistence_checkpoint.h"
#include "net/gmcp.h"
#include <cassert>
#include <cstdarg>
#include <string>
#include <vector>

index_data indexes[1] = {};
P_index mob_index = indexes;
Skill skills[MAX_SKILLS] = {};
struct race_names race_names_table[LAST_RACE + 1] = {};
static char_data pupil = {}, teacher = {};
static pc_only_data pc = {};
static npc_only_data npc = {};
static int minimum = 30;
static int cash_charges = 0, saves = 0, waits = 0, refreshes = 0, vitals = 0;
static int refreshed_at_save = 0, refreshed_at_vitals = 0;
static std::string feedback;
static std::vector<critical_command> ledger;

float get_property(const char *key, double fallback)
{
	return std::string(key) == "epic.skills.minLevel" ? minimum : fallback;
}
int get_property(const char *key, int fallback)
{
	// TRAINING_PROPERTIES
	return fallback;
}
int GET_CHAR_SKILL_P(P_char ch, int skill)
{
	return ch->only.pc->skills[skill].learned;
}
int SUB_MONEY(P_char ch, int amount, int mode)
{
	assert(mode == 0 && amount > 0 && GET_MONEY(ch) >= amount);
	++cash_charges;
	ch->points.cash[0] -= amount;
	return 0;
}
char *coin_stringv(int, int)
{
	static char text[] = "fixture coins";
	return text;
}
// These cases submit a full skill name, never the informational quote page.
void CAP(char *)
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
char affect_total(P_char ch, int)
{
	assert(ch == &pupil && pc.skills[SKILL_TOUGHNESS].learned > 0);
	++refreshes;
	return true;
}
void gmcp_char_vitals(P_char ch)
{
	assert(ch == &pupil);
	refreshed_at_vitals = refreshes;
	++vitals;
}
bool do_save_silent(P_char ch, int)
{
	assert(ch == &pupil);
	refreshed_at_save = refreshes;
	++saves;
	return true;
}
void CharWait(P_char ch, int)
{
	assert(ch == &pupil);
	++waits;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	ledger.push_back(std::move(command));
	return critical_submit_result::accepted;
}

// PRODUCTION

static void reset(int level, int learned = 0, int teacher_vnum = 80862)
{
	pupil = {};
	teacher = {};
	pc = {};
	npc = {};
	pupil.only.pc = &pc;
	teacher.only.npc = &npc;
	pc.pid = 42;
	pc.epics = 10000;
	pc.skills[SKILL_TOUGHNESS].learned = pc.skills[SKILL_TOUGHNESS].taught = learned;
	pupil.player.level = level;
	pupil.player.m_class = CLASS_WARRIOR;
	pupil.player.race = RACE_HUMAN;
	SET_POS(&pupil, POS_STANDING + STAT_NORMAL);
	pupil.player.name = const_cast<char *>("Trainfixture");
	pupil.points.cash[0] = 10000000;
	teacher.specials.act = ACT_ISNPC;
	indexes[0].virtual_number = teacher_vnum;
	cash_charges = saves = waits = refreshes = vitals = 0;
	refreshed_at_save = refreshed_at_vitals = 0;
	feedback.clear();
	ledger.clear();
}
static void practice(const char *skill = "toughness")
{
	assert(epic_teacher(&teacher, &pupil, CMD_PRACTICE, const_cast<char *>(skill)));
}
static void unchanged(int learned = 0)
{
	assert(pc.epics == 10000 && GET_MONEY(&pupil) == 10000000);
	assert(pc.skills[SKILL_TOUGHNESS].learned == learned);
	assert(!cash_charges && !saves && !waits && !refreshes && !vitals && ledger.empty());
}
static void bought(int before, int learned)
{
	const int multiplier = 1 + before / 30;
	assert(pc.epics == 10000 - 150 * multiplier);
	assert(GET_MONEY(&pupil) == 10000000 - 1000000 * multiplier);
	assert(pc.skills[SKILL_TOUGHNESS].learned == learned &&
	       pc.skills[SKILL_TOUGHNESS].taught == learned);
	assert(cash_charges == 1 && saves == 1 && waits == 1 && ledger.size() == 1);
}
static void documented_cost(int skill, const char *name, int first_epics, int first_plat,
			    int total_epics, int total_plat)
{
	epic_teacher_skill *entry = epic_teachers;
	while (entry->vnum && entry->skill != skill)
		++entry;
	assert(entry->vnum);
	epic_reward *reward = epic_rewards;
	while (reward->type && reward->value != skill)
		++reward;
	assert(reward->type);
	skills[skill].name = const_cast<char *>(name);
	int charged_epics = 0, charged_coins = 0;
	for (int learned = 0; learned < 100; learned += get_property("epic.skillGain", 10))
	{
		reset(30, 0, entry->vnum);
		pupil.player.m_class = reward->classes ? reward->classes & (~reward->classes + 1) :
							 CLASS_WARRIOR;
		pc.skills[SKILL_TOUGHNESS].learned = 100;
		pc.skills[skill].learned = pc.skills[skill].taught = learned;
		if (entry->pre_requisite)
			pc.skills[entry->pre_requisite].learned = 100;
		pc.epics = 1000000;
		pupil.points.cash[0] = 1000000000;
		practice(name);
		assert(ledger.size() == 1 && cash_charges == 1);
		const int epics = 1000000 - pc.epics;
		const int coins = 1000000000 - GET_MONEY(&pupil);
		if (learned == 0)
			assert(epics == first_epics && (coins + 999) / 1000 == first_plat);
		charged_epics += epics;
		charged_coins += coins;
	}
	if (charged_epics != total_epics || (charged_coins + 999) / 1000 != total_plat)
		fprintf(stderr, "%s: charged %d epics, %d plat; help says %d epics, %d plat\n",
			name, charged_epics, (charged_coins + 999) / 1000, total_epics, total_plat);
	assert(charged_epics == total_epics && (charged_coins + 999) / 1000 == total_plat);
}
int main(int argc, char **argv)
{
	assert(argc == 2);
	skills[SKILL_TOUGHNESS].name = const_cast<char *>("toughness");
	skills[SKILL_ANATOMY].name = const_cast<char *>("anatomy");
	skills[SKILL_IMPROVED_LISTEN].name = const_cast<char *>("improved listen");
	skills[SKILL_LISTEN].name = const_cast<char *>("listen");
	const std::string mode = argv[1];
	if (mode == "boundaries")
	{
		for (int gate : { 30, 40 })
		{
			minimum = gate;
			reset(gate - 1);
			practice();
			unchanged();
			assert(feedback.find("reach level " + std::to_string(gate)) !=
			       std::string::npos);
			for (int level : { gate, gate + 1 })
			{
				reset(level);
				practice();
				bought(0, 10);
			}
		}
		minimum = 30;
		reset(30, 0, 19141);
		pupil.player.m_class = CLASS_NECROMANCER;
		practice("anatomy");
		unchanged();
		assert(feedback.find("people of your class") != std::string::npos);
		reset(30, 0, 27035);
		pupil.player.m_class = CLASS_ROGUE;
		pc.skills[SKILL_LISTEN].learned = 79;
		practice("improved listen");
		unchanged();
		assert(feedback.find("not yet mastered") != std::string::npos);
		reset(30);
		pc.epics = 149;
		practice();
		assert(pc.epics == 149 && GET_MONEY(&pupil) == 10000000 && !cash_charges && !saves);
		reset(30);
		pupil.points.cash[0] = 999999;
		practice();
		assert(pc.epics == 10000 && GET_MONEY(&pupil) == 999999 && !cash_charges && !saves);
		for (auto *entry = epic_teachers; entry->vnum; ++entry)
			if (entry->vnum == 80862)
			{
				const int maximum = entry->max;
				entry->max = 50;
				reset(30, 50);
				practice();
				unchanged(50);
				assert(feedback.find("cannot teach you anything more") !=
				       std::string::npos);
				entry->max = maximum;
			}
	}
	else if (mode == "mastery")
	{
		reset(30, 80);
		practice();
		bought(80, 90);
		assert(feedback.find("improve your mastery") != std::string::npos);
		assert(feedback.find("You have mastered") == std::string::npos);
		reset(30, 95);
		practice();
		bought(95, 100);
		assert(feedback.find("You have mastered") != std::string::npos);
		assert(feedback.find("improve your mastery") == std::string::npos);
		reset(30, 100);
		practice();
		unchanged(100);
		assert(feedback.find("already mastered this skill") != std::string::npos);
	}
	else if (mode == "costs")
	{
		// DOCUMENTED_COSTS
	}
	else
	{
		assert(mode == "refresh");
		reset(30);
		practice();
		bought(0, 10);
		assert(refreshes == 1 && refreshed_at_save == 1);
		assert(vitals == 1 && refreshed_at_vitals == 1);
	}
	printf("PASS real epic teacher: %s\n", mode.c_str());
}
