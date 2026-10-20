#!/usr/bin/env python3
"""Regression for linked paladin-aura cleanup and stale bit state."""

from pathlib import Path
import re
import subprocess
import tempfile

from _paths import SRC, extract_function
from _source_contract import function_body


source = (SRC / "classes/paladins.c").read_text(encoding="utf-8", errors="replace")
body = function_body(source, r"\bvoid\s+aura_broken\s*\(")
assert body is not None, "aura_broken definition is missing"
body = body[body.index("{") + 1 : body.rindex("}")]

scan = re.search(
    r"if\s*\(\s*aff\s*!=\s*cld->affect\s*&&\s*"
    r"aff->type\s*>=\s*FIRST_AURA\s*&&\s*"
    r"aff->type\s*<=\s*LAST_AURA\s*\)",
    body,
)
assert scan, "aura cleanup must exclude the broken affect and bound the scanned type"
assert body.index("aura_type >= FIRST_AURA") < scan.start()
assert "aura_type <= LAST_AURA" not in body[scan.start() :]


PRELUDE = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <string>
#include <vector>

struct affected_type {
    int type = 0;
    affected_type *next = nullptr;
};
struct char_data {
    struct { int spec = 0; unsigned m_class = 32; } player;
    struct pc_data { int time_unspecced = 0; };
    struct { pc_data *pc = nullptr; } only;
    bool npc = false;
    affected_type *affected = nullptr;
    struct { unsigned affected_by3 = 0; } specials;
    std::vector<std::string> messages;
};
using P_char = char_data *;
struct char_link_data {
    P_char linking = nullptr;
    affected_type *affect = nullptr;
};
struct aura_description {
    const char *name;
    const char *glow_name;
};

#define FIRST_AURA 1502
#define LAST_AURA 1508
#define AFF3_PALADIN_AURA (1u << 6)
#define MAX_STRING_LENGTH 1024
#define REMOVE_BIT(bits, flag) ((bits) &= ~(flag))
#define IS_NPC(ch) ((ch)->npc)
#define IS_SPECIALIZED(ch) ((ch)->player.spec != 0)
#define CLASS_CLERIC 32u
#define CLASS_PALADIN 8u
#define CLASS_ANTIPALADIN 16u
int GET_CLASS(P_char ch, unsigned cls) { return (ch->player.m_class & cls) != 0; }

char _buff[MAX_STRING_LENGTH];
aura_description auras[LAST_AURA - FIRST_AURA + 1] = {};
void send_to_char(const char *message, P_char ch) { ch->messages.emplace_back(message); }
struct epic_command_result {};
static int purges = 0, updates = 0, forgotten = 0;
static P_char updated = nullptr, selected = nullptr;
void purge_linked_auras(P_char) { ++purges; }
void update_skills(P_char ch) { ++updates; updated = ch; }
void forget_spells(P_char, int) { ++forgotten; }
char *one_argument(const char *text, char *word) { std::strcpy(word, text); return word; }
P_char get_char_room_vis(P_char, const char *) { return selected; }
'''


DRIVER = r'''
void test_last_aura_clears() {
    char_data ch;
    affected_type aura{FIRST_AURA};
    ch.affected = &aura;
    ch.specials.affected_by3 = AFF3_PALADIN_AURA;
    char_link_data link{&ch, &aura};

    aura_broken(&link);

    assert(!(ch.specials.affected_by3 & AFF3_PALADIN_AURA));
    assert(ch.messages.size() == 1);
}

void test_other_aura_keeps_bit() {
    char_data ch;
    affected_type broken{FIRST_AURA};
    affected_type remaining{LAST_AURA};
    broken.next = &remaining;
    ch.affected = &broken;
    ch.specials.affected_by3 = AFF3_PALADIN_AURA;
    char_link_data link{&ch, &broken};

    aura_broken(&link);

    assert(ch.specials.affected_by3 & AFF3_PALADIN_AURA);
}

void test_unrelated_high_affect_does_not_keep_bit() {
    char_data ch;
    affected_type broken{FIRST_AURA};
    affected_type unrelated{LAST_AURA + 1};
    broken.next = &unrelated;
    ch.affected = &broken;
    ch.specials.affected_by3 = AFF3_PALADIN_AURA;
    char_link_data link{&ch, &broken};

    aura_broken(&link);

    assert(!(ch.specials.affected_by3 & AFF3_PALADIN_AURA));
}

void test_invalid_broken_affect_is_ignored() {
    char_data ch;
    affected_type unrelated{LAST_AURA + 1};
    ch.affected = &unrelated;
    ch.specials.affected_by3 = AFF3_PALADIN_AURA;
    char_link_data link{&ch, &unrelated};

    aura_broken(&link);

    assert(ch.specials.affected_by3 & AFF3_PALADIN_AURA);
    assert(ch.messages.empty());
}

int main() {
    test_last_aura_clears();
    test_other_aura_keeps_bit();
    test_unrelated_high_affect_does_not_keep_bit();
    test_invalid_broken_affect_is_ignored();
    char_data healer;
    healer.player.spec = 2;
    epic_command_result result;
    unspecialize_committed(&healer, false, result, 0, nullptr, 0);
    assert(healer.player.spec == 2 && purges == 0 && updates == 0 && forgotten == 0);
    unspecialize_committed(&healer, true, result, 0, nullptr, 0);
    assert(healer.player.spec == 0 && purges == 1 && updates == 1 && forgotten == 1);
    healer.player.spec = 2;
    char_data staff;
    selected = &healer;
    char argument[] = "healer";
    do_unspec(&staff, argument, 0);
    assert(healer.player.spec == 0 && purges == 2 && updated == &healer);
    // Both these classes keep their aura entitlement when their spec is removed.
    for (unsigned cls : {CLASS_PALADIN, CLASS_ANTIPALADIN}) {
        healer.player.m_class = cls;
        healer.player.spec = 1;
        unspecialize_committed(&healer, true, result, 0, nullptr, 0);
        assert(healer.player.spec == 0 && purges == 2);
        healer.player.spec = 1;
        do_unspec(&staff, argument, 0);
        assert(healer.player.spec == 0 && purges == 2 && updated == &healer);
    }
    std::puts("paladin aura cleanup regression passed");
}
'''

harness = (
    PRELUDE
    + "void aura_broken(struct char_link_data *cld)\n{\n"
    + body
    + "\n}\n"
    + extract_function("specializations.c", "void unspecialize_committed(")
    + extract_function("actwiz.c", "void do_unspec(")
    + DRIVER
)
with tempfile.TemporaryDirectory(prefix="paladin-aura-cleanup-") as directory:
    cpp = Path(directory) / "aura.cc"
    binary = Path(directory) / "aura"
    cpp.write_text(harness, encoding="utf-8")
    subprocess.run(
        [
            "g++",
            "-std=c++20",
            "-Wall",
            "-Wextra",
            "-Wpedantic",
            "-Werror",
            str(cpp),
            "-o",
            str(binary),
        ],
        check=True,
    )
    subprocess.run([str(binary)], check=True, timeout=10)
