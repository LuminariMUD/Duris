/****************************************************************************
 *
 *  File: chat_presentation.c                                   Part of Duris
 *  Usage: serializes chat frames for delivery
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "net/chat_presentation.h"
#include "net/gmcp.h"
#include "core/utils.h"
#include "net/output_presentation.h"
#include "core/json_utils.h"
#include <cjson/cJSON.h>
#include <cstdlib>
#include <cstring>
#include <algorithm>

static void chat_body_presentation(cJSON *root, char_data *recipient, const char *text)
{
	if (!gmcp_links_enabled(recipient->desc) || !text || strlen(text) >= MAX_STRING_LENGTH ||
	    strchr(text, '\x1b'))
		return;
	const auto links = output_links_with_urls(text, {});
	const auto frame = freeze_output_links(text, links);
	cJSON *body = output_presentation_json(frame, PLR3_FLAGGED(recipient, PLR3_UNDERLINE));
	if (body && !cJSON_AddItemToObject(root, "bodyPresentation", body))
		cJSON_Delete(body);
}

static void send_chat(cJSON *root, char_data *recipient)
{
	char *json = cJSON_PrintUnformatted(root);
	if (json)
	{
		gmcp_send(recipient->desc, GMCP_PKG_COMM_CHANNEL, json);
		std::free(json);
	}
	cJSON_Delete(root);
}

void gmcp_comm_channel_body(char_data *recipient, const char *channel, const char *sender,
			    const char *text, const char *alignment)
{
	if (!GMCP_ENABLED(recipient))
		return;
	cJSON *root = json_comm_channel_object(channel, sender, text, alignment);
	if (!root)
		return;
	chat_body_presentation(root, recipient, text);
	send_chat(root, recipient);
}

void gmcp_comm_channel_output(char_data *recipient, const OutputChatMessage &chat,
			      const OutputContext &context, const char *frozen)
{
	if (!GMCP_ENABLED(recipient) || !frozen)
		return;
	const char *canonical = nullptr;
	if (context.channel == OutputChannel::ChatSay && chat.channel == "say")
		canonical = "chat.say";
	else if (context.channel == OutputChannel::ChatTell && chat.channel == "tell")
		canonical = "chat.tell";
	else if (context.channel == OutputChannel::ChatGuild && chat.channel == "gcc")
		canonical = "chat.guild";
	if (!canonical)
		return;

	cJSON *root = json_comm_channel_object(chat.channel.c_str(), chat.sender.c_str(),
					       chat.text.c_str());
	if (!root)
		return;
	chat_body_presentation(root, recipient, chat.text.c_str());

	// Retain the existing full terminal snapshot for adopted profile consumers.
	if (std::strlen(frozen) < MAX_STRING_LENGTH && !std::strchr(frozen, '\x1b') &&
	    output_message_fits_serializers(frozen))
	{
		auto frame = freeze_output_links(frozen, context.links);
		while (!frame.text.empty() && frame.text.ch(frame.text.size() - 1) == '\n')
			frame.text.pop_back();
		for (auto &link : frame.links)
			link.end = std::min(link.end, frame.text.size());
		if (!gmcp_links_enabled(recipient->desc))
			frame.links.clear();
		cJSON *presentation =
			frame.text.size() <= 16384 ?
				output_presentation_json(frame,
							 PLR3_FLAGGED(recipient, PLR3_UNDERLINE)) :
				nullptr;
		if (presentation)
		{
			if (cJSON_AddNumberToObject(presentation, "channelId",
						    (int)context.channel) &&
			    cJSON_AddStringToObject(presentation, "channel", canonical) &&
			    cJSON_AddStringToObject(
				    presentation, "policy",
				    context.policy == OutputPolicy::Preserve ? "preserve" :
				    context.policy == OutputPolicy::Animated ? "animated" :
									       "static") &&
			    cJSON_AddItemToObject(root, "presentation", presentation))
				presentation = nullptr;
			cJSON_Delete(presentation);
		}
	}
	send_chat(root, recipient);
}
