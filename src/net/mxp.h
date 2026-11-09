#pragma once

#include "net/output_links.h"

struct descriptor_data;
enum : unsigned char
{
	MXP_OFF,
	MXP_SENT_DO,
	MXP_SENT_WILL,
	MXP_ENABLED
};

void mxp_negotiate(descriptor_data *descriptor);
void mxp_handle_negotiation(descriptor_data *descriptor, unsigned char command);
// Input is frozen markup, not wire text. Only explicit records become tags;
// literal text is emitted in locked mode and raw MXP controls are defused.
std::string mxp_render_output(const char *markup, std::span<const OutputLink> links,
			      bool plain_terminal, int lastbit);
