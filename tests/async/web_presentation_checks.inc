static size_t presentation_allocations, presentation_fail_at;
static void *presentation_malloc(size_t bytes)
{
	return ++presentation_allocations == presentation_fail_at ? nullptr : malloc(bytes);
}

static void web_presentation_matrix()
{
	cJSON *fixtures = cJSON_CreateArray();
	assert(fixtures);
	char_data player{};
	pc_only_data pc{};
	descriptor_data d{};
	player.only.pc = &pc;
	player.desc = &d;
	d.character = &player;
	d.websocket = d.gmcp_enabled = 1;
	d.connected = CON_PLAYING;
	d.term_type = TERM_ANSI;
	d.gmcp_supports = GMCP_SUPPORT_LINKS;
	SET_BIT(player.specials.act, PLR_COMPACT | PLR_SMARTPROMPT);
	const string text = "😀 &+cweather&n & <literal> https://example.test/?x=1&name=two\n";
	OutputLinks links{ { text.find("weather"), text.find("weather") + 7,
			     OutputLinkKind::Command, "help weather" } };
	OutputContext context;
	context.links = links;
	websocket_packets.clear();
	send_to_char("\n", &player, LOG_NONE);
	send_to_char(text.c_str(), &player, LOG_NONE, context);
	send_to_char(string(2000, 'x').c_str(), &player, LOG_NONE);
	assert(d.output.head != d.output.tail && process_output(&d) == 1);
	assert(websocket_packets[&d].size() == 1 && !d.output.head);
	cJSON *root = cJSON_Parse(websocket_packets[&d][0].c_str());
	assert(root);
	assert(cJSON_AddItemToArray(fixtures, cJSON_Duplicate(root, true)));
	auto field = [&](const char *key) { return cJSON_GetObjectItem(root, key); };
	assert(string(cJSON_GetStringValue(field("type"))) == "text");
	assert(string(cJSON_GetStringValue(field("category"))) == "info");
	auto *snapshot = field("presentation");
	assert(snapshot && cJSON_GetObjectItem(snapshot, "version")->valueint == 1);
	string terminal = observe_mxp(cJSON_GetStringValue(field("data"))).first;
	terminal.erase(std::remove(terminal.begin(), terminal.end(), '\r'), terminal.end());
	assert(terminal == cJSON_GetStringValue(cJSON_GetObjectItem(snapshot, "text")));
	auto *annotations = cJSON_GetObjectItem(snapshot, "links");
	assert(cJSON_GetArraySize(annotations) == 2);
	auto *help = cJSON_GetArrayItem(annotations, 0);
	assert(cJSON_GetObjectItem(help, "start")->valueint == 3); // prefix LF + emoji + space
	assert(cJSON_GetObjectItem(help, "end")->valueint == 10);
	assert(string(cJSON_GetStringValue(cJSON_GetObjectItem(help, "target"))) == "help weather");
	auto *url = cJSON_GetArrayItem(annotations, 1);
	assert(string(cJSON_GetStringValue(cJSON_GetObjectItem(url, "target"))) ==
	       "https://example.test/?x=1&name=two");
	cJSON_Delete(root);

	for (bool control : { false, true })
	{
		websocket_packets.clear();
		send_to_char(text.c_str(), &player, LOG_NONE, context);
		auto *head = d.output.head;
		d.prompt_mode = true;
		if (control)
			d.ws_control_output_len = 10;
		else
			d.ws_output_len = 10;
		assert(process_output(&d) == 1 && d.output.head == head && d.prompt_mode &&
		       websocket_packets[&d].empty());
		d.ws_control_output_len = d.ws_output_len = 0;
		d.prompt_mode = false;
		assert(process_output(&d) == 1 && !d.output.head &&
		       websocket_packets[&d].size() == 1);
	}
	for (int disabled : { 0, 1, 2 })
	{
		d.gmcp_enabled = disabled != 0;
		d.gmcp_supports = disabled == 1 ? 0 : GMCP_SUPPORT_LINKS;
		if (disabled == 2)
			SET_BIT(player.specials.act3, PLR3_NOGMCP);
		websocket_packets.clear();
		send_to_char(text.c_str(), &player, LOG_NONE, context);
		assert(process_output(&d) == 1 && websocket_packets[&d].empty());
		REMOVE_BIT(player.specials.act3, PLR3_NOGMCP);
	}
	d.gmcp_enabled = 1;
	d.gmcp_supports = GMCP_SUPPORT_LINKS;
	chat_packets.clear();
	OutputChatMessage chat{ "say", "Alice", "[[Weather]] https://example.test/?x=1&name=two" };
	OutputContext styled{ OutputChannel::ChatSay, OutputPolicy::Static, nullptr, ATTR_FG(25) };
	styled.chat = &chat;
	send_to_char(("Alice says '" + chat.text + "'\n").c_str(), &player, LOG_NONE, styled);
	assert(chat_packets.size() == 1);
	root = cJSON_Parse(chat_packets[0].second.c_str());
	assert(root &&
	       string(cJSON_GetStringValue(cJSON_GetObjectItem(root, "text"))) == chat.text);
	snapshot = cJSON_GetObjectItem(root, "bodyPresentation");
	assert(snapshot && cJSON_GetArraySize(cJSON_GetObjectItem(snapshot, "links")) == 1);
	assert(string(cJSON_GetStringValue(cJSON_GetObjectItem(
		       cJSON_GetArrayItem(cJSON_GetObjectItem(snapshot, "links"), 0), "kind"))) ==
	       "url");
	assert(cJSON_GetObjectItem(root, "presentation"));
	assert(cJSON_AddItemToArray(fixtures, cJSON_Duplicate(root, true)));
	cJSON_Delete(root);
	drain(&d);
	chat_packets.clear();
	gmcp_comm_channel_body(&player, "nchat", "Alice", chat.text.c_str(), "good");
	assert(chat_packets.size() == 1);
	root = cJSON_Parse(chat_packets[0].second.c_str());
	assert(cJSON_GetObjectItem(root, "bodyPresentation") &&
	       !cJSON_GetObjectItem(root, "presentation"));
	assert(string(cJSON_GetStringValue(cJSON_GetObjectItem(root, "alignment"))) == "good");
	assert(cJSON_AddItemToArray(fixtures, cJSON_Duplicate(root, true)));
	cJSON_Delete(root);
	chat_packets.clear();

	const auto frame =
		freeze_output_links(text.c_str(), output_links_with_urls(text.c_str(), links));
	for (size_t failure = 1; failure <= 150; ++failure)
	{
		presentation_allocations = 0;
		presentation_fail_at = failure;
		cJSON_Hooks hooks{ presentation_malloc, free };
		cJSON_InitHooks(&hooks);
		char *json = output_text_json("legacy", &frame, false);
		cJSON_InitHooks(nullptr);
		if (!json)
			continue;
		root = cJSON_Parse(json);
		free(json);
		assert(root &&
		       string(cJSON_GetStringValue(cJSON_GetObjectItem(root, "data"))) == "legacy");
		snapshot = cJSON_GetObjectItem(root, "presentation");
		if (snapshot)
			assert(cJSON_GetObjectItem(snapshot, "version") &&
			       cJSON_GetObjectItem(snapshot, "text") &&
			       cJSON_GetObjectItem(snapshot, "runs"));
		cJSON_Delete(root);
	}
	websocket_packets.clear();
	terminal_output.clear();
	if (const char *file = std::getenv("OUTPUT_PRESENTATION_FIXTURE"))
	{
		char *json = cJSON_Print(fixtures);
		assert(json);
		std::ofstream(file) << json << '\n';
		free(json);
	}
	cJSON_Delete(fixtures);
	puts("Web output: ordered single envelopes, Unicode offsets, literal text, capability/opt-out, chat layouts, pressure and allocation fallback passed");
}
