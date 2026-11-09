static void help_output_matrix()
{
	output_help_pages = { { { "help", "Read '''[[Weather]]''' and [[Weather magic]].", "1",
				  "2026-11-09", "Editor" } },
			      { { "Weather", "The weather changes. See [[help]].", "1",
				  "2026-11-09", "Editor" } },
			      { { "Weather magic", "Magical weather.", "1", "2026-11-09",
				  "Editor" } },
			      { { "Alias", "Redirect: Weather", "1", "2026-11-09", "Editor" } },
			      { { "Cycle", "Redirect: Cycle", "1", "2026-11-09", "Editor" } } };
	OutputLinks links;
	for (const char *query : { "", "Weather", "weAther", "magic", "Alias", "Cycle", "missing" })
	{
		const string text = wiki_help(query, &links);
		assert(text == wiki_help(query)); // Prose callers retain the same interface.
		assert(valid_output_links(links, text.size()));
	}
	const auto normal = wiki_help("help", &links);
	assert(links.size() == 2 && links[0].target == "help Weather" &&
	       links[1].target == "help Weather magic");
	assert(normal.substr(links[0].begin, links[0].end - links[0].begin) == "Weather");
	assert(normal.find("'''") == string::npos);
	const auto search = wiki_help("Weather", &links);
	assert(links.size() == 2 && links[0].target == "help help" &&
	       links[1].target == "help Weather magic");
	assert(search.substr(links[1].begin, links[1].end - links[1].begin) == "Weather magic");
	wiki_help("Alias", &links);
	assert(links.size() == 1 && links[0].target == "help help");
	wiki_help("Cycle", &links);
	assert(links.empty());
	output_help_ready = false;
	assert(wiki_help("help", &links).find("unavailable") != string::npos && links.empty());
	output_help_ready = true;

	const string malformed =
		"[[]] [[ ]] [[bad;quit]] [[bad|quit]] [[bad\nquit]] [[bad [[Weather]]]] [[unfinished";
	const string unchanged = dewikify(malformed, &links);
	assert(unchanged == malformed && links.empty());
	assert(dewikify("x ]] y [[ Weather ]]", &links) == "x ]] y &+c Weather &n");
	assert(links.size() == 1 && links[0].target == "help Weather");
	const auto unicode = dewikify("😀 [[主题 😀]]", &links);
	const auto unicode_frame = freeze_output_links(unicode.c_str(), links);
	assert(unicode_frame.links.size() == 1 && unicode_frame.links[0].begin == 2 &&
	       unicode_frame.links[0].target == "help 主题 😀");

	char_data player{};
	pc_only_data pc{};
	descriptor_data d{};
	player.only.pc = &pc;
	player.desc = &d;
	d.character = &player;
	d.connected = CON_PLAYING;
	d.term_type = TERM_ANSI;
	SET_BIT(player.specials.act, PLR_COMPACT | PLR_SMARTPROMPT);
	for (bool enabled : { false, true })
	{
		d.mxp_state = enabled ? MXP_ENABLED : MXP_OFF;
		terminal_output.clear();
		const auto before = attribute_help_calls;
		char query[] = "help";
		do_help(&player, query, 0);
		assert(attribute_help_calls == before + 1 && process_output(&d) == 1);
		if (enabled)
		{
			const auto [text, tags] = observe_mxp(terminal_output[&d]);
			assert(text.find("Read Weather and Weather magic.") != string::npos);
			assert(tags.size() == 4 && tags[0] == "SEND HREF=\"help Weather\"" &&
			       tags[2] == "SEND HREF=\"help Weather magic\"");
		}
		else
			assert(terminal_output[&d].find("<SEND") == string::npos &&
			       terminal_output[&d].find("[7z") == string::npos);
	}

	// Every result in the existing 101-title search fits the metadata budget,
	// including the catalog's maximum title width. Real delivery spans chunks.
	for (int i = 0; i < WIKIHELP_RESULTS_LIMIT + 1; ++i)
	{
		const string title = "bulk" + to_string(i);
		output_help_pages.push_back({ { title + string(256 - title.size(), 'x'), "body",
						"1", "2026-11-09", "Editor" } });
	}
	const auto titles = wiki_help("bulk", &links);
	assert(links.size() == WIKIHELP_RESULTS_LIMIT + 1 &&
	       valid_output_links(links, titles.size()));
	char bulk[] = "bulk";
	terminal_output.clear();
	d.mxp_state = MXP_ENABLED;
	do_help(&player, bulk, 0);
	assert(process_output(&d) == 1);
	const auto [bulk_text, bulk_tags] = observe_mxp(terminal_output[&d]);
	assert(bulk_tags.size() >= 2 * links.size() && bulk_tags.size() % 2 == 0);
	for (const auto &link : links)
	{
		assert(bulk_text.find(link.target.substr(5)) != string::npos);
		assert(std::find(bulk_tags.begin(), bulk_tags.end(),
				 "SEND HREF=\"" + link.target + "\"") != bulk_tags.end());
	}

	// A legal cached page can exceed MAX_STRING_LENGTH. Chunking must retain
	// all visible Unicode text and the final link, even with paging disabled.
	string large, expected;
	for (int i = 0; i < 6000; ++i)
	{
		large += "&+rcafé 😀 &n";
		expected += "café 😀 ";
	}
	large += "[[Weather]]";
	output_help_pages.push_back({ { "Large", large, "1", "2026-11-09", "Editor" } });
	terminal_output.clear();
	char large_query[] = "Large";
	do_help(&player, large_query, 0);
	assert(process_output(&d) == 1);
	const auto [large_text, large_tags] = observe_mxp(terminal_output[&d]);
	assert(large_text.find(expected + "Weather") != string::npos);
	assert(large_tags.size() == 2 && large_tags[0] == "SEND HREF=\"help Weather\"");
	output_help_pages.push_back({ { "Dollars", "", "1", "2026-11-09", "Editor" } });
	const size_t header = AnsiString(wiki_help_single("Dollars").c_str()).size();
	for (bool generic : { false, true })
		for (const char *pair : { "$$", "$&+r$" })
		{
			// Place a pair across the proposed chunk boundary, after the header.
			output_help_pages.back().fields[1] = string(MAX_STRING_LENGTH / 32 - 1 - header, 'x') + pair + " tail";
			d.term_type = generic ? TERM_GENERIC : TERM_ANSI;
			terminal_output.clear();
			char query[] = "Dollars";
			do_help(&player, query, 0);
			assert(process_output(&d) == 1);
			const auto text = observe_mxp(terminal_output[&d]).first;
			const auto dollars = text.find('$');
			assert(dollars != string::npos);
			assert(text.substr(dollars, text.size() - dollars - 2) ==
			       (!generic && string(pair) == "$&+r$" ? "$$ tail" : "$ tail"));
		}
	d.term_type = TERM_ANSI;

	// The production help command also reaches the existing command pager.
	// Mutating the catalog later must not change refresh or subsequent pages.
	string paged;
	for (int i = 0; i < 20; ++i)
		paged += "line [[Weather]]\n";
	output_help_pages.push_back({ { "Paged", paged, "1", "2026-11-09", "Editor" } });
	SET_BIT(player.specials.act, PLR_PAGING_ON);
	pc.screen_length = 12;
	command_action = [&](P_char recipient)
	{
		char query[] = "Paged";
		do_help(recipient, query, 0);
	};
	char command[] = "help Paged";
	terminal_output.clear();
	logged.clear();
	process_with_paging(&player, command);
	assert(d.showstr_count > 1 && process_output(&d) == 1);
	const auto original_logs = logged.size();
	const auto first = observe_mxp(terminal_output[&d]);
	assert(!first.second.empty() && first.second[0] == "SEND HREF=\"help Weather\"");
	output_help_pages.back().fields[1] = "changed [[missing]]";
	terminal_output.clear();
	show_string(&d, "r");
	assert(process_output(&d) == 1 && observe_mxp(terminal_output[&d]) == first);
	while (d.showstr_count)
	{
		terminal_output.clear();
		show_string(&d, "");
		assert(process_output(&d) == 1);
		const auto [text, tags] = observe_mxp(terminal_output[&d]);
		assert(text.find("changed") == string::npos);
		for (size_t i = 0; i < tags.size(); i += 2)
			assert(tags[i] == "SEND HREF=\"help Weather\"" && tags[i + 1] == "/SEND");
	}
	assert(logged.size() == original_logs);
	assert(!d.showstr_head && !d.showstr_links && !d.output.head);
	command_action = {};
	delete GET_PLAYER_LOG(&player);
	GET_PLAYER_LOG(&player) = nullptr;
	terminal_output.clear();
	output_help_pages.clear();
	puts("Help links: real lookup/command/output, references/results/redirects, malformed prose, large pages and frozen paging passed");
}
