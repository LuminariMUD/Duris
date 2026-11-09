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
		entry.target = "help " + std::string(200, 'x');
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
