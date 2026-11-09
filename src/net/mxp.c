#include "net/mxp.h"
#include "core/prototypes.h"
#include "net/telnet.h"
#include <algorithm>

void mxp_negotiate(P_desc descriptor)
{
	if (!descriptor || descriptor->websocket || descriptor->mxp_state != MXP_OFF)
		return;
	descriptor->mxp_state = MXP_SENT_DO;
	const unsigned char request[] = { IAC, DO, TELOPT_MXP };
	write_to_descriptor_binary(descriptor, request, sizeof request);
}

void mxp_handle_negotiation(P_desc descriptor, unsigned char command)
{
	if (!descriptor || descriptor->websocket)
		return;
	const auto state = descriptor->mxp_state;
	if (command == WILL || command == DO)
	{
		if (state == MXP_ENABLED)
			return;
		if ((command == WILL && state != MXP_SENT_DO) ||
		    (command == DO && state != MXP_SENT_WILL))
		{
			const unsigned char reply[] = {
				IAC, static_cast<unsigned char>(command == WILL ? DO : WILL),
				TELOPT_MXP
			};
			write_to_descriptor_binary(descriptor, reply, sizeof reply);
		}
		descriptor->mxp_state = MXP_ENABLED;
		const unsigned char enable[] = {
			IAC, SB, TELOPT_MXP, IAC, SE, '\x1b', '[', '7', 'z'
		};
		write_to_descriptor_binary(descriptor, enable, sizeof enable);
	}
	else if (command == WONT && state == MXP_SENT_DO)
	{
		// Clients disagree about the negotiation direction. Try the alternative
		// once after refusal, as in Luminari's protocol implementation.
		descriptor->mxp_state = MXP_SENT_WILL;
		const unsigned char request[] = { IAC, WILL, TELOPT_MXP };
		write_to_descriptor_binary(descriptor, request, sizeof request);
	}
	else if (command == WONT || command == DONT)
	{
		descriptor->mxp_state = MXP_OFF;
		if (state == MXP_ENABLED)
		{
			const unsigned char reply[] = {
				IAC, static_cast<unsigned char>(command == WONT ? DONT : WONT),
				TELOPT_MXP
			};
			write_to_descriptor_binary(descriptor, reply, sizeof reply);
		}
	}
}

namespace
{
std::string attribute(const std::string &value, bool url)
{
	std::string result;
	for (unsigned char c : value)
	{
		// URI targets must survive a legacy terminal's CP437 conversion.
		if (url && c >= 128)
		{
			constexpr char hex[] = "0123456789ABCDEF";
			result += '%';
			result += hex[c >> 4];
			result += hex[c & 15];
			continue;
		}
		switch (c)
		{
		case '&':
			result += "&amp;";
			break;
		case '<':
			result += "&lt;";
			break;
		case '>':
			result += "&gt;";
			break;
		case '"':
			result += "&quot;";
			break;
		case '\'':
			result += "&apos;";
			break;
		default:
			result += c;
			break;
		}
	}
	return result;
}

// Preserve SGR and existing cursor/screen controls, but never let authored ESC[z
// sequences leave locked MXP mode. The link freezer declines raw-ESC metadata.
AnsiString literal_controls(const AnsiString &text)
{
	AnsiString result;
	for (size_t i = 0; i < text.size(); ++i)
	{
		bool safe_csi = false;
		if (text.ch(i) == '\x1b' && text.ch(i + 1) == '[')
		{
			size_t end = i + 2;
			while (end < std::min(text.size(), i + 34) &&
			       ((text.ch(end) >= '0' && text.ch(end) <= '9') ||
				text.ch(end) == ';'))
				++end;
			switch (text.ch(end))
			{
			case 'm': // SGR
			case 'C': // Cursor right/left and absolute position
			case 'D':
			case 'H':
			case 'J': // Clear screen/line
			case 'K':
			case 'r': // Scroll region
			case 's': // Save/restore cursor
			case 'u':
				safe_csi = true;
			}
		}
		if (text.ch(i) == '\x1b' && !safe_csi)
		{
			result.push_back('^' | text.attr(i));
			result.push_back('[' | text.attr(i));
		}
		else if ((text.ch(i) < 32 && text.ch(i) != '\n' && text.ch(i) != '\t' &&
			  text.ch(i) != '\x1b') ||
			 text.ch(i) == 127 || (text.ch(i) >= 0x80 && text.ch(i) <= 0x9f))
			result.push_back('?' | text.attr(i));
		else
			result.push_back(text[i]);
	}
	return result;
}
}

std::string mxp_render_output(const char *markup, std::span<const OutputLink> links,
			      bool plain_terminal, int lastbit)
{
	auto frame = freeze_output_links(markup, links, plain_terminal);
	frame.text = literal_controls(frame.text);
	char buffer[MAX_STRING_LENGTH];
	frame.text.term(buffer, lastbit);
	const std::string fallback = std::string("\x1b[7z") + buffer;
	if (frame.links.empty())
		return fallback;
	std::string result = "\x1b[7z";
	auto emit = [&](size_t begin, size_t end)
	{
		AnsiString part;
		part.assign(frame.text.begin() + begin, frame.text.begin() + end);
		part.term(buffer, lastbit);
		result += buffer;
	};
	size_t position = 0;
	for (const auto &link : frame.links)
	{
		emit(position, link.begin);
		const std::string tag = link.kind == OutputLinkKind::Command ? "SEND" : "A";
		const std::string open = "\x1b[1z<" + tag + " HREF=\"" +
					 attribute(link.target, link.kind == OutputLinkKind::Url) +
					 "\">\x1b[7z";
		const std::string close = "\x1b[1z</" + tag + ">\x1b[7z";
		position = link.begin;
		while (position < link.end)
		{
			// Balance tags on each line, as well as on each independently sent page.
			const size_t begin = position;
			while (position < link.end && frame.text.ch(position) != '\n')
				++position;
			if (begin != position)
			{
				result += open;
				emit(begin, position);
				result += close;
			}
			if (position < link.end)
			{
				emit(position, position + 1);
				++position;
			}
			if (result.size() >= MAX_STRING_LENGTH)
				return fallback;
		}
	}
	emit(position, frame.text.size());
	return result.size() < MAX_STRING_LENGTH ? result : fallback;
}
