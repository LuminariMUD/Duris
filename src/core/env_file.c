/****************************************************************************
 *
 *  File: env_file.c                                            Part of Duris
 *  Usage: loads the .env file into the environment at boot
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "core/prototypes.h"
#include "core/structs.h"
#include "core/utils.h"

#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

/* Load .env before selecting a persistence backend. */
int load_env_file(void)
{
	int fd = open(".env", O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
	if (fd < 0)
	{
		if (errno != ENOENT)
		{
			logit(LOG_STATUS, "Unable to open .env securely");
			return -1;
		}
		logit(LOG_STATUS, "No .env file found; explicit process environment is required.");
		return 0;
	}

	struct stat file_stat;
	if (fstat(fd, &file_stat) || !S_ISREG(file_stat.st_mode) || file_stat.st_uid != geteuid() ||
	    (file_stat.st_mode & 0177))
	{
		logit(LOG_STATUS,
		      "Unsafe .env metadata: require an owner-controlled regular file with mode 0600 or stricter");
		close(fd);
		return -1;
	}

	FILE *f = fdopen(fd, "r");
	if (!f)
	{
		close(fd);
		return -1;
	}

	char line[256];
	int count = 0;
	while (fgets(line, sizeof(line), f))
	{
		if (line[0] == '#' || line[0] == '\n' || line[0] == '\r')
			continue;

		char *nl = strchr(line, '\n');
		if (nl)
			*nl = '\0';
		nl = strchr(line, '\r');
		if (nl)
			*nl = '\0';
		if (line[0] == '\0')
			continue;

		char *eq = strchr(line, '=');
		if (eq)
		{
			*eq = '\0';
			setenv(line, eq + 1, 0);
			count++;
		}
	}
	fclose(f);

	logit(LOG_STATUS, "Loaded %d environment variables from .env file.", count);
	return count;
}
