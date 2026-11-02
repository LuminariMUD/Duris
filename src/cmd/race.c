/* Player-facing race catalog, using character creation's eligibility rules. */
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "account/creation_availability_config.h"
#include "classes/specializations.h"
#include "cmd/race.h"
#include "cmd/wikihelp.h"

#include <cstring>
#include <strings.h>

extern const struct race_names race_names_table[];
extern const struct class_names class_names_table[];
extern const struct stat_data stat_factor[];
extern float combat_by_race[][3];
extern float spell_pulse_data[];

string race_display_name(int race)
{
	const race_names &name = race_names_table[race];
	if (strip_ansi(name.ansi) == name.normal)
		return name.ansi;
	// Some catalog labels are shortened (Dwarf, Duergar, Illithid). Keep their
	// opening &+ color, but show the full name that players can use in commands.
	return string(name.ansi, 3) + name.normal + "&n";
}

static const char *race_creation_note(int race)
{
	if (!creation_race_enabled(race))
		return "Disabled in character creation";
	for (const playable_race_info *entry = playable_races; entry->race_id >= 0; ++entry)
		if (entry->race_id == race)
			return "Available in character creation";
	if (creation_all_races_enabled())
		return "Creation enabled (normally restricted)";
	for (const restricted_race_info *entry = restricted_races; entry->race_id >= 0; ++entry)
		if (entry->race_id == race)
			return entry->note;
	return "Unavailable in character creation";
}

static void show_race_list(P_char ch)
{
	send_to_char_f(
		ch,
		"\n&+L  /====================================================================\\\n"
		"  | %s&+L |\n"
		"  | %s&+L |\n"
		"  \\====================================================================/&n\n",
		pad_ansi("&+R       D U R I S  :  L A N D  O F  B L O O D L U S T", 66).c_str(),
		pad_ansi("&+W             >====[  THE RACEWAR ROSTER  ]====<", 66).c_str());
	const struct
	{
		const char *faction;
		const char *banner;
		const char *color;
	} sides[] = {
		{ "good", " /\\   GOOD RACES   /\\ ", "&+C" },
		{ "evil", " \\/   EVIL RACES   \\/ ", "&+R" },
		{ "neutral", " <>   NEUTRAL RACES   <> ", "&+Y" },
	};
	for (const auto &side : sides)
	{
		string banner((66 - strlen(side.banner)) / 2, ' ');
		banner += side.banner;
		send_to_char_f(
			ch,
			"\n%s  +--------------------------------------------------------------------+\n"
			"  | %s |\n"
			"  +--------------------------------------------------------------------+&n\n",
			side.color, pad_ansi(banner.c_str(), 66).c_str());
		int columns = 0;
		for (const playable_race_info *entry = playable_races; entry->race_id >= 0; ++entry)
		{
			if (strcmp(entry->faction, side.faction))
				continue;
			if (columns == 0)
				send_to_char_f(ch, "%s  |  &n", side.color);
			string name = creation_race_enabled(entry->race_id) ? " " : "&+L*";
			name += race_display_name(entry->race_id);
			send_to_char(pad_ansi(name.c_str(), 22).c_str(), ch);
			if (++columns == 3)
			{
				send_to_char_f(ch, "%s|&n\n", side.color);
				columns = 0;
			}
		}
		if (columns)
			send_to_char_f(ch, "%*s%s|&n\n", (3 - columns) * 22, "", side.color);
		send_to_char_f(
			ch,
			"%s  +--------------------------------------------------------------------+&n\n",
			side.color);
	}
	send_to_char("\n&+Y  Neutral races choose their racewar side during creation.&n\n"
		     "  * Disabled in character creation.\n"
		     "\n&+M  >====[ SPECIAL / LEGACY RACES ]====<&n\n",
		     ch);
	for (const restricted_race_info *entry = restricted_races; entry->race_id >= 0; ++entry)
		send_to_char_f(ch, "    %s &n- %s\n",
			       pad_ansi(race_display_name(entry->race_id).c_str(), 22).c_str(),
			       race_creation_note(entry->race_id));
	send_to_char("\n  &+WRace info <race name>&n     Profile and valid classes\n"
		     "  &+WRace innates <race name>&n  Racial abilities and unlock levels\n",
		     ch);
}

static int find_player_race(P_char ch, const char *name)
{
	for (int race = 1; race <= RACE_PLAYER_MAX; ++race)
		if (!strcasecmp(name, race_names_table[race].normal) ||
		    !strcasecmp(name, race_names_table[race].no_spaces))
			return race;
	int found = -1;
	string matches;
	for (int race = 1; race <= RACE_PLAYER_MAX; ++race)
	{
		if (!is_abbrev(name, race_names_table[race].normal) &&
		    !is_abbrev(name, race_names_table[race].no_spaces))
			continue;
		if (!matches.empty())
			matches += ", ";
		matches += race_names_table[race].normal;
		found = found == -1 ? race : -2;
	}
	if (found == -1)
		send_to_char("No such player race. Use 'race list' to see the races.\n", ch);
	else if (found == -2)
		send_to_char_f(ch, "Be more specific. Matching races: %s.\n", matches.c_str());
	return found;
}

static void show_race_info(P_char ch, int race)
{
	const char *faction = "No racewar side";
	if (OLD_RACE_NEUTRAL(race) || race == RACE_HARPY)
		faction = "&+YNeutral&n";
	else if (OLD_RACE_GOOD(race, -1))
		faction = "&+CGood&n";
	else if (OLD_RACE_EVIL(race, 1))
		faction = "&+REvil&n";
	else if (OLD_RACE_PUNDEAD(race))
		faction = "&+MUndead&n";

	send_to_char_f(ch,
		       "\n&+C  >====[ %s&+C ]====<&n\n"
		       "  Racewar side : %s\n"
		       "  Creation     : %s\n",
		       race_display_name(race).c_str(), faction, race_creation_note(race));
	string description = wiki_race_description(race_names_table[race].normal);
	if (!description.empty())
		send_to_char_f(ch, "\n%s\n", description.c_str());

	send_to_char("\n&+W  Valid classes (current character creation rules)&n\n", ch);
	int shown = 0;
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
	{
		if (!creation_class_enabled(cls) || creation_class_align(race, cls) == 5)
			continue;
		string name = class_names_table[cls].ansi;
		string specs = single_spec_list(race, cls);
		if (!specs.empty())
			name = pad_ansi(name.c_str(), 12) + "&n: " + specs;
		send_to_char_f(ch, "    %s&n\n", name.c_str());
		++shown;
	}
	if (!shown)
		send_to_char("    None.\n", ch);

	const stat_data &stats = stat_factor[race];
	send_to_char_f(ch,
		       "\n&+W  Racial stat factors (100%% is the baseline)&n\n"
		       "    Strength     &+c%3d%%&n    Power        &+c%3d%%&n\n"
		       "    Dexterity    &+c%3d%%&n    Intelligence &+c%3d%%&n\n"
		       "    Agility      &+c%3d%%&n    Wisdom       &+c%3d%%&n\n"
		       "    Constitution &+c%3d%%&n    Charisma     &+c%3d%%&n\n"
		       "    Luck         &+c%3d%%&n    Karma        &+c%3d%%&n\n"
		       "\n    Combat speed : &+c%s&n\n"
		       "    Spell speed  : &+c%s&n\n",
		       stats.Str, stats.Pow, stats.Dex, stats.Int, stats.Agi, stats.Wis, stats.Con,
		       stats.Cha, stats.Luk, stats.Kar,
		       stat_to_string_damage_pulse(combat_by_race[race][0]),
		       stat_to_string_spell_pulse(spell_pulse_data[race]));
	send_to_char_f(ch,
		       "\n  Abilities: &+Wrace innates %s&n\n"
		       "  More lore and racial traits: &+Whelp %s&n\n",
		       race_names_table[race].normal, race_names_table[race].normal);
}

void do_race(P_char ch, char *argument, int /*cmd*/)
{
	char option[MAX_INPUT_LENGTH];
	char *rest = one_argument(argument, option);
	string name = rest ? skip_spaces(rest) : "";
	const size_t end = name.find_last_not_of(" \t\r\n");
	name.erase(end == string::npos ? 0 : end + 1);
	if ((!*option || is_abbrev(option, "list")) && name.empty())
	{
		show_race_list(ch);
		return;
	}
	if (!is_abbrev(option, "info") && !is_abbrev(option, "innates"))
	{
		send_to_char(
			"Usage: race list | race info <race name> | race innates <race name>\n",
			ch);
		return;
	}
	if (name.empty())
	{
		send_to_char("Please provide a race name. Example: race info grey elf\n", ch);
		return;
	}
	int race = find_player_race(ch, name.c_str());
	if (race < 0)
		return;
	if (is_abbrev(option, "info"))
		show_race_info(ch, race);
	else
	{
		send_to_char_f(ch, "\n&+C  >====[ %s&+C : RACIAL INNATES ]====<&n\n\n",
			       race_display_name(race).c_str());
		send_to_char(list_innates(race, 0, 0).c_str(), ch);
		send_to_char("\n  Use &+Whelp <ability name>&n for details about an innate.\n", ch);
	}
}
