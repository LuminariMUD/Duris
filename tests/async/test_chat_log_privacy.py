"""Source contracts: players' conversation stays out of the logs (ADR 0003).

The chat log carries only petitions, the newbie channel and immortals' commands, and
cmd.debug keeps a conversation command's word but not its text.
"""

import re

from _paths import SRC, SRC_ROOT

# Every logit(LOG_CHAT, ...) left in the server, by its format string. A new one is a
# decision under ADR 0003, not a code change alone.
ALLOWED = {
    "%s petitioned '%s'",
    "%s newb chat's (%s) '%s'",
    "%s echo's '%s'",
    "%s echoa's '%s'",
    "%s echoz's '%s'",
    "%s echog's '%s'",
    "%s echoe's '%s'",
    "%s echou's '%s'",
    "%s echot's to %s '%s'",
    "%s wizmsg's '%s'",
    "%s ptells %s '%s'",
    "%s gshout's '%s'",
}
found = set()
for path in sorted(SRC_ROOT.rglob("*.c")):
    for match in re.finditer(r'logit\(\s*LOG_CHAT\s*,\s*"([^"]*)"', path.read_text()):
        found.add(match.group(1))
assert found == ALLOWED, (sorted(found - ALLOWED), sorted(ALLOWED - found))

# cmd.debug: the conversation commands keep their word and lose their text.
debug = (SRC / "debug.c").read_text()
start = debug.index("static int cmdlog_kept_length(")
body = debug[start:debug.index("\nvoid cmdlog(", start)]
cases = set(re.findall(r"case (CMD_[A-Z0-9_]+):", body))
assert cases == {
    "CMD_SAY", "CMD_TELL", "CMD_REPLY", "CMD_WHISPER", "CMD_ASK", "CMD_EMOTE",
    "CMD_PROJECT", "CMD_BEEP", "CMD_GSAY", "CMD_GCC", "CMD_ACC", "CMD_JESTROS",
    "CMD_SHOUT",
}, sorted(cases)
# "'" and ":" are say and emote even with the text glued on.
assert "str[begin] == '\\'' || str[begin] == ':'" in body
cmdlog = debug[debug.index("\nvoid cmdlog("):]
assert "cmdlog_kept_length(str)" in cmdlog
assert '" <text withheld>"' in cmdlog

print("chat log privacy contracts passed")
