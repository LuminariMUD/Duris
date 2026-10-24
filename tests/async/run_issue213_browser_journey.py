#!/usr/bin/env python3
"""Real Chromium onboarding against a disposable full-world MUD and a live frontend.

Requires Python Playwright and Chromium. Run the SQL leg under
with_disposable_mariadb.sh. Only the unrelated website HTTP shell and map-data
are fixtures; all account, chargen, hometown, room and warning traffic uses the
real MUD. No repository .env, shared account or production service is used.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import uuid

from playwright.sync_api import sync_playwright
import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority, command
from run_world_quest_dual_backend import setup_run_root
from run_issue213_onboarding_journey import authored_graph, guild_rooms, path_between

ROOT = journey.ROOT
GOD, GOD_ACCOUNT = 'Browserward', 'Browserstaff'


@contextmanager
def full_world(args):
    with tempfile.TemporaryDirectory(prefix='issue213-browser-') as temporary:
        runtime = Path(temporary)
        _, critical, log = setup_run_root(runtime)
        (runtime / 'help').symlink_to(ROOT / 'help', target_is_directory=True)
        plain, tls, websocket = journey.available_ports()
        process = None
        with authority(args.backend, runtime) as (environment, sql):
            environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls),
                               DURIS_WEBSOCKET_PORT=str(websocket), DURIS_WEBSOCKET='TRUE')
            def boot():
                nonlocal process
                offset = log.stat().st_size if log.exists() else 0
                with log.open('a') as stream:
                    process = subprocess.Popen([str(args.server), '-d', str(runtime), str(plain)],
                        cwd=runtime, env=environment, stdout=stream, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 120
                while 'Entering game loop.' not in log.read_text(errors='replace')[offset:]:
                    assert process.poll() is None and time.monotonic() < deadline, log.read_text(errors='replace')[-5000:]
                    time.sleep(.1)
            def stop():
                if process and process.poll() is None:
                    process.terminate()
                    process.wait(timeout=45)
                    assert process.returncode == 0
            try:
                boot()
                staff = journey.MudClient(plain, source_host='127.0.0.90')
                journey.create_character(staff, expected_room=None, account=GOD_ACCOUNT, character=GOD,
                                         email='browserward@example.invalid', hometown='t')
                staff.send('save')
                staff.expect('Save complete for ' + GOD + '.')
                staff.close()
                stop()
                if sql:
                    sql(f"UPDATE player_data SET level=62,highest_level=62 WHERE name='{GOD}'")
                else:
                    journey.make_overlord(Path(environment['FLATFILE_STATE_DIR']), GOD)
                boot()
                yield {'runtime': str(runtime), 'plain': plain, 'tls': tls, 'websocket': websocket}, sql
            finally:
                stop()
                if log.exists():
                    args.output.with_suffix('.log').write_bytes(log.read_bytes())


def exercise(server, sql, args, evidence):
    character = 'Web' + ''.join(chr(97 + int(letter, 16)) for letter in uuid.uuid4().hex[:8])
    def player_count():
        return int(sql('SELECT COUNT(*) FROM player_data')) if sql else len(list((Path(server['runtime']) / 'state/players').glob('*.snapshot')))
    def saved_state(stat_text):
        pid = int(re.search(r'ID numb:\s*(\d+)', stat_text)[1])
        if sql:
            row = list(map(int, sql(f'SELECT hometown,birthplace,orig_birthplace FROM player_data WHERE pid={pid}').split('\t')))
            return dict(zip(('hometown', 'birthplace', 'original_birthplace'), row))
        return json.loads(subprocess.check_output([str(args.inspector), str(Path(server['runtime']) / 'state'), 'inspect', str(pid)], text=True))
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, executable_path=str(args.browser_executable) if args.browser_executable else None)
        context = browser.new_context(viewport={'width': 1280, 'height': 900})
        context.add_init_script("localStorage.setItem('duris-ws-proxy', " + json.dumps(json.dumps({
            'enabled': True, 'host': '127.0.0.1', 'port': str(server['websocket'])})) + ");")
        context.add_init_script('''
          const originalSend = WebSocket.prototype.send;
          WebSocket.prototype.send = function(packet) {
            const value = JSON.parse(packet);
            if (value.cmd === 'create_character' && window.forgeHometown !== undefined) {
              value.data.hometown = window.forgeHometown;
              value.data.name = 'Forgedweb';
              delete window.forgeHometown;
              return originalSend.call(this, JSON.stringify(value));
            }
            return originalSend.call(this, packet);
          };
        ''')
        page = context.new_page()
        errors = []
        frames = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type in ('error', 'warning') else None)
        def frame(payload):
            try:
                value = json.loads(payload)
                frames.append(value)
            except json.JSONDecodeError:
                pass
        def socket_connected(socket):
            if str(server['websocket']) in socket.url:
                socket.on('framereceived', frame)
                socket.on('close', lambda: frames.append({'closed': True}))
        page.on('websocket', socket_connected)
        def api(route):
            if route.request.url.split('?')[0].endswith('/site-config'):
                route.fulfill(json={
                    'siteTitle': 'Duris Local Onboarding', 'siteLogoUrl': '', 'supportUrl': '',
                    'mudHost': '127.0.0.1', 'mudPort': str(server['plain']), 'mudPortTls': str(server['tls']),
                    'mudWsUrl': f"wss://127.0.0.1:{server['websocket']}",
                    'frontPageHeroEnabled': False, 'frontPageHeroTitle': '', 'frontPageHeroSubtitle': '',
                    'frontPageHeroImageUrl': '', 'frontPageContent': '',
                })
            elif route.request.url.split('?')[0].endswith('/map-data'):
                route.fulfill(json={'nodes': [], 'edges': []})
            else:
                route.fulfill(json={'success': True, 'user': None, 'status': 'ok', 'data': []})
        page.route('**/api/**', api)
        page.goto(args.frontend_url.rstrip('/') + '/play')
        page.get_by_role('tab', name='Register', exact=True).wait_for()
        page.get_by_role('tab', name='Register', exact=True).click()
        account = 'Obr' + ''.join(chr(97 + int(letter, 16)) for letter in uuid.uuid4().hex[:8])
        page.locator('#register-account').fill(account)
        page.locator('#register-email').fill(account.lower() + '@example.invalid')
        page.locator('#register-password').fill('Qz7!mN4@')
        page.locator('#register-confirm').fill('Qz7!mN4@')
        page.get_by_role('button', name='Create Account', exact=True).click()
        try:
            page.get_by_role('button', name='Create New Character', exact=True).wait_for(timeout=15000)
        except Exception:
            print(page.locator('body').inner_text(), errors, frames, flush=True)
            page.screenshot(path=str(args.output.parent / 'browser-register-error.png'))
            raise
        page.get_by_role('button', name='Create New Character', exact=True).click()
        page.get_by_role('button', name='New Player', exact=False).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('button', name='Firbolg', exact=True).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.locator('#male').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('button', name='Warrior', exact=False).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Choose Your Hometown').wait_for()
        assert page.get_by_role('button', name='Next', exact=True).is_disabled()
        page.screenshot(path=str(args.output.parent / 'browser-firbolg.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        page.screenshot(path=str(args.output.parent / 'browser-firbolg-mobile.png'))
        assert not page.evaluate('document.documentElement.scrollWidth > window.innerWidth'), 'phone layout overflows'
        page.set_viewport_size({'width': 1280, 'height': 900})
        for heading in ('Choose Your Class', 'Choose Your Sex', 'Choose Your Race'):
            page.get_by_role('button', name='Back', exact=True).click()
            page.get_by_role('heading', name=heading).wait_for()
        page.get_by_role('tab', name='Neutral', exact=False).click()
        page.get_by_role('button', name='Thri-Kreen', exact=True).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.locator('#male').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('button', name='Warrior', exact=False).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.locator('#good').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Choose Your Hometown').wait_for()
        page.get_by_role('button', name='Plane of Life', exact=False).click()
        assert page.get_by_role('button', name='Next', exact=True).is_enabled()
        page.get_by_role('button', name='Back', exact=True).click()
        page.locator('#evil').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Choose Your Hometown').wait_for()
        assert page.get_by_role('button', name='Next', exact=True).is_disabled()
        assert page.get_by_role('button', name='Plane of Chaos', exact=False).count() == 1
        assert page.get_by_role('button', name='Wutvr', exact=False).count() == 1
        page.get_by_role('button', name='Back', exact=True).click()
        page.locator('#good').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Choose Your Hometown').wait_for()
        assert page.get_by_role('button', name='Next', exact=True).is_disabled()
        page.screenshot(path=str(args.output.parent / 'browser-neutral-return.png'))
        page.get_by_role('button', name='Back', exact=True).click()
        page.locator('#evil').click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('button', name='Plane of Chaos', exact=False).click()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Choose Your Stat Rolling System').wait_for()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Your Statistics').wait_for()
        page.get_by_role('button', name='Next', exact=True).click()
        heading = page.get_by_role('heading', name='Allocate Bonus Points')
        heading.wait_for()
        panel = heading.locator('xpath=../..')
        for remaining, index in zip(range(4, 0, -1), (0, 1, 2, 8)):
            page.get_by_text(str(remaining) + ' remaining', exact=True).wait_for()
            panel.get_by_role('button').nth(index).click()
            page.get_by_text(str(remaining - 1) + ' remaining', exact=True).wait_for()
        page.get_by_role('button', name='Next', exact=True).click()
        page.get_by_role('heading', name='Swap Statistics (Optional)').wait_for()
        page.get_by_role('button', name='Next', exact=True).click()
        page.locator('#name').fill(character)
        page.get_by_text('Name is available!', exact=True).wait_for()
        page.get_by_role('button', name='Next', exact=True).click()
        # Send actual malformed/opposite-side requests from the completed wizard.
        # Only request data changes; all responses and persistence use the real MUD.
        before_count = player_count()
        for forged in (1, '26', -1, True):
            before = len(frames)
            page.evaluate('(value) => window.forgeHometown = value', forged)
            page.get_by_role('button', name='Create Character', exact=True).click()
            deadline = time.monotonic() + 10
            while not any(frame.get('status') == 'error' or frame.get('data', {}).get('status') == 'error' for frame in frames[before:]):
                assert time.monotonic() < deadline, (frames[before:], page.locator('body').inner_text())
                page.wait_for_timeout(100)
        assert player_count() == before_count, 'forged hometown allocated a player'
        page.get_by_role('button', name='Create Character', exact=True).click()
        field = page.get_by_placeholder('Enter command...')
        field.wait_for(timeout=15000)
        god = journey.reconnect_character(server['plain'], expected_room=None, account=GOD_ACCOUNT, character=GOD)
        god.expect('Welcome to Duris', timeout=45)
        assert 'Paging mode off' in command(god, 'toggle paging no')
        def room():
            value = command(god, 'stat char ' + character)
            return int(re.search(r'In room:\s*\[(\d+)\]', value)[1])
        def send(text, expected=None):
            field.fill(text)
            field.press('Enter')
            if expected is not None:
                deadline = time.monotonic() + 10
                while room() != expected:
                    assert time.monotonic() < deadline, (text, expected, room())
                    page.wait_for_timeout(100)
            else:
                page.wait_for_timeout(300)
        def walk(target):
            for direction, expected in path_between(authored_graph(), room(), target):
                send(direction, expected)
        assert room() == 91200
        walk(91206)
        send('enter stream')
        page.get_by_text('Your not ready yet, ask the reaver about racewar.', exact=False).wait_for()
        walk(91204)
        send('ask reaver racewars')
        walk(91206)
        send('enter stream', 91401)
        send('ask grubruk map')
        page.get_by_text('Grubruk the goblin smiles and hands you a map.', exact=False).wait_for()
        walk(91440)
        send('enter archway')
        expected = guild_rooms()[18][1]
        assert room() == expected
        send('save')
        page.get_by_text('Save complete for ' + character + '.', exact=False).wait_for()
        saved = saved_state(command(god, 'stat char ' + character))
        assert [saved[key] for key in ('hometown', 'birthplace', 'original_birthplace')] == [expected] * 3, saved
        command(god, 'advance ' + character + ' 30')
        warning = 'WARNING: YOU HAVE REACHED LEVEL 30.'
        page.get_by_text(warning, exact=False).wait_for()
        style = page.evaluate('''() => Array.from(document.querySelectorAll('.mud-output span')).filter(
          el => el.childElementCount === 0 && el.textContent.includes('WARNING: YOU HAVE REACHED LEVEL 30.')
        ).map(el => ({text: el.textContent, weight: getComputedStyle(el).fontWeight, color: getComputedStyle(el).color}))''')
        assert style and all(int(value['weight']) >= 700 for value in style), style
        page.screenshot(path=str(args.output.parent / 'browser-warning.png'))
        print('BROWSER FULL EVIL ROUTE, INVALID REQUESTS AND BOLD WARNING', style, flush=True)
        evidence.update(character=character, saved_home=saved, forged_hometowns=[1, '26', -1, True], warning_style=style, browser_errors=errors)
        print('PAGE ERRORS', errors, flush=True)
        assert all('VUE_ROUTER_R0025' in error for error in errors), errors
        god.close()
        evidence['passed'] = True
        browser.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, required=True)
    parser.add_argument('--backend', choices=('flatfile', 'mariadb'), default='flatfile')
    parser.add_argument('--frontend-url', required=True)
    parser.add_argument('--frontend-source', type=Path)
    parser.add_argument('--browser-executable', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    args.server = args.server.resolve()
    args.output = (args.output or ROOT / f'bin/qualification/issue213/browser-{args.backend}.json').resolve()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.inspector = ROOT / 'bin/qualification/issue213/player-inspector'
    if args.backend == 'flatfile' and not args.inspector.exists():
        subprocess.run(['python3', 'tests/async/test_flatfile_player_repository.py', '--build-inspector', str(args.inspector)], cwd=ROOT, check=True)
    evidence = {'backend': args.backend, 'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'binary_sha256': hashlib.sha256(args.server.read_bytes()).hexdigest(),
                'frontend_url': args.frontend_url, 'passed': False,
                'world_sha256': {kind: hashlib.sha256((ROOT / f'areas/world.{kind}').read_bytes()).hexdigest()
                                 for kind in ('wld', 'mob', 'obj', 'zon', 'qst', 'shp', 'trg')}}
    if args.frontend_source:
        evidence['frontend_commit'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.frontend_source, text=True).strip()
    try:
        with full_world(args) as (server, sql):
            exercise(server, sql, args, evidence)
    finally:
        args.output.write_text(json.dumps(evidence, indent=2))
