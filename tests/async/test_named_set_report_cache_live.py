#!/usr/bin/env python3
"""Run the real named-report/cache APIs through expiry on isolated live Redis."""

from pathlib import Path
import subprocess
import tempfile
import time

from _paths import ROOT, extract_function
import test_flatfile_combat_journey as journey


harness = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "world/db.h"
#include "item/named_sets.h"
#include "redis/redis_report_cache.h"
#include "redis/redis_cache_store.h"
#include "redis/redis_connection.h"
#include <hiredis/hiredis.h>
#include <cassert>
#include <chrono>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

Skill skills[MAX_AFFECT_TYPES + 1];
zone_data *zone_table;
static std::vector<zone_data> zones;
static std::string displayed;
static void fixture_spell(int, P_char, char *, int, P_char, P_obj) {}
void logit(const char *, const char *, ...) {}
int real_zone(int zone) {
    for (size_t i = 0; i < named_set_count; ++i)
        if (named_sets[i].zone == zone) return i;
    return -1;
}
void page_string(P_desc, char *text, int copy) {
    assert(copy == 1);
    displayed = text;
}
''' + extract_function("utility.c", "string strip_ansi(") + \
    extract_function("utility.c", "string pad_ansi(") + \
    extract_function("random.mob.c", "void do_namedreport(") + r'''
int main(int argc, char **argv) {
    assert(argc == 2);
    zones.resize(named_set_count);
    zone_table = zones.data();
    for (size_t i = 0; i < named_set_count; ++i) {
        zones[i].number = named_sets[i].zone;
        zones[i].name = const_cast<char *>("Fixture zone");
        for (const auto &tier : named_sets[i].proc_spells) {
            if (!tier[1]) continue;
            skills[tier[1]].name = const_cast<char *>("fixture effect");
            skills[tier[1]].spell_pointer = fixture_spell;
        }
    }
    assert(named_set_count == 298 && validate_named_sets());
    redis_connection_options options = {
        "127.0.0.1", atoi(argv[1]), 250, 100, 0, nullptr, nullptr,
        false, nullptr, nullptr, false, nullptr};
    auto *settings = redis_connection_settings_create(&options);
    assert(settings);
    assert(redis_report_cache_configure("duris:local:named-expiry", 1));
    assert(redis_report_cache_start(settings));
    auto *context = redis_connection_open(settings);
    assert(context && !context->err);
    const char *key = "duris:local:named-expiry:season:1:cache:named";
    char *generated = generate_named_report();
    assert(generated);
    const std::string expected = generated;
    free(generated);
    auto remote = [&]() {
        auto *reply = static_cast<redisReply *>(redisCommand(context, "GET %s", key));
        assert(reply);
        std::string value;
        if (reply->type == REDIS_REPLY_STRING) value.assign(reply->str, reply->len);
        else assert(reply->type == REDIS_REPLY_NIL);
        freeReplyObject(reply);
        return value;
    };
    auto ttl = [&]() {
        auto *reply = static_cast<redisReply *>(redisCommand(context, "TTL %s", key));
        assert(reply && reply->type == REDIS_REPLY_INTEGER);
        auto value = reply->integer;
        freeReplyObject(reply);
        return value;
    };
    redis_cache_named_report();
    assert(redis_cache_store_drain(5000));
    assert(remote() == expected && ttl() > 86390 && ttl() <= 86400);
    // Shorten both real cache clocks through the existing store API. A remote
    // EXPIRE alone cannot expire a process-local entry's steady-clock deadline.
    assert(redis_cache_store_set(key, expected.c_str(), 1));
    assert(redis_cache_store_drain(5000));
    char *cached = redis_get_named_report();
    assert(cached && expected == cached && remote() == expected && ttl() == 1);
    free(cached);
    std::this_thread::sleep_for(std::chrono::milliseconds(1100));
    assert(!redis_get_named_report() && remote().empty());
    char_data ch = {};
    do_namedreport(&ch, nullptr, 0);
    assert(displayed == expected && redis_cache_store_drain(5000));
    assert(remote() == expected && ttl() > 86390);
    const auto submitted = redis_cache_store_health_copy().submitted;
    do_namedreport(&ch, nullptr, 0);
    assert(displayed == expected && redis_cache_store_health_copy().submitted == submitted);
    assert(redis_invalidate_named_report());
    assert(!redis_get_named_report() && redis_cache_store_drain(5000) && remote().empty());
    do_namedreport(&ch, nullptr, 0);
    assert(displayed == expected && redis_cache_store_drain(5000) && remote() == expected);
    assert(redis_report_cache_shutdown(5000));
    do_namedreport(&ch, nullptr, 0);
    assert(displayed == expected); // disabled cache uses the same complete formatter
    redisFree(context);
    redis_connection_settings_destroy(settings);
}
'''


with tempfile.TemporaryDirectory(prefix="named-cache-", dir=ROOT / "bin/tests") as temporary:
    runtime = Path(temporary)
    source = runtime / "report.cpp"
    source.write_text(harness)
    binary = runtime / "report"
    subprocess.run([
        "g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-ffunction-sections",
        "-fdata-sections", "-D__NO_MYSQL__", "-Isrc/no_mysql", "-Isrc",
        str(source), "src/item/named_sets.c",
        "src/redis/redis_report_cache.c", "src/redis/redis_namespace.c",
        "src/redis/redis_cache_store.c", "src/redis/redis_connection.c",
        "src/redis/redis_command_observability.c", "-Wl,--gc-sections",
        "-lhiredis", "-lhiredis_ssl", "-lssl", "-lcrypto", "-pthread", "-o", str(binary),
    ], cwd=ROOT, check=True)
    port = journey.available_ports()[0]
    redis = subprocess.Popen([
        "redis-server", "--bind", "127.0.0.1", "--port", str(port), "--save", "",
        "--appendonly", "no", "--dir", str(runtime),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while subprocess.run(["redis-cli", "-p", str(port), "PING"], capture_output=True,
                             text=True).stdout.strip() != "PONG":
            assert redis.poll() is None and time.monotonic() < deadline
            time.sleep(.1)
        subprocess.run([str(binary), str(port)], cwd=ROOT, check=True, timeout=20)
    finally:
        redis.terminate()
        redis.wait(timeout=5)

print("Live named-report local/Redis expiry, regeneration, warm reads and invalidation pass")
