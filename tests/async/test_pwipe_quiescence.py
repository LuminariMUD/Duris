from _paths import SRC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
actwiz = (SRC / "actwiz.c").read_text()
comm = (SRC / "comm.c").read_text()

pwipe_start = actwiz.rindex("case TimedShutdownData::PWIPE:")
pwipe_case = actwiz[pwipe_start:actwiz.index("default:", pwipe_start)]
assert "shutdownflag = _pwipe = 1" in pwipe_case
assert "shutdownData.eShutdownType = TimedShutdownData::NONE" in pwipe_case
assert "sql_pwipe_crossed_boundary()" in pwipe_case
assert "forcing fenced shutdown" in pwipe_case

terminal_gate = "if (!_pwipe)\n\t{\n\t\tpersistence_save_all_characters_terminal(RENT_CRASH);"
assert terminal_gate in comm
assert comm.index(terminal_gate) < comm.index("if (!_copyover && !_pwipe)\n\t{")
main_shutdown = comm[comm.index("game_loop(port, sslport);"):comm.index("/* Don't need this anymore")]
assert main_shutdown.index("game_loop(port, sslport);") < main_shutdown.index(
    "critical_command_coordinator_shutdown();"
)
assert "if (!_pwipe)" in comm[comm.index("game_loop(port, sslport);"):comm.index("/* Don't need this anymore")]

print("pwipe quiescence checks passed")
