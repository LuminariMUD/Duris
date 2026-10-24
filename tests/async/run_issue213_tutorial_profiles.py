#!/usr/bin/env python3
"""Compare real loaded tutorial counterparts with identical RNG and configuration.

Use a matching --server and --backend. The MariaDB leg runs through the existing
disposable MariaDB wrapper; no checkout .env or production service is used.
GDB controls only the freshly launched child. Instance/prototype/shop IDs are
identity, while every captured mechanical field, innate and item access must
match. This is profile proof, not the complete command/persistence journey.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo / 'tests/async'))
import test_flatfile_combat_journey as journey
from test_flight_network_journey import authority
from run_world_quest_dual_backend import setup_run_root
import test_issue213_tutorial_parity as fixture

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--server', type=Path, required=True)
parser.add_argument('--backend', choices=('flatfile', 'mariadb'), default='flatfile')
parser.add_argument('--output', type=Path)
arguments = parser.parse_args()
binary = arguments.server.resolve()
assert binary.is_file(), f'server binary does not exist: {binary}'
output_path = (arguments.output or repo / f'bin/qualification/issue213/loaded-profiles-{arguments.backend}.json').resolve()
output_path.parent.mkdir(parents=True, exist_ok=True)

equipment = {}
for source in fixture.COPIES:
    owner = None
    for line in (fixture.AREAS / 'zon' / (source + '.zon')).read_text().splitlines():
        words = line.split()
        if words and words[0] == 'M':
            owner = int(words[2])
        elif owner and words and words[0] in ('E', 'G'):
            equipment.setdefault(owner, set()).add(int(words[2]))
cases = [{'original': original, 'copied': copied,
          'equipment': [[obj, fixture.remap('obj', obj)] for obj in sorted(equipment.get(original, ()))]}
         for source in fixture.COPIES for original, copied in fixture.MAPS[source]['mob'].items()]

gdb_python = r'''
import gdb, json
def numeric(value):
    kind = value.type.strip_typedefs().code
    if kind in (gdb.TYPE_CODE_INT, gdb.TYPE_CODE_ENUM, gdb.TYPE_CODE_BOOL, gdb.TYPE_CODE_CHAR): return int(value)
    if kind == gdb.TYPE_CODE_FLT: return float(value)
    if kind == gdb.TYPE_CODE_PTR: return bool(int(value))
    if kind == gdb.TYPE_CODE_ARRAY:
        low, high = value.type.range()
        return [numeric(value[index]) for index in range(low, high + 1)]
    if kind == gdb.TYPE_CODE_STRUCT:
        return {field.name: numeric(value[field.name]) for field in value.type.fields() if field.name}
    raise gdb.GdbError('Uncaptured profile field type: ' + str(value.type))
def profile(pointer):
    ch = pointer.dereference()
    gdb.set_convenience_variable('active', pointer)
    npc = numeric(ch['only']['npc'].dereference())
    del npc['R_num']; del npc['shopkeeper_shop_id']; del npc['idnum']
    return {'player': {field: int(ch['player'][field]) for field in
        ('level', 'm_class', 'secondary_class', 'spec', 'sex', 'racewar', 'size', 'weight', 'height')},
        'base_stats': numeric(ch['base_stats']), 'curr_stats': numeric(ch['curr_stats']),
        'points': numeric(ch['points']), 'specials': numeric(ch['specials']), 'npc': npc,
        'resistance': int(gdb.parse_and_eval('get_innate_resistance($active)'))}
def differences(left, right, path=''):
    result = []
    if isinstance(left, dict):
        for key in left: result += differences(left[key], right[key], path + '.' + key)
    elif left != right: result.append([path, left, right])
    return result
cases = json.load(open(CASES_FILE))
rows = []
innates = gdb.parse_and_eval('racial_innates')
low, high = innates.type.range()
for seed in (4242, 987654):
    for case in cases:
        gdb.parse_and_eval('randomize(%d)' % seed)
        original = gdb.parse_and_eval('read_mobile_probe(%d, 1)' % case['original'])
        if not int(original): raise gdb.GdbError('Missing source mobile ' + str(case['original']))
        source = profile(original)
        gdb.parse_and_eval('randomize(%d)' % seed)
        copied = gdb.parse_and_eval('read_mobile_probe(%d, 1)' % case['copied'])
        if not int(copied): raise gdb.GdbError('Missing copied mobile ' + str(case['copied']))
        target = profile(copied)
        mismatch = differences(source, target)
        old_race = int(original.dereference()['player']['race'])
        new_race = int(copied.dereference()['player']['race'])
        ability_ids = [index for index in range(max(1, low), high + 1)
                       if int(innates[index][old_race]) or int(innates[index][new_race])]
        abilities = {}
        gdb.set_convenience_variable('original', original)
        gdb.set_convenience_variable('copied', copied)
        for innate in ability_ids:
            before = int(gdb.parse_and_eval('has_innate($original, %d)' % innate))
            after = int(gdb.parse_and_eval('has_innate($copied, %d)' % innate))
            abilities[str(innate)] = [before, after]
            if before != after: mismatch.append(['innate.' + str(innate), before, after])
        items = []
        for source_obj, copied_obj in case['equipment']:
            gdb.set_convenience_variable('source_item', gdb.parse_and_eval('read_object(%d, 1)' % source_obj))
            gdb.set_convenience_variable('copied_item', gdb.parse_and_eval('read_object(%d, 1)' % copied_obj))
            if not int(gdb.parse_and_eval('$source_item')) or not int(gdb.parse_and_eval('$copied_item')):
                raise gdb.GdbError('Missing equipment prototype ' + str([source_obj, copied_obj]))
            before = int(gdb.parse_and_eval('can_char_use_item($original, $source_item)'))
            after = int(gdb.parse_and_eval('can_char_use_item($copied, $copied_item)'))
            items.append([source_obj, copied_obj, before, after])
            if before != after: mismatch.append(['equipment.' + str(source_obj), before, after])
        rows.append({**case, 'seed': seed, 'races': [old_race, new_race], 'original_profile': source,
                     'copied_profile': target, 'innates': abilities, 'equipment_access': items,
                     'differences': mismatch})
json.dump(rows, open(RESULT_FILE, 'w'), indent=2)
print('PROFILE_COMPARISONS', len(rows), 'MISMATCHES', sum(bool(row['differences']) for row in rows))
'''

with tempfile.TemporaryDirectory(prefix='duris-issue213-profiles-') as temporary:
    runtime = Path(temporary)
    _, critical, _ = setup_run_root(runtime)
    (runtime / 'help').symlink_to(repo / 'help', target_is_directory=True)
    plain, tls, websocket = journey.available_ports()
    case_file, result_file = runtime / 'cases.json', runtime / 'profiles.json'
    case_file.write_text(json.dumps(cases))
    with authority(arguments.backend, runtime) as (environment, _):
        environment.update(CRITICAL_COMMAND_JOURNAL_DIR=str(critical), DURIS_TLS_PORT=str(tls), DURIS_WEBSOCKET_PORT=str(websocket))
        commands = runtime / 'profiles.gdb'
        commands.write_text('set pagination off\nset confirm off\nset print thread-events off\nbreak run_connection_phase\n'
            f'run -d {runtime} {plain}\nset scheduler-locking on\npython\n' +
            'CASES_FILE = ' + repr(str(case_file)) + '\nRESULT_FILE = ' + repr(str(result_file)) + '\n' +
            gdb_python + '\nend\nkill\n')
        result = subprocess.run(['gdb', '--batch', '-nx', '-x', str(commands), str(binary)],
            cwd=runtime, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
        output_path.with_suffix('.log').write_text(result.stdout)
        assert result.returncode == 0, result.stdout[-5000:]
        rows = json.loads(result_file.read_text())
        assert len(rows) == len(cases) * 2
        mismatches = [{'original': row['original'], 'copied': row['copied'], 'seed': row['seed'],
                       'differences': row['differences']} for row in rows if row['differences']]
        files = [path for directory in ('src', 'areas/wld', 'areas/mob', 'areas/obj', 'areas/zon', 'areas/qst', 'areas/shp')
                 for path in (repo / directory).rglob('*') if path.is_file()]
        files += [repo / name for name in ('lib/duris.properties', 'lib/difficulty.cfg',
                                          'lib/hardcore.cfg', 'lib/creation_availability.cfg')
                  if (repo / name).is_file()]
        output_path.write_text(json.dumps({
            'backend': arguments.backend,
            'persistence_mode': environment['PERSISTENCE_MODE'], 'chaos_mode': environment['CHAOS_MUD'],
            'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=repo, text=True).strip(),
            'source_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo, text=True).strip()),
            'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            'source_files_sha256': {str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(files)},
            'world_sha256': {kind: hashlib.sha256((fixture.AREAS / f'world.{kind}').read_bytes()).hexdigest() for kind in (*fixture.KINDS, 'trg')},
            'passed': not mismatches, 'comparisons': rows,
        }, indent=2))
        print('loaded NPC comparisons', len(rows), 'mismatching pairs', len(mismatches), 'evidence', output_path)
        if mismatches:
            print(json.dumps(mismatches[:10], indent=2))
        assert not mismatches, 'loaded tutorial counterparts differ'
