#!/usr/bin/env python3
"""Execute shared hometown policy, terminal menus and WebSocket pre-persistence validation."""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source


def table(declaration):
    text = source("constant.c").read_text()
    start = text.index(declaration)
    return text[start:text.index("};", start) + 2]


create = extract_function("ws_handlers.c", "void ws_cmd_create_character(")
# Execute the unchanged production validation prefix. Surrounding account/class
# services are controlled boundaries; stop exactly where mutations would begin.
prefix = create[:create.index("\t/* store chargen options in descriptor */")]
prefix = prefix.replace("\tcJSON *response;\n", "").replace("\tchar *json_str;\n", "")
prefix += "\t++accepted; selected_home = actual_hometown;\n}\n"
assert create.index("!creation_hometown_available(") < create.index("mm_get(")
for mutation in ("init_char(ch)", "add_char_to_account(d)", "writeCharacter(ch"):
    assert create.index("!creation_hometown_available(") < create.index(mutation)
nanny = source("nanny.c").read_text()
assert nanny.count("find_hometown(GET_RACE(d->character), false, GET_RACEWAR(d->character))") == 2

prelude = r'''
#include "core/prototypes.h"
#include "core/utils.h"
#include "net/comm.h"
#include "net/ws_handlers.h"
#include "account/account.h"
#include "cmd/interp.h"
#include "account/creation_availability_config.h"
#include "world/hardcore_config.h"
#include "sql/sql.h"
#include <cassert>
#include <algorithm>
#include <cstring>
#include <string>
#include <vector>

int accepted = 0, selected_home = -1, prompts = 0, disabled_race = -1;
unsigned int game_locked = 0;
bool all_races = false, admission_allowed = true;
std::string output, error, json;
bool creation_race_enabled(int race) { return race != disabled_race; }
bool creation_all_races_enabled() { return all_races; }
bool creation_class_enabled(int) { return true; }
int creation_class_align(int, int) { return 0; }
static bool ws_chargen_allowed(P_desc) { return true; }
int bannedsite(char *, int) { return false; }
std::string get_mud_info(const char *) { return {}; }
bool chaos_mud_enabled() { return false; }
const hardcore_config *hardcore_config_get() {
    static hardcore_config config{};
    return &config;
}
account_racewar_admission account_check_racewar_admission(P_desc, int, bool, bool) {
    account_racewar_admission result{};
    result.allowed = admission_allowed;
    return result;
}
void account_format_racewar_denial(const account_racewar_admission *, char *buffer, size_t size) {
    snprintf(buffer, size, "Account side denied");
}
void ws_send_system(P_desc, const char *, const char *message) { error = message; }
int websocket_send_text(P_desc, const char *text) { json = text; return 1; }
void write_to_q(const char *text, txt_q *, int) { output += text; }
void logit(const char *, const char *, ...) {}
static void prompt_stat_method(P_desc) { ++prompts; }
'''

cases = r'''
int main() {
    char_data ch{};
    descriptor_data d{};
    d.character = &ch;
    d.chargen_phase = CHARGEN_READY;
    auto menu = [&](int race, const char *alignment) {
        auto *request = cJSON_CreateObject();
        cJSON_AddNumberToObject(request, "race", race);
        if (alignment) cJSON_AddStringToObject(request, "alignment", alignment);
        json.clear(); error.clear();
        ws_cmd_get_hometowns(&d, request);
        cJSON_Delete(request);
        assert(error.empty());
        auto *response = cJSON_Parse(json.c_str());
        assert(cJSON_GetObjectItem(response, "race")->valueint == race);
        std::vector<int> homes;
        cJSON *item;
        cJSON_ArrayForEach(item, cJSON_GetObjectItem(response, "options"))
            homes.push_back(cJSON_GetObjectItem(item, "id")->valueint);
        cJSON_Delete(response);
        return homes;
    };
    // All current roster entries: authoritative side, shared listing/count,
    // terminal display/selection, retained racial choices and rejected forgeries.
    for (int r = 0; playable_races[r].race_id != -1; ++r) {
        const auto &race = playable_races[r];
        for (const char *alignment : {"good", "evil"}) {
            const bool neutral = !strcmp(race.faction, "neutral");
            const bool good = neutral ? !strcmp(alignment, "good") : !strcmp(race.faction, "good");
            const int side = good ? RACEWAR_GOOD : RACEWAR_EVIL;
            const auto homes = menu(race.race_id, neutral ? alignment : nullptr);
            ch.player.race = race.race_id;
            ch.player.racewar = side;
            output.clear();
            show_avail_hometowns(&d);
            int count = 0;
            for (int home = 0; home <= LAST_HOME; ++home) {
                const bool tutorial = home == HOME_NEWBIE || home == HOME_PLANE_OF_LIFE;
                const bool expected = tutorial ? good : avail_hometowns[home][race.race_id] == 1;
                assert(creation_hometown_available(race.race_id, side, home) == expected);
                if (!expected) continue;
                ++count;
                assert(std::find(homes.begin(), homes.end(), home) != homes.end());
                std::string label(1, hometown_selection_key(race.race_id, home));
                label += ") " + std::string(town_name_list[home]);
                assert(output.find(label) != std::string::npos);
                char key[] = {hometown_selection_key(race.race_id, home), 0};
                const int before = prompts;
                select_hometown(&d, key);
                assert(prompts == before + 1 && GET_HOME(&ch) == home);
                assert(GET_BIRTHPLACE(&ch) == home && GET_ORIG_BIRTHPLACE(&ch) == home);
            }
            assert(count == static_cast<int>(homes.size()));
            assert(find_hometown(race.race_id, false, side) == (count > 1 ? HOME_CHOICE : homes[0]));
            const int racial_home = find_hometown(race.race_id, true);
            assert(racial_home != HOME_NEWBIE && racial_home != HOME_PLANE_OF_LIFE);
            d.chargen_race = race.race_id;
            for (const char *home : {"0", "-1", "999999", "22.5", "\"22\"", "null", "false", "{}", "[]", "22", "23", "1", "13", "omitted"}) {
                const bool omitted = !strcmp(home, "omitted");
                std::string request = "{\"name\":\"Pupil\",\"race\":" + std::to_string(race.race_id) +
                    ",\"class\":1,\"sex\":1,\"alignment\":\"" + alignment + "\"";
                if (!omitted) request += ",\"hometown\":" + std::string(home);
                request += "}";
                auto *data = cJSON_Parse(request.c_str());
                assert(data);
                accepted = 0; selected_home = -1; error.clear();
                ws_cmd_create_character(&d, data);
                const int id = omitted ? racial_home : cJSON_GetObjectItem(data, "hometown")->valueint;
                const bool numeric = omitted || (cJSON_IsNumber(cJSON_GetObjectItem(data, "hometown")) &&
                    cJSON_GetObjectItem(data, "hometown")->valuedouble == id);
                const bool expected = numeric && creation_hometown_available(race.race_id, side, id);
                assert(accepted == expected);
                assert(expected ? selected_home == id && error.empty() : !error.empty());
                cJSON_Delete(data);
            }
        }
    }
    assert(menu(RACE_FIRBOLG, nullptr).size() == 3);
    for (int race : {RACE_THRIKREEN, RACE_MINOTAUR, RACE_TIEFLING}) {
        const auto homes = menu(race, nullptr);
        assert(homes.size() == 1);
        assert(homes[0] != HOME_NEWBIE && homes[0] != HOME_PLANE_OF_LIFE);
    }
    assert(!creation_hometown_available(-1, RACEWAR_GOOD, HOME_NEWBIE));
    assert(!creation_hometown_available(LAST_RACE + 1, RACEWAR_GOOD, HOME_NEWBIE));
    for (const char *request : {"{\"race\":1.5}", "{\"race\":0}", "{\"race\":9999}",
            "{\"race\":1,\"alignment\":false}", "{\"race\":14,\"alignment\":false}",
            "{\"race\":14,\"alignment\":\"bogus\"}"}) {
        auto *data = cJSON_Parse(request);
        json.clear(); error.clear();
        ws_cmd_get_hometowns(&d, data);
        // A fixed-side race derives its own faction, ignoring supplied alignment.
        if (std::string(request) == "{\"race\":1,\"alignment\":false}") assert(!json.empty());
        else assert(!error.empty() && json.empty());
        cJSON_Delete(data);
    }
    disabled_race = RACE_OGRE;
    auto *data = cJSON_Parse("{\"race\":9}");
    json.clear(); error.clear();
    ws_cmd_get_hometowns(&d, data);
    assert(!error.empty() && json.empty());
    cJSON_Delete(data);
    disabled_race = -1;
    data = cJSON_Parse("{\"name\":\"Pupil\",\"race\":1,\"class\":1,\"sex\":1,\"hometown\":22}");
    d.chargen_race = RACE_HUMAN;
    admission_allowed = false;
    accepted = 0; error.clear();
    ws_cmd_create_character(&d, data);
    assert(!accepted && error == "Account side denied");
    cJSON_Delete(data);
}
'''

tables = "\n".join(table(declaration) for declaration in (
    "const int avail_hometowns[][LAST_RACE + 1] =",
    "const char *town_name_list[] =",
    "const struct playable_race_info playable_races[] =",
    "const struct restricted_race_info restricted_races[] =",
))
functions = [extract_function("nanny.c", signature) for signature in (
    "bool creation_hometown_available(", "int find_hometown(",
    "static char hometown_selection_key(",
    "void show_avail_hometowns(", "void select_hometown(",
)]
functions += [extract_function("ws_handlers.c", signature) for signature in (
    "static const struct restricted_race_info *ws_find_restricted_race(",
    "static const char *ws_get_race_faction(", "static int ws_resolve_racewar_side(",
    "static int ws_is_playable_race(", "void ws_cmd_get_hometowns(",
)]
directory = ROOT / "bin/tests"
directory.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="creation-hometowns-", dir=directory) as temporary:
    root = Path(temporary)
    program = root / "harness.cpp"
    program.write_text(prelude + tables + "\n" + "\n".join(functions) + prefix + cases)
    for backend in ("mariadb", "flatfile"):
        binary = root / backend
        flags = ["-I/usr/include/mysql"] if backend == "mariadb" else ["-D__NO_MYSQL__", "-Isrc/no_mysql"]
        subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-Isrc",
                        "-fsanitize=address,undefined", "-fno-pie", "-no-pie", *flags,
                        str(program), "-lcjson", "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], check=True, timeout=10)
print("shared/terminal/web hometown policy and pre-persistence validation passed")
