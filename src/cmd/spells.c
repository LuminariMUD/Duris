/* Personal spell access and live class/specialization reference catalogs. */
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "cmd/wikihelp.h"
#include "magic/spells.h"
#include "abilities/abilities.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <vector>

extern const struct class_names class_names_table[];
extern const char *specdata[][MAX_SPEC];
extern Skill skills[];

namespace
{
bool valid_circle(int circle)
{
	return circle > 0 && circle <= MAX_CIRCLE;
}

int reference_circle(int spell, int cls, int spec)
{
	const ClassSkillInfo &data = skills[spell].m_class[cls - 1];
	return valid_circle(data.rlevel[spec]) && data.maxlearn[spec] > 0 ? data.rlevel[spec] : 0;
}

bool named_spec(int cls, int spec)
{
	return *specdata[cls][spec - 1] && strcmp(specdata[cls][spec - 1], "Not Used");
}

bool defined_spell(int spell)
{
	return IS_SPELL(spell) && skills[spell].name && *skills[spell].name &&
	       strcmp(skills[spell].name, "Undefined");
}

bool public_spell(int spell)
{
	if (!defined_spell(spell))
		return false;
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		for (int spec = 0; spec <= MAX_SPEC; ++spec)
			if ((!spec || named_spec(cls, spec)) && reference_circle(spell, cls, spec))
				return true;
	return false;
}

string name_key(const string &name)
{
	string result;
	for (unsigned char letter : strip_ansi(name.c_str()))
		if (!std::isspace(letter) && letter != '-')
			result += static_cast<char>(std::tolower(letter));
	return result;
}

// As in skills, exact names win and abbreviations must be unique.
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

string heading(const string &title)
{
	return "\n&+C  >====[ " + title + "&+C ]====<&n\n\n";
}

void usage(P_char ch)
{
	send_to_char("Usage: spells | spells <class or specialization>\n"
		     "       spells info <spell name>\n",
		     ch);
	if (IS_TRUSTED(ch))
		send_to_char("Staff: spells <target> | spells target <name> | spells all\n", ch);
}

// Follow the character's spell rules, including secondary-only circle adjustment.
int personal_circle(P_char target, int spell)
{
	if (!target->player.m_class)
		return 0;
	const int circle = get_spell_circle(target, spell);
	if (!valid_circle(circle))
		return 0;
	if (IS_PC(target))
	{
		const ClassSkillInfo data = SKILL_DATA_ALL(target, spell);
		if (!data.maxlearn[0] && !data.maxlearn[target->player.spec])
			return 0;
	}
	return circle;
}

bool shows_book(P_char target)
{
	return IS_PC(target) && book_class(target) && !USES_MANA(target) &&
	       !USES_SPELL_SLOTS(target);
}

bool in_book(P_char target, int spell)
{
	return SpellInSpellBook(target, spell,
				SBOOK_MODE_IN_INV | SBOOK_MODE_AT_HAND | SBOOK_MODE_ON_BELT);
}

void personal_spells(P_char ch, P_char target)
{
	std::ostringstream out;
	out << "&+C>====[ " << GET_NAME(target) << " |";
	if (!target->player.m_class)
		out << " " << class_names_table[0].normal;
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		if (target->player.m_class & (1U << (cls - 1)))
			out << " " << class_names_table[cls].ansi << "&+C";
	const int cls = flag2idx(target->player.m_class);
	if (target->player.spec && cls > 0 && named_spec(cls, target->player.spec))
		out << " / " << specdata[cls][target->player.spec - 1] << "&+C";
	if (target->player.secondary_class)
		out << " + " << class_names_table[flag2idx(target->player.secondary_class)].ansi
		    << "&+C";
	const int maximum = get_max_circle(target);
	out << " | Max Circle " << maximum << " ]====<&n\n";
	const bool books = shows_book(target);
	std::vector<std::pair<int, string>> entries;
	for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell)
	{
		if (!defined_spell(spell))
			continue;
		const int circle = personal_circle(target, spell);
		if (circle)
			entries.emplace_back(circle, string(skills[spell].name) +
							     (books && in_book(target, spell) ?
								      " [in spellbook]" :
								      ""));
	}
	std::sort(entries.begin(), entries.end(),
		  [](const auto &left, const auto &right)
		  {
			  return left.first != right.first ?
					 left.first < right.first :
					 strcasecmp(left.second.c_str(), right.second.c_str()) < 0;
		  });
	int previous = 0;
	const char *const suffixes[] = { "th", "st", "nd", "rd" };
	for (const auto &[circle, name] : entries)
	{
		if (circle != previous)
			out << "\n&+B" << circle << suffixes[circle <= 3 ? circle : 0]
			    << " CIRCLE:&n\n";
		if (circle <= maximum)
			out << name << "\n";
		else
			out << "&+L" << name << "&n\n";
		previous = circle;
	}
	if (entries.empty())
		out << "\n  No eligible spells for this character's current classes/specialization.\n";
	out << "\n";
	if (!entries.empty() && ch == target)
	{
		if (const char *command = spell_interface_command(target))
			out << "&+W" << command << "&n is your spell interface\n";
	}
	out << "See: &+Wspells <class or specialization>&n | &+Wspells info <spell name>&n\n";
	send_to_char(out.str().c_str(), ch);
}

void catalog(P_char ch, int cls, int spec)
{
	std::ostringstream out;
	const string title = spec ? string(specdata[cls][spec - 1]) + "&n (" +
					     class_names_table[cls].normal + ") : SPECIALIZATION" :
				    string(class_names_table[cls].ansi) + " : BASE CLASS";
	out << heading(title);
	int count = 0;
	bool gained = false;
	for (int circle = 1; circle <= MAX_CIRCLE; ++circle)
	{
		std::vector<int> entries;
		for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell)
			if (defined_spell(spell) && reference_circle(spell, cls, spec) == circle)
				entries.push_back(spell);
		if (entries.empty())
			continue;
		std::sort(entries.begin(), entries.end(), [](int left, int right)
			  { return strcasecmp(skills[left].name, skills[right].name) < 0; });
		out << "&+B  Circle " << circle << "&n\n";
		for (int spell : entries)
		{
			const bool added = spec && !reference_circle(spell, cls, 0);
			out << (added ? "  * " : "  ") << skills[spell].name << "\n";
			gained |= added;
		}
		out << "\n";
		count += entries.size();
	}
	if (!count)
		out << "  No spells assigned. Bard songs and instruments use &+Wskills&n.\n";
	if (spec)
	{
		std::vector<string> lost;
		for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell)
			if (defined_spell(spell) && reference_circle(spell, cls, 0) &&
			    !reference_circle(spell, cls, spec))
				lost.emplace_back(skills[spell].name);
		if (gained)
			out << "&+W  * indicates spells gained from spec.&n"
			    << (lost.empty() ? "\n" : " ");
		if (!lost.empty())
		{
			std::sort(lost.begin(), lost.end(),
				  [](const string &left, const string &right)
				  { return strcasecmp(left.c_str(), right.c_str()) < 0; });
			if (!gained)
				out << "  ";
			out << "&+WSpells lost from base class:&n\n";
			for (const string &name : lost)
				out << "  " << name << "\n";
		}
	}
	out << "\n";
	if (count)
	{
		if (const char *command = default_spell_interface_command(1U << (cls - 1)))
			out << "  &+W" << command << "&n is the default spell interface\n";
	}
	out << "  Details: &+Wspells info <spell name>&n\n";
	send_to_char(out.str().c_str(), ch);
}

void spell_info(P_char ch, int spell)
{
	const auto white = [](int value) { return "&+W" + std::to_string(value) + "&n"; };
	std::ostringstream out;
	out << heading("&+W" + string(skills[spell].name) + "&+C : SPELL INFO")
	    << info_field("Registered aggression", IS_AGG_SPELL(spell) ? "&+RYes&n" : "No")
	    << "\n&+W  Class / specialization availability&n\n";
	// Every class and specialization row is padded to the widest label so the circles
	// line up. A specialization is indented under its class only when that class has
	// a row of its own.
	std::vector<std::pair<string, string>> rows;
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
	{
		const int base = reference_circle(spell, cls, 0);
		if (base)
			rows.push_back({ string("  ") + class_names_table[cls].ansi,
					 "&+cCircle&n " + white(base) });
		for (int spec = 1; spec <= MAX_SPEC; ++spec)
		{
			const int circle = reference_circle(spell, cls, spec);
			if (!named_spec(cls, spec) || circle == base)
				continue;
			rows.push_back({ string(base ? "    " : "  ") + specdata[cls][spec - 1] +
						 "&n (" + class_names_table[cls].normal + ")",
					 circle ?
						 "&+cCircle&n " + white(circle) + "&+L" +
							 (base ? " (changed)" : " (added)") + "&n" :
						 "&+rUnavailable&n&+L (lost from base class)&n" });
		}
	}
	size_t width = 0;
	for (const auto &row : rows)
		width = std::max(width, strip_ansi(row.first.c_str()).size());
	for (const auto &row : rows)
		out << pad_ansi(row.first.c_str(), static_cast<int>(width)) << " " << row.second
		    << "\n";
	if (rows.empty())
		out << "&+L  No ordinary class/specialization grants.&n\n";
	out << "&+L  Unlisted specializations inherit the listed base-class behavior.&n\n"
	       "\n&+W  Your access&n\n";
	const int circle = personal_circle(ch, spell);
	const int maximum = get_max_circle(ch);
	out << info_field("Current maximum Circle", white(maximum));
	if (circle)
	{
		out << info_field("Your required Circle", white(circle))
		    << info_field("Circle requirement",
				  circle <= maximum ? "&+Gmet&n" : "&+Ynot yet met&n");
		if (shows_book(ch))
			out << info_field("Spellbook (inventory, hands, belt)",
					  in_book(ch, spell) ? "&+Gpresent&n" : "&+Ynot found&n");
	}
	else
		out << "&+L  Not available through your current classes/specialization.&n\n";
	out << "&+L  Class/circle access and book presence do not establish readiness to "
	       "cast.&n\n";
	if (AbilityFacts facts = ability_facts(spell))
		out << mechanics_section(facts(ch));
	out << "\n&+W  Helpfile details&n\n" << wiki_help_single(skills[spell].name) << "\n";
	send_to_char(out.str().c_str(), ch);
}

void all_spells(P_char ch)
{
	std::ostringstream out;
	out << heading("BASE-CLASS CIRCLE REFERENCE")
	    << "  IDs and registered aggression; assignments are base-class Circles.\n"
	       "  Specialization grants/changes: spells info <name> or spells <spec>.\n\n";
	for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		out << "  " << class_names_table[cls].code << " = " << class_names_table[cls].normal
		    << "\n";
	std::vector<int> entries;
	for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell)
		if (defined_spell(spell))
			entries.push_back(spell);
	std::sort(entries.begin(), entries.end(), [](int left, int right)
		  { return strcasecmp(skills[left].name, skills[right].name) < 0; });
	for (int spell : entries)
	{
		out << "\n  [" << spell << "] " << skills[spell].name
		    << (IS_AGG_SPELL(spell) ? " &+RAGGR&n" : "") << "\n";
		string line = "    ";
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		{
			const int circle = reference_circle(spell, cls, 0);
			if (!circle)
				continue;
			const string assignment = string(class_names_table[cls].code) + "(" +
						  std::to_string(circle) + ") ";
			if (line.size() + assignment.size() > 78)
			{
				out << line << "\n";
				line = "    ";
			}
			line += assignment;
		}
		out << (line == "    " ?
				"    No base-class grant; see info for specialization access." :
				line)
		    << "\n";
	}
	send_to_char(out.str().c_str(), ch);
}
} // namespace

void do_spells(P_char ch, char *argument, int /*cmd*/)
{
	if (IS_NPC(ch))
		return;
	char option[MAX_INPUT_LENGTH];
	char *rest = one_argument(argument, option);
	const string name = trim(argument, " \t\r\n");
	const string detail = trim(rest ? rest : "", " \t\r\n");
	if (name.empty())
	{
		personal_spells(ch, ch);
		return;
	}
	if (is_abbrev(option, "info"))
	{
		std::vector<int> ids;
		std::vector<string> names;
		for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell)
			if (public_spell(spell) || (IS_TRUSTED(ch) && defined_spell(spell)))
			{
				ids.push_back(spell);
				names.emplace_back(skills[spell].name);
			}
		const int found = match_name(ch, detail, names);
		if (found >= 0)
			spell_info(ch, ids[found]);
		else if (found == -1)
		{
			send_to_char("Provide a known spell name. Example: spells info fireball\n",
				     ch);
			usage(ch);
		}
		return;
	}
	if (is_abbrev(option, "all"))
	{
		if (!IS_TRUSTED(ch))
			send_to_char("The global spell catalog is for staff only.\n", ch);
		else if (!detail.empty())
			usage(ch);
		else
			all_spells(ch);
		return;
	}
	const bool explicit_target = !strcmp(option, "target");
	if (!explicit_target)
	{
		std::vector<std::pair<int, int>> paths;
		std::vector<string> names;
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		{
			if (cls != flag2idx(CLASS_ASSASSIN) && cls != flag2idx(CLASS_THIEF))
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
		const int found = match_name(ch, name, names);
		if (found == -2)
			return;
		if (found >= 0)
		{
			catalog(ch, paths[found].first, paths[found].second);
			return;
		}
	}
	if (IS_TRUSTED(ch))
	{
		const string target_name = explicit_target ? detail : name;
		if (target_name.empty() || target_name.find_first_of(" \t") != string::npos)
		{
			send_to_char("Provide one visible character name: spells target <name>\n",
				     ch);
			usage(ch);
			return;
		}
		P_char target = get_char_vis(ch, target_name.c_str());
		if (target)
		{
			personal_spells(ch, target);
			return;
		}
		send_to_char("No such visible character or class/specialization.\n", ch);
	}
	else
		send_to_char(
			"No such class/specialization. Inspecting other characters is staff-only.\n",
			ch);
	usage(ch);
}
