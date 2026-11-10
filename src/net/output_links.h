#pragma once

#include "net/ansi.h"
#include <span>

enum class OutputLinkKind
{
	Command,
	Url
};

// Half-open byte ranges in owned Duris markup. Queue concatenation and pager
// slicing operate in bytes; styling rebases these spans before retaining them.
// Wire offsets are converted separately to Unicode code points after $$ folding.
struct OutputLink
{
	size_t begin, end;
	OutputLinkKind kind;
	std::string target;
};
using OutputLinks = std::vector<OutputLink>;
// A help search returns at most 101 titles (each at most 256 bytes).
inline constexpr size_t OUTPUT_LINK_MAX_COUNT = 128;
inline constexpr size_t OUTPUT_LINK_MAX_TARGET_BYTES = 32768;

struct VisibleOutputLink
{
	size_t begin, end;
	OutputLinkKind kind;
	std::string target;
};

struct OutputLinkFrame
{
	AnsiString text;
	std::vector<VisibleOutputLink> links;
};

bool valid_output_links(std::span<const OutputLink> links, size_t bytes);
// Ranges describe the input. Optional frozen markup escapes literal ampersands
// so slices no longer depend on seeing the original scheme.
OutputLinks output_links_with_urls(const char *markup, std::span<const OutputLink> explicit_links,
				   std::string *frozen = nullptr);
bool canonical_output_markup(const char *markup, std::string &frozen);
void append_output_links(OutputLinks &output, std::span<const OutputLink> links, size_t offset,
			 size_t bytes);
OutputLinks slice_output_links(std::span<const OutputLink> links, size_t begin, size_t end);
OutputLinks rebase_output_links(const char *source, const char *frozen,
				std::span<const OutputLink> links);
OutputLinkFrame freeze_output_links(const char *markup, std::span<const OutputLink> links,
				    bool plain_terminal = false);

struct txt_q;
// New raw output is scanned once before concatenation. Frozen sends/pager
// replay use write_linked_output instead, retaining complete original targets.
void write_output(const char *text, txt_q *queue);
// Existing queue functions retain their plain-text API. These output-only
// boundaries copy borrowed metadata on enqueue and move it out before dequeue.
void write_linked_output(const char *text, txt_q *queue, std::span<const OutputLink> links);
int get_linked_output(txt_q *queue, char *text, OutputLinks &links);
// Map the existing cyan snoop prefixes and CR removal without storing wire tags.
OutputLinks snoop_output_links(const char *markup, std::span<const OutputLink> links);
