/* Read-only class and specialization guide, alongside race/skills/spells. */
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "account/creation_availability_config.h"
#include "classes/specializations.h"
#include "cmd/class.h"
#include "cmd/race.h"
#include "cmd/wikihelp.h"
#include "magic/spells.h"
#include "abilities/abilities.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <vector>

extern const struct class_names class_names_table[];
extern const struct race_names race_names_table[];
extern float combat_by_class[][2];
extern int class_table[LAST_RACE + 1][CLASS_COUNT + 1];
extern const char *specdata[][MAX_SPEC];
extern Skill skills[];
extern char class_innates[LAST_INNATE + 2][CLASS_COUNT][5];
extern const struct innate_data innates_data[];

namespace
{
// Keep names and exact/unique-prefix matching consistent with skills and spells.
string name_key(const string &name)
{
	string result;
	for (unsigned char letter : strip_ansi(name.c_str()))
		if (!std::isspace(letter) && letter != '-')
			result += static_cast<char>(std::tolower(letter));
	return result;
}

int match_name(P_char ch, const string &name, const std::vector<string> &names)
{
	const string key = name_key(name);
	if (key.empty())
		return -1;
	int found = -1;
	string matches;
	for (size_t i = 0; i < names.size(); ++i)
	{
		const string candidate = name_key(names[i]);
		if (candidate == key)
			return static_cast<int>(i);
		if (candidate.rfind(key, 0) != 0)
			continue;
		matches += "  " + strip_ansi(names[i].c_str()) + "\n";
		found = found == -1 ? static_cast<int>(i) : -2;
	}
	if (found == -2)
		send_to_char_f(ch, "Be more specific. Matching names:\n%s", matches.c_str());
	return found;
}

void heading(std::ostringstream &out, const string &title)
{
	out << "\n&+C  >====[ " << title << "&+C ]====<&n\n\n";
}

// Wrap authored paragraphs and generated lists without counting MUD colors.
void paragraph(std::ostringstream &out, const string &text, int indent = 2)
{
	std::istringstream lines(text);
	for (string line; std::getline(lines, line);)
	{
		std::istringstream words(line);
		string word;
		int width = indent;
		out << string(indent, ' ');
		while (words >> word)
		{
			const int length = ansi_strlen(word.c_str());
			if (width > indent && width + 1 + length > 79)
			{
				out << "\n" << string(indent, ' ');
				width = indent;
			}
			if (width > indent)
			{
				out << ' ';
				++width;
			}
			out << word;
			width += length;
		}
		out << "&n\n";
	}
}

void list_entry(std::ostringstream &out, const string &text)
{
	std::istringstream words(text);
	string word;
	words >> word;
	out << "  " << word;
	while (words >> word)
		out << ' ' << word;
	out << "&n\n";
}

bool named_spec(int cls, int spec)
{
	return *specdata[cls][spec - 1] && strcmp(specdata[cls][spec - 1], "Not Used");
}

bool legacy_class(int cls)
{
	return cls == flag2idx(CLASS_ASSASSIN) || cls == flag2idx(CLASS_THIEF);
}

string help_topic(int cls, int spec)
{
	if (!spec)
		return class_names_table[cls].normal;
	const string name = strip_ansi(specdata[cls][spec - 1]);
	return name == "Assassin" || name == "Thief" ? "Rogue " + name : name;
}

string description(int cls, int spec, bool brief)
{
	const string topic = help_topic(cls, spec);
	string text = wiki_help_prose(topic, "");
	text = text.substr(0, text.find("\n\n"));
	if (spec)
	{
		const string intro = strip_ansi(specdata[cls][spec - 1]) + " is a " +
				     class_names_table[cls].normal + " specialization.";
		if (!strncasecmp(text.c_str(), intro.c_str(), intro.size()))
			text.clear();
	}
	if (brief)
	{
		const string mechanics = wiki_help_prose(topic, "Class mechanics");
		if (spec && !mechanics.empty())
			text = mechanics;
		const size_t end = text.find(". ");
		if (end != string::npos)
			text.erase(end + 1);
	}
	return text.empty() && !spec ? "Description unavailable." : text;
}

bool normal_race(int race)
{
	for (const playable_race_info *entry = playable_races; entry->race_id >= 0; ++entry)
		if (entry->race_id == race)
			return true;
	return false;
}

bool available_race(int race)
{
	return creation_race_enabled(race) && (normal_race(race) || creation_all_races_enabled());
}

const char *race_status(int race)
{
	if (!creation_race_enabled(race))
		return "Disabled in character creation";
	if (normal_race(race))
		return "Available in character creation";
	return creation_all_races_enabled() ? "Creation enabled (normally restricted)" :
					      "Special / legacy: unavailable in creation";
}

bool eligible(int race, int cls)
{
	return available_race(race) && creation_class_enabled(cls) &&
	       creation_class_align(race, cls) != 5;
}

string class_status(int cls, bool brief = false)
{
	bool normal = false, current = false, override = false;
	for (int race = 1; race <= RACE_PLAYER_MAX; ++race)
	{
		normal |= normal_race(race) && class_table[race][cls] != 5;
		if (eligible(race, cls))
		{
			current = true;
			override |= !normal_race(race) ||
				    !creation_class_normally_available(race, cls);
		}
	}
	if (brief)
	{
		string status;
		if (legacy_class(cls))
			status = "Retired ID " + std::to_string(cls);
		else if (!creation_class_enabled(cls) || !current)
			status = "Disabled";
		if (!normal)
			status += string(status.empty() ? "" : ": ") + "Special/Legacy";
		else if (creation_class_enabled(cls) && !current)
			status += ": no eligible races";
		if (current && override)
			status += string(status.empty() ? "" : "; ") + "Override";
		return status;
	}
	if (!creation_class_enabled(cls))
		return "Disabled in character creation";
	if (current)
		return override ? "Available in creation (includes normally restricted choices)" :
				  "Available in character creation";
	return normal ? "Unavailable: no eligible creation races" :
			"Special / legacy: unavailable in creation";
}

const char *alignment(int code)
{
	switch (code)
	{
	case -1:
		return "evil";
	case 0:
		return "neutral";
	case 1:
		return "good";
	case 2:
		return "any";
	case 3:
		return "good/neutral";
	case 4:
		return "neutral/evil";
	default:
		return "unavailable";
	}
}

void usage(P_char ch)
{
	send_to_char("Usage: class | class list [race]\n"
		     "       class info <class or specialization> | class specs <class>\n"
		     "       class innates <class or specialization>\n"
		     "Examples: class list grey elf | class info guardian | class specs warrior\n",
		     ch);
}

void roster(std::ostringstream &out, int race)
{
	heading(out, race ? race_display_name(race) + " : CLASS CHOICES" : "THE CLASS ROSTER");
	if (race)
	{
		paragraph(out, string("Race creation: ") + race_status(race));
		if (!available_race(race))
		{
			paragraph(out, "No new character can currently select this race.");
			return;
		}
	}
	int shown = 0;
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
	{
		if (race && !eligible(race, cls))
			continue;
		string label = class_names_table[cls].ansi;
		string status = class_status(cls, true);
		if (race)
		{
			if (!status.empty())
				status += "; ";
			status +=
				string("Alignment: ") + alignment(creation_class_align(race, cls));
			if (!creation_class_normally_available(race, cls))
				status += "; normally restricted";
		}
		if (!status.empty())
			label += "&n (" + status + ")";
		list_entry(out, label + "&n - " + description(cls, 0, true));
		++shown;
	}
	if (!shown)
		paragraph(out, "None under current creation policy.");
	paragraph(out, "\nAlignment is separate from racewar side.");
	paragraph(out, "\nInspect: &+Wclass info <name>&n | &+Wclass specs <class>&n");
}

string race_permission(P_char ch, int cls, int spec)
{
	return string("Your race permission (") + race_names_table[GET_RACE(ch)].normal + "): " +
	       (is_allowed_race_spec(GET_RACE(ch), 1U << (cls - 1), spec) ? "allowed" :
									    "not allowed");
}

void specializations(std::ostringstream &out, P_char ch, int cls)
{
	out << "\n&+W  Specializations&n\n";
	int shown = 0;
	for (int spec = 1; spec <= MAX_SPEC; ++spec)
	{
		if (!named_spec(cls, spec))
			continue;
		string row = specdata[cls][spec - 1];
		if (!is_allowed_race_spec(GET_RACE(ch), 1U << (cls - 1), spec))
			row += string("&n (Not available to ") +
			       race_names_table[GET_RACE(ch)].normal + ")";
		const string text = description(cls, spec, true);
		if (!text.empty())
			row += "&n - " + text;
		list_entry(out, row);
		++shown;
	}
	if (!shown)
		paragraph(out, "No named specializations.");
	else
	{
		paragraph(out, "\nInspect: &+Wclass info <specialization>&n");
		paragraph(
			out,
			"Use &+Wspecialize&n at level 30. See &+Whelp specialization&n for requirements.");
	}
}

int innate_level(int innate, int cls, int spec)
{
	const int base = class_innates[innate][cls - 1][0];
	const int extra = class_innates[innate][cls - 1][spec];
	return base && extra ? std::min(base, extra) : std::max(base, extra);
}

std::vector<int> innate_entries(int cls, int spec)
{
	std::vector<int> entries;
	for (int innate = 0; innate <= LAST_INNATE; ++innate)
		if (innate_level(innate, cls, spec))
			entries.push_back(innate);
	std::sort(entries.begin(), entries.end(),
		  [cls, spec](int left, int right)
		  {
			  const int a = innate_level(left, cls, spec);
			  const int b = innate_level(right, cls, spec);
			  return a != b ? a < b :
					  strcmp(innates_data[left].name,
						 innates_data[right].name) < 0;
		  });
	return entries;
}

void innates(std::ostringstream &out, int cls, int spec)
{
	const string damage_modifier = damage_modifier_innate(combat_by_class[cls][1]);
	if (!damage_modifier.empty())
		paragraph(out, damage_modifier);
	const auto entries = innate_entries(cls, spec);
	for (int innate : entries)
		paragraph(out, string(innates_data[innate].func ? " &+c" : "*&+c") +
				       innates_data[innate].name + "&n (level " +
				       std::to_string(innate_level(innate, cls, spec)) +
				       (innates_data[innate].func ? ", active)" : ", passive)"));
	if (entries.empty() && damage_modifier.empty())
		paragraph(out, "None. No class innates assigned.");
	paragraph(
		out,
		"\n'*' Designates passive ability. Includes inherited class abilities.\nUse &+Whelp <ability name>&n for usage. Racial abilities: &+Wrace innates <race>&n.");
}

bool grant_available(const ClassSkillInfo &data, int spec, int maximum)
{
	return data.rlevel[spec] > 0 && data.rlevel[spec] <= maximum && data.maxlearn[spec] > 0;
}

void differences(std::ostringstream &out, int cls, int spec)
{
	out << "\n&+W  Changes from the base class&n\n";
	int shown = 0;
	for (int id = 0; id <= MAX_AFFECT_TYPES; ++id)
	{
		const bool spell = IS_SPELL(id);
		if ((!spell && !(IS_SKILL(id) || IS_INSTRUMENT_SKILL(id) || IS_BARD_SONG(id))) ||
		    IS_EPIC_SKILL(id) || !skills[id].name || !strcmp(skills[id].name, "Undefined"))
			continue;
		const ClassSkillInfo &data = skills[id].m_class[cls - 1];
		const int maximum = spell ? MAX_CIRCLE : MAXLVLMORTAL;
		const bool base = grant_available(data, 0, maximum);
		const bool current = grant_available(data, spec, maximum);
		if ((!base && !current) ||
		    (base && current && data.rlevel[0] == data.rlevel[spec] &&
		     (spell || data.maxlearn[0] == data.maxlearn[spec])))
			continue;
		string row = string(!base    ? "Added " :
				    !current ? "Lost " :
					       "Changed ") +
			     (spell ? "spell: &+c" : "skill: &+c") + skills[id].name + "&n";
		if (current)
		{
			row += spell ? " (Circle " : " (level ";
			if (base)
				row += std::to_string(data.rlevel[0]) + " -> ";
			row += std::to_string(data.rlevel[spec]);
			if (!spell)
			{
				row += ", cap ";
				if (base)
					row += std::to_string(data.maxlearn[0]) + "% -> ";
				row += std::to_string(data.maxlearn[spec]) + "%";
			}
			row += ")";
		}
		paragraph(out, row);
		++shown;
	}
	for (int innate : innate_entries(cls, spec))
	{
		const int base = innate_level(innate, cls, 0);
		const int current = innate_level(innate, cls, spec);
		if (base == current)
			continue;
		paragraph(out, string(base ? "Changed innate: &+c" : "Added innate: &+c") +
				       innates_data[innate].name + "&n (level " +
				       (base ? std::to_string(base) + " -> " : "") +
				       std::to_string(current) +
				       (innates_data[innate].func ? ", active)" : ", passive)"));
		++shown;
	}
	if (!shown)
		paragraph(out, "No changes to registered skills, spells or innates.");
}

void profile(std::ostringstream &out, P_char ch, int cls, int spec)
{
	const string name = spec ? specdata[cls][spec - 1] : class_names_table[cls].ansi;
	const string plain = strip_ansi(name.c_str());
	heading(out, name + (spec ? "&n : SPECIALIZATION" : "&n : BASE CLASS"));
	if (spec)
		paragraph(out, string("Parent class: ") + class_names_table[cls].ansi);
	paragraph(out, description(cls, spec, false));
	out << "\n&+W  Availability&n\n";
	paragraph(out, string(spec ? "Parent creation: " : "Creation: ") + class_status(cls));
	paragraph(out, "Eligible creation races and alignment:");
	int shown = 0;
	for (int race = 1; race <= RACE_PLAYER_MAX; ++race)
		if (eligible(race, cls))
		{
			string row = race_display_name(race) +
				     "&n: " + alignment(creation_class_align(race, cls));
			if (!normal_race(race) || !creation_class_normally_available(race, cls))
				row += " (normally restricted; override enabled)";
			paragraph(out, row, 4);
			++shown;
		}
	if (!shown)
		paragraph(out, "None under current creation policy.", 4);
	paragraph(out, "Alignment is separate from racewar side.");
	if (spec)
	{
		out << "\n&+W  Allowed specialization races&n\n";
		string races;
		for (int race = 1; race <= RACE_PLAYER_MAX; ++race)
			if (is_allowed_race_spec(race, 1U << (cls - 1), spec))
				races +=
					string(races.empty() ? "" : ", ") + race_display_name(race);
		paragraph(out, races.empty() ? "None." : races);
		paragraph(out, race_permission(ch, cls, spec));
		if (creation_all_classes_enabled())
			paragraph(
				out,
				"Race permission override enabled (includes normally restricted paths).");
		paragraph(
			out,
			"Use &+Wspecialize&n at level 30. See &+Whelp specialization&n for requirements.");
	}
	else
		specializations(out, ch, cls);
	out << "\n&+W  Class features&n\n";
	const auto entries = innate_entries(cls, spec);
	int active = 0;
	string summary;
	for (int innate : entries)
	{
		active += innates_data[innate].func != nullptr;
		summary += string(summary.empty() ? "" : ", ") + "&+c" + innates_data[innate].name +
			   "&n (level " + std::to_string(innate_level(innate, cls, spec)) + ")";
	}
	paragraph(out, "Innates: " + std::to_string(entries.size()) + " grants (" +
			       std::to_string(active) + " active, " +
			       std::to_string(entries.size() - active) + " passive).");
	if (!summary.empty())
		paragraph(out, summary, 4);
	const string mechanics = wiki_help_prose(help_topic(cls, spec), "Class mechanics");
	if (!mechanics.empty())
	{
		paragraph(out, mechanics, 4);
	}
	if (spec)
		differences(out, cls, spec);
	out << "\n&+W  Further reading&n\n";
	paragraph(out, "&+Wskills " + plain + "&n | &+Wspells " + plain + "&n");
	paragraph(out,
		  "&+Wclass innates " + plain + "&n | &+Whelp " + help_topic(cls, spec) + "&n");
	if (spec)
		paragraph(out, string("&+Wclass info ") + class_names_table[cls].normal + "&n");
	paragraph(out, "&+Whelp specialization&n | &+Whelp multiclass&n");
}
} // namespace

void do_class(P_char ch, char *argument, int /*cmd*/)
{
	if (IS_NPC(ch))
		return;
	char option[MAX_INPUT_LENGTH];
	char *rest = one_argument(argument, option);
	const string detail = trim(rest ? rest : "", " \t\r\n");
	const std::vector<string> commands = { "list", "info", "specs", "innates" };
	const int command = *option ? match_name(ch, option, commands) : 0;
	if (command == -2)
		return;
	if (command == -1 || (command != 0 && detail.empty()))
	{
		usage(ch);
		return;
	}
	std::ostringstream out;
	if (command == 0)
	{
		int race = 0;
		if (!detail.empty())
		{
			std::vector<string> names;
			for (int id = 1; id <= RACE_PLAYER_MAX; ++id)
				names.emplace_back(race_names_table[id].normal);
			int found = match_name(ch, detail, names);
			if (found == -1)
			{
				names.clear();
				for (int id = 1; id <= RACE_PLAYER_MAX; ++id)
					names.emplace_back(race_names_table[id].no_spaces);
				found = match_name(ch, detail, names);
			}
			if (found < 0)
			{
				if (found == -1)
					send_to_char(
						"No such player race. Example: class list grey elf\n",
						ch);
				return;
			}
			race = found + 1;
		}
		roster(out, race);
	}
	else
	{
		std::vector<std::pair<int, int>> paths;
		std::vector<string> names;
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		{
			if (!legacy_class(cls))
			{
				paths.emplace_back(cls, 0);
				names.emplace_back(class_names_table[cls].normal);
			}
			for (int spec = 1; spec <= MAX_SPEC; ++spec)
				if (named_spec(cls, spec))
				{
					paths.emplace_back(cls, spec);
					names.emplace_back(specdata[cls][spec - 1]);
				}
		}
		const int found = match_name(ch, detail, names);
		if (found < 0)
		{
			if (found == -1)
			{
				send_to_char(
					"No such class/specialization. Example: class info dark knight\n",
					ch);
				usage(ch);
			}
			return;
		}
		const auto [cls, spec] = paths[found];
		if (command == 1)
			profile(out, ch, cls, spec);
		else if (command == 2)
		{
			if (spec)
			{
				send_to_char("Provide a base class. Example: class specs rogue\n",
					     ch);
				return;
			}
			heading(out, string(class_names_table[cls].ansi) + " : SPECIALIZATIONS");
			specializations(out, ch, cls);
		}
		else
		{
			heading(out, names[found] + " : CLASS INNATES");
			innates(out, cls, spec);
		}
	}
	send_to_char(out.str().c_str(), ch);
}
