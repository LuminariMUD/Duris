static void url_output_matrix()
{
	for (const auto &[source, expected] : std::vector<std::pair<string, string>>{
		     { "See https://example.test/p?a=1&name=2&n=3#frag.",
		       "https://example.test/p?a=1&name=2&n=3#frag" },
		     { "(http://example.test/a(b)).", "http://example.test/a(b)" },
		     { "[http://[::1]:8080/a],", "http://[::1]:8080/a" },
		     { "URL:HTTPS://example.test/path?", "HTTPS://example.test/path?" },
		     { "h&+rt&+btps://exa&+gmple.test/p&n?a=1&name=é#part",
		       "https://example.test/p?a=1&name=é#part" },
		     { "https://example.test/?a=1&nåme=2", "https://example.test/?a=1&nåme=2" },
		     { "https://example.test/?a=1&+r=2&=3", "https://example.test/?a=1&+r=2&=3" },
		     { "https://example.test/?a=1&&nn", "https://example.test/?a=1&n" },
		   { "https://example.test/?download&no-cache", "https://example.test/?download&no-cache" },
		     { "https://example.test/a$$b", "https://example.test/a$b" },
		     { "https://example.test/\nnext", "https://example.test/" } })
	{
		std::string frozen;
		const auto links = output_links_with_urls(source.c_str(), {}, &frozen);
		assert(links.size() == 1 && links[0].kind == OutputLinkKind::Url &&
		       links[0].target == expected);
		const char *emitted = frozen.empty() ? source.c_str() : frozen.c_str();
		assert(AnsiString(emitted) == AnsiString(source.c_str()));
		const auto rebased = rebase_output_links(source.c_str(), emitted, links);
		const auto frame = freeze_output_links(emitted, rebased);
		assert(frame.links.size() == 1 && frame.links[0].target == expected);
	}
	for (const char *source :
	     { "ftp://example.test/", "javascript:alert(1)", "bare.example.test",
	       "https:///missing", "http://?missing", "xhttps://example.test/", "http://" })
		assert(output_links_with_urls(source, {}).empty());
	char outside[MAX_STRING_LENGTH];
	AnsiString("https://example.test/?x=1&name=2 end &name=3").plain(outside);
	assert(string(outside) == "https://example.test/?x=1&name=2 end ame=3");
	const string help_label = "[[Weather]] https://example.test/";
	OutputLinks command{ { 12, help_label.size(), OutputLinkKind::Command, "help Weather" } };
	assert(output_links_with_urls(help_label.c_str(), command).size() == 1);
	assert(output_links_with_urls(help_label.c_str(), {}).front().kind == OutputLinkKind::Url);
	const string excessive = "https://example.test/" + string(2500, 'x');
	assert(output_links_with_urls(excessive.c_str(), {}).empty());

	char_data player{};
	pc_only_data pc{};
	descriptor_data d{};
	player.only.pc = &pc;
	player.desc = &d;
	d.character = &player;
	d.connected = CON_PLAYING;
	d.term_type = TERM_ANSI;
	SET_BIT(player.specials.act, PLR_COMPACT | PLR_SMARTPROMPT);
	const string url = "https://example.test/p?a=1&name=2#fragment";
	WordColorDictionary words{ { "example", ATTR_FG(25) } };
	OutputContext style{ OutputChannel::Chat, OutputPolicy::Static, &words };
	for (bool enabled : { false, true })
	{
		d.mxp_state = enabled ? MXP_ENABLED : MXP_OFF;
		terminal_output.clear();
		logged.clear();
		send_to_char(url.c_str(), &player, LOG_PRIVATE, style);
		assert(process_output(&d) == 1);
		const auto [text, tags] = observe_mxp(terminal_output[&d]);
		assert(text == url);
		assert(logged.size() == 1 && logged[0].first == url);
		if (enabled)
			assert(tags ==
			       std::vector<string>(
				       { "A HREF=\"https://example.test/p?a=1&amp;name=2#fragment\"",
					 "/A" }));
		else
			assert(tags.empty());
	}
	d.mxp_state = MXP_ENABLED;
	terminal_output.clear();
	const auto previous_descriptors = descriptor_list;
	descriptor_list = &d;
	send_to_all(url.c_str());
	assert(process_output(&d) == 1 && observe_mxp(terminal_output[&d]).second.size() == 2);
	descriptor_list = previous_descriptors;

	// Coalescing preserves the target inferred from each original send. It must
	// not append an unrelated message's bytes to a URL's destination.
	terminal_output.clear();
	SEND_TO_Q("https://example.test/", &d);
	SEND_TO_Q("unrelated", &d);
	assert(d.output.head == d.output.tail);
	assert(process_output(&d) == 1);
	const auto [combined_text, combined_tags] = observe_mxp(terminal_output[&d]);
	assert(combined_text == "https://example.test/unrelated");
	assert(combined_tags == std::vector<string>({ "A HREF=\"https://example.test/\"", "/A" }));
	write_to_q(url.c_str(), &d.input, 0);
	assert(d.input.head && !d.input.head->links);
	char input[MAX_STRING_LENGTH];
	assert(get_from_q(&d.input, input) && input == url);

	// Long help chunks must freeze the whole destination before slicing. A
	// rejected oversized target cannot reappear as a shorter URL in a chunk.
	output_help_pages = { { { "URL help", string(1900, 'x') + " " + url, "1", "2026-11-09",
				  "Editor" } },
			      { { "Oversized URL", excessive, "1", "2026-11-09", "Editor" } } };
	for (const auto &test :
	     std::vector<std::pair<string, size_t>>{ { "URL help", 2 }, { "Oversized URL", 0 } })
	{
		terminal_output.clear();
		auto query = test.first;
		do_help(&player, query.data(), 0);
		assert(process_output(&d) == 1);
		const auto [text, tags] = observe_mxp(terminal_output[&d]);
		assert(tags.size() == test.second);
		assert(text.find(test.second ? url : excessive) != string::npos);
	}
	output_help_pages.clear();

	const string paged_url = "https://example.test/" + string(1300, 'a') + "?x=1&name=two#part";
	const string expected_tag =
		"A HREF=\"https://example.test/" + string(1300, 'a') + "?x=1&amp;name=two#part\"";
	output_help_pages = { { { "Large URL", string(65536 + 1800, 'x') + "\n" + paged_url,
				 "1", "2026-11-09", "Editor" } } };
	terminal_output.clear();
	char large_query[] = "Large URL";
	do_help(&player, large_query, 0);
	assert(process_output(&d) == 1);
	const auto large = observe_mxp(terminal_output[&d]);
	assert(large.first.find(paged_url) != string::npos && large.second.size() >= 4);
	for (size_t i = 0; i < large.second.size(); i += 2)
		assert(large.second[i] == expected_tag && large.second[i + 1] == "/A");
	output_help_pages.clear();
	SET_BIT(player.specials.act, PLR_PAGING_ON);
	pc.screen_length = 12;
	command_action = [&](P_char recipient)
	{ send_to_char(paged_url.c_str(), recipient, LOG_PRIVATE); };
	char command_input[] = "url-fixture";
	terminal_output.clear();
	logged.clear();
	process_with_paging(&player, command_input);
	assert(d.showstr_count > 1 && process_output(&d) == 1);
	const auto first = observe_mxp(terminal_output[&d]);
	assert(first.second == std::vector<string>({ expected_tag, "/A" }));
	terminal_output.clear();
	show_string(&d, "r");
	assert(process_output(&d) == 1 && observe_mxp(terminal_output[&d]) == first);
	string complete = first.first;
	while (d.showstr_count)
	{
		terminal_output.clear();
		show_string(&d, "");
		assert(process_output(&d) == 1);
		const auto [text, tags] = observe_mxp(terminal_output[&d]);
		assert(tags == std::vector<string>({ expected_tag, "/A" }));
		complete += text;
	}
	assert(complete == paged_url && logged.size() == 1 && logged[0].first == paged_url);
	command_action = {};
	REMOVE_BIT(player.specials.act, PLR_PAGING_ON);

	// Canonical escaping may exceed a queue block although the original news
	// view fits. The existing command accumulator must still accept and page it.
	string dense_url = "https://example.test/?x=1";
	for (int i = 0; i < 470; ++i) dense_url += "&n=x";
	string dense;
	for (int i = 0; i < 25; ++i) dense += dense_url + "\n";
	SET_BIT(player.specials.act, PLR_PAGING_ON);
	bool accepted = false;
	command_action = [&](P_char recipient) { accepted = send_paged_text(recipient, dense, LOG_NONE); };
	terminal_output.clear();
	process_with_paging(&player, command_input);
	assert(accepted && d.showstr_count > 1 && process_output(&d) == 1);
	string dense_visible = observe_mxp(terminal_output[&d]).first;
	while (d.showstr_count)
	{
		terminal_output.clear();
		show_string(&d, "");
		assert(process_output(&d) == 1);
		dense_visible += observe_mxp(terminal_output[&d]).first;
	}
	string dense_expected;
	for (char c : dense) dense_expected += c == '\n' ? "\r\n" : string(1, c);
	assert(dense_visible == dense_expected);
	command_action = {};
	REMOVE_BIT(player.specials.act, PLR_PAGING_ON);

	// Authored delivery resolves profiles but must keep frozen link provenance.
	const string fragment = "https://part";
	OutputLinks fixed{ { 0, fragment.size(), OutputLinkKind::Url, paged_url } };
	auto authored = recipient_output_context(OutputChannel::RoomDescription);
	authored.links = fixed;
	authored.links_prepared = true;
	terminal_output.clear();
	send_authored_output(fragment.c_str(), &player, authored);
	assert(process_output(&d) == 1 &&
	       observe_mxp(terminal_output[&d]).second.front() == expected_tag);
	delete GET_PLAYER_LOG(&player);
	GET_PLAYER_LOG(&player) = nullptr;
	terminal_output.clear();
	puts("URL links: exact shared targets, parameter ampersands/colors/Unicode/dollars, real sends/announcements/help/pager and frozen fragments passed");
}
