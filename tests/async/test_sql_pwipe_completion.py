from _paths import SRC
from pathlib import Path

source = (SRC / "sql.c").read_text()
start = source.rindex("bool sql_pwipe(int code_verify)")
end = source.index("void sql_log_player_login", start)
body = source[start:end]

assert 'WIPE COMPLETED!' not in body
assert 'reset_status=\'active\'' not in body
assert body.index('redis_clear_pwipe_state()') < body.index('sql_prepare_pwipe_filesystem()')
assert body.index('sql_prepare_pwipe_filesystem()') < body.index('pwipe_filesystem_ready = true')
assert body.index('pwipe_filesystem_ready = true') < body.index('return TRUE;')
rewards = body[body.index('if (!account_bound_rewards_on_successful_pwipe())'):]
assert rewards.index('return FALSE;') < rewards.index('sql_prepare_pwipe_filesystem()')
assert '{ "player_data", "learned_flight_stops" }' in source
assert 'UPDATE player_data SET active = 0, learned_flight_stops = 0' in body
assert 'Only clean, recreated Overlords may be active.' in body
assert 'WHERE learned_flight_stops <> 0 OR ' in body

print("sql pwipe completion reporting checks passed")
