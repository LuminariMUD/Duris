#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../area_file.h"

#define AREA_LIST "AREA"
#define TRG_DIR "trg"

#define ALL_TRG "tworld.trg"

/*
 * Checks the framing studioproc_boot() reads (src/mob/studioproc.c) and appends each
 * area's trg/<area>.trg to tworld.trg: blank lines and '*' comments anywhere, a
 * "#<vnum> <M|O|R>" header, "T <event>" triggers each ended by "~", and "S" ending the
 * record. "#~" ends the combined file, so a source may not hold it. The engine skips a
 * malformed record at boot; here it fails the build, naming the file and line.
 */
enum frame
{
	OUTSIDE,
	RECORD,
	TRIGGER
};

static void punt(const char *msg)
{
	fprintf(stderr, "%s\n", msg);
	exit(EXIT_FAILURE);
}

static void malformed(const char *path, int line, const char *message)
{
	fprintf(stderr, "error: %s:%d: %s\n", path, line, message);
	exit(EXIT_FAILURE);
}

static int append_triggers(FILE *source, const char *path, FILE *all_trg)
{
	char buf[8192];
	enum frame frame = OUTSIDE;
	int line = 0, records = 0;

	while (fgets(buf, sizeof(buf), source))
	{
		size_t length = strlen(buf);

		line++;
		if (length == sizeof(buf) - 1 && buf[length - 1] != '\n')
			malformed(path, line, "line too long");
		while (length > 0 && (buf[length - 1] == '\n' || buf[length - 1] == '\r'))
			buf[--length] = '\0';
		/* one '\n' per line, so a source without a final newline cannot run
		   into the next area's first line */
		fprintf(all_trg, "%s\n", buf);

		if (!strcmp(buf, "#~"))
			malformed(path, line,
				  "\"#~\" ends the combined file; a source may not hold it");
		if (!buf[0] || buf[0] == '*')
			continue;
		switch (frame)
		{
		case OUTSIDE:
		{
			int vnum;
			char target;

			if (sscanf(buf, "#%d %c", &vnum, &target) != 2 || vnum <= 0 ||
			    !strchr("MOR", toupper((unsigned char)target)))
				malformed(path, line, "expected a #<vnum> <M|O|R> record header");
			frame = RECORD;
			records++;
			break;
		}
		case RECORD:
			if (buf[0] == 'S' && (buf[1] == '\0' || buf[1] == ' '))
				frame = OUTSIDE;
			else if (buf[0] == 'T' && buf[1] == ' ')
				frame = TRIGGER;
			else
				malformed(path, line, "expected T, S or a * comment");
			break;
		case TRIGGER:
			if (!strcmp(buf, "~"))
				frame = RECORD;
			break;
		}
	}
	if (ferror(source))
		malformed(path, line, "read error");
	if (frame != OUTSIDE)
		malformed(path, line,
			  frame == TRIGGER ? "a trigger is not ended by ~" :
					     "a record is not ended by S");
	return records;
}

int main()
{
	FILE *area_list, *all_trg, *source;
	char area[8192], area_name[80], trg_name[sizeof(area_name) + 16];
	int area_count = 0, record_count = 0;

	area_list = fopen(AREA_LIST, "r");
	if (area_list == NULL)
		punt("AREA file cannot be opened");

	all_trg = fopen(ALL_TRG, "w");
	if (all_trg == NULL)
		punt("tworld.trg cannot be opened");

	while (fgets(area, sizeof(area), area_list))
	{
		if (area[0] == '*') /* a comment */
			continue;
		if (sscanf(area, "%79s", area_name) != 1)
			continue;
		if (snprintf(trg_name, sizeof(trg_name), "%s/%s.trg", TRG_DIR, area_name) < 0)
			punt("trigger filename cannot be formatted");
		source = fopen_area_file(trg_name);
		if (source == NULL)
		{
			if (!area_file_is_optional_missing(TRG_DIR))
				punt_area_file(trg_name);
			continue;
		}
		fprintf(stdout, "Compiling trigger file %2d : %s\n", area_count++, area_name);
		record_count += append_triggers(source, trg_name, all_trg);
		fclose(source);
	}

	fputs("#~\n", all_trg);
	fclose(area_list);
	if (fclose(all_trg) != 0)
		punt("tworld.trg cannot be written");

	fprintf(stdout, "\nSummary\t%d trigger records\n\n", record_count);

	system("chmod 600 tworld.trg");

	fprintf(stdout, "Done\n");
	return 0;
}
