#include "economy/divine_boon_runtime.h"
#include "economy/divine_boon_selection.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "ships/ships.h"
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <new>
#include <string>

extern zone_data *zone_table;
extern int top_of_zone_table;
extern P_desc descriptor_list;

namespace
{
const char *category_name(divine_boon_category category)
{
	switch (category)
	{
	case divine_boon_category::experience:
		return "Zone EXP (200% total base)";
	case divine_boon_category::epic:
		return "Epic stone (+50% base)";
	case divine_boon_category::cargo:
		return "Cargo & contraband (+25% base sale)";
	case divine_boon_category::pvp:
		return "Opposing racewar PvP (+50% base epics)";
	default:
		return "Unknown";
	}
}

constexpr int reward_width = 31;
constexpr int objective_width = 32;
constexpr int remaining_width = 10;

// Category colour belongs to the reward only. Targets retain their native ANSI.
const char *reward_color(divine_boon_category category)
{
	switch (category)
	{
	case divine_boon_category::experience:
		return "&+G";
	case divine_boon_category::epic:
		return "&+M";
	case divine_boon_category::cargo:
		return "&+C";
	case divine_boon_category::pvp:
		return "&+R";
	default:
		return "&+W";
	}
}

const char *reward_label(divine_boon_category category)
{
	switch (category)
	{
	case divine_boon_category::experience:
		return "200% Experience";
	case divine_boon_category::epic:
		return "+50% Epic Points";
	case divine_boon_category::cargo:
		return "+25% Cargo & Contraband";
	case divine_boon_category::pvp:
		return "+50% PvP Epic Points";
	default:
		return "Unknown";
	}
}

std::string player_objective(const divine_boon_slot &slot, int side)
{
	if (slot.category == divine_boon_category::cargo)
	{
		if (slot.source_port < 0 || slot.source_port >= NUM_PORTS ||
		    slot.destination_port < 0 || slot.destination_port >= NUM_PORTS)
			return "Unavailable";
		// Preserve any colours defined by the port names and reset around the arrow.
		return std::string("&+W") + ports[slot.source_port].loc_name + "&n &+L->&n &+W" +
		       ports[slot.destination_port].loc_name + "&n";
	}
	if (slot.category == divine_boon_category::pvp)
		return side == 0 ? "Frags against Evil racewar" : "Frags against Good racewar";
	const int zone = divine_boon_shared_target_zone(slot);
	if (zone < 0)
		return "Unavailable";
	for (int index = 0; index <= top_of_zone_table; ++index)
		if (zone_table[index].number == zone && zone_table[index].name)
			return zone_table[index].name; // Original zone ANSI must be kept.
	return "Unavailable";
}

std::string remaining_label(int64_t seconds)
{
	const int64_t hours = seconds / 3600;
	const int64_t minutes = seconds / 60 % 60;
	if (hours)
		return std::to_string(hours) + "h " + std::to_string(minutes) + "m";
	if (minutes)
		return std::to_string(minutes) + "m " + std::to_string(seconds % 60) + "s";
	return std::to_string(seconds) + "s";
}

void player_next_hour(P_char ch, const divine_boon_state &state, int64_t now)
{
	const int64_t next =
		std::max(now - now % DIVINE_BOON_HOUR, state.last_opportunity) + DIVINE_BOON_HOUR;
	const int64_t remaining = std::max<int64_t>(0, next - now);
	send_to_char_f(ch, "&+YNext Divine Boon opportunity in %lldm %02llds&n\r\n",
		       static_cast<long long>(remaining / 60),
		       static_cast<long long>(remaining % 60));
}

void target(P_char ch, const divine_boon_slot &slot, int side, bool history = false)
{
	if (slot.category == divine_boon_category::cargo)
	{
		if (slot.source_port < 0 || slot.source_port >= NUM_PORTS ||
		    slot.destination_port < 0 || slot.destination_port >= NUM_PORTS)
			return;
		send_to_char_f(ch, "    From: %s&n\r\n    To:   %s&n\r\n",
			       ports[slot.source_port].loc_name,
			       ports[slot.destination_port].loc_name);
	}
	else if (slot.category == divine_boon_category::pvp)
		send_to_char(side == 0 ? "    Good defeats qualifying Evil opponents.\r\n" :
					 "    Evil defeats qualifying Good opponents.\r\n",
			     ch);
	else if (side >= 0 &&
		 (history ? slot.zones[side] : divine_boon_shared_target_zone(slot)) >= 0)
	{
		const int zone = history ? slot.zones[side] : divine_boon_shared_target_zone(slot);
		if (!history && !(slot.category == divine_boon_category::epic ?
					  (divine_boon_epic_zone_eligible(zone, 0) ||
					   divine_boon_epic_zone_eligible(zone, 1)) :
					  (divine_boon_zone_eligible(zone, 0) ||
					   divine_boon_zone_eligible(zone, 1))))
			return;
		for (int index = 0; index <= top_of_zone_table; ++index)
			if (zone_table[index].number == zone)
			{
				send_to_char_f(ch, "    %s target: %s&n\r\n",
					       side ? "Evil" : "Good",
					       pad_ansi(zone_table[index].name, 60, true).c_str());
				return;
			}
	}
}
bool visible(const divine_boon_slot &slot, int side, int64_t now)
{
	if (!divine_boon_active(slot, now))
		return false;
	if (slot.category == divine_boon_category::cargo)
		return divine_boon_cargo_eligible(slot);
	if (side < 0)
		return false;
	if (slot.category == divine_boon_category::pvp)
		return true;
	const int zone = divine_boon_shared_target_zone(slot);
	if (zone < 0)
		return false;
	// Legacy one-sided saved objectives must be visible to both factions.
	return slot.category == divine_boon_category::epic ?
		       (divine_boon_epic_zone_eligible(zone, 0) ||
			divine_boon_epic_zone_eligible(zone, 1)) :
		       (divine_boon_zone_eligible(zone, 0) || divine_boon_zone_eligible(zone, 1));
}
void next_hour(P_char ch, const divine_boon_state &state, int64_t now)
{
	const time_t next =
		std::max(now - now % DIVINE_BOON_HOUR, state.last_opportunity) + DIVINE_BOON_HOUR;
	tm utc = {};
	gmtime_r(&next, &utc);
	send_to_char_f(ch, "Next hourly opportunity: %02d:%02d UTC (in %lldm %llds).\r\n",
		       utc.tm_hour, utc.tm_min, static_cast<long long>((next - now) / 60),
		       static_cast<long long>((next - now) % 60));
}
}

void do_divine_boon(P_char ch, char *argument, int /*cmd*/)
{
	if (!ch || IS_NPC(ch))
		return;
	char verb[MAX_INPUT_LENGTH];
	one_argument(argument, verb);
	if (*verb && strcmp(verb, "list"))
	{
		send_to_char("Usage: boon [list]. Divine benefits apply automatically.\r\n", ch);
		return;
	}
	send_to_char(
		"&+YThe Gods of Duris have given you and your allies the following boons:&n\r\n",
		ch);
	const auto *state = divine_boon_runtime_state();
	if (!state)
	{
		send_to_char("Divine Boons are initializing; no bonus is advertised yet.\r\n", ch);
		return;
	}
	if (state->mode != divine_boon_mode::divine)
	{
		send_to_char(
			"Legacy rewards are being reconciled before the new rotation starts.\r\n",
			ch);
		return;
	}
	const int side = IS_RACEWAR_GOOD(ch) ? 0 : IS_RACEWAR_EVIL(ch) ? 1 : -1;
	const int64_t now = time(nullptr);
	const std::string heading_reward = pad_ansi("BOON / REWARD", reward_width);
	const std::string heading_objective = pad_ansi("TARGET / OBJECTIVE", objective_width);
	const std::string heading_time = pad_ansi("TIME LEFT", -remaining_width);
	send_to_char_f(ch, "\r\n  &+W%s  %s  %s&n\r\n", heading_reward.c_str(),
		       heading_objective.c_str(), heading_time.c_str());
	send_to_char(
		"&+L-------------------------------------------------------------------------------&n\r\n",
		ch);
	unsigned shown = 0;
	for (size_t index = 0; index < state->slots.size(); ++index)
	{
		const auto &slot = state->slots[index];
		if (!visible(slot, side, now))
			continue;
		++shown;
		const std::string reward = std::string(reward_color(slot.category)) + "[" +
					   std::to_string(index + 1) + "] " +
					   reward_label(slot.category) + "&n";
		std::string objective = player_objective(slot, side);
		if ((slot.category == divine_boon_category::experience ||
		     slot.category == divine_boon_category::epic) &&
		    strip_ansi(objective.c_str()).size() > objective_width)
		{
			const std::string identity =
				"&n... [" + std::to_string(divine_boon_shared_target_zone(slot)) +
				"]";
			objective = pad_ansi(objective.c_str(),
					     objective_width -
						     static_cast<int>(
							     strip_ansi(identity.c_str()).size()),
					     true) +
				    identity;
		}
		const std::string duration = remaining_label(slot.expires_at - now);
		const std::string reward_cell = pad_ansi(reward.c_str(), reward_width, true);
		const std::string objective_cell =
			pad_ansi(objective.c_str(), objective_width, true);
		const std::string time_cell = pad_ansi(duration.c_str(), -remaining_width, true);
		// Exactly 79 visible columns. Explicit resets also cover truncated ANSI names.
		send_to_char_f(ch, "  %s&n  %s&n  &+W%s&n\r\n", reward_cell.c_str(),
			       objective_cell.c_str(), time_cell.c_str());
	}
	if (!shown)
		send_to_char("&+L  There are no active boons applicable to you.&n\r\n", ch);
	send_to_char(
		"&+L-------------------------------------------------------------------------------&n\r\n",
		ch);
	if (state->paused)
		send_to_char("&+YNew boons are paused; existing boons still expire on time.&n\r\n",
			     ch);
	if (divine_boon_runtime_pending())
		send_to_char("&+YRotation update awaiting durable confirmation.&n\r\n", ch);
	player_next_hour(ch, *state, now);
	send_to_char("&+LBenefits are automatic. Type HELP DIVINE BOONS for rules.&n\r\n", ch);
}

void do_divineboon(P_char ch, char *argument, int /*cmd*/)
{
	if (!ch || IS_NPC(ch) || !IS_TRUSTED(ch))
		return;
	char verb[MAX_INPUT_LENGTH], value[MAX_INPUT_LENGTH], extra[MAX_INPUT_LENGTH];
	argument = one_argument(argument, verb);
	argument = one_argument(argument, value);
	one_argument(argument, extra);
	const auto *state = divine_boon_runtime_state();
	if (!state)
	{
		send_to_char(
			"Divine state is initializing or requires persistence reconciliation.\r\n",
			ch);
		return;
	}
	const int64_t now = time(nullptr);
	if (!*verb || !strcmp(verb, "status"))
	{
		const char *mode = state->mode == divine_boon_mode::divine   ? "divine" :
				   state->mode == divine_boon_mode::draining ? "draining" :
									       "legacy";
		send_to_char_f(ch, "Divine mode=%s paused=%s pending=%s revision=%llu\r\n", mode,
			       state->paused ? "yes" : "no",
			       divine_boon_runtime_pending() ? "yes" : "no",
			       static_cast<unsigned long long>(state->revision));
		next_hour(ch, *state, now);
		for (size_t index = 0; index < state->slots.size(); ++index)
		{
			const auto &slot = state->slots[index];
			if (!divine_boon_active(slot, now))
				continue;
			send_to_char_f(ch, "[%zu] id=%llu %s\r\n    start=%lld expiry=%lld\r\n",
				       index + 1, static_cast<unsigned long long>(slot.id),
				       category_name(slot.category),
				       static_cast<long long>(slot.starts_at),
				       static_cast<long long>(slot.expires_at));
			// Staff inspect exact persisted targets, even when temporarily
			// ineligible. Player BOON output resolves a single shared target.
			target(ch, slot, 0, true);
			if (slot.category != divine_boon_category::cargo)
				target(ch, slot, 1, true);
		}
		divine_boon_selection_status(ch);
		return;
	}
	if (!strcmp(verb, "history") && !*value)
	{
		if (state->recent.empty())
			send_to_char("No retired Divine Boons have been recorded yet.\r\n", ch);
		for (auto it = state->recent.rbegin(); it != state->recent.rend(); ++it)
		{
			send_to_char_f(ch, "id=%llu %s\r\n    ended=%lld\r\n",
				       static_cast<unsigned long long>(it->objective.id),
				       category_name(it->objective.category),
				       static_cast<long long>(it->ended_at));
			target(ch, it->objective, 0, true);
			if (it->objective.category != divine_boon_category::cargo)
				target(ch, it->objective, 1, true);
		}
		return;
	}
	if (divine_boon_runtime_pending())
	{
		send_to_char("A state update is pending; inspect status after it completes.\r\n",
			     ch);
		return;
	}
	bool changed = false;
	auto next = *state;
	if ((!strcmp(verb, "pause") || !strcmp(verb, "resume")) && !*value)
		changed = divine_boon_set_paused(&next, !strcmp(verb, "pause"), now,
						 divine_boon_shared_target_zone);
	else if (!strcmp(verb, "replace") && *value && !*extra)
	{
		char *end = nullptr;
		const long index = strtol(value, &end, 10);
		if (end && !*end && index >= 1 && index <= static_cast<long>(DIVINE_BOON_SLOTS))
			changed = divine_boon_replace(&next, static_cast<size_t>(index - 1), now,
						      divine_boon_shared_target_zone);
	}
	else if (!strcmp(verb, "force") && !*value)
	{
		divine_boon_selection_pulse(now);
		const bool accepted = divine_boon_runtime_pending();
		send_to_char(
			accepted ?
				"Due hourly opportunity submitted; inspect status for confirmation.\r\n" :
				"No due unconsumed opportunity was submitted. Timing and pause rules apply.\r\n",
			ch);
		wizlog(IMMORTAL, "%s divineboon force revision=%llu accepted=%d", GET_NAME(ch),
		       static_cast<unsigned long long>(state->revision), accepted);
		return;
	}
	else
	{
		send_to_char(
			"Usage: divineboon status|pause|resume|replace <slot>|force|history\r\n",
			ch);
		return;
	}
	if (!changed)
	{
		send_to_char("No change: check the mode, pause state or active slot.\r\n", ch);
		return;
	}
	if (!divine_boon_runtime_queue(next))
	{
		send_to_char("The update was not admitted; published state is unchanged.\r\n", ch);
		return;
	}
	wizlog(IMMORTAL, "%s divineboon %s %s requested revision=%llu", GET_NAME(ch), verb, value,
	       static_cast<unsigned long long>(next.revision));
	send_to_char("State update submitted; inspect status for durable confirmation.\r\n", ch);
}

namespace
{
bool same_boon(const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &slots, uint64_t id)
{
	return std::any_of(slots.begin(), slots.end(),
			   [id](const divine_boon_slot &slot) { return slot.id == id; });
}

void announce_divine_event(const divine_boon_slot &slot, bool granted)
{
	if (slot.category == divine_boon_category::none)
		return;
	const std::string reward =
		std::string(reward_color(slot.category)) + reward_label(slot.category) + "&n";
	const std::string prefix = "&+YThe Gods of Duris&n ";
	if (slot.category == divine_boon_category::cargo)
	{
		const std::string route = player_objective(slot, 0);
		if (route == "Unavailable")
			return;
		const std::string message =
			prefix +
			(granted ? "have blessed the trade route " :
				   "have withdrawn their blessing from the trade route ") +
			route +
			(granted ? "! " + reward + " is active. Type BOON for details.&n\r\n" :
				   ". " + reward + " has expired.&n\r\n");
		send_to_all(message.c_str());
		return;
	}
	if (slot.category == divine_boon_category::pvp)
	{
		const std::string message =
			prefix + (granted ? "have blessed the racewar! " + reward +
						    " is active. Type BOON for details.&n\r\n" :
					    "have withdrawn their racewar blessing. " + reward +
						    " has expired.&n\r\n");
		send_to_all(message.c_str());
		return;
	}
	// Zone boons are shared racewar hotspots. Announce the same objective to all.
	const std::string zone = player_objective(slot, 0);
	if (zone == "Unavailable")
		return;
	const std::string message =
		prefix + (granted ? "have blessed " + zone + "&n with " + reward +
					    "! Type BOON for details.&n\r\n" :
				    "have withdrawn " + reward + " from " + zone + "&n.&n\r\n");
	send_to_all(message.c_str());
}
} // namespace

void divine_boon_announce_changes(const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &previous,
				  const std::array<divine_boon_slot, DIVINE_BOON_SLOTS> &current,
				  int64_t now)
try
{
	// Staff replacement is not expiry; a committed new ID is a real grant.
	for (const auto &old : previous)
		if (old.id && old.expires_at <= now && !same_boon(current, old.id))
			announce_divine_event(old, false);
	for (const auto &slot : current)
		if (slot.id && divine_boon_active(slot, now) && !same_boon(previous, slot.id))
			announce_divine_event(slot, true);
}
catch (const std::bad_alloc &)
{
	// Cosmetic broadcast failures must not unwind committed state publication.
}
