#!/usr/bin/env python3
"""Native input reset preserves terminal output and other player sessions."""
from pathlib import Path
import subprocess
import tempfile
from _paths import ROOT, extract_function, source

HARNESS = r'''
#include "core/prototypes.h"
#include "net/comm.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <cstdio>
#undef FREE
#define FREE(pointer) free(pointer)
void logit(const char *, const char *, ...) {}
// PRODUCTION
void queue(txt_q &q, const char *text) {
    auto *entry = static_cast<txt_block *>(calloc(1, sizeof(txt_block)));
    entry->text = strdup(text);
    if (q.tail) q.tail->next = entry; else q.head = entry;
    q.tail = entry;
}
int main() {
    descriptor_data player{}, other{};
    queue(player.input, "look"); queue(player.input, "score");
    queue(player.output, "Your wounds claim you at last. ACCOUNT MENU");
    strcpy(player.buf, "unfinished"); player.buflen = strlen(player.buf);
    queue(other.input, "look"); strcpy(other.buf, "pending"); other.buflen = 7;
    auto *output = player.output.head;
    flush_input_queue(&player);
    assert(!player.input.head && !player.input.tail && !player.buflen && !player.buf[0]);
    assert(player.output.head == output && strstr(output->text, "ACCOUNT MENU"));
    assert(other.input.head && !strcmp(other.buf,"pending") && other.buflen == 7);
    flush_input_queue(&player); // Empty reset is safe.
    queue(player.input, "1"); // Fresh menu input is still admitted normally.
    char text[MAX_STRING_LENGTH];
    assert(get_from_q(&player.input, text) && !strcmp(text, "1"));
    assert(get_from_q(&player.output, text) && strstr(text, "ACCOUNT MENU"));
    flush_input_queue(&other);
    puts("native input reset: complete/partial lines cleared, output and other sessions preserved");
}
'''
handler = source("handler.c").read_text()
transition = handler.split("if (ch->desc && ch->desc->connected != CON_DELETE)", 1)[1]
assert transition.index("flush_input_queue(ch->desc)") < transition.index("CON_DISPLAY_ACCT_MENU")
fight = source("fight.c").read_text()
hardcore = fight.split("// With account system, return to account menu instead of disconnecting", 1)[1]
assert hardcore.index("flush_input_queue(d)") < hardcore.index("CON_DISPLAY_ACCT_MENU")
native = "\n".join(extract_function("comm.c", name) for name in
                   ("int get_from_q(", "void flush_input_queue("))
(ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="input-reset-", dir=ROOT / "bin/tests") as directory:
    path, binary = Path(directory) / "test.cpp", Path(directory) / "test"
    path.write_text(HARNESS.replace("// PRODUCTION", native))
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-g",
                    "-fsanitize=address,undefined", "-Isrc", str(path), "-o", str(binary)], cwd=ROOT, check=True)
    subprocess.run([str(binary)], check=True)
