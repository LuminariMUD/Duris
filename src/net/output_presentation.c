#include "net/output_presentation.h"
#include "net/unicode.h"
#include "net/websocket.h"
#include <cjson/cJSON.h>
#include <cstring>
#include <cstdlib>

cJSON *output_presentation_json(const OutputLinkFrame &frame, bool underline)
{
	if (frame.text.size() > OUTPUT_PRESENTATION_MAX_TEXT ||
	    frame.links.size() > OUTPUT_LINK_MAX_COUNT)
		return nullptr;
	size_t previous = 0, targets = 0;
	for (const auto &link : frame.links)
	{
		const OutputLink checked{ link.begin, link.end, link.kind, link.target };
		if (link.begin < previous ||
		    !valid_output_links(std::span(&checked, 1), frame.text.size()))
			return nullptr;
		previous = link.end;
		targets += link.target.size();
	}
	if (targets > OUTPUT_LINK_MAX_TARGET_BYTES)
		return nullptr;
	std::string plain;
	for (size_t i = 0; i < frame.text.size(); ++i)
	{
		const auto c = frame.text.ch(i);
		if ((c < 32 && c != '\n' && c != '\t') || (c >= 127 && c <= 159))
			return nullptr;
		const auto attr = frame.text.attr(i);
		if ((GET_FG(attr) && GET_FG(attr) < 16) || (GET_BG(attr) && GET_BG(attr) < 16))
			return nullptr;
		char bytes[8], *out = bytes;
		put_utf8(out, c);
		plain.append(bytes, out);
	}
	cJSON *root = cJSON_CreateObject();
	auto fail = [&]() -> cJSON *
	{
		cJSON_Delete(root);
		return nullptr;
	};
	if (!root || !cJSON_AddNumberToObject(root, "version", 1) ||
	    !cJSON_AddStringToObject(root, "text", plain.c_str()) ||
	    !cJSON_AddBoolToObject(root, "underline", underline))
		return fail();
	cJSON *runs = cJSON_AddArrayToObject(root, "runs");
	if (!runs)
		return fail();
	size_t count = 0;
	for (size_t begin = 0; begin < frame.text.size();)
	{
		if (++count > 4096)
			return fail();
		size_t end = begin + 1;
		const auto attr = frame.text.attr(begin);
		while (end < frame.text.size() && frame.text.attr(end) == attr)
			++end;
		const int tuple[] = { (int)begin, (int)end, GET_FG(attr), GET_BG(attr) };
		cJSON *run = cJSON_CreateIntArray(tuple, 4);
		if (!run || !cJSON_AddItemToArray(runs, run))
		{
			cJSON_Delete(run);
			return fail();
		}
		begin = end;
	}
	if (!frame.links.empty())
	{
		cJSON *links = cJSON_AddArrayToObject(root, "links");
		if (!links)
			return fail();
		for (const auto &link : frame.links)
		{
			cJSON *item = cJSON_CreateObject();
			if (!item || !cJSON_AddItemToArray(links, item))
			{
				cJSON_Delete(item);
				return fail();
			}
			if (!cJSON_AddNumberToObject(item, "start", link.begin) ||
			    !cJSON_AddNumberToObject(item, "end", link.end) ||
			    !cJSON_AddStringToObject(
				    item, "kind",
				    link.kind == OutputLinkKind::Command ? "command" : "url") ||
			    !cJSON_AddStringToObject(item, "target", link.target.c_str()))
				return fail();
		}
	}
	return root;
}

char *output_text_json(const char *terminal, const OutputLinkFrame *frame, bool underline)
{
	cJSON *root = cJSON_CreateObject();
	if (!root || !cJSON_AddStringToObject(root, "type", "text") ||
	    !cJSON_AddStringToObject(root, "category", "info") ||
	    !cJSON_AddStringToObject(root, "data", terminal))
	{
		cJSON_Delete(root);
		return nullptr;
	}
	cJSON *presentation = frame ? output_presentation_json(*frame, underline) : nullptr;
	if (presentation && !cJSON_AddItemToObject(root, "presentation", presentation))
		cJSON_Delete(presentation);
	char *json = cJSON_PrintUnformatted(root);
	constexpr size_t budget = WS_MAX_OUTPUT_BYTES - WS_CONTROL_OUTPUT_RESERVE - 14;
	if (json && strlen(json) > budget)
	{
		free(json);
		cJSON_DeleteItemFromObject(root, "presentation");
		json = cJSON_PrintUnformatted(root);
	}
	if (json && strlen(json) > budget)
	{
		free(json);
		json = nullptr;
	}
	cJSON_Delete(root);
	return json;
}
