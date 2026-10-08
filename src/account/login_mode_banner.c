/****************************************************************************
 *
 *  File: login_mode_banner.c                                   Part of Duris
 *  Usage: the staging banner shown at login
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "account/login_mode_banner.h"

#include <stdlib.h>
#include <strings.h>

bool duris_staging_enabled(void)
{
	const char *value = getenv("DURIS_STAGING");

	return value && strcasecmp(value, "TRUE") == 0;
}

std::string login_mode_banner(bool staging, bool chaos, bool all_races, bool all_classes)
{
	/* "&=L" sets the bright-black background, whose bright bit login output
	 * renders as blink; each mode then gets its own bright foreground. */
	const struct
	{
		bool enabled;
		const char *label;
	} modes[] = {
		{ staging, "&=LYSTAGING" },
		{ chaos, "&=LRCHAOS" },
		{ all_races, "&=LGALL-RACES" },
		{ all_classes, "&=LCALL-CLASSES" },
	};
	std::string banner;
	for (const auto &mode : modes)
	{
		if (!mode.enabled)
			continue;
		banner += banner.empty() ? "&=LM*** " : "&=LW | ";
		banner += mode.label;
	}
	if (!banner.empty())
		banner += "&=LM ***&n\r\n";
	return banner;
}
