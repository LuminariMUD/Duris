#pragma once

#include "net/output_links.h"

struct cJSON;
inline constexpr size_t OUTPUT_PRESENTATION_MAX_TEXT = 1024 * 1024;

// Owns its JSON result. Invalid/over-budget presentation returns null, allowing
// callers to retain the ordinary text fields in the same message.
cJSON *output_presentation_json(const OutputLinkFrame &frame, bool underline);
char *output_text_json(const char *terminal, const OutputLinkFrame *frame, bool underline);
