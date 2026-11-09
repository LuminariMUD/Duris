#include "net/output_links.h"
#include "core/prototypes.h"
#include "net/url_text.h"
#include "net/unicode.h"
#include <algorithm>
#include <cstring>

bool valid_output_links(std::span<const OutputLink> links, size_t bytes)
{
	if (links.size() > OUTPUT_LINK_MAX_COUNT)
		return false;
	size_t previous = 0, target_bytes = 0;
	for (const auto &link : links)
	{
		if (link.begin < previous || link.begin >= link.end || link.end > bytes ||
		    link.target.empty())
			return false;
		if (link.kind == OutputLinkKind::Command)
		{
			if (link.target.size() >= MAX_INPUT_LENGTH ||
			    !link.target.starts_with("help ") || link.target.size() == 5 ||
			    link.target.find_first_of(";|") != std::string::npos)
				return false;
		}
		else if (link.kind == OutputLinkKind::Url)
		{
			const size_t scheme =
				output_url_scheme_length(std::string_view(link.target), 0);
			if (link.target.size() > 2048 || !scheme || link.target.size() == scheme ||
			    link.target.find_first_of("/?#", scheme) == scheme)
				return false;
		}
		else
			return false;
		for (size_t i = 0; i < link.target.size(); ++i)
		{
			const auto c = static_cast<unsigned char>(link.target[i]);
			const bool c1 = c == 0xc2 && i + 1 < link.target.size() &&
					static_cast<unsigned char>(link.target[i + 1]) >= 0x80 &&
					static_cast<unsigned char>(link.target[i + 1]) <= 0x9f;
			if (c < 32 || c == 127 || c1 ||
			    (link.kind == OutputLinkKind::Url && c == ' '))
				return false;
		}
		target_bytes += link.target.size();
		if (target_bytes > OUTPUT_LINK_MAX_TARGET_BYTES)
			return false;
		previous = link.end;
	}
	return true;
}

OutputLinks slice_output_links(std::span<const OutputLink> links, size_t begin, size_t end)
{
	OutputLinks result;
	if (begin >= end)
		return result;
	for (const auto &link : links)
		if (link.begin < end && link.end > begin)
			result.push_back({ std::max(begin, link.begin) - begin,
					   std::min(end, link.end) - begin, link.kind,
					   link.target });
	return result;
}

void append_output_links(OutputLinks &output, std::span<const OutputLink> links, size_t offset,
			 size_t bytes)
{
	if (links.empty() || offset > bytes || !valid_output_links(links, bytes - offset))
		return;
	OutputLinks merged = output;
	for (const auto &link : links)
		merged.push_back(
			{ link.begin + offset, link.end + offset, link.kind, link.target });
	if (valid_output_links(merged, bytes))
		output = std::move(merged);
}

OutputLinks rebase_output_links(const char *source, const char *frozen,
				std::span<const OutputLink> links)
{
	if (links.empty() || !valid_output_links(links, strlen(source)))
		return {};
	if (!strcmp(source, frozen))
		return { links.begin(), links.end() };
	std::vector<size_t> old_offsets, new_offsets;
	AnsiString before, after;
	before.set(source, &old_offsets);
	after.set(frozen, &new_offsets);
	if (before.size() != after.size())
		return {};
	for (size_t i = 0; i < before.size(); ++i)
		if (before.ch(i) != after.ch(i))
			return {};
	new_offsets.push_back(strlen(frozen));
	OutputLinks result;
	for (const auto &link : links)
	{
		const size_t begin =
			std::lower_bound(old_offsets.begin(), old_offsets.end(), link.begin) -
			old_offsets.begin();
		const size_t end =
			std::lower_bound(old_offsets.begin(), old_offsets.end(), link.end) -
			old_offsets.begin();
		if (begin < end)
			result.push_back(
				{ new_offsets[begin], new_offsets[end], link.kind, link.target });
	}
	return result;
}

static void fold_output_dollars(AnsiString &text, std::vector<size_t> *positions,
				std::vector<size_t> *offsets)
{
	// The wire converter needs original-to-visible positions; URL producers
	// instead compact the original source offsets. Both use the same folding.
	if (positions)
		positions->resize(text.size() + 1);
	const size_t source_end = offsets ? offsets->back() : 0;
	size_t out = 0;
	for (size_t i = 0; i < text.size(); ++i)
	{
		if (positions)
			(*positions)[i] = out;
		if (offsets)
			(*offsets)[out] = (*offsets)[i];
		const bool pair = text.ch(i) == '$' && i + 1 < text.size() &&
				  text[i] == text[i + 1];
		text[out++] = text[i];
		if (pair)
		{
			++i;
			if (positions)
				(*positions)[i] = out - 1;
		}
	}
	if (positions)
		(*positions)[text.size()] = out;
	if (offsets)
	{
		offsets->resize(out + 1);
		offsets->back() = source_end;
	}
	text.resize(out);
}

bool canonical_output_markup(const char *markup, std::string &frozen)
{
	if (strlen(markup) >= MAX_STRING_LENGTH)
		return false;
	const AnsiString visible(markup);
	// Input is bounded; canonical literal-& escapes can exceed a single queue
	// block while still fitting the existing command/pager accumulator.
	std::string buffer(visible.size() * 8 + 12, '\0');
	visible.ansi(buffer.data(), buffer.size());
	buffer.resize(strlen(buffer.c_str()));
	if (AnsiString(buffer.c_str()) != visible)
		return false;
	frozen = std::move(buffer);
	return true;
}

OutputLinks output_links_with_urls(const char *markup, std::span<const OutputLink> explicit_links,
				   std::string *frozen)
{
	if (frozen)
		frozen->clear();
	const size_t length = strlen(markup);
	if (!valid_output_links(explicit_links, length))
		explicit_links = {};
	OutputLinks result(explicit_links.begin(), explicit_links.end());
	// The overwhelming majority of output has neither a scheme nor slashes.
	// Preserve that path without allocating per-character maps.
	if (!strchr(markup, ':') || !strchr(markup, '/') || strchr(markup, '\x1b'))
		return result;
	AnsiString text;
	std::vector<size_t> offsets;
	text.set(markup, &offsets);
	offsets.push_back(length);
	fold_output_dollars(text, nullptr, &offsets);
	bool freeze_needed = false;
	auto source_offset = [&](size_t visible) { return offsets[visible]; };
	for (size_t begin = 0; begin < text.size();)
	{
		const auto scheme = output_url_scheme_length(std::wstring_view(text), begin);
		if (!scheme || (begin && !output_url_boundary(text.ch(begin - 1))))
		{
			++begin;
			continue;
		}
		size_t end = begin + scheme;
		int parentheses = 0, brackets = 0, braces = 0;
		while (end < text.size() && !output_url_delimiter(text.ch(end)))
		{
			const auto c = text.ch(end++);
			if (c == '&' && !freeze_needed)
			{
				const auto at = source_offset(end - 1);
				freeze_needed = markup[at + 1] && strchr("nN+-=", markup[at + 1]);
			}
			parentheses += (c == '(') - (c == ')');
			brackets += (c == '[') - (c == ']');
			braces += (c == '{') - (c == '}');
		}
		const size_t next = end;
		while (end > begin + scheme)
		{
			const auto c = text.ch(end - 1);
			if (c == '.' || c == ',' || c == ';' || c == ':' || c == '!')
				--end;
			else if ((c == ')' && parentheses < 0) || (c == ']' && brackets < 0) ||
				 (c == '}' && braces < 0))
			{
				parentheses += c == ')';
				brackets += c == ']';
				braces += c == '}';
				--end;
			}
			else
				break;
		}
		const size_t first_byte = source_offset(begin), last_byte = source_offset(end);
		const auto next_explicit =
			std::lower_bound(explicit_links.begin(), explicit_links.end(), first_byte,
					 [](const OutputLink &link, size_t position)
					 { return link.end <= position; });
		if (next_explicit == explicit_links.end() || next_explicit->begin >= last_byte)
		{
			string target;
			for (size_t i = begin; i < end && target.size() <= 2048; ++i)
			{
				char bytes[8], *out = bytes;
				put_utf8(out, text.ch(i));
				target.append(bytes, out);
			}
			const OutputLink link{ first_byte, last_byte, OutputLinkKind::Url,
					       std::move(target) };
			const auto insertion =
				std::lower_bound(result.begin(), result.end(), first_byte,
						 [](const OutputLink &item, size_t position)
						 { return item.begin < position; });
			if (valid_output_links(std::span(&link, 1), length) &&
			    result.size() < OUTPUT_LINK_MAX_COUNT)
			{
				const auto index = insertion - result.begin();
				result.insert(insertion, link);
				if (!valid_output_links(result, length))
					result.erase(result.begin() + index);
			}
		}
		begin = next;
	}
	if (frozen && freeze_needed)
		canonical_output_markup(markup, *frozen);
	return result;
}

OutputLinkFrame freeze_output_links(const char *markup, std::span<const OutputLink> links,
				    bool plain_terminal)
{
	OutputLinkFrame frame;
	std::vector<size_t> offsets;
	frame.text.set(markup, &offsets);
	if (plain_terminal)
		frame.text.colorize(0);
	if (!valid_output_links(links, strlen(markup)) || strchr(markup, '\x1b'))
		links = {};
	std::vector<size_t> positions;
	fold_output_dollars(frame.text, &positions, nullptr);
	for (const auto &link : links)
	{
		const size_t first = std::lower_bound(offsets.begin(), offsets.end(), link.begin) -
				     offsets.begin();
		const size_t last = std::lower_bound(offsets.begin(), offsets.end(), link.end) -
				    offsets.begin();
		const size_t begin = positions[first], end = positions[last];
		if (begin < end)
			frame.links.push_back({ begin, end, link.kind, link.target });
	}
	return frame;
}

void write_output(const char *text, txt_q *queue)
{
	if (!text || !queue || strlen(text) >= MAX_STRING_LENGTH)
	{
		write_to_q(text, queue, 1);
		return;
	}
	std::string frozen;
	auto links = output_links_with_urls(text, {}, &frozen);
	if (frozen.empty() || frozen.size() >= MAX_STRING_LENGTH)
		write_linked_output(text, queue, links);
	else
		write_linked_output(frozen.c_str(), queue,
				    rebase_output_links(text, frozen.c_str(), links));
}

static int output_queue_concat(const char *text, const txt_q *queue)
{
	if (!text || !queue || !queue->tail)
		return 1;
	const char *previous = queue->tail->text;
	const size_t length = strlen(previous);
	// A color token must not start in one send and finish in another.
	if ((length && previous[length - 1] == '&') ||
	    (length > 1 && previous[length - 2] == '&' && strchr("+-=", previous[length - 1])))
		return 0;
	// Reparse joined markup only when the preceding URL cannot change the next
	// send's ampersands, or a scheme cannot be completed across this boundary.
	if (strchr(previous, ':') &&
	    (strchr(text, '/') || (strchr(previous, '/') && strchr(text, '&'))))
		return 0;
	return 1;
}

void write_linked_output(const char *text, txt_q *queue, std::span<const OutputLink> links)
{
	if (links.empty() || !text || !queue || strlen(text) >= MAX_STRING_LENGTH)
	{
		write_to_q(text, queue, output_queue_concat(text, queue));
		return;
	}
	const size_t length = strlen(text);
	const bool valid = valid_output_links(links, length);
	const auto *tail = queue->tail;
	const size_t prefix = tail ? strlen(tail->text) : 0;
	write_to_q(text, queue, output_queue_concat(text, queue));
	if (!valid || links.empty())
		return;
	const size_t shift = queue->tail == tail ? prefix : 0;
	if (!queue->tail->links)
		queue->tail->links = new OutputLinks;
	append_output_links(*queue->tail->links, links, shift, strlen(queue->tail->text));
}

int get_linked_output(txt_q *queue, char *text, OutputLinks &links)
{
	links.clear();
	if (text && queue && queue->head && queue->head->links)
		links = std::move(*queue->head->links);
	return get_from_q(queue, text);
}

OutputLinks snoop_output_links(const char *markup, std::span<const OutputLink> links)
{
	if (links.empty() || !valid_output_links(links, strlen(markup)))
		return {};
	OutputLinks result;
	size_t used = 7, index = 0;
	for (size_t i = 0; markup[i] && used < MAX_STRING_LENGTH - 9; ++i)
	{
		while (index < links.size() && links[index].end <= i)
			++index;
		if (index == links.size())
			break;
		if (markup[i] == '\r')
			continue;
		const auto &link = links[index];
		if (link.begin <= i)
		{
			if (!result.empty() && result.back().end == used &&
			    result.back().target == link.target && result.back().kind == link.kind)
				++result.back().end;
			else if (result.size() < OUTPUT_LINK_MAX_COUNT)
				result.push_back({ used, used + 1, link.kind, link.target });
		}
		used += markup[i] == '\n' && markup[i + 1] ? 8 : 1;
	}
	return result;
}
