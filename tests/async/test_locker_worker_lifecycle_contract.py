from _paths import SRC

src = (SRC / "locker_async.c").read_text()

# Locker saves run on the one persistence writer; the locker module starts no
# thread of its own and has none to join at shutdown.
assert "pthread_create" not in src and "pthread_join" not in src
assert "g_worker_created" not in src
assert "return player_save_worker_health_copy().running;" in src
assert "!g_inited || !locker_async_worker_available()" in src
assert "persistence_job_kind::locker" in src
print("locker saves use the one persistence writer")
