#!/usr/bin/env python3
"""The real browser client keeps a launch refusal visible after its socket closes.

Run against a local DurisWeb frontend; only its unrelated HTTP shell is mocked.
Registration and the refusal use an actual disposable MUD WebSocket listener.
"""

import argparse
import json
from pathlib import Path
import time

from playwright.sync_api import sync_playwright
from test_account_recovery_journey import IsolatedServer
from run_pwipe_launch_gate_journey import launch_config, ROOT


def run(binary, frontend_url, browser_executable=None):
    output = ROOT / "bin/analysis/pwipe-launch"
    output.mkdir(parents=True, exist_ok=True)
    evidence = {"frontend_url": frontend_url, "browser": "Chromium 1280x900",
                "browser_plugin": "Browser plugin not available; regular Playwright", "passed": False}

    def prepare(root):
        launch_config(root / "lib/pwipe_launch.cfg", int(time.time()) + 300)

    try:
        with IsolatedServer(binary, {"DURIS_WEBSOCKET": "TRUE"}, prepare_run_root=prepare) as server:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, executable_path=str(browser_executable) if browser_executable else None)
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.add_init_script("localStorage.setItem('duris-ws-proxy', " + json.dumps(json.dumps({
                    "enabled": True, "host": "127.0.0.1", "port": str(server.websocket_port)})) + ");")
                page = context.new_page()
                errors, frames, closed, console = [], [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("console", lambda message: console.append(message.text) if message.type in ("error", "warning") else None)

                def socket_opened(socket):
                    if str(server.websocket_port) in socket.url:
                        socket.on("framereceived", lambda frame: frames.append(json.loads(frame)))
                        socket.on("close", lambda: closed.append(True))

                page.on("websocket", socket_opened)

                def api(route):
                    if route.request.url.split("?")[0].endswith("/site-config"):
                        route.fulfill(json={
                            "siteTitle": "Local Launch QA", "siteLogoUrl": "", "supportUrl": "",
                            "mudHost": "127.0.0.1", "mudPort": str(server.plain_port), "mudPortTls": "",
                            "mudWsUrl": f"wss://127.0.0.1:{server.websocket_port}",
                            "frontPageHeroEnabled": False, "frontPageHeroTitle": "", "frontPageHeroSubtitle": "",
                            "frontPageHeroImageUrl": "", "frontPageContent": ""})
                    elif route.request.url.split("?")[0].endswith("/map-data"):
                        route.fulfill(json={"nodes": [], "edges": []})
                    else:
                        route.fulfill(json={"success": True, "user": None, "status": "ok", "data": []})

                page.route("**/api/**", api)
                page.goto(frontend_url.rstrip("/") + "/play")
                page.get_by_role("tab", name="Register", exact=True).click()
                page.locator("#register-account").fill("Newlaunch")
                page.locator("#register-email").fill("newlaunch@example.invalid")
                page.locator("#register-password").fill("Qz7!mN4@")
                page.locator("#register-confirm").fill("Qz7!mN4@")
                page.get_by_role("button", name="Create Account", exact=True).click()
                deadline = time.monotonic() + 10
                while not closed and time.monotonic() < deadline:
                    page.wait_for_timeout(100)
                evidence.update(url=page.url, title=page.title(), frames=frames, errors=errors,
                                socket_closed=bool(closed), visible_text=page.locator("body").inner_text())
                page.wait_for_timeout(350)  # Let the existing dialog transition finish for visual QA.
                page.screenshot(path=str(output / "browser-denial.png"), full_page=False)
                assert closed, "the server did not drain/disconnect the denied browser connection"
                assert any(frame.get("status") == "failed" and "Reconnect at" in frame.get("error", "") for frame in frames)
                dialog = page.get_by_role("alertdialog", name="Disconnected")
                assert dialog.get_by_text("The new season is being prepared.", exact=False).is_visible(), evidence["visible_text"]
                assert "Reconnect at" in evidence["visible_text"]
                assert not page.locator("vite-error-overlay").count()
                assert not errors, errors
                assert page.url.endswith("/play") and page.title()
                for width in (375, 768, 1280):
                    page.set_viewport_size({"width": width, "height": 900})
                    assert dialog.get_by_text("Reconnect at", exact=False).is_visible()
                    page.screenshot(path=str(output / f"browser-denial-{width}.png"), full_page=False)
                evidence.update(console=console, viewports=[375, 768, 1280])
                evidence["passed"] = True
                browser.close()
                print("PASS: browser displays the real launch reason/date after the WebSocket denial drains", flush=True)
    finally:
        (output / "browser.json").write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--frontend-url", required=True)
    parser.add_argument("--browser-executable", type=Path)
    args = parser.parse_args()
    run(args.server.resolve(strict=True), args.frontend_url, args.browser_executable)
