#!/usr/bin/env python3
"""Execute specialization restoration and innate grants under ASan/UBSan."""
import subprocess
import sys
import tempfile
from pathlib import Path

from _paths import ROOT, HARNESS_STUBS, extract_function, source

innates = source("innates.c").read_text()
macros = innates[innates.index("#define ADD_RACIAL_INNATE"):innates.index("float regen_factor")]
arrays = innates[innates.index("char racial_innates["):innates.index("extern const struct race_names")]
files = source("files.c").read_text()
restore = files[files.index("int restoreStatus("):files.index("#ifndef _PFILE_\nint restoreAffects(")]
functions = [
    ("utility.c", "int flag2idx("),
    ("affects.c", "struct affected_type *get_spell_from_char("),
    ("innates.c", "static int innate_char_race("),
    ("innates.c", "static int innate_unlock_level("),
    ("innates.c", "bool has_innate("),
    ("innates.c", "void assign_innates("),
    ("files.c", "ush_int getShort("),
    ("files.c", "uint getInt("),
    ("files.c", "long getLong("),
    ("files.c", "char *getString("),
    ("player_load_materialize.c", "int64_t value("),
    ("player_load_materialize.c", "void apply_integer("),
]
prelude = r'''
#include "core/files.h"
#include "guild/assocs.h"
#include "magic/spells.h"
#include "classes/necromancy.h"
#include "player/player_snapshot.h"
#include "item/trophy.h"
#include <cassert>
#include <climits>
#include <cstdlib>
#include <cstring>
#include <string>
static int short_size = sizeof(short), int_size = sizeof(int), long_size = sizeof(long);
static int stat_vers;
int GET_CLASS(P_char ch, unsigned int cls) { return (ch->player.m_class & cls) != 0; }
void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
void __free(void *p, const char *, int) { free(p); }
P_Guild get_guild_from_id(int) { return nullptr; }
void clear_title(P_char) {}
int calculate_mana(P_char) { return 0; }
int vitality_limit(P_char) { return 0; }
'''
driver = r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    assign_innates();
    const std::string mode = argv[1];
    if (mode == "lookup") {
        char_data ch{};
        ch.player.race = RACE_HUMAN;
        ch.player.m_class = CLASS_CONJURER;
        ch.player.level = 51;
        // Bypass loaders to exercise the lookup's independent safety boundary.
        for (int spec : {255, MAX_SPEC + 1, 128}) {
            ch.player.spec = spec;
            for (int innate = 0; innate <= LAST_INNATE; ++innate)
                (void)has_innate(&ch, innate);
            assert(!has_innate(&ch, INNATE_FIRESHIELD));
        }
        for (int spec = 0; spec <= MAX_SPEC; ++spec) {
            ch.player.spec = spec;
            for (int level : {29, 30, 51}) {
                ch.player.level = level;
                assert(has_innate(&ch, INNATE_FIRESHIELD) ==
                       (spec == SPEC_FIRE && level >= 30));
            }
        }
        ch.player.m_class = CLASS_PSIONICIST;
        ch.player.spec = SPEC_PYROKINETIC;
        ch.player.level = 30;
        assert(has_innate(&ch, INNATE_FIRESHIELD));
        // Invalid specialization must leave ordinary class and race grants intact.
        ch.player.spec = 255;
        ch.player.m_class = CLASS_ETHERMANCER;
        assert(has_innate(&ch, INNATE_FLY));
        ch.player.m_class = CLASS_CONJURER;
        ch.player.race = RACE_MOUNTAIN;
        assert(has_innate(&ch, INNATE_INFRAVISION));
    } else if (mode == "restore") {
        for (unsigned secondary : {0u, CLASS_WARRIOR}) {
            for (int spec = 255; spec >= 0; --spec) {
                char buffer[65536]{};
                char *cursor = buffer;
                ADD_BYTE(cursor, SAV_STATVERS);
                ADD_STRING(cursor, "Specfixture");
                ADD_INT(cursor, 1);
                ADD_BYTE(cursor, 24);
                ADD_STRING(cursor, "fixture-password");
                for (int field = 0; field < 4; ++field) { ADD_SHORT(cursor, 0); }
                ADD_INT(cursor, CLASS_CONJURER);
                ADD_INT(cursor, secondary);
                ADD_BYTE(cursor, spec);
                ADD_BYTE(cursor, RACE_HUMAN);
                ADD_BYTE(cursor, 1);
                ADD_BYTE(cursor, 30);
                // The remaining current-format status fields are all zero.
                char_data ch{};
                pc_only_data pc{};
                ch.only.pc = &pc;
                assert(restoreStatus(buffer, &ch) > cursor - buffer);
                assert(ch.player.spec == (!secondary && spec <= MAX_SPEC ? spec : 0));
                assert(ch.player.race == RACE_HUMAN && ch.player.level == 30);
                assert(has_innate(&ch, INNATE_FIRESHIELD) ==
                       (!secondary && spec == SPEC_FIRE));
                free(GET_NAME(&ch));
            }
        }
    } else {
        assert(mode == "snapshot");
        char_data ch{};
        ch.player.race = RACE_HUMAN;
        ch.player.m_class = CLASS_CONJURER;
        ch.player.level = 30;
        for (int64_t spec : {int64_t(-1), int64_t(255), int64_t(259),
                            int64_t(MAX_SPEC + 1), int64_t(INT64_MAX),
                            int64_t(INT64_MIN), int64_t(0), int64_t(1),
                            int64_t(2), int64_t(3), int64_t(MAX_SPEC)}) {
            player_snapshot_integer entry{player_status_field::specialization, spec, 0, false};
            apply_integer(&ch, entry, nullptr);
            assert(ch.player.spec == (spec >= 0 && spec <= MAX_SPEC ? spec : 0));
            assert(has_innate(&ch, INNATE_FIRESHIELD) == (spec == SPEC_FIRE));
        }
    }
    printf("Specialization %s passed under ASan/UBSan.\n", argv[1]);
}
'''
build = ROOT / "bin/tests"
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="innate-specialization-", dir=build) as directory:
    cpp, binary = Path(directory) / "harness.cpp", Path(directory) / "harness"
    cpp.write_text(prelude + macros + arrays + "\n" + "\n".join(
        extract_function(file, signature) for file, signature in functions) + restore + driver)
    subprocess.run([
        "g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections",
        "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
        "-fno-omit-frame-pointer", "-fno-pie", "-no-pie",
        "-I" + str(ROOT / "src"), str(cpp), str(HARNESS_STUBS),
        "-Wl,--gc-sections", "-lbsd", "-o", str(binary),
    ], check=True)
    for mode in sys.argv[1:] or ["lookup", "restore", "snapshot"]:
        subprocess.run([str(binary), mode], check=True)
