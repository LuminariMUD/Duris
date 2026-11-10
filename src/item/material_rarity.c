/*
 * File: material_rarity.c
 * Usage: read-only static material-composition reporting for object templates.
 *
 * This intentionally reports template composition frequency, not live economic
 * scarcity.  It uses the booted object prototypes and itemvalue() so its recipe
 * interpretation matches the game rather than a separately-maintained parser.
 */
#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <string>
#include <openssl/evp.h>

#ifndef DURIS_SOURCE_REVISION
#define DURIS_SOURCE_REVISION "unavailable"
#endif

#include "world/db.h"
#include "core/defines.h"
#include "item/material_rarity.h"
#include "item/objmisc.h"
#include "item/item_value.h"
#include "world/object_template.h"
#include "core/prototypes.h"
#include "core/structs.h"
#include "economy/tradeskill.h"
#include "core/utils.h"

#define MATERIAL_RARITY_MIN_VNUM 400000
#define MATERIAL_RARITY_MAX_VNUM 400209
#define MATERIAL_RARITY_COUNT (MATERIAL_RARITY_MAX_VNUM - MATERIAL_RARITY_MIN_VNUM + 1)

typedef struct material_rarity_tally
{
	long units;
	long templates;
} material_rarity_tally;

extern P_index obj_index;
extern int top_of_objt;
extern int mini_mode;
extern int no_specials;

static bool report_fingerprint(FILE *report, const char *label, const char *path, bool required)
{
	FILE *file = fopen(path, "rb");
	if (!file)
	{
		if (!required && errno == ENOENT)
		{
			fprintf(report, "%s=absent\n", label);
			return true;
		}
		fprintf(stderr, "material rarity report: cannot fingerprint %s: %s\n", path,
			strerror(errno));
		return false;
	}
	EVP_MD_CTX *context = EVP_MD_CTX_new();
	bool ok = context && EVP_DigestInit_ex(context, EVP_sha256(), nullptr) == 1;
	unsigned char buffer[8192], digest[EVP_MAX_MD_SIZE];
	unsigned int length = 0;
	size_t count;
	while (ok && (count = fread(buffer, 1, sizeof(buffer), file)) != 0)
		ok = EVP_DigestUpdate(context, buffer, count) == 1;
	ok = ok && !ferror(file) && EVP_DigestFinal_ex(context, digest, &length) == 1;
	if (fclose(file) != 0)
		ok = false;
	EVP_MD_CTX_free(context);
	if (!ok)
	{
		fprintf(stderr, "material rarity report: fingerprint failed for %s\n", path);
		return false;
	}
	fprintf(report, "%s=", label);
	for (unsigned int i = 0; i < length; ++i)
		fprintf(report, "%02x", digest[i]);
	fputc('\n', report);
	return true;
}

static bool report_provenance(FILE *report)
{
	fprintf(report, "formula_revision=%s\nsource_revision=%s\n", ITEM_VALUE_FORMULA_REVISION,
		DURIS_SOURCE_REVISION);
	fprintf(report, "context=configured-healthy-boot\nmini_mode=%d\nno_specials=%d\n",
		mini_mode, no_specials);
	bool ok = report_fingerprint(report, "binary_sha256", "/proc/self/exe", true);
	ok = report_fingerprint(report, "objects_sha256",
				mini_mode ? "areas_mini/mini.obj" : OBJ_FILE, top_of_objt >= 0) &&
	     ok;
	ok = report_fingerprint(report, "properties_sha256", "lib/duris.properties",
				top_of_objt >= 0) &&
	     ok;
	ok = report_fingerprint(report, "studio_sha256", "areas/world.trg", false) && ok;
	ok = report_fingerprint(report, "item_abilities_sha256", "lib/item_abilities.json",
				false) &&
	     ok;
	ok = report_fingerprint(report, "kingdom_config_sha256", "lib/kingdom.cfg", false) && ok;
	if (mini_mode != 1 && top_of_objt >= 0)
	{
		ok = report_fingerprint(report, "mobiles_sha256",
					mini_mode ? "areas_mini/mini.mob" : MOB_FILE, true) &&
		     ok;
		ok = report_fingerprint(report, "rooms_sha256", WORLD_FILE, true) && ok;
		ok = report_fingerprint(report, "zones_sha256",
					mini_mode ? "areas_mini/mini.zon" : ZONE_FILE, true) &&
		     ok;
	}
	fputc('\n', report);
	return ok;
}

static void csv_field(FILE *file, const char *value)
{
	const char *p;

	fputc('"', file);
	for (p = value ? value : ""; *p; ++p)
	{
		if (*p == '"')
			fputc('"', file);
		fputc(*p, file);
	}
	fputc('"', file);
}

static void display_name(char *out, size_t out_size, const char *value)
{
	size_t used = 0;

	if (!out_size)
		return;
	for (; value && *value && used + 1 < out_size; ++value)
	{
		/* Strip Duris colour markup for stable CSV labels. */
		if (*value == '&')
		{
			if (value[1] == '+')
			{
				if (value[2])
					value += 2;
				continue;
			}
			if (value[1])
			{
				++value;
				continue;
			}
		}
		out[used++] = *value;
	}
	out[used] = '\0';
}

/* get_matstart() defaults unknown material families to nonsubstantial.  Do
 * not silently fold those templates into that family in an audit report. */
static int material_family_is_mapped(int material)
{
	switch (material)
	{
	case MAT_NONSUBSTANTIAL:
	case MAT_FLESH:
	case MAT_CLOTH:
	case MAT_BARK:
	case MAT_SOFTWOOD:
	case MAT_HARDWOOD:
	case MAT_CRYSTAL:
	case MAT_BONE:
	case MAT_STONE:
	case MAT_HIDE:
	case MAT_LEATHER:
	case MAT_CURED_LEATHER:
	case MAT_IRON:
	case MAT_STEEL:
	case MAT_BRASS:
	case MAT_MITHRIL:
	case MAT_ADAMANTIUM:
	case MAT_BRONZE:
	case MAT_COPPER:
	case MAT_SILVER:
	case MAT_ELECTRUM:
	case MAT_GOLD:
	case MAT_PLATINUM:
	case MAT_GEM:
	case MAT_DIAMOND:
	case MAT_RUBY:
	case MAT_EMERALD:
	case MAT_SAPPHIRE:
	case MAT_IVORY:
	case MAT_DRAGONSCALE:
	case MAT_OBSIDIAN:
	case MAT_GRANITE:
	case MAT_MARBLE:
	case MAT_BAMBOO:
	case MAT_REEDS:
	case MAT_HEMP:
	case MAT_GLASSTEEL:
	case MAT_CHITINOUS:
	case MAT_REPTILESCALE:
	case MAT_RUBBER:
	case MAT_FEATHER:
	case MAT_PEARL:
		return TRUE;
	default:
		return FALSE;
	}
}

static const object_template *material_template(int vnum)
{
	return cache_object_template(vnum) ? find_object_template(vnum) : nullptr;
}

static void material_template_name(int vnum, char *out, size_t out_size)
{
	const auto *prototype = material_template(vnum);
	if (!prototype)
	{
		snprintf(out, out_size, "missing material template %d", vnum);
		return;
	}
	display_name(out, out_size, prototype->short_description.c_str());
}

static void write_exclusion(FILE *file, const object_template *obj, int vnum, const char *reason,
			    int ival)
{
	char name[MAX_STRING_LENGTH];
	display_name(name, sizeof(name), obj->short_description.c_str());
	fprintf(file, "%d,%d,%d,", vnum, obj->material, ival);
	csv_field(file, reason);
	fputc(',', file);
	csv_field(file, name);
	fputc('\n', file);
}

bool write_material_rarity_report(const char *output_dir)
{
	char source_name[MAX_STRING_LENGTH], low_name[MAX_STRING_LENGTH],
		high_name[MAX_STRING_LENGTH];
	FILE *summary = NULL, *recipes = NULL, *exclusions = NULL, *readme = NULL;
	material_rarity_tally tally[MATERIAL_RARITY_COUNT];
	long total_material_units = 0;
	long qualifying_templates = 0;
	long excluded_templates = 0;
	bool complete = true;
	int rnum;

	if (!output_dir || !*output_dir)
		output_dir = "material-rarity-report";
	if (mkdir(output_dir, 0755) < 0 && errno != EEXIST)
	{
		fprintf(stderr, "material rarity report: cannot create %s: %s\n", output_dir,
			strerror(errno));
		return false;
	}

	const std::string path(output_dir);
	if (!(summary = fopen((path + "/material-rarity-summary.csv").c_str(), "w")) ||
	    !(recipes = fopen((path + "/material-rarity-recipes.csv").c_str(), "w")) ||
	    !(exclusions = fopen((path + "/material-rarity-exclusions.csv").c_str(), "w")) ||
	    !(readme = fopen((path + "/material-rarity-README.txt").c_str(), "w")))
	{
		fprintf(stderr, "material rarity report: cannot open output in %s: %s\n",
			output_dir, strerror(errno));
		if (summary)
			fclose(summary);
		if (recipes)
			fclose(recipes);
		if (exclusions)
			fclose(exclusions);
		if (readme)
			fclose(readme);
		return false;
	}

	memset(tally, 0, sizeof(tally));
	fprintf(recipes,
		"template_vnum,itemvalue,material_family,ingredient_vnum,ingredient_role,declared_quantity,contributed_units,template_name,ingredient_name\n");
	fprintf(exclusions, "template_vnum,material_family,itemvalue,reason,template_name\n");

	for (rnum = 0; rnum <= top_of_objt; ++rnum)
	{
		const auto *obj = material_template(obj_index[rnum].virtual_number);
		int ival, low_vnum, high_vnum, high_quantity, low_quantity;
		int vnum;

		if (!obj)
		{
			fprintf(stderr, "material rarity report: cannot parse object template %d\n",
				obj_index[rnum].virtual_number);
			complete = false;
			break;
		}
		vnum = obj_index[rnum].virtual_number;
		ival = itemvalue(*obj);
		if (ival < 1)
		{
			write_exclusion(exclusions, obj, vnum, "nonpositive-itemvalue", ival);
			excluded_templates++;
			continue;
		}
		if (!material_family_is_mapped(obj->material))
		{
			write_exclusion(exclusions, obj, vnum, "unmapped-material-family", ival);
			excluded_templates++;
			continue;
		}

		low_vnum = material_start_vnum(obj->material);
		high_vnum = low_vnum + 4;
		if (low_vnum < MATERIAL_RARITY_MIN_VNUM || high_vnum > MATERIAL_RARITY_MAX_VNUM ||
		    !material_template(low_vnum) || !material_template(high_vnum))
		{
			write_exclusion(exclusions, obj, vnum, "missing-material-template", ival);
			excluded_templates++;
			continue;
		}

		/* Canonical craft decomposition: one high-quality unit every five itemvalue
		 * points, with the remainder represented by lowest-quality units. */
		const int64_t material_value = static_cast<int64_t>(ival) + 4;
		high_quantity = material_value / 5;
		low_quantity = material_value % 5;
		display_name(source_name, sizeof(source_name), obj->short_description.c_str());
		material_template_name(low_vnum, low_name, sizeof(low_name));
		material_template_name(high_vnum, high_name, sizeof(high_name));

		/* This report's denominator deliberately counts one unit for every required
		 * ingredient identity, not its declared stack quantity. */
		tally[high_vnum - MATERIAL_RARITY_MIN_VNUM].units++;
		tally[high_vnum - MATERIAL_RARITY_MIN_VNUM].templates++;
		total_material_units++;
		fprintf(recipes, "%d,%d,%d,%d,highest,%d,1,", vnum, ival, obj->material, high_vnum,
			high_quantity);
		csv_field(recipes, source_name);
		fputc(',', recipes);
		csv_field(recipes, high_name);
		fputc('\n', recipes);

		if (low_quantity > 0 && low_vnum != high_vnum)
		{
			tally[low_vnum - MATERIAL_RARITY_MIN_VNUM].units++;
			tally[low_vnum - MATERIAL_RARITY_MIN_VNUM].templates++;
			total_material_units++;
			fprintf(recipes, "%d,%d,%d,%d,lowest,%d,1,", vnum, ival, obj->material,
				low_vnum, low_quantity);
			csv_field(recipes, source_name);
			fputc(',', recipes);
			csv_field(recipes, low_name);
			fputc('\n', recipes);
		}
		qualifying_templates++;
	}

	fprintf(summary,
		"material_vnum,material_name,template_contributions,total_material_units,share_percent\n");
	for (rnum = 0; rnum < MATERIAL_RARITY_COUNT; ++rnum)
	{
		int vnum = MATERIAL_RARITY_MIN_VNUM + rnum;
		if (!tally[rnum].units)
			continue;
		material_template_name(vnum, low_name, sizeof(low_name));
		fprintf(summary, "%d,", vnum);
		csv_field(summary, low_name);
		fprintf(summary, ",%ld,%ld,%.6f\n", tally[rnum].units, total_material_units,
			((double)tally[rnum].units * 100.0) / (double)total_material_units);
	}
	fprintf(readme, "DurisMUD static material-composition report\n\n");
	fprintf(readme,
		"qualifying_templates=%ld\nexcluded_templates=%ld\ningredient_contributions=%ld\n\n",
		qualifying_templates, excluded_templates, total_material_units);
	fprintf(readme, "count_mode=one-per-required-material\n");
	fprintf(readme,
		"Each template contributes one to each distinct required material identity.\n");
	fprintf(readme,
		"Declared recipe stack quantities remain in material-rarity-recipes.csv.\n\n");
	fprintf(readme,
		"Scope: static object templates only. This is not reset frequency, loot probability,\n");
	fprintf(readme, "player stock, replenishment rate, or economic scarcity.\n");

	bool ok = report_provenance(readme) && complete;
	for (FILE *file : { summary, recipes, exclusions, readme })
	{
		const bool write_failed = ferror(file);
		if (fclose(file) != 0 || write_failed)
			ok = false;
	}
	if (!ok)
	{
		fprintf(stderr,
			"material rarity report: output failed in %s; discard partial files\n",
			output_dir);
		return false;
	}
	fprintf(stderr,
		"material rarity report: %ld qualifying templates, %ld ingredient contributions written to %s\n",
		qualifying_templates, total_material_units, output_dir);
	return true;
}
