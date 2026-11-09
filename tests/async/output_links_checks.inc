// Real send, styling, queue, accumulation and pager bodies are included by the
// integration harness. Only their world/logging/command boundaries are doubles.
static OutputLinkFrame linked_frame(P_desc d)
{
	char text[MAX_STRING_LENGTH];
	OutputLinks links, combined_links;
	std::string combined;
	assert(d->output.head);
	while (get_linked_output(&d->output, text, links))
	{
		const size_t begin = combined.size();
		combined += text;
		append_output_links(combined_links, links, begin, combined.size());
	}
	assert(!d->output.head && !d->output.tail);
	return freeze_output_links(combined.c_str(), combined_links);
}

// Minimal independent MXP observation: tags count only while the wire is in
// secure mode. Locked-mode angle brackets are ordinary visible player text.
static std::pair<std::string, std::vector<std::string>> observe_mxp(const std::string &wire)
{
	std::string visible;
	std::vector<std::string> tags;
	bool secure = false;
	for (size_t i = 0; i < wire.size();)
	{
		if (wire[i] == '\x1b' && i + 1 < wire.size() && wire[i + 1] == '[')
		{
			size_t end = i + 2;
			while (end < wire.size() &&
			       ((wire[end] >= '0' && wire[end] <= '9') || wire[end] == ';'))
				++end;
			assert(end < wire.size());
			if (wire[end] == 'z')
			{
				assert(wire.substr(i, end - i + 1) == "\x1b[1z" ||
				       wire.substr(i, end - i + 1) == "\x1b[7z");
				secure = wire[i + 2] == '1';
			}
			else
				assert(wire[end] == 'm');
			i = end + 1;
		}
		else if (secure && wire[i] == '<')
		{
			const size_t end = wire.find('>', i);
			assert(end != std::string::npos);
			tags.push_back(wire.substr(i + 1, end - i - 1));
			i = end + 1;
		}
		else
		{
			assert(!secure); // No label or untrusted text may remain in secure mode.
			visible += wire[i++];
		}
	}
	assert(!secure);
	return { visible, tags };
}

static void mxp_delivery_matrix()
{
	char_data player{}, snooper{};
	pc_only_data pc{}, spc{};
	descriptor_data d{}, sd{};
	player.only.pc = &pc;
	snooper.only.pc = &spc;
	player.desc = &d;
	snooper.desc = &sd;
	d.character = &player;
	sd.character = &snooper;
	d.connected = sd.connected = CON_PLAYING;
	d.term_type = sd.term_type = TERM_ANSI;
	SET_BIT(player.specials.act, PLR_COMPACT | PLR_SMARTPROMPT);
	SET_BIT(snooper.specials.act, PLR_COMPACT | PLR_SMARTPROMPT);
	const std::string message = "😀 $$ &+cweather&n\n&+r<literal> & ok&n\n";
	const OutputLinks links{ { message.find("weather"), message.find("weather") + 7,
				   OutputLinkKind::Command, "help weather" },
				 { message.find("<literal>"), message.size(), OutputLinkKind::Url,
				   "https://durismud.com/?a=1&b=\"<2>\"" } };
	OutputContext context;
	context.links = links;
	for (bool enabled : { false, true })
		for (bool snoop_enabled : { false, true })
		{
			d.mxp_state = enabled ? MXP_ENABLED : MXP_OFF;
			sd.mxp_state = snoop_enabled ? MXP_ENABLED : MXP_OFF;
			snoop_by_data watching{ &snooper, nullptr };
			d.snoop.snoop_by_list = &watching;
			terminal_output.clear();
			send_to_char(message.c_str(), &player, LOG_NONE, context);
			assert(process_output(&d) == 1);
			assert(process_output(&sd) == 1);
			if (enabled)
			{
				auto [text, tags] = observe_mxp(terminal_output[&d]);
				assert(text.find("😀 $ weather\r\n<literal> & ok") !=
				       std::string::npos);
				assert(tags.size() == 4 &&
				       tags[0] == "SEND HREF=\"help weather\"" &&
				       tags[1] == "/SEND");
				assert(tags[2] ==
				       "A HREF=\"https://durismud.com/?a=1&amp;b=%22%3C2%3E%22\"");
				assert(tags[3] == "/A");
			}
			else
				assert(terminal_output[&d].find("[7z") == std::string::npos &&
				       terminal_output[&d].find("<SEND") == std::string::npos);
			if (snoop_enabled)
			{
				auto [text, tags] = observe_mxp(terminal_output[&sd]);
				assert(text.find("% 😀 $ weather\r\n% <literal> & ok") !=
				       std::string::npos);
				assert(tags.size() == 4 && tags[0] == "SEND HREF=\"help weather\"");
			}
			else
				assert(terminal_output[&sd].find("[7z") == std::string::npos &&
				       terminal_output[&sd].find("<SEND") == std::string::npos);
			d.snoop.snoop_by_list = nullptr;
		}
	// Mudlet does not decode attribute entities. Select quoting independently
	// for each recipient, including a standards-decoding snooper.
	d.mxp_state = sd.mxp_state = MXP_ENABLED;
	snoop_by_data watching{ &snooper, nullptr };
	d.snoop.snoop_by_list = &watching;
	for (const char *client : { "Mudlet", "Mudlet-ArjUI" })
	{
		strlcpy(d.client_name, client, sizeof d.client_name);
		terminal_output.clear();
		send_to_char(message.c_str(), &player, LOG_NONE, context);
		assert(process_output(&d) == 1 && process_output(&sd) == 1);
		assert(observe_mxp(terminal_output[&d]).second[2] ==
		       "A HREF=\"https://durismud.com/?a=1&b=%22%3C2%3E%22\"");
		assert(observe_mxp(terminal_output[&sd]).second[2] ==
		       "A HREF=\"https://durismud.com/?a=1&amp;b=%22%3C2%3E%22\"");
	}
	d.snoop.snoop_by_list = nullptr;
	d.client_name[0] = '\0';
	for (const char *target : { "help O'Brien", "help a\"b", "help a&b" })
	{
		OutputLinks command{ { 0, 5, OutputLinkKind::Command, target } };
		auto [text, tags] =
			observe_mxp(mxp_render_output("label", command, false, TL_BLINK, true));
		assert(text == "label" && tags.size() == 2);
		assert(tags[0].find(target) != std::string::npos);
	}
	// An unrepresentable legacy-client command stays readable and inert.
	for (const char *target : { "help a\"'b", "help <chapter>", "help chapter ]]" })
	{
		OutputLinks command{ { 0, 5, OutputLinkKind::Command, target } };
		auto [text, tags] =
			observe_mxp(mxp_render_output("label", command, false, TL_BLINK, true));
		assert(text == "label" && tags.empty());
	}
	OutputLinks uri{ { 0, 5, OutputLinkKind::Url, "https://example.test/a[1]?x=2&name=two" } };
	assert(observe_mxp(mxp_render_output("label", uri, false, TL_BLINK, true)).second[0] ==
	       "A HREF=\"https://example.test/a%5B1%5D?x=2&name=two\"");
	// The existing greeting uses cursor-forward CSI for its artwork.
	assert(mxp_render_output("a\x1b[12Cb", {}, false, TL_BLINK).find("\x1b[12C") !=
	       std::string::npos);
	for (const char *literal :
	     { "<SEND HREF=\"quit\">literal</SEND>", "\x1b[1z<SEND HREF=\"quit\">literal\x1b[7z",
				    "\x1b[31mcolored\x1b[m", "\xc2\x9b", "\a\b" })
	{
		auto [text, tags] = observe_mxp(mxp_render_output(literal, {}, false, TL_BLINK));
		assert(tags.empty() && !text.empty());
	}
	const std::string multiline = "one\ntwo\nthree";
	OutputLinks spanning{ { 0, multiline.size(), OutputLinkKind::Command, "help lines" } };
	auto [plain, balanced] =
		observe_mxp(mxp_render_output(multiline.c_str(), spanning, false, TL_BLINK));
	assert(plain == "one\r\ntwo\r\nthree" && balanced.size() == 6);
	spanning = { { 0, 1, OutputLinkKind::Command, "help " + std::string(900, 'x') } };
	// Repeated line labels can multiply attribute overhead. A rejected decoration
	// emits all original characters with no partial tag.
	std::string dense;
	for (int i = 0; i < 2000; ++i)
		dense += "x\n";
	spanning[0].end = dense.size();
	auto [fallback, no_tags] =
		observe_mxp(mxp_render_output(dense.c_str(), spanning, true, TL_BLINK));
	assert(no_tags.empty() && fallback.size() == 6000);
	// Send paged output through the actual output loop, then refresh it. The
	// target and terminal text are frozen, with no open tag left on either page.
	pc.screen_length = 12;
	SET_BIT(player.specials.act, PLR_PAGING_ON);
	d.mxp_state = MXP_ENABLED;
	const std::string page_text = dense.substr(0, 100);
	OutputLinks page_link{ { 0, page_text.size(), OutputLinkKind::Command, "help paging" } };
	OutputContext paged;
	paged.links = page_link;
	command_action = [&](P_char recipient) { send_to_char(page_text.c_str(), recipient, LOG_NONE, paged); };
	char command[] = "mxp-paging";
	terminal_output.clear();
	process_with_paging(&player, command);
	assert(d.showstr_count > 1 && process_output(&d) == 1);
	const auto first_page = observe_mxp(terminal_output[&d]);
	assert(!first_page.second.empty() && first_page.second.size() % 2 == 0);
	terminal_output.clear();
	show_string(&d, "r");
	assert(process_output(&d) == 1 && observe_mxp(terminal_output[&d]) == first_page);
	while (d.showstr_count)
	{
		terminal_output.clear();
		show_string(&d, "");
		assert(process_output(&d) == 1);
		const auto page = observe_mxp(terminal_output[&d]);
		assert(!page.second.empty() && page.second.size() % 2 == 0);
	}
	command_action = {};
	terminal_output.clear();
	puts("MXP delivery: real output, independent snoopers, locked text, escaping, line balance and size fallback passed");
}

static void output_links_matrix()
{
	char_data ch{};
	pc_only_data pc{};
	descriptor_data d{};
	ch.only.pc = &pc;
	ch.desc = &d;
	d.character = &ch;
	d.connected = CON_PLAYING;
	pc.screen_length = 12;

	std::string message = "water 😀 $$ &+cwe&+Cather&n";
	OutputLinks links{ { message.find("we"), message.find("&n"), OutputLinkKind::Command,
			     "help weather" } };
	WordColorDictionary words{ { "water", ATTR_FG(25) } };
	OutputContext context{ OutputChannel::Chat, OutputPolicy::Static, &words };
	context.links = links;
	logged.clear();
	send_to_char("intro ", &ch, LOG_NONE);
	send_to_char(message.c_str(), &ch, LOG_PRIVATE, context);
	assert(d.output.head == d.output.tail && d.output.head->links);
	// A producer can release or modify its storage as soon as send returns.
	links[0].target = "help changed";
	write_to_q(" suffix", &d.output, 1);
	auto frame = linked_frame(&d);
	char plain[MAX_STRING_LENGTH];
	frame.text.plain(plain);
	assert(std::string(plain) == "intro water 😀 $ weather suffix");
	assert(frame.links.size() == 1 && frame.links[0].target == "help weather");
	const auto &link = frame.links[0];
	assert(link.begin == AnsiString("intro water 😀 $ ").size());
	assert(link.end == link.begin + 7);
	assert(frame.text.attr(6) == ATTR_FG(25));
	assert(frame.text.attr(link.begin) == ATTR_FG(19));
	assert(frame.text.attr(link.begin + 2) == ATTR_FG(27));
	assert(logged.size() == 1 && logged[0].first == message);
	const OutputLinks dollars{ { 0, 6, OutputLinkKind::Command, "help dollars" } };
	assert(freeze_output_links("$&+r$x", dollars).text.size() == 3);
	const auto generic = freeze_output_links("$&+r$x", dollars, true);
	assert(generic.text.size() == 2 && generic.links[0].begin == 0 &&
	       generic.links[0].end == 2);

	for (const auto &bad : OutputLinks{ { 0, 5, OutputLinkKind::Command, "help a;quit" },
					    { 0, 5, OutputLinkKind::Command, "help a|quit" },
					    { 0, 5, OutputLinkKind::Command, "help a\nquit" },
					    { 0, 5, OutputLinkKind::Command, "help \xc2\x9b" },
					    { 0, 5, OutputLinkKind::Command, "quit" },
					    { 0, 5, OutputLinkKind::Url, "javascript:alert(1)" },
					    { 0, 5, OutputLinkKind::Url, "https://a b" },
					    { 0, 5, OutputLinkKind::Url, std::string(2049, 'a') },
					    { 0, 6, OutputLinkKind::Command, "help bounds" },
					    { 2, 1, OutputLinkKind::Command, "help reversed" } })
	{
		OutputLinks invalid{ bad };
		OutputContext rejected;
		rejected.links = invalid;
		send_to_char("label", &ch, LOG_NONE, rejected);
		auto fallback = linked_frame(&d);
		fallback.text.plain(plain);
		assert(std::string(plain) == "label" && fallback.links.empty());
	}
	OutputLinks overlap{ { 0, 3, OutputLinkKind::Command, "help first" },
			     { 2, 5, OutputLinkKind::Command, "help second" } };
	assert(!valid_output_links(overlap, 5));
	assert(freeze_output_links("label", overlap).links.empty());
	assert(freeze_output_links("\x1b[1zlabel", {}).links.empty());

	OutputLinks bounded;
	for (size_t i = 0; i < OUTPUT_LINK_MAX_COUNT + 1; ++i)
		bounded.push_back({ i, i + 1, OutputLinkKind::Command, "help count" });
	assert(!valid_output_links(bounded, bounded.size()));
	bounded.resize(OUTPUT_LINK_MAX_COUNT);
	assert(valid_output_links(bounded, bounded.size()));
	for (auto &entry : bounded)
		entry.target = "help " + std::string(400, 'x');
	assert(!valid_output_links(bounded, bounded.size()));

	// An over-budget append keeps the accepted metadata and all visible text.
	OutputLinks one{ { 0, 1, OutputLinkKind::Command, "help count" } };
	for (size_t i = 0; i < OUTPUT_LINK_MAX_COUNT + 1; ++i)
		write_linked_output("x", &d.output, one);
	frame = linked_frame(&d);
	assert(frame.text.size() == OUTPUT_LINK_MAX_COUNT + 1);
	assert(frame.links.size() == OUTPUT_LINK_MAX_COUNT);

	// A large queue block cannot coalesce. Dequeue must move exactly its own
	// metadata, and legacy dequeue/disconnect must release it when not consumed.
	std::string large(MAX_INPUT_LENGTH, 'x');
	write_linked_output(large.c_str(), &d.output, one);
	write_linked_output("x", &d.output, one);
	assert(d.output.head != d.output.tail);
	OutputLinks taken;
	assert(get_linked_output(&d.output, plain, taken) && taken.size() == 1);
	assert(get_from_q(&d.output, plain));
	assert(!d.output.head && !d.output.tail);

	// The label crosses pages and UTF-8 boundaries; every page is a valid slice
	// with the same frozen target. Refresh/back never re-resolve it or log again.
	std::string paged = "x";
	for (int i = 0; i < 1500; ++i)
		paged += "😀";
	paged += "\n";
	OutputLinks page_links{ { 0, paged.size(), OutputLinkKind::Command, "help pages" } };
	OutputContext paging;
	paging.links = page_links;
	SET_BIT(ch.specials.act, PLR_PAGING_ON);
	logged.clear();
	command_action = [&](P_char recipient)
	{
		send_to_char("prefix\n", recipient, LOG_NONE);
		send_to_char(paged.c_str(), recipient, LOG_PRIVATE, paging);
	};
	char command[] = "link-fixture";
	process_with_paging(&ch, command);
	assert(d.showstr_count > 1 && d.showstr_links);
	page_links[0].target = "help modified";
	auto first = linked_frame(&d);
	assert(first.links.size() == 1 && first.links[0].target == "help pages");
	show_string(&d, "r");
	auto refresh = linked_frame(&d);
	assert(first.text == refresh.text && first.links[0].begin == refresh.links[0].begin &&
	       first.links[0].end == refresh.links[0].end);
	show_string(&d, "");
	auto second = linked_frame(&d);
	assert(second.links.size() == 1 && second.links[0].target == "help pages");
	show_string(&d, "b");
	assert(linked_frame(&d).text == first.text);
	size_t characters = first.text.size();
	while (d.showstr_count)
	{
		show_string(&d, "");
		auto page = linked_frame(&d);
		for (size_t i = 0; i < page.text.size(); ++i)
			assert(page.text.ch(i) != 0xfffd);
		assert(page.links.size() == 1 && page.links[0].target == "help pages");
		characters += page.text.size();
	}
	assert(characters == AnsiString(("prefix\n" + paged).c_str()).size());
	assert(!d.showstr_head && !d.showstr_vector && !d.showstr_links);
	assert(logged.size() == 1 && logged[0].first == paged);
	command_action = {};
	// Explicit quit and disconnect use the same owned pager teardown.
	page_string_real(&d, paged.data(), page_links);
	drain(&d);
	show_string(&d, "q");
	assert(!d.showstr_links && !d.showstr_head && !d.showstr_vector);
	page_string_real(&d, paged.data(), page_links);
	drain(&d);
	free_paging_data(&d);
	assert(!d.showstr_links && !d.showstr_head && !d.showstr_vector);

	REMOVE_BIT(ch.specials.act, PLR_PAGING_ON);
	page_string_real(&d, paged.data(), page_links);
	assert(linked_frame(&d).links[0].target == "help modified");

	// Final serializer-budget fallback replaces accumulated styled markup with
	// original bytes. The three labels must survive that coordinate conversion.
	SET_BIT(ch.specials.act, PLR_PAGING_ON);
	std::string ampersands(8000, '&');
	OutputLinks amp_links{ { 0, ampersands.size(), OutputLinkKind::Command, "help amp" } };
	OutputContext amps{ OutputChannel::Chat, OutputPolicy::Static, nullptr, ATTR_FG(25) };
	amps.links = amp_links;
	command_action = [&](P_char recipient)
	{
		for (int i = 0; i < 3; ++i)
			send_to_char(ampersands.c_str(), recipient, LOG_NONE, amps);
	};
	process_with_paging(&ch, command);
	frame = linked_frame(&d);
	assert(frame.text.size() == 24000 && frame.links.size() == 3);
	for (size_t i = 0; i < frame.links.size(); ++i)
		assert(frame.links[i].begin == i * 8000 && frame.links[i].end == (i + 1) * 8000);
	assert(!d.showstr_count);
	command_action = {};
	puts("Output links: owned queue/pager spans, styling, Unicode, dollars, limits, replay and cleanup passed");
}
