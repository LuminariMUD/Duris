from _paths import SRC
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
structs = (SRC / "structs.h").read_text()
actoth = (SRC / "actoth.c").read_text()
nanny = (SRC / "nanny.c").read_text()
sql_player = (SRC / "sql_player.c").read_text()

assert "constexpr int DEFAULT_SCREEN_LENGTH = 40;" in structs

assert "ch->only.pc->screen_length = DEFAULT_SCREEN_LENGTH;" in nanny
assert "ch->only.pc->screen_length = reset ? DEFAULT_SCREEN_LENGTH : number;" in actoth
assert 'snprintf(Gbuf3, sizeof Gbuf3, "%d", ch->only.pc->screen_length);' in actoth
assert 'snprintf(Gbuf3, MAX_INPUT_LENGTH, "%3d", DEFAULT_SCREEN_LENGTH);' in actoth
assert "Screen length set to default %s lines." in actoth

for runtime_source in (actoth, nanny, sql_player):
    assert "screen_length = 24" not in runtime_source
    assert "default 24 lines" not in runtime_source

print("screen-length default contract passed")
