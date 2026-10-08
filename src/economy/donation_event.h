/****************************************************************************
 *
 *  File: donation_event.h                                      Part of Duris
 *  Usage: donation event type and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef DONATION_EVENT_H
#define DONATION_EVENT_H

#include <stddef.h>
#include <stdint.h>
#include <time.h>

struct donation_event
{
	char event_id[65];
	int64_t issued_at;
	int64_t amount_cents;
	char currency[4];
	bool is_public;
	char character_name[33];
	char message[257];
};

bool donation_event_decode(const char *json, size_t length, const char *secret, time_t now,
			   struct donation_event *event);

#endif
