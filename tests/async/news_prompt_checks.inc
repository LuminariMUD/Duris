static void news_prompt_matrix()
{
	char_data actor{}, other{}, body{};
	pc_only_data pc{}, other_pc{};
	npc_only_data npc{};
	descriptor_data desc{};
	actor.only.pc = &pc;
	other.only.pc = &other_pc;
	body.only.npc = &npc;
	body.specials.act = ACT_ISNPC;
	pc.pid = 42;
	other_pc.pid = 43;
	actor.in_room = other.in_room = NOWHERE;
	actor.player.name = writable_arg("Reader");
	actor.desc = &desc;
	desc.character = &actor;
	desc.connected = CON_PLAYING;
	actor.specials.position = STAT_NORMAL;
	actor.points.max_hit = actor.points.max_mana = actor.points.max_vitality = 100;
	pc.prompt = PROMPT_HIT | PROMPT_MOVE;
	const auto prompt = [&]()
	{
		desc.prompt_mode = true;
		make_prompt(&desc);
		return drain(&desc);
	};
	const auto read = [&]()
	{
		command_action = [](P_char ch) { do_news(ch, writable_arg(""), 0); };
		process_with_paging(&actor, writable_arg("news"));
		if (desc.showstr_count)
			show_string(&desc, writable_arg("q"));
		return drain(&desc);
	};
	assert(publish_news("first news\n"));
	assert(has_unread_news(&actor) && has_unread_news(&other));
	assert(prompt().find("(news)") != std::string::npos);
	assert(read().find("tog page on") != std::string::npos && has_unread_news(&actor));
	SET_BIT(actor.specials.act, PLR_PAGING_ON);
	const int before = save_calls;
	assert(read().find("first news") != std::string::npos);
	assert(!has_unread_news(&actor) && has_unread_news(&other));
	assert(saved_owner == &actor && save_calls == before + 1);
	assert(prompt().find("(news)") == std::string::npos);
	read();
	assert(save_calls == before + 1);
	assert(publish_news("first news\n") && !has_unread_news(&actor));
	assert(publish_news("second news\n") && has_unread_news(&actor));
	for (auto rejected :
	     { player_save_pipeline_result::capture_failed,
	       player_save_pipeline_result::unavailable, player_save_pipeline_result::invalid })
	{
		save_result = rejected;
		assert(read().find("try 'news' again") != std::string::npos);
		assert(has_unread_news(&actor));
	}
	save_result = player_save_pipeline_result::coalesced;
	read();
	assert(!has_unread_news(&actor));
	save_result = player_save_pipeline_result::queued;

	// An existing pager owns A even if B is published while it is open.
	std::string pages;
	for (int line = 1; line <= 100; ++line)
		pages += "A" + std::to_string(line) + "\n";
	assert(publish_news(pages));
	pc.screen_length = 2;
	process_with_paging(&actor, writable_arg("news"));
	assert(desc.showstr_count && !has_unread_news(&actor));
	assert(std::string(desc.showstr_head).find("A1") != std::string::npos);
	assert(publish_news("B\n") && has_unread_news(&actor));
	assert(prompt().find("(news)") == std::string::npos);
	show_string(&desc, writable_arg("q"));
	drain(&desc);
	assert(prompt().find("(news)") != std::string::npos);

	for (unsigned mask : { unsigned(PROMPT_HIT), unsigned(PROMPT_HIT | PROMPT_TWOLINE),
			       unsigned(PROMPT_TWOLINE), unsigned(PROMPT_TWOLINE | PROMPT_STATUS) })
	{
		pc.prompt = mask;
		for (int terminal : { TERM_ANSI, TERM_MSP })
		{
			desc.term_type = terminal;
			const auto shown = prompt();
			const auto marker = shown.find("(news)");
			assert(marker != std::string::npos &&
			       shown.find("(news)", marker + 1) == std::string::npos);
			if (terminal == TERM_MSP)
				assert(shown.find("</prompt>", marker) != std::string::npos);
		}
	}
	pc.prompt = 0;
	assert(prompt().empty());
	SET_BIT(actor.specials.act, PLR_SMARTPROMPT);
	assert(prompt().find("(news)") != std::string::npos);
	REMOVE_BIT(actor.specials.act, PLR_SMARTPROMPT);
	pc.prompt = PROMPT_HIT;
	char *editing = nullptr;
	desc.str = &editing;
	assert(prompt() == "] ");
	desc.str = nullptr;
	desc.confirm_state = CONFIRM_AWAIT;
	assert(prompt().empty());
	desc.confirm_state = 0;
	desc.connected = CON_MAIN_MENU;
	assert(prompt().empty());
	desc.connected = CON_PLAYING;
	desc.term_type = TERM_ANSI;

	// The whole body must fit. A prior refused output also prevents acknowledgement.
	assert(publish_news(std::string(MAX_COMMAND_OUTPUT, 'x')));
	assert(read().find("remains unread") != std::string::npos && has_unread_news(&actor));
	const std::string header = "&+WDuris News\n\n";
	assert(publish_news(std::string(MAX_COMMAND_OUTPUT - header.size() - 1, 'x')));
	read();
	assert(!has_unread_news(&actor));
	assert(publish_news("after overflow\n"));
	command_action = [](P_char ch)
	{
		send_to_char(std::string(MAX_COMMAND_OUTPUT, 'x').c_str(), ch);
		do_news(ch, writable_arg(""), 0);
	};
	process_with_paging(&actor, writable_arg("news"));
	if (desc.showstr_count)
		show_string(&desc, writable_arg("q"));
	drain(&desc);
	assert(has_unread_news(&actor));
	// Long NPC names cannot crowd out the marker or MSP closing frame.
	char_data enemy{};
	npc_only_data enemy_npc{};
	std::string long_name(MAX_INPUT_LENGTH, 'e');
	enemy.only.npc = &enemy_npc;
	enemy.specials.act = ACT_ISNPC;
	enemy.player.name = long_name.data();
	enemy.points.hit = enemy.points.max_hit = 100;
	enemy.specials.position = STAT_NORMAL;
	enemy.specials.fighting = &actor;
	actor.specials.fighting = &enemy;
	actor.in_room = enemy.in_room = 0;
	pc.prompt = PROMPT_HIT | PROMPT_ENEMY | PROMPT_ENEMY_COND | PROMPT_STATUS;
	desc.term_type = TERM_MSP;
	const auto crowded = prompt();
	assert(crowded.size() < MAX_INPUT_LENGTH && crowded.find("(news)") != std::string::npos &&
	       crowded.ends_with("&n\n</prompt>\n"));
	actor.specials.fighting = nullptr;
	actor.in_room = NOWHERE;
	pc.prompt = PROMPT_HIT;
	desc.term_type = TERM_ANSI;

	// Ownership and delivery use different bodies while switched or morphed.
	body.desc = &desc;
	desc.character = &body;
	desc.original = &actor;
	assert(prompt().find("(news)") != std::string::npos);
	SET_BIT(body.specials.act, PLR_PAGING_ON);
	command_action = [](P_char ch) { do_news(ch, writable_arg(""), 0); };
	process_with_paging(&body, writable_arg("news"));
	if (desc.showstr_count)
		show_string(&desc, writable_arg("q"));
	drain(&desc);
	assert(!has_unread_news(&body) && saved_owner == &actor);
	desc.original = nullptr;
	morphed = &body;
	npc.orig_char = &actor;
	assert(publish_news("morphed news\n"));
	assert(prompt().find("(news)") != std::string::npos);
	process_with_paging(&body, writable_arg("news"));
	if (desc.showstr_count)
		show_string(&desc, writable_arg("q"));
	drain(&desc);
	assert(!has_unread_news(&body) && saved_owner == &actor);
	morphed = nullptr;
	const int saved = save_calls;
	do_news(&body, writable_arg(""), 0);
	do_news(nullptr, writable_arg(""), 0);
	assert(save_calls == saved && !has_unread_news(&body));
	desc.character = &actor;
	assert(publish_news(""));
	assert(read().find("unavailable") != std::string::npos && save_calls == saved);
	assert(!has_unread_news(&actor));
	for (const std::string &value : { std::string(), std::string(64, 'a'), std::string(63, 'a'),
					  std::string(64, 'G'), std::string("a\0bad", 5) })
	{
		assert(apply_string(&actor,
				    { player_status_string_field::last_read_news_hash, value }));
		assert(std::string(pc.last_read_news_hash) ==
		       (value == std::string(64, 'a') ? value : ""));
	}
	command_action = {};
}
