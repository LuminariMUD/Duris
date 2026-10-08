/****************************************************************************
 *
 *  File: color_command.h                                       Part of Duris
 *  Usage: color command types and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#pragma once

#include "net/output_profiles.h"
#include <string>

struct char_data;

struct ColorCommandChannel
{
	OutputChannel channel;
	std::string_view name;
	std::string_view alias;
	std::string_view description;
	std::string_view sample;
	bool modes;
	bool template_wrappers = true;
};

std::span<const ColorCommandChannel> color_command_channels();
std::string output_preference_label(const OutputProfilePreferences &, OutputChannel);

struct ColorCommandResult
{
	OutputProfilePreferences preferences;
	std::string text;
	bool mutation = false;
};

// Pure command planning and preview. The adapter below owns save admission.
ColorCommandResult evaluate_color_command(std::string_view arguments,
					  const OutputProfilePreferences &preferences,
					  std::shared_ptr<const OutputProfileSnapshot> snapshot);
void do_color_preferences(char_data *recipient, const char *arguments);
