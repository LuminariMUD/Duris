// Live locker traversal, departure guards, item capture/codec, recovery publication,
// and SQL ownership repositories are production code. Gameplay/event boundaries
// and private durability/admission outcomes are controlled by this fixture.
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "item/storage_lockers.h"
#include "persistence/locker_recovery.h"
#include "persistence/locker_async.h"
#include "persistence/persistence_observability.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "flatfile/flatfile_player_repository.h"
#include "sql/sql.h"
#include "sql/sql_pool.h"
#define LOCKERS_START 65201
#define LOCKERS_MAX 99
#define IS_TOWN_RAIDED(ch) false
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <signal.h>
#include <sys/wait.h>
#include <sys/stat.h>
#include <unistd.h>

MYSQL *DB;
P_char character_list;
static room_data rooms[3]{};
P_room world = rooms;
extern const int top_of_world = 2;
static index_data indexes[1]{};
P_index obj_index = indexes, mob_index = indexes;
int top_of_objt = 0, top_of_mobt = 0;
Skill skills[MAX_SKILLS]{};
static StorageLocker *active;
static bool movement, purchase, audit, durable = true, prepare = true, queue = true;
static bool fail_write;
static int prepare_calls;
static std::string test_database;
static bool block_child_io;
static pid_t parent_pid;
static volatile sig_atomic_t reaped_pid, reaped_status;
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd)
{
	if (block_child_io && getpid() != parent_pid)
		raise(SIGSTOP);
	return __real_fsync(fd);
}
static void reap_fixture(int)
{
	int status;
	const pid_t pid = waitpid(-1, &status, WNOHANG);
	if (pid > 0)
	{
		reaped_pid = pid;
		reaped_status = status;
	}
}
const unsigned LockerChest::m_chestVnum = 173;
const char *persistence_mode_flatfile_root()
{
	return nullptr;
}
const char *sql_persistence_db_name()
{
	return test_database.c_str();
}
bool take_reaped_child_status(pid_t pid, int *status)
{
	if (pid != reaped_pid)
		return false;
	*status = reaped_status;
	reaped_pid = 0;
	return true;
}
bool training_dummy_capture_target_allowed(P_char)
{
	return true;
}
void event_short_affect(P_char, P_char, P_obj, void *) {}
int ne_event_time(nevent_data *)
{
	return 0;
}
void logit(const char *, const char *format, ...)
{
	va_list args;
	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);
	fputc('\n', stderr);
}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
}
void send_to_char(const char *, P_char) {}
void *__malloc(size_t size, const char *, const char *, int)
{
	return calloc(1, size);
}
char *str_dup(const char *value)
{
	return strdup(value);
}
char *sql_escape_string(const char *)
{
	abort();
}
bool esc_locker_name_matches_player(const char *, P_char)
{
	return true;
}
bool item_movement_transaction_player_busy(P_char)
{
	return movement;
}
bool private_chest_purchase_locker_busy(int)
{
	return purchase;
}
bool sql_chest_log_pending(int)
{
	return audit;
}
bool StorageLocker::PrivateContentsDurable()
{
	return durable;
}
bool PrivateChest::SaveContents(StorageLocker *, bool)
{
	return prepare;
}
extern "C" int sql_pool_is_active()
{
	return 1;
}
MYSQL *sql_pool_acquire()
{
	return DB;
}
MYSQL *sql_pool_replace_connection(MYSQL *)
{
	abort();
}
void sql_pool_release(MYSQL *) {}
player_save_worker_health player_save_worker_health_copy()
{
	player_save_worker_health health{};
	health.running = true;
	return health;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t, size_t,
						    persistence_job_write_fn write)
{
	if (fail_write)
		assert(write().outcome == player_save_apply_outcome::terminal_failure);
	return queue ? player_save_submit_result::accepted : player_save_submit_result::unavailable;
}
extern "C" int locker_async_prepare_snapshot(P_char, P_char)
{
	return 1;
}
extern "C" void locker_async_request_resort(P_char, P_char)
{
	abort();
}
extern "C" void locker_async_restore_snapshot_view(P_char, P_char)
{
	abort();
}
void extract_char(P_char)
{
	abort();
}
static const char *locker_room_name(int)
{
	return "fixture";
}
static int locker_exit_room(P_char, int)
{
	return 2;
}
static void locker_log_save_failure(StorageLocker *, P_char, P_char, const char *, const char *) {}
static void event_deferredTerminalSave(P_char, P_char, P_obj, void *) {}
P_nevent get_scheduled(P_char, event_func)
{
	return nullptr;
}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int)
{
	return {};
}
void char_from_room(P_char)
{
	abort();
}
bool char_to_room(P_char, int, int)
{
	abort();
}
static void free_locker(int room)
{
	world[room].funct = nullptr;
	active = nullptr;
}
int storage_locker(int, P_char, int, char *)
{
	return 0;
}
int real_room0(int vnum)
{
	return vnum == 65202 ? 1 : NOWHERE;
}
int char_in_list(const P_char ch)
{
	for (P_char current = character_list; current; current = current->next)
		if (current == ch)
			return 1;
	return 0;
}
void obj_from_obj(P_obj object)
{
	P_obj *link = &object->loc.inside->contains;
	while (*link != object)
		link = &(*link)->next_content;
	*link = object->next_content;
	object->next_content = nullptr;
}
void obj_from_room(P_obj object)
{
	P_obj *link = &world[object->loc.room].contents;
	while (*link != object)
		link = &(*link)->next_content;
	*link = object->next_content;
	object->next_content = nullptr;
}
void obj_to_char(P_obj object, P_char ch)
{
	object->loc_p = LOC_CARRIED;
	object->loc.carrying = ch;
	object->next_content = ch->carrying;
	ch->carrying = object;
}
void obj_to_room(P_obj, int)
{
	abort();
}
LockerChest::~LockerChest() {}
StorageLocker::~StorageLocker() {}
PrivateChest::PrivateChest(int id, const char *name, const char *)
	: LockerChest(name, "fixture")
	, m_chestId(id)
{
}
class PublicChest : public LockerChest
{
    public:
	PublicChest(P_obj object)
		: LockerChest("public", "fixture")
	{
		m_pChestObject = object;
	}
	void FillExtraDescBuf(char *) override {}
};
class TestPrivateChest : public PrivateChest
{
    public:
	TestPrivateChest(P_obj object)
		: PrivateChest(3, "private", "")
	{
		m_pChestObject = object;
	}
	void FillExtraDescBuf(char *) override {}
};
class TestLocker : public StorageLocker
{
    public:
	using StorageLocker::StorageLocker;
	void add(LockerChest *chest) { AddLockerChest(chest); }
	void lose_holder() { m_chLocker = nullptr; }
};
void LockerChest::FillExtraDescBuf(char *) {}
player_save_apply_result flatfile_locker_snapshot_apply(const std::string &,
							const flatfile_locker_save &, std::string *)
{
	abort();
}
player_save_apply_result flatfile_player_snapshot_apply(const std::string &,
							const player_snapshot &, std::string *)
{
	abort();
}

// PRODUCTION_BODIES

static P_obj object(uint64_t uid, int type = ITEM_OTHER)
{
	P_obj value = new obj_data{};
	value->obj_uid = uid;
	value->R_num = 0;
	value->type = type;
	value->condition = 100;
	value->cost = 25;
	return value;
}
static void contained(P_obj parent, P_obj child)
{
	child->loc_p = LOC_INSIDE;
	child->loc.inside = parent;
	child->next_content = parent->contains;
	parent->contains = child;
}
static void floor(P_obj value)
{
	value->loc_p = LOC_ROOM;
	value->loc.room = 1;
	value->next_content = rooms[1].contents;
	rooms[1].contents = value;
}

int main(int argc, char **argv)
{
	assert(argc == 5);
	parent_pid = getpid();
	test_database = argv[2];
	DB = mysql_init(nullptr);
	assert(mysql_real_connect(DB, "localhost", "root", "locker-test", argv[2], 0, argv[1], 0));
	assert(chdir(argv[3]) == 0);
	const std::string mode = argv[4];
	if (mode == "refuse-boot")
	{
		assert(!locker_recovery_boot());
		return 0;
	}
	assert(locker_recovery_boot());
	if (mode == "recover")
		return 0;

	indexes[0].virtual_number = 48;
	rooms[1].number = 65202;
	rooms[1].room_flags = ROOM_LOCKER;
	rooms[1].funct = storage_locker;
	rooms[2].number = 3001;
	char_data user{}, holder{};
	pc_only_data pc{}, holder_pc{};
	user.only.pc = &pc;
	pc.pid = 42;
	user.player.name = const_cast<char *>("Fixture");
	user.runtime_id = 42;
	user.in_room = 1;
	rooms[1].people = &user;
	holder.only.pc = &holder_pc;
	holder.player.name = const_cast<char *>("Fixture.locker");
	holder.runtime_id = 43;
	holder.in_room = 0;
	character_list = &user;
	user.next = &holder;
	TestLocker locker(1, &holder, &user);
	active = &locker;
	locker.SetLockerId(1);
	locker.SetPublicChestId(2);
	auto public_object = object(900, ITEM_CONTAINER);
	locker.add(new PublicChest(public_object));
	floor(public_object);
	auto bag = object(100, ITEM_CONTAINER);
	contained(bag, object(101));
	contained(public_object, bag);
	contained(public_object, object(105));
	auto coins = object(102, ITEM_MONEY);
	coins->value[0] = 37;
	floor(coins);
	obj_to_char(object(104), &holder);
	obj_to_char(object(300), &user);
	user.equipment[WEAR_HEAD] = object(301);
	const bool terminal = mode == "queue" || mode == "writer-failure" || mode == "capture";
	if (terminal)
		locker_async_init();
	if (!terminal)
	{
		auto private_object = object(901, ITEM_CONTAINER);
		locker.add(new TestPrivateChest(private_object));
		floor(private_object);
		auto private_bag = object(200, ITEM_CONTAINER);
		contained(private_bag, object(201));
		contained(private_object, private_bag);
	}
	movement = mode == "movement";
	purchase = mode == "purchase";
	audit = mode == "audit";
	durable = mode != "durability" && mode != "malformed" && mode != "blocked-publish" &&
		  mode != "blocked-io" && mode != "reaped";
	prepare = mode != "prepare";
	queue = mode != "queue";
	fail_write = mode == "writer-failure";
	locker.SetChestWritePending(mode == "write");
	if (mode == "holder-missing")
		locker.lose_holder();
	const bool left = locker_handle_leave(&user, &locker, 1, 2);
	assert(left == terminal);
	if (terminal)
	{
		const int old_rnum = holder.carrying->R_num;
		if (mode == "capture")
			holder.carrying->R_num = -1;
		assert(!locker_async_drain(0));
		holder.carrying->R_num = old_rnum;
		rooms[1].people = nullptr;
		user.in_room = 2;
		// An ordinary terminal player save had already landed. Recovery here
		// concerns the retained locker holder, not all shutdown player saves.
		player_snapshot player;
		assert(player_snapshot_capture(
			       &user, 1, PLAYER_COMPONENT_EQUIPMENT | PLAYER_COMPONENT_INVENTORY,
			       RENT_CRASH, 3001, &player) == player_snapshot_capture_result::ok);
		assert(player_snapshot_repository_apply(DB, player).outcome ==
		       player_save_apply_outcome::applied);
	}
	if (mode == "malformed")
		coins->R_num = -1;
	if (mode == "blocked-publish")
	{
		// A FIFO at the temporary file makes open(O_EXCL) fail immediately.
		assert(mkfifo("runtime/locker-shutdown/shutdown.pending", 0600) == 0);
	}
	const int calls_before_capture = prepare_calls;
	block_child_io = mode == "blocked-io";
	if (mode == "reaped")
		signal(SIGCHLD, reap_fixture);
	locker_recovery_begin();
	if (mode == "reaped")
		usleep(100000);
	locker_recovery_finish(persistence_observability_now_usec() +
			       (block_child_io ? 100000 : 2000000));
	assert(prepare_calls == calls_before_capture);
	mysql_close(DB);
	// Real exit: none of the live room, holder or occupant objects reach restart.
	_exit(0);
}
