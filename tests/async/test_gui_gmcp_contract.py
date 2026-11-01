#!/usr/bin/env python3
"""Execute production GMCP serializers, wire framing and bridge delivery lifecycle.

No server boot, database, credentials, sockets or player files are used. The
harness substitutes world lookup/ship mechanics; the protocol functions and
serializers are extracted unchanged from the current source. --output retains
real payloads for all eleven client-consumed packages for integration tests.
"""
import argparse
import subprocess
import tempfile
from pathlib import Path
from _paths import ROOT, HARNESS_STUBS, extract_function, source

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path)
parser.add_argument('--sanitize', action='store_true')
args = parser.parse_args()
sanitizers = ['-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', '-fno-pie', '-no-pie'] if args.sanitize else []
functions = [
    ('utility.c', 'string strip_ansi('),
    ('condition.c', 'char *item_condition('),
    ('salchemist.c', 'void set_short_description('),
    ('random_equipment.c', 'bool identify_random('),
    ('magic.c', 'void spell_reveal_true_name('),
    ('handler.c', 'int set_obj_condition('),
    ('handler.c', 'P_obj unequip_char('),
    ('interp.c', 'char *one_argument('),
    ('actnew.c', 'void do_disarm('),
    ('magic.c', 'void spell_repair_one_item('),
    ('handler.c', 'void set_obj_extra_flags('),
    ('handler.c', 'void set_obj_extra2_flags('),
    ('handler.c', 'int get_number('),
    ('handler.c', 'bool isname(const char *str, const char *namelist)'),
    ('handler.c', 'bool obj_name_matches('),
    ('handler.c', 'P_obj get_obj_in_list_vis('),
    ('handler.c', 'P_obj get_obj_equipped('),
    ('actinf.c', 'P_obj get_object_in_equip('),
    ('ship_utils.c', 'char *ShipSlot::get_status_str('),
    ('ship_utils.c', 'const char *ShipSlot::get_position_str('),
    ('ship_utils.c', 'char *ShipSlot::get_description('),
    ('ship_utils.c', 'int ShipSlot::get_weight('),
    ('ship_utils.c', 'int ShipData::slot_weight('),
    ('ship_utils.c', 'const char *ShipCrew::get_stamina_prefix('),
    ('ship_utils.c', 'int ShipCrew::get_display_stamina('),
    ('ship_utils.c', 'int eq_ram_weight('),
    ('ship_utils.c', 'int eq_levistone_weight('),
    ('gmcp.c', 'void gmcp_send_group_status('),
    ('gmcp.c', 'void gmcp_char_status('),
    ('gmcp.c', 'void gmcp_char_affects('),
    ('gmcp.c', 'void gmcp_room_info('),
    ('gmcp.c', 'void gmcp_comm_channel_ex('),
    ('gmcp.c', 'void gmcp_char_vitals('),
    ('gmcp.c', 'void gmcp_input_receipt('),
    ('gmcp.c', 'void gmcp_handle_negotiation('),
    ('gmcp.c', 'void gmcp_flush_initial_states('),
    ('gmcp.c', 'void gmcp_send_initial_state('),
    ('gmcp.c', 'static std::unordered_map<int, struct ShipData *> gmcp_ship_bridges('),
    ('gmcp.c', 'static struct ShipData *gmcp_player_ship('),
    ('gmcp.c', 'static unsigned long hash_string('),
    ('gmcp.c', 'static cJSON *json_build_ship_contacts('),
    ('gmcp.c', 'void gmcp_flush_dirty_ship_contacts('),
    ('gmcp.c', 'void gmcp_flush_dirty_ship_info('),
    ('gmcp.c', 'void gmcp_send_room_map('),
    ('gmcp.c', 'void gmcp_send_quest_map('),
    ('gmcp.c', 'void gmcp_quest_status(struct char_data *ch)'),
    ('gmcp.c', 'void gmcp_quest_status(struct char_data *ch, world_quest_target_status status)'),
    ('gmcp.c', 'void gmcp_quest_map(struct char_data *ch, world_quest_target_status status)'),
    ('weather.c', 'void event_another_hour('),
    ('world_quest.c', 'void show_map_at('),
    ('utility.c', 'int IS_MORPH('),
    ('ws_handlers.c', 'void ws_send_full_game_state('),
    ('ws_handlers.c', 'static void ws_reset_chargen('),
]
# MAP_AUTOMAP already suppresses text; mutating websocket would change framing.
comm = source('comm.c').read_text()
passenger_map = comm[comm.index('// For ship passengers:'):comm.index('t_ch->desc->last_map_update = 0;')]
assert 'websocket =' not in passenger_map
assert 'MAP_AUTOMAP, 0' in passenger_map
assert 'gmcp_send_initial_state(ch);' in source('nanny.c').read_text()
assert 'gmcp_send_initial_state(send_ch);' in source('actoth.c').read_text()
assert 'gmcp_send_initial_state(d->character);' in source('account.c').read_text()
assert 'ws_send_full_game_state(d);' in extract_function('ws_handlers.c', 'void ws_finish_login(')
periodic = extract_function('comm.c', 'static void run_recurring_persistence_phase(')
assert periodic.index('if (!(pulse % 2))') < periodic.index('gmcp_flush_initial_states();')

build = ROOT / 'bin/tests'
build.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix='gui-gmcp-', dir=build) as directory:
    tmp = Path(directory)
    damage = extract_function('fight.c', 'int raw_damage(')
    start = damage.index('/* Send GMCP updates for combat */')
    application_start = damage.index('if (flags & RAWDAM_NOKILL)')
    application_end = damage.index('telemetry_runtime_game_combat_damage(', application_start)
    notice = damage[application_start:application_end] + damage[start:damage.index('\n\t\t}', start)]
    delivery_paths = []
    for function, name, params in [
        ('int spell_damage(', 'capture_spell_delivery', 'int type, uint flags'),
        ('int melee_damage(', 'capture_physical_delivery', 'int flags'),
    ]:
        implementation = extract_function('fight.c', function)
        begin = implementation.index('damage_messages delivery = *messages;')
        end = implementation.index('damAccumulator);', begin) + len('damAccumulator);')
        delivery_paths.append(f'int {name}(P_char ch, P_char victim, double dam, {params}, damage_messages *messages) {{ int result; int *damAccumulator = nullptr;\n' + implementation[begin:end] + '\nreturn result; }')
    gmcp = source('gmcp.c').read_text()
    control = gmcp[gmcp.index('// New-stream control and time.'):gmcp.index('// End new-stream control and time.')]
    auth_source = gmcp[gmcp.index('static int gmcp_durisweb_auth_limited('):gmcp.index('void gmcp_input_receipt(')]
    parser_source = gmcp[gmcp.index('void gmcp_handle_input('):gmcp.index('/* core gmcp send')]
    combat_source = gmcp[gmcp.index('// Combat snapshots.'):gmcp.index('// End combat snapshots.')]
    sql = source('sql/sql.c').read_text()
    reward_source = sql[sql.index('struct world_quest_reward_publication\n'):sql.index('// End world quest reward publication.')]
    sender_source = gmcp[gmcp.index('/* core gmcp send'):gmcp.index('/* Bootstrap state')]
    (tmp / 'production.inc').write_text(control + '\n' + sender_source + '\n' + auth_source + '\n' + parser_source + '\n' + combat_source + '\n' + '\n\n'.join(extract_function(*f) for f in functions)
        + '\n' + reward_source + '\n' + '\n'.join(delivery_paths) + '\nvoid applied_damage_notice(P_char ch, P_char victim, double dam, damage_messages *messages = nullptr, uint flags = 0) {\n' + notice + '\n}\n'
        + '\nvoid rejected_creation(P_desc d, P_char ch) { account_racewar_admission admission{};\n'
        + extract_function('ws_handlers.c', 'if (!account_commit_character_admission(d, ch, false, &admission))') + '\n}\n')
    binary = tmp / 'test'
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror',
        *sanitizers, '-ffunction-sections', '-fdata-sections', '-Isrc', '-I/usr/include/mysql', f'-I{tmp}',
        str(ROOT/'tests/async/gui_gmcp_contract_harness.cpp'), str(source('json_utils.c')),
        str(source('random_equipment_tables.c')), str(source('safe_format.c')), str(HARNESS_STUBS),
        '-Wl,--gc-sections', '-lcjson', '-lcrypto', '-o', str(binary)], cwd=ROOT, check=True, timeout=120)
    result = subprocess.run([str(binary)], cwd=ROOT, check=False, text=True, capture_output=True, timeout=30)
    if result.returncode:
        print(result.stderr)
        result.check_returncode()
    if args.output:
        args.output.write_text(result.stdout)
print('GUI GMCP wire, serializer, snapshot and bridge lifecycle checks passed')
