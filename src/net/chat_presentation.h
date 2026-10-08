/****************************************************************************
 *
 *  File: chat_presentation.h                                   Part of Duris
 *  Usage: chat presentation interface
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

#include "net/output_style.h"

struct char_data;

// Called only from an accepted terminal delivery. Serializes the frozen frame;
// never resolves a second profile, transforms language, or advances animation.
void gmcp_comm_channel_output(char_data *recipient, const OutputChatMessage &chat,
			      const OutputContext &context, const char *frozen);
