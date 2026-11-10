static void colorization_benchmark()
{
	// Real delivery, profile lookup, builder, queue and terminal serialization.
	// Gameplay/visibility/database/socket work is intentionally outside this
	// presentation differential; the harness controls those existing boundaries.
	constexpr size_t recipients = 64;
	std::array<char_data, recipients> players{};
	std::array<pc_only_data, recipients> pcs{};
	std::array<descriptor_data, recipients> descriptors{};
	char name[] = "Reader";
	for (size_t i = 0; i < recipients; ++i)
	{
		players[i].only.pc = &pcs[i];
		players[i].desc = &descriptors[i];
		players[i].player.name = name;
		players[i].player.level = 30;
		descriptors[i].character = &players[i];
		descriptors[i].connected = CON_PLAYING;
		pcs[i].pid = i + 1;
	}
	auto loaded =
		output_profile_registry().reload_file("docs/examples/scenery-profiles-v1.json");
	assert(loaded.ok);
	std::string description;
	while (description.size() < 4096)
		description +=
			"Water from the river passes beneath the forest. Moss grows on stone beside the old path, where trees hide the distant lake. ";
	const std::string chat_text =
		"Meet me beside the river after sunset; the &+gforest&n path is clear. Bring a torch and follow the eastern bank.";
	const std::string link_text = "Read &+cweather&n: https://durismud.com/help?topic=weather";
	const OutputLinks link_spans{
		{ 8, 15, OutputLinkKind::Command, "help weather" },
		{ 19, link_text.size(), OutputLinkKind::Url,
		  "https://durismud.com/help?topic=weather" }
	};
	cJSON_Hooks hooks{ benchmark_json_malloc, std::free };
	cJSON_InitHooks(&hooks);
	std::cout
		<< "scenario,mode,recipients,messages,cpu_us_per_message,wall_us_per_message,allocations_per_message,allocated_bytes_per_message,terminal_bytes_per_message,gmcp_bytes_per_message\n";
	for (const std::string scenario : { "room", "chat", "chat_gmcp", "chat_links", "combat", "links", "links_mxp" })
	{
		const std::string body = chat_text + (scenario == "chat_links" ? " https://example.test/?x=1&name=two" : "");
		for (const std::string mode : { "legacy", "preserve", "static", "animated" })
		{
			if ((mode == "animated" && scenario != "room") || (scenario == "chat_links" && mode == "legacy"))
				continue;
			const bool decorate = mode == "static" || mode == "animated";
			for (size_t i = 0; i < recipients; ++i)
			{
				OutputProfilePreferences pref;
				if (scenario == "room")
					pref.set(OutputChannel::RoomDescription,
						 mode == "animated" ?
							 OutputProfileChoice::Animated :
						 mode == "static" ? OutputProfileChoice::Static :
								    OutputProfileChoice::Preserve);
				else if (decorate)
					pref.set_color(scenario == "combat" ?
							       OutputChannel::CombatIncoming :
							       OutputChannel::ChatTell,
						       ATTR_FG(i % 2 ? 20 : 27));
				pcs[i].output_preferences = pref.state();
				descriptors[i].gmcp_enabled = scenario == "chat_gmcp" || scenario == "chat_links";
				descriptors[i].gmcp_supports = scenario == "chat_links" ? GMCP_SUPPORT_LINKS : 0;
			}
			const size_t batches = scenario == "room" ? 500 : 200;
			const size_t audience = scenario == "room" ? 1 : recipients;
			uint64_t terminal_bytes = 0, gmcp_bytes = 0;
			// Capture vectors retain capacity; per-message queues and frames do not.
			logged.reserve(2);
			chat_packets.reserve(1);
			benchmark_allocations = benchmark_allocated_bytes = 0;
			const auto wall_start = std::chrono::steady_clock::now();
			const auto cpu_start = std::clock();
			benchmark_counting = true;
			for (size_t batch = 0; batch < batches; ++batch)
				for (size_t i = 0; i < audience; ++i)
				{
					auto *ch = &players[i];
					if (scenario == "room")
					{
						if (mode == "legacy")
							send_to_char(description.c_str(), ch,
								     LOG_NONE);
						else
							send_to_char(
								description.c_str(), ch, LOG_NONE,
								recipient_output_context(
									OutputChannel::RoomDescription,
									OutputPolicy::Animated));
					}
					else if (scenario == "links" || scenario == "links_mxp")
					{
						OutputContext context = recipient_output_context(
							OutputChannel::ChatTell,
							decorate ? OutputPolicy::Static : OutputPolicy::Preserve);
						if (mode != "legacy")
							context.links = link_spans;
						else
							context.links_prepared = true; // Explicit plain baseline.
						send_to_char(link_text.c_str(), ch, LOG_NONE, context);
					}
					else if (scenario == "combat")
					{
						const char *text =
							"The goblin hits you hard. [42 damage]\r\n";
						if (mode == "legacy")
							send_to_char(text, ch, LOG_NONE);
						else
							send_to_char(
								text, ch, LOG_NONE,
								recipient_role_context(
									OutputChannel::CombatIncoming,
									OutputRole::Hit));
					}
					else if (mode == "legacy")
					{
						std::string text = "&+WAlice tells you '" +
								   body + "'&N\r\n";
						send_to_char(text.c_str(), ch, LOG_NONE);
						if (scenario == "chat_gmcp" || scenario == "chat_links")
						{
							char *json = json_build_comm_channel(
								"tell", "Alice", body.c_str());
							gmcp_send(ch->desc, "Comm.Channel", json);
							std::free(json);
						}
					}
					else
					{
						PlayerOutputMessage message(
							ch, OutputChannel::ChatTell);
						if (scenario == "chat_gmcp" || scenario == "chat_links")
							message.chat("tell", "Alice",
								     body.c_str());
						message.literal("&+W")
							.entity("Alice", StyleOrigin::Sender)
							.literal("&+W tells you '")
							.body(body)
							.literal("'&N\r\n")
							.send(LOG_NONE);
					}
					char terminal[MAX_STRING_LENGTH];
					if (scenario == "links" || scenario == "links_mxp")
					{
						char markup[MAX_STRING_LENGTH];
						OutputLinks spans;
						while (get_linked_output(&descriptors[i].output, markup, spans))
						{
							if (scenario == "links_mxp")
								terminal_bytes += mxp_render_output(markup, spans, false, TL_BLINK).size();
							else
							{
								auto frame = freeze_output_links(markup, spans);
								assert(frame.links.size() == (mode == "legacy" ? 0 : 2));
								frame.text.term(terminal, TL_BLINK);
								terminal_bytes += strlen(terminal);
							}
						}
					}
					else
					{
						const std::string queued = drain(&descriptors[i]);
						AnsiString(queued.c_str()).term(terminal, TL_BLINK);
						terminal_bytes += strlen(terminal);
					}
					for (auto &packet : chat_packets)
						gmcp_bytes += packet.second.size();
					chat_packets.clear();
					logged.clear();
				}
			benchmark_counting = false;
			const double messages = batches * audience;
			const auto wall_end = std::chrono::steady_clock::now();
			const double cpu_us =
				1e6 * (std::clock() - cpu_start) / CLOCKS_PER_SEC / messages;
			const double wall_us =
				std::chrono::duration<double, std::micro>(wall_end - wall_start)
					.count() /
				messages;
			std::cout << scenario << ',' << mode << ',' << audience << ','
				  << (size_t)messages << ',' << cpu_us << ',' << wall_us << ','
				  << benchmark_allocations / messages << ','
				  << benchmark_allocated_bytes / messages << ','
				  << terminal_bytes / messages << ',' << gmcp_bytes / messages
				  << '\n';
		}
	}
	cJSON_InitHooks(nullptr);
}
