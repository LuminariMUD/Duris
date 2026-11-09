#include "net/output_links.h"
#include "core/prototypes.h"
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
			    link.target.find(';') != std::string::npos)
				return false;
		}
		else if (link.kind == OutputLinkKind::Url)
		{
			if (link.target.size() > 2048 || (!link.target.starts_with("http://") &&
							  !link.target.starts_with("https://")))
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
	// Match process_output: adjacent equal-attribute dollars collapse after
	// terminal conversion. Map each source character to the retained character.
	std::vector<size_t> positions(offsets.size() + 1);
	size_t out = 0;
	for (size_t i = 0; i < frame.text.size(); ++i)
	{
		positions[i] = out;
		const bool pair = frame.text.ch(i) == '$' && i + 1 < frame.text.size() &&
				  frame.text[i] == frame.text[i + 1];
		frame.text[out++] = frame.text[i];
		if (pair)
			positions[++i] = out - 1;
	}
	positions[offsets.size()] = out;
	frame.text.resize(out);
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

void write_linked_output(const char *text, txt_q *queue, std::span<const OutputLink> links)
{
	if (links.empty() || !text || !queue || strlen(text) >= MAX_STRING_LENGTH)
	{
		write_to_q(text, queue, 1);
		return;
	}
	const size_t length = strlen(text);
	const bool valid = valid_output_links(links, length);
	const auto *tail = queue->tail;
	const size_t prefix = tail ? strlen(tail->text) : 0;
	write_to_q(text, queue, 1);
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
