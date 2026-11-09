#!/usr/bin/env python3
"""Compare read-only valuation with the real engine constructor and callbacks.

Uses the existing server objects, renaming only its main entry point. UID and
RNG endpoints are controlled; valuation, decoders, native handlers, object
construction, conversion, and cleanup are production code. Metadata uses native
loaders; no game loop, reset execution, listening socket, or database is started.
"""
from pathlib import Path
import os
import shlex
import shutil
import csv
import hashlib
import subprocess
import tempfile
import argparse
import json

from _paths import ROOT, extract_function


HARNESS = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "item/item_value.h"
#include "item/objmisc.h"
#include "world/object_template.h"
#include "specs/object_bindings.h"
#include "world/db.h"
#include "core/mm.h"
#include "magic/spells.h"
#include "core/proc-libs.h"
#include "combat/ctf.h"
#include "economy/nexus_stones.h"
#include "economy/mining.h"
#include "kingdom/kingdom.h"
#include "world/vnum.obj.h"
#include "mob/studioproc.h"
#include "item/random_equipment.h"
#include "item/random_equipment_config.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <set>
#include <string>

extern P_index obj_index;
extern P_obj object_list;
extern int top_of_objt;
extern long ne_event_counter;
extern mm_ds *dead_obj_pool;
extern struct race_names race_names_table[];
void update_stat_data();
void ne_init_event_pool();
static unsigned long long identities = 1000000;
static unsigned long rolls;
static bool seeded_rng;
static bool corpus;
static int compared;
static FILE *reference_scores;
extern "C" unsigned long long __wrap__Z25persistence_next_item_uidv() { return ++identities; }
extern "C" int __real__Z6numberii(int, int);
extern "C" int __wrap__Z6numberii(int low, int high) {
    ++rolls; return seeded_rng ? __real__Z6numberii(low, high) : low;
}

#if CIRCLE_BASELINE
extern Skill skills[];
// BASELINE_CIRCLE
static bool before_context;
extern "C" int __real__Z13get_mincirclei(int);
extern "C" int __wrap__Z13get_mincirclei(int spell) {
    return before_context ? get_mincircle_before(spell) : __real__Z13get_mincirclei(spell);
}
static FILE *deltas;
static void circle_delta(const char *cohort, int id, P_obj object) {
    const auto random = rolls;
    const auto ids = identities;
    before_context = true;
    const int old_score = itemvalue(object);
    before_context = false;
    const int new_score = itemvalue(object);
    assert(rolls == random && identities == ids);
    std::fprintf(deltas, "%s,%d,%d,%d,%d\n", cohort, id, old_score, new_score, object->value[5]);
}

static void generated_deltas() {
    boot_random_equipment_config();
    FILE *pool = std::fopen("generator-circles.csv", "w"); assert(pool);
    std::fputs("spell,self_only,before,after\n", pool);
    for (const auto &entry : spells_data)
        std::fprintf(pool, "%d,%d,%d,%d\n", entry.spell, entry.self_only,
                     get_mincircle_before(entry.spell), __real__Z13get_mincirclei(entry.spell));
    assert(!std::fclose(pool));
    char_data finder{};
    pc_only_data pc{};
    finder.only.pc = &pc;
    finder.player.name = const_cast<char *>("ValuationFixture");
    finder.player.level = 56;
    finder.curr_stats.Luk = 160;
    extern P_room world;
    extern int top_of_world;
    extern zone_data *zone_table;
    for (int room = 0; room <= top_of_world; ++room)
        if (!zone_table[world[room].zone].hometown &&
            strip_ansi(zone_table[world[room].zone].name) != zone_table[world[room].zone].name) {
            finder.in_room = room;
            break;
        }
    seeded_rng = true;
    int count = 0;
    for (int seed = 1; seed <= 16; ++seed)
    for (int level : {1, 20, 40, 60, 62})
    for (int slot = 0; slot < MAX_SLOT; ++slot) {
        randomize(seed * 100000 + level * 1000 + slot);
        P_obj object = create_random_eq(&finder, 56, level, slot, -1);
        assert(object);
        circle_delta("generated", ++count, object);
        extract_obj(object);
    }
    std::printf("seeded native generator comparisons: %d samples\n", count);
}
#endif

static void fixture_files()
{
    std::filesystem::create_directories("areas");
    std::filesystem::create_directories("lib");
    std::set<int> numbers;
    for (auto stage : {object_proc_binding_stage::objects, object_proc_binding_stage::rooms})
        for (const auto &binding : object_proc_bindings(stage)) numbers.insert(binding.vnum);
    for (int i = 0; i < 12; ++i) numbers.insert(9000000 + i);
    for (int vnum : {193, 394, 395, 434, 477, 478, 479, 480, 481, 482, 483, 484,
                     485, 486, 790, 48111}) numbers.insert(vnum);
    FILE *objects = std::fopen("areas/world.obj", "w"); assert(objects);
    for (int vnum : numbers)
        std::fprintf(objects, "#%d\nfixture~\na fixture~\nA fixture is here.~\n~\n"
                     "11 1 0 0 7 0 0 1 0 0 0\n0 0 0 0 0 0 0 0\n1 0 100 0 0 0 0\n", vnum);
    std::fputs("$~\n", objects); assert(!std::fclose(objects));
    FILE *properties = std::fopen("lib/duris.properties", "w"); assert(properties);
    std::fprintf(properties, "stats.str.%s=140\n", race_names_table[RACE_HUMAN].no_spaces);
    assert(!std::fclose(properties));
    FILE *config = std::fopen("lib/kingdom.cfg", "w"); assert(config);
    std::fputs("kingdom.enabled=1\n", config); assert(!std::fclose(config));
    FILE *triggers = std::fopen("areas/world.trg", "w"); assert(triggers);
    // Non-object targets must be skipped before looking up unloaded mobiles/rooms.
    std::fputs("#9000009 M\nT REPOP\necho unused\n~\nS\n"
               "#9000009 R\nT ENTER\necho unused\n~\nS\n"
               "#9000009 O\nT SEARCH\nmload 87\ntransfer 22800\n~\nS\n#~\n", triggers);
    assert(!std::fclose(triggers));
}

static object_template base(int vnum = 9000000)
{
    assert(cache_object_template(vnum));
    object_template object = *find_object_template(vnum);
    object.affected[0] = {APPLY_HIT, 10};
    return object;
}

static void parity(object_template &prototype, const char *label)
{
    std::fprintf(stderr, "checking real engine template parity %s vnum=%d\n", label,
                 obj_index[prototype.R_num].virtual_number);
    const auto ids = identities;
    const auto random = rolls;
    const auto events = ne_event_counter;
    const auto objects = object_list;
    const auto count = obj_index[prototype.R_num].number;
    const auto proc = obj_index[prototype.R_num].func.obj;
    const auto values = prototype;
    item_value_breakdown detail;
    const int from_template = itemvalue(prototype, &detail);
    assert(from_template == detail.score && detail.unrounded == detail.base * detail.multiplier);
    assert(identities == ids && rolls == random && ne_event_counter == events);
    assert(object_list == objects && obj_index[prototype.R_num].number == count);
    assert(obj_index[prototype.R_num].func.obj == proc);
    assert(!std::memcmp(prototype.value, values.value, sizeof(prototype.value)));
    assert(!std::memcmp(prototype.affected, values.affected, sizeof(prototype.affected)));
    assert(prototype.bitvector == values.bitvector && prototype.extra_flags == values.extra_flags);
    assert(prototype.descriptions.size() == values.descriptions.size());
    for (size_t i = 0; i < prototype.descriptions.size(); ++i)
        assert(prototype.descriptions[i].keyword == values.descriptions[i].keyword &&
               prototype.descriptions[i].description == values.descriptions[i].description);
    P_obj instance = instantiate_object_template(prototype);
    assert(instance && identities == ids + 1);
    const int runtime = itemvalue(instance);
    if (runtime != from_template) {
        std::fprintf(stderr, "%s: template=%d runtime=%d\n", label, from_template, runtime);
        std::abort();
    }
#if CIRCLE_BASELINE
    if (corpus) circle_delta("template", obj_index[prototype.R_num].virtual_number, instance);
#endif
    extract_obj(instance);
    assert(object_list == objects && obj_index[prototype.R_num].number == count);
    if (ne_event_counter != events) {
        std::fprintf(stderr, "%s: reference extraction events before=%ld after=%ld\n", label, events, ne_event_counter);
        std::abort();
    }
    ++compared;
    if (corpus) std::fprintf(reference_scores, "%d,%d\n",
                             obj_index[prototype.R_num].virtual_number, runtime);
    if (!corpus) std::printf("real engine template parity %s: %d\n", label, runtime);
}

int main(int argc, char **)
{
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    corpus = argc > 1;
    if (!corpus) fixture_files();
    assert(boot_material_rarity_objects(0));
    assert(identities == 1000000 && rolls == 0 && !object_list && ne_event_counter == 0);
    dead_obj_pool = mm_create("OBJS", sizeof(obj_data), offsetof(obj_data, next), 4);
    ne_init_event_pool();
    if (corpus) {
#if CIRCLE_BASELINE
        deltas = std::fopen("circle-deltas.csv", "w"); assert(deltas);
        std::fputs("cohort,id,before,after,packed_spells\n", deltas);
        FILE *circles = std::fopen("changed-circles.csv", "w"); assert(circles);
        std::fputs("spell,before,after\n", circles);
        for (int spell = FIRST_SPELL; spell <= LAST_SPELL; ++spell) {
            const int old_circle = get_mincircle_before(spell);
            const int new_circle = __real__Z13get_mincirclei(spell);
            if (old_circle != new_circle)
                std::fprintf(circles, "%d,%d,%d\n", spell, old_circle, new_circle);
        }
        assert(!std::fclose(circles));
#endif
        reference_scores = std::fopen("reference-scores.csv", "w"); assert(reference_scores);
        for (int rnum = 0; rnum <= top_of_objt; ++rnum) {
            assert(cache_object_template(obj_index[rnum].virtual_number));
            auto object = *find_object_template(obj_index[rnum].virtual_number);
            parity(object, "effective-world");
        }
        std::printf("effective-world native constructor/template parity: %d templates\n", compared);
        assert(!std::fclose(reference_scores));
#if CIRCLE_BASELINE
        generated_deltas();
        assert(!std::fclose(deltas));
#endif
        return 0;
    }
    assert(kingdom_enabled());
    for (int vnum : {477, 478, 479, 480, 481, 482, 483, 484, 485, 486, 48111})
        assert(obj_index[real_object(vnum)].func.obj);
    assert(obj_index[real_object(193)].func.obj == mine);
    assert(obj_index[real_object(434)].func.obj == mine);
    assert(obj_index[real_object(394)].func.obj == nexus_stone);
    assert(obj_index[real_object(395)].func.obj == nexus_guardian_pwn_mace);
    assert(obj_index[real_object(9000009)].func.obj == studioproc_obj);
    const auto first_proc = obj_index[0].func.obj;
    assign_ctf_object_procs(); // Missing flags must not index -1 or overwrite slot 0.
    assert(obj_index[real_object(790)].func.obj == ctf_flag_proc);
    assert(obj_index[0].func.obj == first_proc && !object_list && ne_event_counter == 0);
    auto object = base(); parity(object, "stat-only");
    object = base(23808); parity(object, "native-stoneskin");
    object = base(1372); object.type = ITEM_WEAPON; object.wear_flags |= ITEM_WIELD;
    object.value[0] = WEAPON_LONGSWORD; object.value[1] = 2; object.value[2] = 6;
    parity(object, "native-weapon");
    object = base(9000001); object.type = ITEM_WEAPON; object.wear_flags |= ITEM_WIELD;
    object.value[0] = WEAPON_LONGSWORD; object.value[1] = 2; object.value[2] = 6;
    object.value[5] = 32; object.value[6] = 60; object.value[7] = 30;
    parity(object, "packed");
    object = base(9000002); object.affected[3] = {APPLY_STR_RACE, RACE_HUMAN};
    assert(itemvalue(object) == 159); parity(object, "configured-racial");
    object = base(9000003); object.type = ITEM_ARMOR; object.value[0] = 10;
    parity(object, "armor");
    object = base(9000004); object.type = ITEM_SHIELD; object.value[3] = 10;
    parity(object, "shield-legacy");
    object = base(9000005); object.type = ITEM_WEAPON; object.value[0] = WEAPON_DAGGER;
    object.value[1] = 0; object.value[2] = -1;
    object.bitvector = AFF_SLEEP | AFF_FEAR | AFF_CHARM | AFF_HASTE;
    parity(object, "normalization");
    object.extra_flags |= ITEM_IGNORE; parity(object, "ignored-normalization");
    object = base(9000006); object.descriptions.push_back({"_proclib_hummer1", ""});
    parity(object, "proclib-hummer");
    object = base(9000007); object.descriptions.push_back({"_PROCLIB_TRANSPORTER1", "portal 101"});
    parity(object, "proclib-uppercase-transporter");
    object = base(9000008); object.descriptions.push_back({"_proclib_transporter1", "not-valid"});
    parity(object, "invalid-proclib");
    object = base(1372); object.descriptions.push_back({"_proclib_sayresponse1", "'hello' 'a reply'"});
    parity(object, "native-plus-proclib");
    for (const char *name : {"actroom1", "actworn1", "hummer1", "sayresponse1", "transporter1"})
        assert(!valid_object_proclib(name, std::string(MAX_STRING_LENGTH, 'x').c_str()));
    object.R_num = -1; assert(itemvalue(object) == 0);
    assert(!object_list && ne_event_counter == 0);
    std::puts("real engine: template evaluation creates no identities/objects/events, consumes no RNG, and leaves inputs/bindings unchanged");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--circle-baseline", help="Git revision providing the unchanged pre-fix circle lookup")
    parser.add_argument("--delta-output", type=Path, help="Directory for circle-fix qualification evidence")
    args = parser.parse_args()
    assert bool(args.circle_baseline) == bool(args.delta_output), "provide both circle comparison arguments"
    configuration = ["make", "-s", "--no-print-directory", "-C", "src",
                     "--eval=.PHONY: ivalue-objects ivalue-libs",
                     "--eval=ivalue-objects:;@echo $(DMS_OBJS)",
                     "--eval=ivalue-libs:;@echo $(LIBS)"]
    objects = shlex.split(subprocess.check_output(configuration + ["ivalue-objects"], cwd=ROOT, text=True))
    libraries = shlex.split(subprocess.check_output(configuration + ["ivalue-libs"], cwd=ROOT, text=True))
    assert objects and all(Path(path).is_file() for path in objects), "build the server with make -C src first"
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="item-value-engine-", dir=build) as tmp:
        path = Path(tmp)
        source, binary = path / "test.cpp", path / "test"
        code = HARNESS
        baseline_flags = []
        if args.circle_baseline:
            for file in ("src/item/item_value.c", "src/item/item_value_runtime.c"):
                old = subprocess.check_output(["git", "show", f"{args.circle_baseline}:{file}"],
                                              cwd=ROOT, text=True)
                assert old == (ROOT / file).read_text(), "circle-only comparison requires unchanged numeric/runtime adapters"
            old = path / "tradeskill-before.c"
            old.write_text(subprocess.check_output([
                "git", "show", f"{args.circle_baseline}:src/economy/tradeskill.c"], cwd=ROOT, text=True))
            function = extract_function(old, "int get_mincircle(int spell)\n{")
            code = code.replace("// BASELINE_CIRCLE", function.replace("get_mincircle(", "get_mincircle_before(", 1))
            baseline_flags = ["-DCIRCLE_BASELINE=1", "-Wl,--wrap=_Z13get_mincirclei"]
        source.write_text(code)
        comm = next(item for item in objects if item.endswith("/net/comm.o"))
        renamed = path / "comm.o"
        subprocess.run(["objcopy", "--redefine-sym", "main=duris_server_main", comm, str(renamed)], check=True)
        objects = [str(renamed) if item == comm else item for item in objects]
        subprocess.run([
            "g++", "-std=c++20", "-g", "-DTEST_MUD", "-Isrc", "-I/usr/include/mysql",
            "-I/usr/include/libxml2", str(source), *objects, "-rdynamic",
            "-Wl,--wrap=_Z25persistence_next_item_uidv", "-Wl,--wrap=_Z6numberii",
            *baseline_flags, *libraries, "-o", str(binary),
        ], cwd=ROOT, check=True)
        world = path / "world"
        (world / "areas").mkdir(parents=True)
        (world / "lib").mkdir()
        for name in ("duris.properties", "kingdom.cfg", "item_abilities.json", "random_equipment.cfg"):
            shutil.copyfile(ROOT / "lib" / name, world / "lib" / name)
        shutil.copyfile(ROOT / "areas/AREA", world / "areas/AREA")
        for name in ("obj", "trg", "mob", "wld", "zon"):
            (world / "areas" / name).symlink_to(ROOT / "areas" / name, target_is_directory=True)
            subprocess.run(["make", "-s", "-C", f"areas/src/{name}"], cwd=ROOT, check=True)
            built = subprocess.run([str(ROOT / f"bin/areas/tools/make_{name}")],
                                   cwd=world / "areas", capture_output=True, text=True)
            assert built.returncode == 0, built.stderr
            (world / "areas" / f"tworld.{name}").rename(world / "areas" / f"world.{name}")
        (path / "areas").mkdir()
        for name in ("mob", "wld", "zon"):
            (path / "areas" / f"world.{name}").symlink_to(world / "areas" / f"world.{name}")
        result = subprocess.run([str(binary)], cwd=path, capture_output=True, text=True,
                                timeout=60, env=os.environ)
        print(result.stdout, end="")
        if result.returncode:
            print(result.stderr, end="")
        assert result.returncode == 0, result.returncode

        result = subprocess.run([str(binary), "corpus"], cwd=world, capture_output=True,
                                text=True, timeout=120, env=os.environ)
        print(result.stdout, end="")
        if result.returncode:
            print(result.stderr[-4000:], end="")
        assert result.returncode == 0, result.returncode

        server = ROOT / "bin/server/dms_new"
        output = world / "report"
        command = [str(server), "--material-rarity-report", str(output)]
        result = subprocess.run(command, cwd=world, capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, result.stderr[-5000:]
        expected = {int(vnum): int(score) for vnum, score in
                    csv.reader((world / "reference-scores.csv").open())}
        reported = {}
        with (output / "material-rarity-summary.csv").open() as file:
            headings = next(csv.reader(file))
            assert "total_material_units" in headings and "share_percent" in headings
        exclusion_reasons = set()
        for name in ("recipes", "exclusions"):
            with (output / f"material-rarity-{name}.csv").open() as file:
                for row in csv.DictReader(file):
                    vnum, score = int(row["template_vnum"]), int(row["itemvalue"])
                    assert score == expected[vnum], (vnum, score, expected[vnum])
                    reported[vnum] = score
                    if name == "exclusions":
                        exclusion_reasons.add(row["reason"])
        assert "unmapped-material-family" in exclusion_reasons
        assert reported == expected
        provenance = dict(line.split("=", 1) for line in
                          (output / "material-rarity-README.txt").read_text().splitlines()
                          if "=" in line)
        for label, file in (("binary", server), ("objects", world / "areas/world.obj"),
                            ("properties", world / "lib/duris.properties"),
                            ("studio", world / "areas/world.trg"),
                            ("mobiles", world / "areas/world.mob"),
                            ("rooms", world / "areas/world.wld"),
                            ("zones", world / "areas/world.zon"),
                            ("kingdom_config", world / "lib/kingdom.cfg"),
                            ("item_abilities", world / "lib/item_abilities.json")):
            assert provenance[label + "_sha256"] == hashlib.sha256(file.read_bytes()).hexdigest()
        assert provenance["formula_revision"] == "ival-v2-class-spec-extents"
        assert provenance["context"] == "configured-healthy-boot"
        assert provenance["mini_mode"] == "0" and provenance["no_specials"] == "0"
        if args.delta_output:
            args.delta_output.mkdir(parents=True, exist_ok=True)
            with (world / "circle-deltas.csv").open() as file:
                rows = list(csv.DictReader(file))
            changed = [row for row in rows if row["before"] != row["after"]]
            with (args.delta_output / "changed-values.csv").open("w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["cohort", "id", "before", "after", "packed_spells"])
                writer.writeheader()
                writer.writerows(changed)
            shutil.copyfile(world / "changed-circles.csv", args.delta_output / "changed-circles.csv")
            shutil.copyfile(world / "generator-circles.csv", args.delta_output / "generator-circles.csv")
            summary = {
                "baseline_revision": args.circle_baseline,
                "circle_functions_sha256": {
                    "before": hashlib.sha256(function.encode()).hexdigest(),
                    "after": hashlib.sha256(extract_function(
                        "tradeskill.c", "int get_mincircle(int spell)\n{").encode()).hexdigest(),
                },
                "formula_revision": provenance["formula_revision"],
                "provenance": provenance,
                "compared": {kind: sum(row["cohort"] == kind for row in rows)
                             for kind in ("template", "generated")},
                "changed": {kind: sum(row["cohort"] == kind for row in changed)
                            for kind in ("template", "generated")},
                "generated_seeds": "seed=1..16; source_level=1,20,40,60,62; every native slot; finder_level=56/luck=160",
                "score_derived_consumer_effects": {
                    "status": "none in measured cohorts" if not changed else "requires cohort analysis",
                    "families": ["salvage quality/breakage", "craft/forge level/recipe/material/XP",
                                 "enhancement source/donor/result/price", "quest floors/zone weights",
                                 "faerie bag 25/50/125"],
                    "basis": "Exact before/after score equality implies no threshold, material, XP, or currency delta"
                             if not changed else "Inspect changed-values.csv before rollout",
                },
            }
            (args.delta_output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print("circle repair deltas:", summary["compared"], summary["changed"], flush=True)
        (world / "areas_mini").symlink_to(ROOT / "areas_mini", target_is_directory=True)
        for flag, mode, specials in (("-s", "0", "1"), ("--minimal", "1", "0")):
            target = world / ("report" + flag)
            result = subprocess.run([str(server), flag, "--material-rarity-report", str(target)],
                                    cwd=world, capture_output=True, text=True, timeout=60)
            assert result.returncode == 0, result.stderr[-5000:]
            metadata = (target / "material-rarity-README.txt").read_text()
            assert f"mini_mode={mode}\n" in metadata and f"no_specials={specials}\n" in metadata
        (world / "lib/duris.properties").unlink()
        result = subprocess.run(command, cwd=world, capture_output=True, text=True, timeout=60)
        assert result.returncode == 1 and "valuation properties could not be loaded" in result.stderr
        print("offline CLI: all effective-world scores match real constructors; provenance and missing-context failure passed")


if __name__ == "__main__":
    main()
