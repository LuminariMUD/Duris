#!/usr/bin/env python3
"""Real creation/alignment/save/restart/relogin on disposable persistence.

Run with --backend flatfile or under with_disposable_mariadb.sh for mariadb.
No checkout environment, shared account, database or running MUD is used.
"""
import argparse
from contextlib import contextmanager
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
import time

from test_character_stat_choice_journey import WebSocketClient
from test_flight_network_journey import authority
from run_world_quest_dual_backend import setup_run_root
import test_flatfile_combat_journey as journey

ROOT = journey.ROOT
PASSWORD = journey.PASSWORD
SOURCES = iter(range(10, 250))


def websocket_client(server):
    # Keep independent synthetic accounts independent under per-address throttles.
    return WebSocketClient(server["websocket"], source_host="127.0.0." + str(next(SOURCES)))


@contextmanager
def isolated(args):
    with tempfile.TemporaryDirectory(prefix="alignment-", dir=ROOT / "bin/tests") as temp:
        runtime = Path(temp)
        _, critical, log = setup_run_root(runtime)
        # Generate private world outputs from this checkout's authored areas.
        (runtime / "areas").unlink()
        shutil.copytree(ROOT / "areas", runtime / "areas")
        subprocess.run(["make", "-C", str(ROOT / "areas/src"), "-j2"], check=True,
                       stdout=subprocess.DEVNULL)
        for kind in ("mob", "obj", "qst", "shp", "trg", "wld", "zon"):
            subprocess.run([str(ROOT / "bin/areas/tools" / ("make_" + kind))],
                           cwd=runtime / "areas", check=True, stdout=subprocess.DEVNULL)
            (runtime / "areas" / ("tworld." + kind)).rename(runtime / "areas" / ("world." + kind))
        with authority(args.backend, runtime) as (env, sql):
            plain, tls, websocket = journey.available_ports()
            env.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                       DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET="TRUE",
                       CREATION_ALL_RACES="FALSE", CREATION_ALL_CLASSES="FALSE")
            process = None

            def stop():
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0

            def boot():
                nonlocal process
                offset = log.stat().st_size if log.exists() else 0
                with log.open("a") as output:
                    process = subprocess.Popen([str(args.server), "-d", str(runtime), str(plain)],
                                               cwd=runtime, env=env, stdout=output, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while "Entering game loop." not in log.read_text(errors="replace")[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors="replace")[-5000:]
                    time.sleep(.1)

            def count():
                return int(sql("SELECT COUNT(*) FROM player_data")) if sql else len(list((runtime / "state/players").glob("*.snapshot")))

            def saved(name):
                if sql:
                    columns = ["alignment", "racewar", "hometown", "birthplace", "orig_birthplace", "m_class"]
                    columns += ["base_" + stat for stat in ("str", "dex", "agi", "con", "pow", "int", "wis", "cha", "kar", "luk")]
                    values = list(map(int, sql("SELECT " + ",".join(columns) + " FROM player_data WHERE name='" + name + "'").split("\t")))
                    result = dict(zip(("alignment", "racewar", "hometown", "birthplace", "original_birthplace", "m_class"), values[:6]))
                    result["base_stats"] = values[6:]
                    return result
                for path in (runtime / "state/players").glob("*.snapshot"):
                    record = json.loads(subprocess.check_output([str(args.inspector), str(runtime / "state"), "inspect", path.stem], text=True))
                    if record["name"].lower() == name.lower():
                        return record
                raise AssertionError("missing saved player " + name)

            try:
                boot()
                yield dict(plain=plain, websocket=websocket, runtime=runtime, env=env,
                           sql=sql, stop=stop, boot=boot, count=count, saved=saved)
            finally:
                stop()


def ready(client, race):
    client.command("roll_stats", {"race": race, "method": "advanced"})
    client.command("accept_stats", expected="stats_accepted")
    for stat in ("str", "dex", "agi", "luk"):
        state = client.command("add_bonus", {"stat": stat}, "bonus_added")
    assert state["phase"] == "ready" and state["bonusRemaining"] == 0
    return state


def save(client, name):
    message = client.command("game", "save", "text")
    deadline = time.monotonic() + 20
    while "Save complete for " + name + "." not in json.dumps(message):
        assert time.monotonic() < deadline, message
        message = client.receive()


def create(server, name, race_name, class_name, alignment, *, rejects=True, expected_side=None, omit_alignment=False):
    client = websocket_client(server)
    try:
        result = client.command("register", {"account": name, "password": PASSWORD,
                                           "email": name.lower() + "@example.invalid"}, "auth")
        assert result["status"] == "success", result
        options = client.command("chargen_options")
        race = next(r for r in options["races"] if r["name"].lower().replace("-", "").replace(" ", "") == race_name.lower().replace("-", "").replace(" ", ""))
        cls = next(c for c in race["classes"] if c["name"].lower() == class_name.lower())
        homes = client.command("get_hometowns", {"race": race["id"], "alignment": alignment}, "hometowns")
        assert homes["alignment"] == alignment
        home = next((h for h in homes["options"] if "Plane" in h["name"]), homes["options"][0])
        original = ready(client, race["id"])
        data = dict(name=name, race=race["id"], **{"class": cls["id"]}, sex=1,
                    alignment=alignment, hometown=home["id"], newbie=True, hardcore=True)
        before = server["count"]()
        if rejects:
            for invalid in (None, False, 0, [], {}, "", "Good", "any", "invalid"):
                client.command("create_character", {**data, "alignment": invalid}, "error")
            permitted = {"any": ("good", "neutral", "evil"), "neutral_evil": ("neutral", "evil"),
                         "good_neutral": ("good", "neutral")}.get(cls["alignment"], (cls["alignment"],))
            for invalid in set(("good", "neutral", "evil")) - set(permitted):
                client.command("create_character", {**data, "alignment": invalid}, "error")
            # These normal test races forbid Psionicist (3); creation policy
            # disables Dragoon (30). Assert metadata as well as submission,
            # so an accidentally enabled option cannot silently skip its test.
            if server["env"]["CREATION_ALL_CLASSES"] == "FALSE":
                assert not any(c["id"] in (3, 30) for c in race["classes"]), race
            for invalid in (3, 30, 11.5):
                if not any(c["id"] == invalid for c in race["classes"]):
                    client.command("create_character", {**data, "class": invalid}, "error")
            if len(permitted) > 1:
                client.command("create_character", {k: v for k, v in data.items() if k != "alignment"}, "error")
            assert server["count"]() == before, "denied submission persisted a partial body"
            swapped = client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            restored = client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            assert swapped["phase"] == restored["phase"] == "ready"
            assert restored["stats"] == original["stats"]
        if omit_alignment:
            del data["alignment"]
        created = client.command("create_character", data)
        assert created["status"] == "created" and created["alignment"] == alignment, created
        assert created["hardcore"] is False and created["newbie"] is True
        rooms = [m["data"]["num"] for m in client.messages if m.get("package") == "Room.Info"]
        if "Plane" in home["name"]:
            assert rooms[-1] == (91200 if alignment == "evil" and race["faction"] == "neutral" else 22800), rooms
        save(client, name)
        record = server["saved"](name)
        assert record["alignment"] == {"good": 1000, "neutral": 0, "evil": -1000}[alignment], record
        side = expected_side or ("evil" if race["faction"] == "evil" or (race["faction"] == "neutral" and alignment == "evil") else "good")
        assert record["racewar"] == {"good": 1, "evil": 2, "undead": 3, "neutral": 4, "none": 0}[side] and created["faction"] == side, (created, record)
        assert record["birthplace"] == record["original_birthplace"] == rooms[-1], (record, rooms, home)
        assert record["m_class"] == 1 << (cls["id"] - 1)
        assert server["count"]() == before + 1
        print("PASS WebSocket", name, race_name, class_name, alignment, "side=" + side, flush=True)
        return record
    finally:
        client.close()



def browser_case(server, args, name, race, cls, alignment, *, relog=False):
    """Exercise the paired, unmodified website; only its HTTP shell is a fixture."""
    from playwright.sync_api import sync_playwright
    args.artifacts.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(args.browser_executable) if args.browser_executable else None)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        context.add_init_script("localStorage.setItem('duris-ws-proxy', " + json.dumps(json.dumps({
            "enabled": True, "host": "127.0.0.1", "port": str(server["websocket"])})) + ");")
        page = context.new_page()
        frames, errors = [], []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type in ("error", "warning") else None)

        def socket_connected(socket):
            if str(server["websocket"]) in socket.url:
                socket.on("framereceived", lambda payload: frames.append(json.loads(payload)))
        page.on("websocket", socket_connected)

        def api(route):
            if route.request.url.split("?")[0].endswith("/site-config"):
                route.fulfill(json={
                    "siteTitle": "Duris Alignment Test", "siteLogoUrl": "", "supportUrl": "",
                    "mudHost": "127.0.0.1", "mudPort": str(server["plain"]),
                    "mudPortTls": str(server["plain"] + 1),
                    "mudWsUrl": "wss://127.0.0.1:" + str(server["websocket"]),
                    "frontPageHeroEnabled": False, "frontPageHeroTitle": "", "frontPageHeroSubtitle": "",
                    "frontPageHeroImageUrl": "", "frontPageContent": "",
                })
            elif route.request.url.split("?")[0].endswith("/map-data"):
                route.fulfill(json={"nodes": [], "edges": []})
            else:
                route.fulfill(json={"success": True, "user": None, "status": "ok", "data": []})
        page.route("**/api/**", api)
        # The website notification socket belongs to the HTTP-shell fixture;
        # MUD sockets connect to their separate listener at the root path.
        page.route_web_socket("**/ws", lambda socket: None)
        page.goto(args.frontend_url.rstrip("/") + "/play")
        assert page.url.endswith("/play") and page.title()
        if not relog:
            registration = websocket_client(server)
            try:
                result = registration.command("register", {"account": name, "password": PASSWORD,
                                                          "email": name.lower() + "@example.invalid"}, "auth")
                assert result["status"] == "success", result
            finally:
                registration.close()
        page.locator("#login-account").fill(name)
        page.locator("#login-password").fill(PASSWORD)
        page.get_by_role("button", name="Login", exact=True).click()
        if relog:
            page.get_by_role("button", name="Enter", exact=True).click()
        else:
            page.get_by_role("button", name="Create New Character", exact=True).click()
            page.get_by_role("button", name="New Player", exact=False).click()
            page.get_by_role("button", name="Next", exact=True).click()
            if race == "Thri-Kreen":
                page.get_by_role("tab", name="Neutral", exact=False).click()
            page.get_by_role("button", name=race, exact=True).click()
            page.get_by_role("button", name="Next", exact=True).click()
            page.locator("#male").click()
            page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("button", name=cls, exact=False).click()
            page.get_by_role("button", name="Next", exact=True).click()
            if cls in ("Rogue", "Warrior"):
                page.get_by_role("heading", name="Choose Your Alignment").wait_for()
                assert page.get_by_role("button", name="Next", exact=True).is_disabled()
                if cls == "Rogue":
                    assert page.locator("#good").count() == 0
                page.locator("#" + alignment).click()
                page.screenshot(path=str(args.artifacts / (name + "-alignment.png")))
                page.set_viewport_size({"width": 390, "height": 844})
                page.screenshot(path=str(args.artifacts / (name + "-mobile.png")))
                assert not page.evaluate("document.documentElement.scrollWidth > innerWidth")
                page.set_viewport_size({"width": 1280, "height": 900})
                page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("heading", name="Choose Your Hometown").wait_for()
            page.get_by_role("button", name="Plane of Life", exact=False).click()
            page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("heading", name="Choose Your Stat Rolling System").wait_for()
            page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("heading", name="Your Statistics").wait_for()
            page.get_by_role("button", name="Next", exact=True).click()
            heading = page.get_by_role("heading", name="Allocate Bonus Points")
            heading.wait_for()
            panel = heading.locator("xpath=../..")
            for remaining, index in zip(range(4, 0, -1), (0, 1, 2, 8)):
                page.get_by_text(str(remaining) + " remaining", exact=True).wait_for()
                panel.get_by_role("button").nth(index).click()
                page.get_by_text(str(remaining - 1) + " remaining", exact=True).wait_for()
            page.get_by_role("button", name="Next", exact=True).click()
            page.get_by_role("heading", name="Swap Statistics (Optional)").wait_for()
            page.get_by_role("button", name="Next", exact=True).click()
            page.locator("#name").fill(name)
            page.get_by_text("Name is available!", exact=True).wait_for()
            page.get_by_role("button", name="Next", exact=True).click()
            page.screenshot(path=str(args.artifacts / (name + "-review.png")))
            before = server["count"]()
            page.get_by_role("button", name="Create Character", exact=True).click()
        field = page.get_by_placeholder("Command (↑ to repeat)")
        try:
            field.wait_for(timeout=20000)
        except Exception:
            page.screenshot(path=str(args.artifacts / (name + "-error.png")))
            raise AssertionError((page.locator("body").inner_text(), frames[-12:], errors))
        field.fill("save")
        field.press("Enter")
        deadline = time.monotonic() + 20
        while "Save complete for " + name + "." not in json.dumps(frames):
            assert time.monotonic() < deadline, (frames[-5:], page.locator("body").inner_text())
            page.wait_for_timeout(100)
        record = server["saved"](name)
        assert record["alignment"] == {"evil": -1000, "neutral": 0}[alignment] and record["racewar"] == 1
        assert record["birthplace"] == record["original_birthplace"] == 22800
        if not relog:
            assert server["count"]() == before + 1
            created = next(frame for frame in frames if frame.get("type") == "create_character")
            assert created["alignment"] == alignment and created["faction"] == "good", created
        relevant_errors = [error for error in errors if not error.startswith("[VUE_ROUTER_R0025]")]
        assert not relevant_errors, relevant_errors
        if errors:
            print("NOTE existing Vue Router navigation-guard deprecation warning", flush=True)
        page.screenshot(path=str(args.artifacts / (name + ("-relogin" if relog else "-game") + ".png")))
        browser.close()
        print("PASS Chromium", "relogin" if relog else "creation", name, alignment, flush=True)
        return record


def run(args):
    with isolated(args) as server:
        records = {}
        browser_cases = (("Webnecro", "Human", "Necromancer", "evil"),
                         ("Webdruid", "Human", "Druid", "neutral"),
                         ("Webrogue", "Human", "Rogue", "evil"),
                         ("Webneutral", "Thri-Kreen", "Warrior", "neutral"))
        if args.frontend_url:
            for case in browser_cases:
                records[case[0]] = browser_case(server, args, *case)
        for case in (("Necrocheck", "Human", "Necromancer", "evil"),
                     ("Druidcheck", "Human", "Druid", "neutral"),
                     ("Roguecheck", "Human", "Rogue", "neutral"),
                     ("Rogueevil", "Human", "Rogue", "evil"),
                     ("Neutralbug", "Thri-Kreen", "Warrior", "neutral"),
                     ("Evilcheck", "Thri-Kreen", "Warrior", "evil")):
            records[case[0]] = create(server, *case, omit_alignment=case[0] == "Druidcheck")
        # Telnet fixed evil/neutral cases must produce the same rules and towns.
        for name, cls, alignment in (("Telnecro", "n", -1000), ("Teldruid", "d", 0)):
            client = journey.MudClient(server["plain"], source_host="127.0.0.2")
            try:
                journey.create_character(client, expected_room=None, class_name=cls,
                                         account=name, character=name, email=name + "@example.invalid", hometown="p")
                client.send("save")
                client.expect("Save complete for " + name + ".")
                record = server["saved"](name)
                assert record["alignment"] == alignment and record["racewar"] == 1, record
                records[name] = record
            finally:
                client.close()
        server["stop"]()
        server["boot"]()
        # An evil-aligned Human still records good-side admission. The same
        # account cannot immediately create an evil-side Thri-kreen.
        client = websocket_client(server)
        try:
            result = client.command("login", {"account": "Necrocheck", "password": PASSWORD}, "auth")
            assert result["status"] == "success", result
            options = client.command("chargen_options")
            race = next(r for r in options["races"] if r["name"] == "Thri-Kreen")
            original = ready(client, race["id"])
            homes = client.command("get_hometowns", {"race": race["id"], "alignment": "evil"}, "hometowns")
            before = server["count"]()
            error = client.command("create_character", {"name": "Deniedside", "race": race["id"],
                                   "class": 1, "sex": 1, "alignment": "evil",
                                   "hometown": homes["options"][0]["id"]}, "error")
            assert "side" in json.dumps(error).lower() or "evil" in json.dumps(error).lower(), error
            assert server["count"]() == before
            state = client.command("swap_stats", {"stat1": "str", "stat2": "luk"}, "stats_swapped")
            assert state["phase"] == "ready" and state["stats"]["str"] == original["stats"]["luk"]
        finally:
            client.close()
        for name, original in records.items():
            if args.frontend_url and name in {case[0] for case in browser_cases}:
                continue
            client = websocket_client(server)
            try:
                result = client.command("login", {"account": name, "password": PASSWORD}, "auth")
                assert result["status"] == "success"
                client.command("enter", {"character": name}, "gmcp")
                save(client, name)
                record = server["saved"](name)
                for key in ("alignment", "racewar", "birthplace", "original_birthplace", "m_class", "base_stats"):
                    assert record[key] == original[key], (name, key, original[key], record[key])
            finally:
                client.close()
        if args.frontend_url:
            for case in browser_cases:
                record = browser_case(server, args, *case, relog=True)
                for key in ("alignment", "racewar", "birthplace", "original_birthplace", "m_class", "base_stats"):
                    assert record[key] == records[case[0]][key], (case[0], key)
        print("PASS", args.backend, "creation/save/restart/relogin: alignment, faction, hometown, class and stats", flush=True)
        server["stop"]()
        server["env"].update(CREATION_ALL_RACES="TRUE", CREATION_ALL_CLASSES="TRUE")
        server["boot"]()
        create(server, "Overrideps", "Human", "Psionicist", "neutral", rejects=False)
        create(server, "Overridehalf", "Half Elf", "Druid", "neutral", rejects=False)
        # Normal restrictions survive both overrides.
        create(server, "Overridenec", "Human", "Necromancer", "evil")
        create(server, "Overrideharp", "Harpy", "Warrior", "neutral", rejects=False, expected_side="neutral")
        create(server, "Overrideshad", "Shade", "Warrior", "evil", rejects=False, expected_side="undead")
        create(server, "Overrideilli", "Illithid", "Psionicist", "evil", rejects=False, expected_side="none")
        print("PASS existing race/class overrides without changing normal-cell alignment", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("flatfile", "mariadb"), required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--inspector", type=Path, required=True)
    parser.add_argument("--browser-executable", type=Path, help="use an installed Chromium binary")
    parser.add_argument("--frontend-url", help="also qualify the paired website in real Chromium")
    parser.add_argument("--artifacts", type=Path, default=Path("/tmp/creation-alignment-browser"))
    args = parser.parse_args()
    args.server = args.server.resolve()
    args.inspector = args.inspector.resolve()
    run(args)
