/* Personal skill progress and live class/specialization reference catalogs. */
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"
#include "cmd/wikihelp.h"
#include "magic/spells.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <vector>

extern const struct class_names class_names_table[];
extern const char *specdata[][MAX_SPEC];
extern int SortedSkills[];
extern Skill skills[];

namespace
{
bool available(const ClassSkillInfo &data, int spec)
{
	return data.rlevel[spec] > 0 && data.rlevel[spec] <= MAXLVLMORTAL &&
	       data.maxlearn[spec] > 0;
}

bool public_skill(int skill)
{
	if (!(IS_SKILL(skill) || IS_INSTRUMENT_SKILL(skill) || IS_BARD_SONG(skill)) ||
	    !skills[skill].name || !strcmp(skills[skill].name, "Undefined"))
		return false;
	if (IS_EPIC_SKILL(skill))
		return true;
	for (int cls = 0; cls < CLASS_COUNT; ++cls)
		for (int spec = 0; spec <= MAX_SPEC; ++spec)
			if (available(skills[skill].m_class[cls], spec))
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

// Exact names win; abbreviations must identify exactly one public entry.
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
		if (!matches.empty())
			matches += ", ";
		matches += strip_ansi(names[i].c_str());
		found = found == -1 ? static_cast<int>(i) : -2;
	}
	if (found == -2)
		send_to_char_f(ch, "Be more specific. Matching names: %s.\n", matches.c_str());
	return found;
}

string heading(const string &title)
{
	return "\n&+C  >====[ " + title + "&+C ]====<&n\n\n";
}

void usage(P_char ch)
{
	send_to_char(
		"Usage: skills | skills <class or specialization> | skills info <skill name>\n",
		ch);
	if (IS_TRUSTED(ch))
		send_to_char("Staff: skills <target> | skills target <name> | skills levels\n", ch);
}

void personal_skills(P_char ch, P_char target)
{
	std::ostringstream out;
	out << heading(string(GET_NAME(target)) + " : SKILLS");
	if (affected_by_spell(target, SPELL_MENTAL_ANGUISH))
		out << "&=LYYou feel a great disturbance in your skills.&n\n";
	for (int index = 0; index <= MAX_AFFECT_TYPES; ++index)
	{
		const int skill = SortedSkills[index];
		if (!public_skill(skill))
			continue;
		const int level = GET_LVL_FOR_SKILL(target, skill);
		const bool learned_epic = IS_PC(target) && IS_EPIC_SKILL(skill) &&
					  target->only.pc->skills[skill].learned;
		if (!learned_epic && (level <= 0 || level > MAXLVLMORTAL))
			continue;
		out << "  " << pad_ansi(skills[skill].name, 28);
		if (IS_PC(target) && level > GET_LEVEL(target))
		{
			out << " (obtained at level " << level << ")";
			if (IS_TRUSTED(ch))
				out << " [taught "
				    << static_cast<int>(target->only.pc->skills[skill].taught)
				    << ", learned "
				    << static_cast<int>(target->only.pc->skills[skill].learned)
				    << "]";
		}
		else
		{
			const int rating = GET_CHAR_SKILL(target, skill);
			const char *color = "";
			if (IS_EPIC_SKILL(skill))
				color = rating < 100 ? "&+y" : "&+Y";
			else if (IS_PC(target) && rating >= target->only.pc->skills[skill].taught)
				color = "&+W";
			out << " " << color << rating << "&n";
			if (IS_TRUSTED(ch) && IS_PC(target))
				out << " [taught "
				    << static_cast<int>(target->only.pc->skills[skill].taught)
				    << "]";
		}
		out << "\n";
	}
	out << "\n  Reference: &+Wskills <class or specialization>&n | &+Wskills info <skill name>&n\n";
	send_to_char(out.str().c_str(), ch);
}

void catalog(P_char ch, int cls, int spec)
{
	std::vector<int> entries;
	for (int skill = 0; skill <= MAX_AFFECT_TYPES; ++skill)
		if (public_skill(skill) && !IS_EPIC_SKILL(skill) &&
		    available(skills[skill].m_class[cls - 1], spec))
			entries.push_back(skill);
	std::sort(entries.begin(), entries.end(),
		  [cls, spec](int left, int right)
		  {
			  const int a = skills[left].m_class[cls - 1].rlevel[spec];
			  const int b = skills[right].m_class[cls - 1].rlevel[spec];
			  return a != b ? a < b : strcmp(skills[left].name, skills[right].name) < 0;
		  });
	std::ostringstream out;
	const string title = spec ? string(specdata[cls][spec - 1]) + "&n (" +
					     class_names_table[cls].normal + ")" :
				    string(class_names_table[cls].ansi) + " : BASE CLASS";
	out << heading(title) << "  Level  Cap  Skill\n";
	for (int skill : entries)
	{
		char row[256];
		const ClassSkillInfo &data = skills[skill].m_class[cls - 1];
		snprintf(row, sizeof row, "  %5d  %3d  %s\n", data.rlevel[spec],
			 data.maxlearn[spec], skills[skill].name);
		out << row;
	}
	if (entries.empty())
		out << "  No ordinary skills assigned.\n";
	if (spec)
	{
		string lost;
		for (int skill = 0; skill <= MAX_AFFECT_TYPES; ++skill)
		{
			const ClassSkillInfo &data = skills[skill].m_class[cls - 1];
			if (public_skill(skill) && !IS_EPIC_SKILL(skill) && available(data, 0) &&
			    !available(data, spec))
				lost += string(lost.empty() ? "" : ", ") + skills[skill].name;
		}
		if (!lost.empty())
			out << "\n  &+WSkills lost from base class:&n " << lost << "\n";
	}
	out << "\n  Caps are proficiency limits. Epic skills use separate acquisition rules.\n"
	       "  Details: &+Wskills info <skill name>&n\n";
	if (!spec)
	{
		out << "  Specializations:";
		for (int sp = 0; sp < MAX_SPEC; ++sp)
			if (*specdata[cls][sp] && strcmp(specdata[cls][sp], "Not Used"))
				out << "  " << specdata[cls][sp] << "&n";
		out << "\n";
	}
	send_to_char(out.str().c_str(), ch);
}

void skill_info(P_char ch, int skill)
{
	std::ostringstream out;
	out << heading(string(skills[skill].name) + " : SKILL INFO");
	const bool epic = IS_EPIC_SKILL(skill);
	out << "  Type: "
	    << (epic			   ? "Epic skill" :
		IS_INSTRUMENT_SKILL(skill) ? "Instrument" :
		IS_BARD_SONG(skill)	   ? "Bard song" :
					     "Skill")
	    << "\n";
	if (epic)
		out << "  Acquisition: separate epic skill rules; use &+Wepic skills&n and help below.\n";
	else
	{
		out << "\n&+W  Class / specialization       Level  Cap&n\n";
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		{
			const ClassSkillInfo &data = skills[skill].m_class[cls - 1];
			if (available(data, 0))
				out << "  " << pad_ansi(class_names_table[cls].ansi, 29) << " "
				    << static_cast<int>(data.rlevel[0]) << "     "
				    << static_cast<int>(data.maxlearn[0]) << "\n";
			for (int spec = 1; spec <= MAX_SPEC; ++spec)
			{
				if (!*specdata[cls][spec - 1] ||
				    !strcmp(specdata[cls][spec - 1], "Not Used") ||
				    (data.rlevel[spec] == data.rlevel[0] &&
				     data.maxlearn[spec] == data.maxlearn[0]))
					continue;
				if (!available(data, spec) && !available(data, 0))
					continue;
				out << "    " << pad_ansi(specdata[cls][spec - 1], 27) << " ";
				if (available(data, spec))
					out << static_cast<int>(data.rlevel[spec]) << "     "
					    << static_cast<int>(data.maxlearn[spec]);
				else
					out << "Unavailable";
				out << "\n";
			}
		}
		out << "  Unlisted specializations inherit their base class's level and cap.\n";
	}
	const ClassSkillInfo data = SKILL_DATA_ALL(ch, skill);
	const int level = GET_LVL_FOR_SKILL(ch, skill);
	out << "\n&+W  Your progress&n\n  Current rating: " << GET_CHAR_SKILL(ch, skill)
	    << "  Learned: " << static_cast<int>(ch->only.pc->skills[skill].learned)
	    << "  Taught: " << static_cast<int>(ch->only.pc->skills[skill].taught) << "\n";
	if (!epic && available(data, ch->player.spec))
		out << "  Your unlock level: " << level
		    << "  Your cap: " << static_cast<int>(data.maxlearn[ch->player.spec]) << "\n";
	else if (!epic)
		out << "  Not available through your current class/specialization.\n";
	out << "\n&+W  Helpfile details&n\n" << wiki_help_single(skills[skill].name) << "\n";
	send_to_char(out.str().c_str(), ch);
}

void level_table(P_char ch)
{
	std::ostringstream out;
	out << heading("BASE CLASS SKILL LEVELS")
	    << "  Numbers are unlock levels; -- means unavailable. Epic skills are separate.\n";
	for (int first = 1; first <= CLASS_COUNT; first += 6)
	{
		const int last = MIN(first + 5, CLASS_COUNT);
		out << "\n  " << pad_ansi("Skill", 28);
		for (int cls = first; cls <= last; ++cls)
			out << " " << pad_ansi(class_names_table[cls].code, 4);
		out << "\n";
		for (int cls = first; cls <= last; ++cls)
			out << "  " << class_names_table[cls].code << " = "
			    << class_names_table[cls].normal << "\n";
		for (int index = 0; index <= MAX_AFFECT_TYPES; ++index)
		{
			const int skill = SortedSkills[index];
			if (!public_skill(skill) || IS_EPIC_SKILL(skill))
				continue;
			bool any = false;
			for (int cls = first; cls <= last; ++cls)
				any |= available(skills[skill].m_class[cls - 1], 0);
			if (!any)
				continue;
			out << "  " << pad_ansi(skills[skill].name, 28);
			for (int cls = first; cls <= last; ++cls)
			{
				const ClassSkillInfo &data = skills[skill].m_class[cls - 1];
				const string value =
					available(data, 0) ? std::to_string(data.rlevel[0]) : "--";
				out << " " << pad_ansi(value.c_str(), 4);
			}
			out << "\n";
		}
	}
	send_to_char(out.str().c_str(), ch);
}
} // namespace

void do_skills(P_char ch, char *argument, int /*cmd*/)
{
	if (IS_NPC(ch))
		return;
	char option[MAX_INPUT_LENGTH];
	char *rest = one_argument(argument, option);
	const string name = trim(argument, " \t\r\n");
	const string detail = trim(rest ? rest : "", " \t\r\n");
	if (name.empty())
	{
		personal_skills(ch, ch);
		return;
	}
	if (is_abbrev(option, "info"))
	{
		std::vector<int> ids;
		std::vector<string> names;
		for (int skill = 0; skill <= MAX_AFFECT_TYPES; ++skill)
			if (public_skill(skill))
			{
				ids.push_back(skill);
				names.emplace_back(skills[skill].name);
			}
		const int found = match_name(ch, detail, names);
		if (found >= 0)
			skill_info(ch, ids[found]);
		else if (found == -1)
		{
			send_to_char("Provide a known skill name. Example: skills info bash\n", ch);
			usage(ch);
		}
		return;
	}
	if (is_abbrev(option, "levels"))
	{
		if (!IS_TRUSTED(ch))
			send_to_char("The class-level table is for staff only.\n", ch);
		else if (!detail.empty())
			usage(ch);
		else
			level_table(ch);
		return;
	}
	const bool explicit_target = !strcmp(option, "target");
	if (!explicit_target)
	{
		std::vector<std::pair<int, int>> paths;
		std::vector<string> names;
		for (int cls = 1; cls <= CLASS_COUNT; ++cls)
		{
			// Assassin/Thief are current Rogue specs, not their legacy classes.
			if (cls != flag2idx(CLASS_ASSASSIN) && cls != flag2idx(CLASS_THIEF))
			{
				paths.emplace_back(cls, 0);
				names.emplace_back(class_names_table[cls].normal);
			}
			for (int spec = 0; spec < MAX_SPEC; ++spec)
				if (*specdata[cls][spec] && strcmp(specdata[cls][spec], "Not Used"))
				{
					paths.emplace_back(cls, spec + 1);
					names.emplace_back(specdata[cls][spec]);
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
		string target_name = explicit_target ? detail : name;
		P_char target = target_name.empty() ? nullptr :
						      get_char_vis(ch, target_name.data());
		if (target)
		{
			personal_skills(ch, target);
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
