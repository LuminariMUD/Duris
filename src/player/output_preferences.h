/****************************************************************************
 *
 *  File: output_preferences.h                                  Part of Duris
 *  Usage: player output preferences interface
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

struct char_data;

enum class OutputPreferenceUpdate
{
	Unchanged,
	PendingSave,
	Unavailable
};

OutputProfilePreferences player_output_preferences(char_data *recipient);
OutputPreferenceUpdate
update_player_output_preferences(char_data *recipient, const OutputProfilePreferences &preferences);
ResolvedOutputProfile player_output_profile(char_data *recipient, OutputChannel channel,
					    OutputPolicy caller_policy);

ResolvedOutputProfile player_output_profile(char_data *recipient, const OutputContext &context);
