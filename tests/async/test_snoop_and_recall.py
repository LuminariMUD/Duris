#!/usr/bin/env python3
"""Snoop and recall follow ADR 0003, run on the real do_snoop() and do_recall().

A snoop tells its target when it starts and when it ends, at every level that can snoop
(60 to 62); before, no target was ever told, because the notice was given only below level
58. Every start and end is audited, at 61 and 62 too, which left no row before. A silent
snoop is only for level 62 and needs a reason, which the audit row keeps; its target is
told nothing. A snoop ends the same way when its target leaves (end_snoops_on()) and when
the snooper's link goes (stop_snooping()), and a snoop the channel spell set up is neither
told nor audited. A god switched into a mob snoops as itself: its stop removes its own entry
and is audited under its own name, where it used to unlink the mob and leave the snoop running.

recall <n> <player> by an immortal answers "Disabled by Zusuk October 9 2026" and shows
nothing of the other player's log; a player's own recall still lists their messages.
"""
from pathlib import Path
import subprocess
import tempfile

from _paths import ROOT, extract_function, source

actwiz = source("actwiz.c").read_text()
snoop = actwiz[actwiz.index("// The body d's snoop is registered under"):
               actwiz.index("void do_switch(P_char ch, char *argument, int cmd)")]
recall = extract_function("actinf.c", "void do_recall(P_char ch, char *argument, int /*cmd*/)")
remove = extract_function("utility.c", "void rem_char_from_snoopby_list(snoop_by_data **head")

HARNESS = r'''
#include "core/structs.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "player/player_log.h"
#include <cassert>
#include <cctype>
#include <cstdarg>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#define WIZLOG "wiz"

P_desc descriptor_list = nullptr;
static std::map<P_char, std::string> screen;
static std::vector<std::string> audit;
static std::vector<P_char> everyone;

void *__malloc(size_t size, const char *, const char *, int) { return calloc(1, size); }
void __free(void *pointer, const char *, int) { free(pointer); }
[[noreturn]] int panic_corruption_int(const char *, const char *, ...) { abort(); }
void logit(const char *, const char *, ...) {}
void send_to_char(const char *text, P_char ch) { screen[ch] += text; }
void send_to_char(const char *text, P_char ch, int) { screen[ch] += text; }
string strip_ansi(const char *text) { return text; }
bool isname(const char *, const char *) { return false; }
void sql_log(P_char ch, const char *kind, const char *format, ...)
{
    if (IS_NPC(ch)) // as the real one: a mob leaves no row
        return;
    char message[512];
    va_list args;
    va_start(args, format);
    vsnprintf(message, sizeof(message), format, args);
    va_end(args);
    audit.push_back(std::string(GET_NAME(ch)) + " " + kind + ": " + message);
}
P_char get_char_vis(P_char, const char *name)
{
    for (P_char ch : everyone)
        if (!strcasecmp(GET_NAME(ch), name))
            return ch;
    return nullptr;
}
char *skip_spaces(char *text)
{
    while (isspace(*text))
        ++text;
    return text;
}
char *one_argument(const char *argument, char *first)
{
    while (isspace(*argument))
        ++argument;
    while (*argument > ' ')
        *first++ = static_cast<char>(tolower(*argument++));
    *first = '\0';
    return const_cast<char *>(argument);
}
''' + remove + "\n" + snoop + "\n" + recall + r'''

struct person
{
    char_data ch = {};
    descriptor_data desc = {};
    pc_only_data pc = {};
    char name[32];

    person(const char *who, int level)
    {
        snprintf(name, sizeof(name), "%s", who);
        ch.player.name = name;
        ch.player.level = level;
        ch.only.pc = &pc;
        ch.desc = &desc;
        desc.character = &ch;
        desc.next = descriptor_list;
        descriptor_list = &desc;
        everyone.push_back(&ch);
    }
};

static void type(person &who, const char *command)
{
    std::string line = command;
    do_snoop(&who.ch, line.data(), 0);
}

static std::string take(person &who)
{
    std::string seen = screen[&who.ch];
    screen[&who.ch].clear();
    return seen;
}

static bool told(person &who, const char *text) { return take(who).find(text) != std::string::npos; }

int main()
{
    static const char started[] = "Someone starts snooping you.";
    static const char stopped[] = "You are no longer being snooped.";
    person tanen("Tanen", 30), bob("Bob", 30);

    // Every level that can snoop tells the target at both ends and audits both.
    for (int level = 60; level <= 62; ++level)
    {
        person god("God", level);
        audit.clear();
        type(god, "tanen");
        assert(god.desc.snoop.snooping == &tanen.ch && told(tanen, started));
        type(god, "god");
        assert(!god.desc.snoop.snooping && !tanen.desc.snoop.snoop_by_list && told(tanen, stopped));
        assert(audit.size() == 2);
        assert(audit[0] == "God wiz: Started snooping Tanen");
        assert(audit[1] == "God wiz: Stopped snooping Tanen");
        everyone.pop_back();
        // do_snoop() moved the god's descriptor behind its target's.
        for (P_desc *link = &descriptor_list; *link; link = &(*link)->next)
            if (*link == &god.desc)
            {
                *link = god.desc.next;
                break;
            }
    }

    // A silent snoop is for level 62 only, and it needs a reason.
    person greater("Greater", 61), overlord("Overlord", 62);
    audit.clear();
    type(greater, "tanen silent looking into a report");
    assert(told(greater, "Only the highest gods may snoop silently."));
    type(overlord, "tanen silent");
    assert(told(overlord, "Syntax: snoop <name> [silent <reason>]"));
    type(overlord, "tanen quietly because");
    assert(told(overlord, "Syntax: snoop <name> [silent <reason>]"));
    assert(!greater.desc.snoop.snooping && !overlord.desc.snoop.snooping && audit.empty());
    assert(take(tanen).empty());

    type(overlord, "tanen silent Looking into a Report");
    assert(overlord.desc.snoop.snooping == &tanen.ch && overlord.desc.snoop.silent);
    assert(take(tanen).empty());
    assert(audit.back() == "Overlord wiz: Started snooping Tanen silently: Looking into a Report");
    // Moving to another target ends the first snoop, silently, and starts a told one.
    type(overlord, "bob");
    assert(take(tanen).empty() && told(bob, started));
    assert(!tanen.desc.snoop.snoop_by_list && bob.desc.snoop.snoop_by_list);
    assert(audit[1] == "Overlord wiz: Stopped snooping Tanen (silent)");
    assert(audit[2] == "Overlord wiz: Started snooping Bob");

    // The target leaving ends every snoop on it: each snooper hears why, and it is audited.
    type(greater, "bob");
    take(bob);
    audit.clear();
    end_snoops_on(&bob.desc, "Your victim is no longer among us.\r\n");
    assert(!bob.desc.snoop.snoop_by_list && !greater.desc.snoop.snooping &&
           !overlord.desc.snoop.snooping);
    assert(told(greater, "no longer among us") && told(overlord, "no longer among us"));
    assert(take(bob).empty() && audit.size() == 2);

    // The snooper's link going ends its snoop as a stop does.
    type(greater, "tanen");
    take(tanen);
    audit.clear();
    stop_snooping(&greater.desc);
    assert(!greater.desc.snoop.snooping && !tanen.desc.snoop.snoop_by_list && told(tanen, stopped));
    assert(audit.size() == 1 && audit[0] == "Greater wiz: Stopped snooping Tanen");

    // The channel spell's snoop is set up outside the command: no notice, no audit.
    CREATE(tanen.desc.snoop.snoop_by_list, snoop_by_data, 1, MEM_TAG_SNOOP);
    tanen.desc.snoop.snoop_by_list->snoop_by = &bob.ch;
    bob.desc.snoop.snooping = &tanen.ch;
    audit.clear();
    stop_snooping(&bob.desc);
    assert(!tanen.desc.snoop.snoop_by_list && take(tanen).empty() && audit.empty());

    // A switched god's Imm commands run as its own body (interp.c), so its snoop is registered
    // under the god: stopping and retargeting remove that entry, and the audit names the god.
    person zusuk("Zusuk", 62);
    char_data goblin = {};
    char goblin_name[] = "goblin";
    goblin.player.name = goblin_name;
    SET_BIT(goblin.specials.act, ACT_ISNPC);
    goblin.desc = &zusuk.desc;
    zusuk.desc.character = &goblin;
    zusuk.desc.original = &zusuk.ch;
    audit.clear();
    type(zusuk, "tanen");
    take(tanen);
    type(zusuk, "bob");
    assert(!tanen.desc.snoop.snoop_by_list && told(tanen, stopped));
    type(zusuk, "zusuk");
    assert(!zusuk.desc.snoop.snooping && !bob.desc.snoop.snoop_by_list && told(bob, stopped));
    assert(screen[&goblin].empty() && audit.size() == 4);
    assert(audit[1] == "Zusuk wiz: Stopped snooping Tanen");
    assert(audit[3] == "Zusuk wiz: Stopped snooping Bob");

    // recall: an immortal cannot read another player's private messages.
    PlayerLog tanen_log, god_log;
    tanen.pc.log = &tanen_log;
    overlord.pc.log = &god_log;
    tanen_log.write(LOG_PRIVATE, "Bob tells you 'a secret'\n");
    take(overlord);
    std::string command = "10 tanen";
    do_recall(&overlord.ch, command.data(), 0);
    assert(take(overlord) == "Disabled by Zusuk October 9 2026\n");
    command = "10";
    do_recall(&tanen.ch, command.data(), 0);
    assert(take(tanen) == "Bob tells you 'a secret'\n");
    // A mortal's extra word is not a name: they still read their own log.
    command = "10 bob";
    do_recall(&tanen.ch, command.data(), 0);
    assert(take(tanen) == "Bob tells you 'a secret'\n");
    puts("snoop tells and audits as ADR 0003 decides; recall reads only one's own log");
}
'''

(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="snoop-recall-", dir=ROOT / "bin/tests") as tmp:
    test, binary = Path(tmp) / "test.cpp", Path(tmp) / "test"
    test.write_text(HARNESS)
    subprocess.run(["g++", "-std=c++20", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-I", str(ROOT / "src"), str(test), "-o",
                    str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
