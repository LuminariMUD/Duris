/****************************************************************************
 *
 *  File: divine_refusal_policy.h                               Part of Duris
 *  Usage: divine refusal configuration and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DURIS_DIVINE_REFUSAL_POLICY_H
#define DURIS_DIVINE_REFUSAL_POLICY_H

constexpr int DIVINE_REFUSAL_MAX_LOCK_SECONDS = 60;
constexpr int DIVINE_REFUSAL_ROLL_SCALE = 10000;
using divine_refusal_tick = unsigned long long;

struct divine_refusal_config
{
	bool enabled = false;
	bool summoner_only = true;
	float percent = 0.0f;
	divine_refusal_tick lock_pulses = 0;
};

enum class divine_refusal_outcome
{
	bypassed,
	allowed,
	refused_new,
	refused_active,
};

using divine_refusal_roll_fn = int (*)(int minimum, int maximum);

divine_refusal_config divine_refusal_make_config(float enabled, float summoner_only, float percent,
						 float retry_lock_seconds,
						 unsigned int pulses_per_second);

divine_refusal_outcome divine_refusal_decide(const divine_refusal_config &config, bool eligible,
					     bool command_recognized, bool command_exempt,
					     bool command_blocked, divine_refusal_tick now,
					     divine_refusal_tick *refusal_until,
					     divine_refusal_roll_fn roll);

#endif // DURIS_DIVINE_REFUSAL_POLICY_H
