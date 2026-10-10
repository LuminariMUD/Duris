#!/usr/bin/env python3
"""A player corpse's save, removal and boot restore go through the writer and the catalog.

Runs the production writeCorpse(), PurgeCorpseFile() and restoreCorpses() from
src/core/files.c on the flat-file backend, with the writer's queue and the corpse catalog
stood in:

- writeCorpse() queues a save for a corpse on the ground or carried (giving it a save id
  first) and a removal for one that is neither, and reports a job the writer refuses;
- PurgeCorpseFile() queues the removal, reports a refusal, and queues nothing while the
  boot restore runs (skip_corpse_save) or for a corpse never saved;
- restoreCorpses() restores the flat-file catalog, and a failure other than an empty
  catalog stops the boot.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import HARNESS_STUBS, ROOT, extract_function

FILES = "files.c"
HARNESS = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/config.h"
#include "classes/necromancy.h"
#include "flatfile/flatfile_corpse_restore.h"
#include "persistence/persistence_mode.h"
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <unistd.h>
#include <utility>
#include <vector>

int skip_corpse_save = 0;
static bool writer_accepts = true;
static std::vector<std::pair<P_obj, bool>> queued;
static std::vector<std::string> alerts;
static flatfile_corpse_restore_result catalog = flatfile_corpse_restore_result::ok;
static std::string catalog_root;
static int fatal = 0;

bool queue_corpse_save(P_obj corpse, bool remove)
{
	queued.push_back({ corpse, remove });
	return writer_accepts;
}
void persistence_alert(int, const char *domain, const char *owner, const char *, const char *,
		       const char *action, const char *, ...)
{
	alerts.push_back(std::string(domain) + ":" + owner + ":" + action);
}
enum persistence_mode persistence_mode_get(void)
{
	return PERSISTENCE_MODE_FLATFILE_PRIMARY;
}
const char *persistence_mode_flatfile_root(void)
{
	return "/state";
}
flatfile_corpse_restore_result flatfile_corpse_restore_catalog(const std::string &root,
							       std::string *error)
{
	catalog_root = root;
	*error = "damaged";
	return catalog;
}
void fatal_boot_error(const char *component, const char *, ...)
{
	assert(std::string(component) == "corpse");
	++fatal;
}
int checked_snprintf_at(const char *, int, char *destination, size_t size, const char *format,
			...)
{
	va_list arguments;
	va_start(arguments, format);
	const int result = std::vsnprintf(destination, size, format, arguments);
	va_end(arguments);
	return result;
}

// PRODUCTION

static void reset()
{
	queued.clear();
	alerts.clear();
	writer_accepts = true;
	skip_corpse_save = 0;
}

int main()
{
	obj_data corpse{};
	corpse.type = ITEM_CORPSE;
	corpse.value[1] = PC_CORPSE;
	corpse.loc_p = LOC_ROOM;

	// On the ground: a save id, then a save.
	writeCorpse(&corpse);
	assert(corpse.value[CORPSE_SAVEID] != 0);
	assert(queued.size() == 1 && queued[0] == std::make_pair(&corpse, false) && alerts.empty());

	// Neither on the ground nor carried: a removal; refused, it is reported.
	reset();
	corpse.loc_p = 0;
	writer_accepts = false;
	writeCorpse(&corpse);
	assert(queued.size() == 1 && queued[0] == std::make_pair(&corpse, true));
	assert(alerts == std::vector<std::string>{ "corpse:remove:queue_failed" });

	// While the boot restore runs, nothing is queued.
	reset();
	skip_corpse_save = 1;
	writeCorpse(&corpse);
	PurgeCorpseFile(&corpse);
	assert(queued.empty() && alerts.empty());

	// A purge queues the removal, and reports a refusal.
	reset();
	PurgeCorpseFile(&corpse);
	assert(queued.size() == 1 && queued[0] == std::make_pair(&corpse, true) && alerts.empty());
	reset();
	writer_accepts = false;
	PurgeCorpseFile(&corpse);
	assert(alerts == std::vector<std::string>{ "corpse:flatfile_remove:queue_failed" });

	// A corpse never saved has nothing to remove.
	reset();
	corpse.value[CORPSE_SAVEID] = 0;
	PurgeCorpseFile(&corpse);
	writeCorpse(&corpse);
	assert(queued.empty() && alerts.empty());

	// The boot restores the catalog; an empty one is fine, a damaged one stops the boot.
	restoreCorpses();
	assert(catalog_root == "/state" && fatal == 0);
	catalog = flatfile_corpse_restore_result::not_found;
	restoreCorpses();
	assert(fatal == 0);
	catalog = flatfile_corpse_restore_result::invalid;
	restoreCorpses();
	assert(fatal == 1);
	std::puts("corpse saves, removals and the boot restore route through the writer");
}
'''

production = "\n\n".join(extract_function(FILES, signature) for signature in (
    "void writeCorpse(P_obj corpse)", "void PurgeCorpseFile(P_obj corpse)",
    "void restoreCorpses(void)"))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="corpse-routing-", dir=ROOT / "bin/tests") as build:
    source = Path(build) / "harness.cpp"
    binary = Path(build) / "harness"
    source.write_text(HARNESS.replace("// PRODUCTION", production))
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-D__NO_MYSQL__", "-Isrc", "-Isrc/no_mysql",
                    str(source), str(HARNESS_STUBS), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
