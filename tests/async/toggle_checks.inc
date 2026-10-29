static void toggle_matrix()
{
	char_data ch{};
	pc_only_data pc{};
	descriptor_data desc{};
	ch.only.pc = &pc;
	ch.desc = &desc;
	desc.character = &ch;
	ch.specials.position = POS_STANDING + STAT_NORMAL;
	ch.in_room = NOWHERE;
	ch.player.racewar = RACEWAR_GOOD;
	char name[] = "ToggleFixture";
	ch.player.name = name;
	auto run = [&](std::string argument)
	{
		do_toggle(&ch, argument.data(), 0);
		return plain_text(drain(&desc));
	};
	struct Preference
	{
		const char *name;
		int bank;
		unsigned flag;
		bool inverted;
		const char *label, *off, *on;
	};
	const Preference preferences[] = {
		{ "brief", 0, PLR_BRIEF, false, "BriefMode", "mode off", "mode on" },
		{ "compact", 0, PLR_COMPACT, false, "CompactMode", "mode off", "mode on" },
		{ "who", 0, PLR_WHO, false, "WhoNotices", "no longer", "now see" },
		{ "vicious", 0, PLR_VICIOUS, false, "Vicious", "mode off", "will kill" },
		{ "tell", 0, PLR_NOTELL, true, "Tell", "deaf", "hear" },
		{ "names", 0, PLR_NAMES, false, "Names", "blind", "spammed" },
		{ "gcc", 0, PLR_GCC, false, "GuildChat", "deaf", "hear" },
		{ "shout", 0, PLR_NOSHOUT, true, "Shout", "deaf", "hear" },
		{ "anonymous", 0, PLR_ANONYMOUS, false, "Anonymous", "no longer", "now Anonymous" },
		{ "petition", 0, PLR_PETITION, false, "Petition", "deaf", "hear" },
		{ "paging", 0, PLR_PAGING_ON, false, "Paging", "mode off", "into Paging" },
		{ "echo", 0, PLR_ECHO, false, "Echo", "turn off", "on." },
		{ "aggimmunity", 0, PLR_AGGIMMUNE, false, "Agg", "WILL attack", "will not attack" },
		{ "savenotify", 0, PLR_SNOTIFY, false, "SaveNotify", "no longer", "now get" },
		{ "wizmessages", 0, PLR_WIZMUFFED, true, "Wmsg", "no longer hear", "tune into" },
		{ "wizlog", 0, PLR_WIZLOG, false, "Wlog", "turn off", "tune into" },
		{ "status", 0, PLR_STATUS, false, "Stat", "turn off", "tune into" },
		{ "vnum", 0, PLR_VNUM, false, "Vnum", "off", "on" },
		{ "fog", 0, PLR_MORTAL, false, "Fog", "rose colored", "clouded" },
		{ "map", 0, PLR_MAP, false, "Map", "maps off", "will be shown" },
		{ "debug", 0, PLR_DEBUG, false, "Debug", "off", "on" },
		{ "oldsmartprompt", 0, PLR_OLDSMARTP, false, "OldSmartP", "off", "on" },
		{ "ban", 0, PLR_BAN, false, "Ban", "off", "on" },
		{ "logmsg", 0, PLR_PLRLOG, false, "Logmsg", "off", "on" },
		{ "nolocate", 1, PLR2_NOLOCATE, false, "NoLocate", "off", "on" },
		{ "titles", 1, PLR2_NOTITLE, true, "ShowTitles", "no longer see", "now see" },
		{ "battle", 1, PLR2_BATTLEALERT, true, "BattleAlert", "off", "on" },
		{ "shipmap", 1, PLR2_SHIPMAP, false, "ShipMap", "no longer see", "now see" },
		{ "take", 1, PLR2_NOTAKE, true, "Take", "no longer accept", "now accept" },
		{ "terse", 1, PLR2_TERSE, false, "TerseBattle", "disabled", "enabled" },
		{ "quickchant", 1, PLR2_QUICKCHANT, false, "QuickChant", "disabled", "enabled" },
		{ "rwc", 1, PLR2_RWC, false, "RacewarChat", "not hear", "tune into" },
		{ "project", 1, PLR2_PROJECT, false, "Project", "ignore", "listen" },
		{ "afk", 0, PLR_AFK, false, "AFK", "no longer", "now AFK" },
		{ "nchat", 1, PLR2_NCHAT, false, "NChat", "OFF", "ON" },
		{ "damage", 1, PLR2_DAMAGE, false, "Damage", "OFF", "ON" },
		{ "heal", 1, PLR2_HEAL, false, "Heal", "OFF", "ON" },
		{ "groupneeded", 1, PLR2_LGROUP, false, "GroupNeeded", "OFF", "ON" },
		{ "experience", 1, PLR2_EXP, false, "Experience", "OFF", "ON" },
		{ "showspec", 1, PLR2_SPEC, false, "Showspec", "OFF", "ON" },
		{ "hint", 1, PLR2_HINT_CHANNEL, false, "HintChannel", "OFF", "ON" },
		{ "acc", 1, PLR2_ACC, false, "AllianceChat", "no longer see", "now see" },
		{ "quest", 1, PLR2_SHOW_QUEST, false, "ShowQuests", "no longer show", "will show" },
		{ "newbie", 1, PLR2_NEWBIEEQ, false, "NewbieEQ", "not load", "now load" },
		{ "beep", 2, PLR3_NOBEEP, true, "Beep", "can not", "can be" },
		{ "underline", 2, PLR3_UNDERLINE, false, "Underline", "blinking instead",
		  "underlined instead" },
		{ "surname", 2, PLR3_SURNAMES, false, "Surname", "not see", "will see" },
		{ "nolevel", 2, PLR3_NOLEVEL, false, "NoLevel", "will level", "will not level" },
		{ "epic", 2, PLR3_EPICWATCH, false, "Epic", "turn off", "tune into" },
		{ "petdamage", 2, PLR3_PET_DAMAGE, false, "PetDamage", "turn off", "turn on" },
		{ "guildname", 2, PLR3_GUILDNAME, false, "Guildname", "turn off", "turn on" },
		{ "gmcp", 2, PLR3_NOGMCP, true, "GMCP", "disabled", "enabled" },
		{ "jchat", 2, PLR3_JESTROS, true, "Jchat", "OFF", "ON" },
		{ "abort", 2, PLR3_ABORT_CASTING, false, "AbortCast", "disabled", "enabled" },
	};
	unsigned *banks[] = { &ch.specials.act, &ch.specials.act2, &ch.specials.act3 };
	const std::array<unsigned, 3> unrelated{ PLR_MAIL, PLR2_HARDCORE_CHAR,
						 PLR3_CHAOS_STARTER_EPIC_PENDING };
	for (const auto &preference : preferences)
	{
		ch.player.level = !strcmp(preference.name, "anonymous") ||
						  !strcmp(preference.name, "groupneeded") ?
					  40 :
					  FORGER;
		if (!strcmp(preference.name, "who"))
			ch.player.level = 2;
		for (bool initial : { false, true })
			for (const char *value : { "", "on", "off", "yes", "no", "1", "0", "true",
						   "false", "ON", "OFF", "  on  ", "off\t", "   " })
			{
				for (int bank = 0; bank < 3; ++bank)
					*banks[bank] = unrelated[bank];
				if (initial != preference.inverted)
					*banks[preference.bank] |= preference.flag;
				const bool bare = !*value || !strcmp(value, "   ");
				const bool enabled = bare ? !initial :
							    !strcmp(value, "on") ||
								     !strcmp(value, "yes") ||
								     !strcmp(value, "1") ||
								     !strcmp(value, "true") ||
								     !strcmp(value, "ON") ||
								     !strcmp(value, "  on  ");
				for (int repeat = 0; repeat < (bare ? 1 : 2); ++repeat)
				{
					const int initial_states = gmcp_initial_states;
					const auto output =
						run(std::string(preference.name) + " " + value);
					assert(gmcp_initial_states ==
					       initial_states + (!strcmp(preference.name, "gmcp") &&
										 enabled ?
									 1 :
									 0));
					if (output.find(enabled ? preference.on : preference.off) ==
					    std::string::npos)
						fprintf(stderr, "toggle %s %s: %s", preference.name,
							value, output.c_str());
					assert(output.find(enabled ? preference.on :
								     preference.off) !=
					       std::string::npos);
					for (int bank = 0; bank < 3; ++bank)
						assert(*banks[bank] ==
						       (unrelated[bank] |
							((bank == preference.bank &&
							  enabled != preference.inverted) ?
								 preference.flag :
								 0u)));
					std::string status = run("");
					status.erase(std::remove_if(status.begin(), status.end(),
								    [](unsigned char c)
								    { return isspace(c); }),
						     status.end());
					assert(status.find(std::string(preference.label) + ":" +
							   (enabled ? "ON" : "OFF")) !=
					       std::string::npos);
				}
				for (const char *invalid :
				     { "invalid", "on extra", "off extra", "true false" })
				{
					const std::array<unsigned, 3> before{ *banks[0], *banks[1],
									      *banks[2] };
					assert(run(std::string(preference.name) + " " + invalid)
						       .find("boolean flag needed") !=
					       std::string::npos);
					for (int bank = 0; bank < 3; ++bank)
						assert(*banks[bank] == before[bank]);
				}
			}
	}
	ch.specials.act = ch.specials.act2 = ch.specials.act3 = 0;
	ch.player.level = 40;
	for (const auto &[alias, canonical] :
	     std::vector<std::pair<const char *, const char *>>{ { "no-locate", "nolocate" },
								 { "no locate", "nolocate" },
								 { "group-needed", "groupneeded" },
								 { "group needed", "groupneeded" },
								 { "no-level", "nolevel" },
								 { "no level", "nolevel" },
								 { "save notify", "savenotify" },
								 { "ship map", "shipmap" },
								 { "show titles", "titles" },
								 { "hint channel", "hint" },
								 { "battle alert", "battle" } })
		for (const char *value : { "", "on", "off" })
		{
			ch.specials.act = ch.specials.act2 = ch.specials.act3 = 0;
			const auto expected = run(std::string(canonical) + " " + value);
			const std::array<unsigned, 3> flags{ *banks[0], *banks[1], *banks[2] };
			ch.specials.act = ch.specials.act2 = ch.specials.act3 = 0;
			assert(run(std::string(alias) + " " + value) == expected);
			for (int bank = 0; bank < 3; ++bank)
				assert(*banks[bank] == flags[bank]);
		}
	ch.specials.act = ch.specials.act2 = ch.specials.act3 = 0;
	const auto options = run("?");
	std::istringstream option_stream(options);
	std::vector<std::string> option_words;
	for (std::string word; option_stream >> word;)
		option_words.push_back(word);
	assert(options.find("experience") != std::string::npos &&
	       options.find("toggle color") != std::string::npos);
	for (const char *inactive :
	     { "wimpy", "smartprompt", "zzxyzz", "spec1", "spec2", "spec3", "spec4", "spec_timer" })
	{
		assert(std::find(option_words.begin(), option_words.end(), inactive) ==
		       option_words.end());
		pc.wimpy = 73;
		const auto output = run(std::string(inactive) + " on");
		assert(output.find("disabled") != std::string::npos ||
		       output.find("unavailable") != std::string::npos ||
		       output.find("no longer available") != std::string::npos);
		assert(!ch.specials.act && !ch.specials.act2 && !ch.specials.act3 &&
		       pc.wimpy == 73);
	}
	for (const char *staff : { "names", "aggimmunity", "wizmessages", "wizlog", "status",
				   "vnum", "fog", "debug", "ban", "logmsg", "epic" })
	{
		assert(std::find(option_words.begin(), option_words.end(), staff) ==
		       option_words.end());
		assert(!run(std::string(staff) + " on").empty());
		assert(!ch.specials.act && !ch.specials.act2 && !ch.specials.act3);
	}
	for (const char *value : { "", "0", "default", "off", "DEFAULT  " })
	{
		pc.screen_length = 31;
		assert(run(std::string("screensize ") + value).find("default") !=
		       std::string::npos);
		assert(pc.screen_length == DEFAULT_SCREEN_LENGTH);
	}
	for (int length : { 12, 24, 48 })
	{
		run("screensize " + std::to_string(length));
		assert(pc.screen_length == length);
	}
	for (const char *invalid : { "banana", "-1", "11", "49", "24junk", "24 30",
				     "9999999999999999999999999999999999", "on" })
	{
		pc.screen_length = 31;
		assert(run(std::string("screensize ") + invalid).find("12-48") !=
		       std::string::npos);
		assert(pc.screen_length == 31);
	}
	for (const auto &[value, type] : std::vector<std::pair<const char *, int>>{
		     { "GEN", 1 }, { "ansi  ", 2 }, { "msp\t", 3 } })
	{
		desc.msp_group_output = str_dup("previous group display");
		desc.last_group_update = 0;
		run(std::string("terminal ") + value);
		assert(desc.term_type == type);
		assert(!desc.msp_group_output);
		assert(desc.last_group_update == (type == TERM_MSP));
	}
	for (const char *invalid : { "invalid", "ansi extra" })
	{
		desc.msp_group_output = str_dup("previous group display");
		assert(run(std::string("terminal ") + invalid).find("USAGE") != std::string::npos);
		assert(desc.term_type == 3);
		assert(std::string(desc.msp_group_output) == "previous group display");
		FREE(desc.msp_group_output);
	}
	run("terminal");
	assert(desc.term_type == 2);
	run("terminal");
	assert(desc.term_type == 3);

	// Restricted characters can still switch off or recover an inherited setting.
	for (const auto &restriction :
	     std::vector<std::tuple<const char *, int, unsigned, int, unsigned, int>>{
		     { "who", 0, PLR_WHO, 1, 0, RACEWAR_GOOD },
		     { "vicious", 0, PLR_VICIOUS, 40, CLASS_PALADIN, RACEWAR_GOOD },
		     { "anonymous", 0, PLR_ANONYMOUS, FORGER, 0, RACEWAR_GOOD },
		     { "nolocate", 1, PLR2_NOLOCATE, 40, 0, RACEWAR_EVIL },
		     { "nolocate", 1, PLR2_NOLOCATE, 40, 0, RACEWAR_UNDEAD },
		     { "groupneeded", 1, PLR2_LGROUP, 51, 0, RACEWAR_GOOD } })
	{
		const auto &[option, bank, flag, level, character_class, side] = restriction;
		ch.player.level = level;
		ch.player.m_class = character_class;
		ch.player.racewar = side;
		const auto preference = std::find_if(std::begin(preferences), std::end(preferences),
						     [&](const auto &entry)
						     { return !strcmp(entry.name, option); });
		assert(preference != std::end(preferences));
		*banks[bank] = 0;
		assert(run(std::string(option) + " off").find(preference->off) !=
		       std::string::npos);
		assert(!*banks[bank]);
		for (const char *value : { "", "on" })
		{
			run(std::string(option) + " " + value);
			assert(!*banks[bank]);
		}
		*banks[bank] = flag;
		run(std::string(option) + " off");
		assert(!*banks[bank]);
	}
	ch.player.level = 40;
	ch.player.m_class = 0;
	ch.player.racewar = RACEWAR_GOOD;
	for (const char *value : { "", "on", "off", "invalid" })
	{
		ch.specials.act2 = PLR2_BOON;
		assert(run(std::string("boon ") + value).find("automatically") !=
		       std::string::npos);
		assert(ch.specials.act2 == PLR2_BOON);
	}
	// Exercise actual accepted-input handling before the command runs.
	for (const char *input : { "toggle afk", "tog af", "TOGGLE AFK off", "tog afk invalid" })
	{
		ch.specials.act = PLR_AFK;
		ch.specials.timer = 12;
		assert(input_is_afk_toggle(input));
		note_player_input_activity(&desc, input);
		assert(ch.specials.timer == 0 && PLR_FLAGGED(&ch, PLR_AFK));
		char verb[MAX_INPUT_LENGTH];
		std::string line(input);
		const auto output = run(one_argument(line.data(), verb));
		if (strstr(input, "invalid"))
			assert(PLR_FLAGGED(&ch, PLR_AFK) &&
			       output.find("boolean") != std::string::npos);
		else
			assert(!PLR_FLAGGED(&ch, PLR_AFK));
	}
	for (const char *input : { "look", "toggle a", "toggle", "afk", "tell someone hello" })
	{
		ch.specials.act = PLR_AFK;
		assert(!input_is_afk_toggle(input));
		note_player_input_activity(&desc, input);
		assert(!PLR_FLAGGED(&ch, PLR_AFK));
	}
	// Login notices must follow Who, independently of the same bit in act2 (quests).
	char_data joining{};
	pc_only_data joining_pc{};
	joining.only.pc = &joining_pc;
	char joining_name[] = "ArrivingPlayer";
	joining.player.name = joining_name;
	joining.player.racewar = RACEWAR_GOOD;
	joining.player.level = 40;
	ch.player.level = 2;
	descriptor_list = &desc;
	for (bool who : { false, true })
		for (bool quests : { false, true })
			for (int side : { RACEWAR_GOOD, RACEWAR_EVIL })
			{
				ch.specials.act = 0;
				ch.specials.act2 = quests ? PLR2_SHOW_QUEST : 0;
				ch.player.racewar = side;
				run(who ? "who on" : "who off");
				login_notice(&joining);
				assert((drain(&desc).find("has just logged on") !=
					std::string::npos) == (who && side == RACEWAR_GOOD));
			}
	descriptor_list = nullptr;
	// A morphed character changes the owning player's flags and receives errors.
	char_data body{};
	npc_only_data npc{};
	body.only.npc = &npc;
	npc.orig_char = &ch;
	body.specials.act = ACT_ISNPC;
	body.desc = &desc;
	desc.character = &body;
	morphed = &body;
	ch.specials.act2 = PLR2_NOTITLE;
	char titles[] = "titles on";
	do_toggle(&body, titles, 0);
	assert(drain(&desc).find("now see player titles") != std::string::npos);
	assert(!PLR2_FLAGGED(&ch, PLR2_NOTITLE) && !body.specials.act2);
	char invalid[] = "titles invalid";
	do_toggle(&body, invalid, 0);
	assert(drain(&desc).find("boolean flag needed") != std::string::npos);
	for (const char *option : { "fog on", "debug on" })
	{
		std::string argument(option);
		do_toggle(&body, argument.data(), 0);
		assert(drain(&desc).find("Return to your own body") != std::string::npos);
	}
	morphed = nullptr;
	do_toggle(&body, titles, 0);
	assert(drain(&desc).empty() && !body.specials.act2);
	desc.character = &ch;
	delete GET_PLAYER_LOG(&ch);
	GET_PLAYER_LOG(&ch) = nullptr;
	puts("Toggles: 54 boolean preferences, status/feedback, aliases, permissions, numeric settings, retired options and AFK input passed");
}
