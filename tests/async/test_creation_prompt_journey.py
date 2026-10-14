#!/usr/bin/env python3
"""Real Telnet account/character creation, correction, confirmation and relog.

Each scenario boots an isolated flat-file server with synthetic accounts. No
production account, database, or listener is used. The existing recovery fixture
provides the real socket client and server lifecycle, not mocked nanny handlers.
"""

from pathlib import Path
import json
import socket
import subprocess
import tempfile
import time

from test_account_recovery_journey import (
    ACCOUNT, OLD_PASSWORD, EMAIL, IsolatedServer, MudClient,
    build_flatfile_server, create_account, enter_account_name, require,
)
from test_flatfile_combat_journey import make_overlord

PASSWORD_PROMPT = "Please enter your password:  "
CONFIRM_PASSWORD = "Please re-enter the same password to confirm:  "
MENU = "Please select an option: "
NAME_PROMPT = "Enter your new name:  "
RACE_MENU = "Your selection: "
KEEP = "Do you want to keep this character? (Y/N/Q)"
STAFF = "Ostrand"


def reply(client, answer, prompt):
    client.send(answer)
    return client.expect(prompt, timeout=5)


def require_prompt_framed(client, prompt, timeout=3):
    """Require Telnet IAC GA straight after the last copy of an unterminated prompt.

    Line-buffering clients show a prompt with no newline only once GA arrives, so
    a prompt queued without it looks to the player as if nothing happened.
    """
    needle = prompt.encode("ascii")
    deadline = time.monotonic() + timeout
    while True:
        wire = bytes(client.transcript)
        rest = wire[wire.rfind(needle) + len(needle):]
        # Echo negotiation is written directly, so only GA should follow the text.
        while rest[:3] in (b"\xff\xfb\x01", b"\xff\xfc\x01"):
            rest = rest[3:]
        if rest.startswith(b"\xff\xf9"):
            return
        require(time.monotonic() < deadline,
                f"{prompt!r} was not followed by Telnet GA; next bytes: {rest[:12].hex(' ') or 'none'}")
        client._receive()


def enter_email(client):
    enter_account_name(client)
    client.expect("is this correct?")
    reply(client, "y", "email address:  ")


def account_name_retry(client, server):
    enter_account_name(client)
    client.expect("is this correct?")
    reply(client, "?", "is this correct?")
    reply(client, "n", "Account Name: ")
    reply(client, "123", "Account Name: ")
    reply(client, ACCOUNT, "is this correct?")
    reply(client, "y", "email address:  ")


def email_retry(client, server):
    enter_email(client)
    reply(client, "bad-email", "Email address:  ")
    reply(client, "first@example.invalid", "is this correct?")
    reply(client, "?", "is this correct?")
    reply(client, "n", "Please enter your email address:  ")
    reply(client, EMAIL, "is this correct?")
    reply(client, "y", PASSWORD_PROMPT)


def password_and_summary_retry(client, server):
    enter_email(client)
    reply(client, EMAIL, "is this correct?")
    reply(client, "y", PASSWORD_PROMPT)
    # Control: this prompt is queued while handling input, which always framed it.
    require_prompt_framed(client, PASSWORD_PROMPT)
    for invalid in ("", "    ", "abc", "alllowercase"):
        reply(client, invalid, PASSWORD_PROMPT)
    # The prompts below are queued when the password worker finishes, not on input.
    reply(client, OLD_PASSWORD, CONFIRM_PASSWORD)
    require_prompt_framed(client, CONFIRM_PASSWORD)
    reply(client, "Different9!", "Passwords do not match!")
    client.expect(PASSWORD_PROMPT)
    require_prompt_framed(client, PASSWORD_PROMPT)
    reply(client, OLD_PASSWORD, CONFIRM_PASSWORD)
    reply(client, OLD_PASSWORD, "Is this information correct?")
    require_prompt_framed(client, "Is this information correct?  (Y/N) ")
    reply(client, "?", "Is this information correct?")
    reply(client, "n", "Please enter your account name: ")
    # Starting over must not have saved the abandoned registration.
    reply(client, ACCOUNT, "is this correct?")
    reply(client, "y", "email address:  ")
    reply(client, EMAIL, "is this correct?")
    reply(client, "y", PASSWORD_PROMPT)
    reply(client, OLD_PASSWORD, CONFIRM_PASSWORD)
    reply(client, OLD_PASSWORD, "Is this information correct?")
    reply(client, "y", "PRESS RETURN")
    reply(client, "", MENU)
    # The same confirmation handler also serves account-menu password changes.
    reply(client, "6", PASSWORD_PROMPT)
    reply(client, OLD_PASSWORD, CONFIRM_PASSWORD)
    require_prompt_framed(client, CONFIRM_PASSWORD)
    reply(client, OLD_PASSWORD, MENU)
    require_prompt_framed(client, MENU)
    wire = bytes(client.transcript)
    require(OLD_PASSWORD.encode() not in wire, "password was echoed to the player")
    require(b"\xff\xfb\x01" in wire, "password input never disabled Telnet echo")
    require(wire.rfind(b"\xff\xfc\x01") > wire.rfind(b"\xff\xfb\x01"),
            "Telnet echo was not restored after confirmation")


def start_character(client):
    reply(client, "2", NAME_PROMPT)


def character_name_retry(client, server, *, policy=False, invalid=False):
    create_account(client, OLD_PASSWORD)
    start_character(client)
    if invalid:
        reply(client, "123", "Illegal character name, please try another.")
        client.expect(NAME_PROMPT)
        # A god_list name makes an OVERLORD of whoever takes it, so creation
        # refuses one whether or not a character already holds it.
        for god in ("Tyrus", "Zusuk"):
            reply(client, god, "Illegal character name, please try another.")
            client.expect(NAME_PROMPT)
    reply(client, "Taverek", "Is this correct?")
    reply(client, "?", "Please type Yes or No")
    if policy:
        reply(client, "y", "meet these criteria?")
        reply(client, "?", "Please type Yes or No")
    reply(client, "n", NAME_PROMPT)
    # One replacement input must be consumed as the name, not discarded.
    reply(client, "Veralis", "You chose the name Veralis")
    client.expect("Is this correct?")
    reply(client, "y", "meet these criteria?")
    reply(client, "y", RACE_MENU)


def reach_race(client):
    create_account(client, OLD_PASSWORD)
    start_character(client)
    reply(client, "Taverek", "Is this correct?")
    reply(client, "y", "meet these criteria?")
    reply(client, "y", RACE_MENU)


def creation_help_and_back(client, server):
    reach_race(client)
    reply(client, "?", RACE_MENU)
    reply(client, "x", "Press return to go back to the race selection menu.")
    reply(client, "", RACE_MENU)
    reply(client, "y", "Press Return and choose your race with care...")
    reply(client, "", RACE_MENU)
    # Uppercase is advertised as help, not an unavailable race selection.
    help_output = reply(client, "H", "[Press Return or Enter to return to the Race Menu]")
    require("not currently available" not in help_output, "race help rejected as a selection")
    reply(client, "", RACE_MENU)
    reply(client, "h", "Male or Female")
    reply(client, "z", RACE_MENU)
    # Mindflayers have no sex choice: their class menu promises a return to race.
    for race in ("Illithid", "Planetbound Illithid"):
        reply(client, race, "H (for Hardcore), N (for Normal)")
        reply(client, "n", "Class Selection")
        client.expect("z) Return to previous menu (selecting your race).")
        client.expect(RACE_MENU)
        reply(client, "z", RACE_MENU)
    reply(client, "h", "Male or Female")
    reply(client, "m", "H (for Hardcore), N (for Normal)")
    reply(client, "n", "Class Selection")
    client.expect(RACE_MENU)
    reply(client, "W", "[Press Return or Enter to return to the Class Menu]")
    reply(client, "", "Class Selection")
    client.expect(RACE_MENU)
    reply(client, "z", "Male or Female")
    reply(client, "f", "H (for Hardcore), N (for Normal)")


def reboot(server):
    """Boot the shut-down isolated server again on the same state and port."""
    server.output.close()
    server.output_path = server.run_root / "restarted.out"
    server.output = server.output_path.open("w", encoding="utf-8")
    server.process = subprocess.Popen(
        server.process.args, cwd=server.run_root, env=server.environment,
        text=True, stdout=server.output, stderr=subprocess.STDOUT,
    )


def invitation_rejection(client, server, *, invited=False):
    create_account(client, OLD_PASSWORD)
    start_character(client)
    # Creation refuses god_list names, so the staff character that runs the
    # real invitation-mode command is an ordinary one raised offline.
    reply(client, STAFF, "Is this correct?")
    reply(client, "y", "meet these criteria?")
    reply(client, "y", RACE_MENU)
    finish_character_choices(client)
    reply(client, "y", "PRESS RETURN")
    reply(client, "", "Your starter kit is ready")
    client.expect("Pos: standing >")
    reply(client, "save", f"Save complete for {STAFF}.")
    # A mortal must camp to quit, so the server stops with the character in game.
    server.shutdown()
    make_overlord(server.state_root, STAFF)
    reboot(server)
    client = MudClient(server.plain_port)
    try:
        enter_account_name(client)
        client.expect("Please enter your password:")
        reply(client, OLD_PASSWORD, "PRESS RETURN")
        reply(client, "", MENU)
        reply(client, "1", STAFF)
        reply(client, "1", "(Y/N)")
        reply(client, "y", "<>")
        response = reply(client, "invite on", "<>")
        require("Huh?" not in response, f"invitation command unavailable: {response}")
        if invited:
            # Invitation records use the legacy directory in this private runtime.
            invitation = server.run_root / "Players/Invited/t/taverek"
            invitation.parent.mkdir(parents=True)
            reply(client, "invite Taverek", "Invited.")
            client.expect("<>")
            require(invitation.is_file(), "invitation command did not save its record")
        reply(client, "quit", "ACCOUNT MENU")
        client.expect(MENU)
        start_character(client)
        reply(client, "Taverek", "Is this correct?")
        reply(client, "y", "meet these criteria?")
        reply(client, "y", RACE_MENU)
        if invited:
            reply(client, "d", "Male or Female")
            return
        reply(client, "d", "only those players that have been invited")
        client.expect(RACE_MENU)
        reply(client, "h", "Male or Female")
    finally:
        client.close()


def invitation_allowed(client, server):
    invitation_rejection(client, server, invited=True)


def sexless_chaos_menu(client, server):
    reach_race(client)
    for race in ("Illithid", "Planetbound Illithid"):
        output = reply(client, race, "Class Selection")
        require("Hardcore" not in output, "Chaos offered disabled Hardcore mode")
        client.expect(RACE_MENU)
        reply(client, "z", RACE_MENU)


def finish_character_choices(client, *, exercise_retries=False, choose_hardcore=False):
    reply(client, "h", "Male or Female")
    if exercise_retries:
        reply(client, "?", "Please select either F")
    reply(client, "m", "H (for Hardcore), N (for Normal)")
    if exercise_retries:
        reply(client, "?", "H (for Hardcore), N (for Normal)")
    reply(client, "h" if choose_hardcore else "n", "Class Selection")
    client.expect(RACE_MENU)
    if exercise_retries:
        reply(client, "?", "Class Selection")
        client.expect(RACE_MENU)
        reply(client, "4", "This is not an allowed class for your race!")
        client.expect("Class Selection")
        client.expect(RACE_MENU)
    reply(client, "w", "Alignment only affects")
    client.expect(RACE_MENU)
    if exercise_retries:
        reply(client, "?", "Please choose an alignment: ")
    reply(client, "g", RACE_MENU)
    if exercise_retries:
        reply(client, "?", "Please choose a real hometown: ")
    reply(client, "p", "Press return to continue")
    finish_stat_choices(client, exercise_retries=exercise_retries)


def finish_stat_choices(client, *, exercise_retries=False):
    reply(client, "", "first bonus")
    for next_bonus in ("second bonus", "third bonus", "fourth bonus"):
        if exercise_retries:
            reply(client, "?", "bonus:")
        reply(client, "s", next_bonus)
    if exercise_retries:
        reply(client, "?", "fourth bonus:")
    reply(client, "s", "swap stats (Y/N): ")
    if exercise_retries:
        reply(client, "?", "swap stats (Y/N): ")
        reply(client, "y", "Enter two letters separated by a space to swap:")
        reply(client, "bogus", "swap stats (Y/N): ")
        reply(client, "y", "Enter two letters separated by a space to swap:")
        reply(client, "s d", "swap more stats (Y/N): ")
    reply(client, "n", KEEP)


def keep_confirmation(client, server):
    reach_race(client)
    finish_character_choices(client, exercise_retries=True)
    for invalid in ("?", "", "    "):
        reply(client, invalid, KEEP)
    reply(client, "n", "Discarding this character.")
    client.expect(MENU)
    reply(client, "1", "Account currently doesn't have any characters (0/")
    client.expect(MENU)


def quit_confirmation(client, server):
    reach_race(client)
    finish_character_choices(client)
    reply(client, "q", "Come back again real soon.")
    client.socket.settimeout(5)
    while client.socket.recv(4096):
        pass
    other = MudClient(server.plain_port)
    try:
        enter_account_name(other)
        other.expect("Please enter your password:")
        reply(other, OLD_PASSWORD, "PRESS RETURN")
        # Login password checks finish on the worker too.
        require_prompt_framed(other, "PRESS RETURN: ")
        reply(other, "", MENU)
        reply(other, "1", "Account currently doesn't have any characters (0/")
        other.expect(MENU)
    finally:
        other.close()


def normal_after_hardcore(client, server):
    reach_race(client)
    reply(client, "h", "Male or Female")
    reply(client, "m", "H (for Hardcore), N (for Normal)")
    reply(client, "h", "Class Selection")
    client.expect(RACE_MENU)
    reply(client, "z", "Male or Female")
    reply(client, "z", RACE_MENU)
    finish_character_choices(client)
    reply(client, "y", "PRESS RETURN")
    reply(client, "", "Your starter kit is ready")
    client.expect("Pos: standing >")
    score = reply(client, "score", "Pos: standing >")
    require("HardCore pts:" not in score, "Normal choice retained the previous Hardcore flag")
    require("Taverek" in score, "score did not display the new character")
    reply(client, "save", "Save complete for Taverek.")
    # A resident linkdead character reconnects immediately by design. Restart
    # the server to exercise disk reload and the saved-character confirmation.
    server.shutdown()
    reboot(server)
    other = MudClient(server.plain_port)
    try:
        enter_account_name(other)
        other.expect("Please enter your password:")
        reply(other, OLD_PASSWORD, "PRESS RETURN")
        # Login password checks finish on the worker too.
        require_prompt_framed(other, "PRESS RETURN: ")
        reply(other, "", MENU)
        reply(other, "1", "Taverek")
        reply(other, "1", "(Y/N)")
        reply(other, "?", "Please answer (Y/N): ")
        reply(other, "n", "Taverek")
        reply(other, "1", "(Y/N)")
        reply(other, "y", "Pos: standing >")
        score = reply(other, "score", "Pos: standing >")
        require("Taverek" in score and "HardCore pts:" not in score,
                "saved character did not reconnect with Normal mode")
    finally:
        other.close()


def human_necromancer_creation(client, server):
    """Telnet accepts the evil-only Human cell that JSON faction alignment rejects."""
    reach_race(client)
    reply(client, "h", "Male or Female")
    reply(client, "m", "H (for Hardcore), N (for Normal)")
    reply(client, "n", "Class Selection")
    client.expect(RACE_MENU)
    selected = reply(client, "n", RACE_MENU)
    require("Alignment only affects" not in selected, "evil-only class unexpectedly offered alignment choice")
    reply(client, "p", "Press return to continue")
    finish_stat_choices(client)
    reply(client, "y", "PRESS RETURN")
    reply(client, "", "Your starter kit is ready")
    client.expect("Pos: standing >")
    score = reply(client, "score", "Pos: standing >")
    require("human" in score.lower() and "necromancer" in score.lower(),
            "Telnet did not create the allowed Human Necromancer")


def websocket_creation(client, server):
    """Normal JSON menus/denials/creation, then a persisted Telnet relog."""
    from test_connection_limit_journey import upgrade, send_frame, take_frame

    create_account(client, OLD_PASSWORD)
    client.close()
    ws = socket.create_connection(("127.0.0.1", int(server.environment["DURIS_WEBSOCKET_PORT"])), timeout=5)
    messages = []
    buffer = bytearray(upgrade(ws, "127.0.0.1"))
    ws.settimeout(.25)

    def wait(predicate):
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            for index, message in enumerate(messages):
                if predicate(message):
                    return messages.pop(index)
            while (frame := take_frame(buffer)) is not None:
                if frame[0] == 9:
                    send_frame(ws, 10, frame[1])
                elif frame[0] == 1:
                    messages.append(json.loads(frame[1]))
            try:
                chunk = ws.recv(65536)
            except socket.timeout:
                continue
            require(bool(chunk), "WebSocket creation connection closed")
            buffer.extend(chunk)
        raise AssertionError("WebSocket response missing: " + repr(messages[-8:]))

    def request(command, data, predicate):
        payload = json.dumps({"type": "cmd", "cmd": command, "data": data}, separators=(",", ":")).encode()
        require(len(payload) < 126, "reuse of the small-frame helper exceeded its payload bound")
        send_frame(ws, 1, payload)
        return wait(predicate)

    def text(needle):
        return lambda message: needle in json.dumps(message)

    selection = {"name": "Webhero", "race": 1, "class": 1, "sex": 1}
    try:
        request("create_character", selection, text("Not authenticated"))
        options = request("chargen_options", {}, lambda m: m.get("type") == "chargen_options")
        human = next(race for race in options["races"] if race["name"] == "Human")
        require(not any(race["restricted"] for race in options["races"]), "normal menu exposed restricted races")
        require(not any(cls["name"] == "Dragoon" for race in options["races"] for cls in race["classes"]),
                "normal menu exposed disabled Dragoon")
        necromancer = next(cls for cls in human["classes"] if cls["name"] == "Necromancer")
        require(necromancer["alignment"] == "evil", "Human Necromancer menu alignment changed")
        request("login", {"account": ACCOUNT, "password": OLD_PASSWORD},
                lambda m: m.get("type") == "auth" and m.get("status") == "success")
        request("create_character", dict(selection, race=21), text("Invalid race selection"))  # Lich.
        request("create_character", dict(selection, **{"class": 30}),
                text("That class is not available for your race"))  # Dragoon.
        request("create_character", dict(selection, **{"class": necromancer["id"]}, alignment="evil"),
                text("That class requires evil alignment"))
        # Human is a good-faction race in this transport: the requested alignment
        # does not override it. Telnet's class-cell alignment choice is separate.
        rolled = request("roll_stats", {"race": 1}, lambda m: m.get("type") == "roll_stats")
        remaining = rolled["bonusRemaining"]
        require(remaining == 5, "initial roll did not supply five bonus points")
        for stat in ("str", "dex", "agi", "con", "pow", "int", "wis", "cha", "luk"):
            bonus = request("add_bonus", {"stat": stat},
                            lambda m: m.get("type") == "bonus_added" or "Stat is already at maximum" in json.dumps(m))
            if bonus.get("type") == "bonus_added":
                require(bonus["bonusRemaining"] == remaining - 1, "bonus point was not consumed exactly once")
                remaining -= 1
            if not remaining:
                break
        require(not remaining, "five stat bonuses could not be allocated")
        created = request("create_character", selection,
                          lambda m: m.get("type") == "create_character" and m.get("status") == "created")
        require(created["name"] == "Webhero" and created["race"] == "Human" and created["class"] == "Warrior",
                "WebSocket created a different identity")
        wait(text("Your starter kit is ready"))
        request("create_character", dict(selection, name="Otherhero", race=13), text("You must wait"))
        # The good-side admission was committed; the opposite-side request is
        # denied before it can replace the resident character or consume its state.
        request("game", {"command": "skills"}, text("kick"))
        request("game", {"command": "save"}, text("Save complete for Webhero."))
        server.shutdown()
    finally:
        ws.close()
    reboot(server)
    other = MudClient(server.plain_port)
    try:
        enter_account_name(other)
        other.expect("Please enter your password:")
        reply(other, OLD_PASSWORD, "PRESS RETURN")
        reply(other, "", MENU)
        reply(other, "1", "Webhero")
        reply(other, "1", "(Y/N)")
        reply(other, "y", "Pos: standing >")
        score = reply(other, "score", "Pos: standing >")
        require("Webhero" in score and "human" in score.lower() and "warrior" in score.lower(),
                "WebSocket identity did not survive restart/Telnet relog")
        skills = reply(other, "skills", "Pos: standing >")
        require("kick" in skills.lower(), "starting class skill did not survive restart")
    finally:
        other.close()


SCENARIOS = (
    ("Telnet Human Necromancer transport characterization", human_necromancer_creation),
    ("WebSocket normal menus, denials, creation and restart/Telnet relog", websocket_creation),
    ("account-name rejection", account_name_retry),
    ("email correction", email_retry),
    ("password mismatch and account-summary restart", password_and_summary_retry),
    ("invalid character name", lambda c, s: character_name_retry(c, s, invalid=True)),
    ("character-name rejection", character_name_retry),
    ("name-policy rejection", lambda c, s: character_name_retry(c, s, policy=True)),
    ("creation help and back navigation", creation_help_and_back),
    ("invitation-only race rejection", invitation_rejection),
    ("invited evil-race creation", invitation_allowed),
    ("sexless race creation with Hardcore disabled in Chaos", sexless_chaos_menu),
    ("selection retries and final discard", keep_confirmation),
    ("final quit flushes its farewell without saving a character", quit_confirmation),
    ("Hardcore correction, world entry, save/restart and relog", normal_after_hardcore),
)


def run_journeys(binary):
    failures = []
    for name, scenario in SCENARIOS:
        environment = {"CHAOS_MUD": "FALSE", "CREATION_ALL_RACES": "FALSE", "CREATION_ALL_CLASSES": "FALSE"}
        if scenario in (creation_help_and_back, invitation_rejection, invitation_allowed, sexless_chaos_menu):
            environment["CREATION_ALL_RACES"] = "TRUE"
        if scenario is sexless_chaos_menu:
            environment["CHAOS_MUD"] = "TRUE"
        if scenario is websocket_creation:
            environment = {"DURIS_WEBSOCKET": "TRUE", "CHAOS_MUD": "FALSE",
                           "CREATION_ALL_RACES": "FALSE", "CREATION_ALL_CLASSES": "FALSE"}
        with IsolatedServer(binary, environment) as server:
            client = MudClient(server.plain_port)
            try:
                scenario(client, server)
                server.shutdown()
                print(f"PASS creation journey: {name}", flush=True)
            except AssertionError as error:
                failures.append(f"{name}: {error}")
                print(f"FAIL creation journey: {name}: {error}", flush=True)
            finally:
                client.close()
    require(not failures, "Creation journey failures:\n" + "\n".join(failures))


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="creation-prompts-build-") as build_tmp:
        run_journeys(build_flatfile_server(Path(build_tmp)))
