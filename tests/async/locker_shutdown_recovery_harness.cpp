// Live locker traversal, departure guards, item capture/codec, recovery publication,
// grant publication, transfer and ownership repositories are production code.
// Gameplay/events, coordinator delivery and private durability/admission outcomes
// are controlled by this fixture.
#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "item/storage_lockers.h"
#include "persistence/locker_recovery.h"
#include "persistence/locker_async.h"
#include "persistence/persistence_observability.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_codec.h"
#include "sql/sql.h"
#include "sql/sql_pool.h"
#include "item/item_movement_transaction.h"
#include "item/item_ownership_runtime.h"
#include "item/item_transfer_repository.h"
#include <deque>
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
P_obj object_list;
static std::deque<critical_command> grants;
static std::deque<critical_completion> grant_completions;
static std::string pending_domain;
bool auction_transaction_player_busy(P_char)
{
	return pending_domain == "auction-pending";
}
bool collector_transaction_player_busy(P_char)
{
	return pending_domain == "collector-pending";
}
bool player_save_pipeline_world_quest_pending(int)
{
	return pending_domain == "quest-pending";
}
bool critical_command_coordinator_is_fenced(const critical_entity_key &, critical_operation_id *)
{
	return pending_domain == "other-fenced";
}
void persistence_critical_failure(int, const critical_completion &) {}
void locker_identify_pulse() {}
void private_chest_purchase_pulse() {}
void sql_chest_log_pulse() {}
void locker_chest_changes_pulse() {}
void auction_transaction_handle_completions(const critical_completion *, size_t) {}
void collector_transaction_handle_completions(const critical_completion *, size_t) {}
void combat_outcome_transaction_handle_completions(const critical_completion *, size_t) {}
void artifact_guild_transaction_handle_completions(const critical_completion *, size_t) {}
void boon_reward_transaction_handle_completions(const critical_completion *, size_t) {}
void divine_trade_runtime_completions(const critical_completion *, size_t) {}
void boon_shop_transaction_handle_completions(const critical_completion *, size_t) {}
void zone_touch_transaction_handle_completions(const critical_completion *, size_t) {}
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
static int data_directory_syncs;
static volatile sig_atomic_t reaped_pid, reaped_status;
extern "C" int __real_fsync(int);
extern "C" int __wrap_fsync(int fd)
{
	if (getpid() == parent_pid)
	{
		struct stat current
		{
		}, target{};
		if (stat(".", &current) == 0 && fstat(fd, &target) == 0 &&
		    current.st_dev == target.st_dev && current.st_ino == target.st_ino)
			++data_directory_syncs;
	}
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
critical_submit_result critical_command_coordinator_submit(critical_command command)
{
	command.accepted_at_usec = 1;
	assert(critical_command_normalize(&command));
	grants.push_back(std::move(command));
	return critical_submit_result::accepted;
}
size_t critical_command_coordinator_pulse(critical_completion *results, size_t capacity)
{
	size_t count = 0;
	while (count < capacity && !grant_completions.empty())
	{
		results[count++] = grant_completions.front();
		grant_completions.pop_front();
	}
	return count;
}
void mark_player_dirty_components(int, player_component_mask_t) {}
void collector_catalog_cache_invalidate() {}
bool collector_transaction_item_busy(uint64_t)
{
	return false;
}
void command_interpreter(P_char, char *)
{
	abort();
}
void process_with_paging(P_char, char *)
{
	abort();
}
void send_to_char(const char *text, P_char ch, int)
{
	send_to_char(text, ch);
}
P_char find_player_by_pid(int pid)
{
	for (P_char ch = character_list; ch; ch = ch->next)
		if (GET_PID(ch) == pid)
			return ch;
	return nullptr;
}
bool player_load_item_graph_materialize_creation(const item_transfer_payload &,
						 const item_transfer_result &, std::vector<P_obj> *)
{
	return false;
}
void obj_from_char(P_obj object)
{
	P_obj *link = &object->loc.carrying->carrying;
	while (*link != object)
		link = &(*link)->next_content;
	*link = object->next_content;
	object->next_content = nullptr;
	object->loc_p = LOC_NOWHERE;
}
void obj_to_obj(P_obj object, P_obj container)
{
	object->loc_p = LOC_INSIDE;
	object->loc.inside = container;
	object->next_content = container->contains;
	container->contains = object;
}
void extract_obj(P_obj object, int)
{
	P_obj *link = &object_list;
	while (*link != object)
		link = &(*link)->next;
	*link = object->next;
	object->next = nullptr;
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
bool obj_to_char(P_obj object, P_char ch)
{
	object->loc_p = LOC_CARRIED;
	object->loc.carrying = ch;
	object->next_content = ch->carrying;
	ch->carrying = object;
	return true;
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
	void lose_object() { m_pChestObject = nullptr; }
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

// PRODUCTION_BODIES

static P_obj object(uint64_t uid, int type = ITEM_OTHER)
{
	P_obj value = new obj_data{};
	value->obj_uid = uid;
	value->R_num = 0;
	value->type = type;
	value->condition = 100;
	value->cost = 25;
	value->loc_p = LOC_NOWHERE;
	value->next = object_list;
	object_list = value;
	return value;
}

static void commit_grant(bool acknowledge)
{
	assert(grants.size() == 1);
	const auto &command = grants.front();
	char operation[33];
	assert(critical_operation_id_to_hex(command.operation_id, operation, sizeof(operation)));
	const std::string insert =
		"INSERT INTO critical_operation_inbox "
		"(operation_id,command_hash,keys_hash,command_type,schema_version,payload_version,status,result_payload) "
		"VALUES (UNHEX('" +
		std::string(operation) + "'),UNHEX(REPEAT('00',32)),UNHEX(REPEAT('00',32))," +
		std::to_string(static_cast<unsigned>(command.type)) + ",1,1,1,'')";
	assert(mysql_query(DB, "START TRANSACTION") == 0);
	assert(mysql_query(DB, insert.c_str()) == 0);
	item_transfer_result result{};
	unsigned int code = 0;
	bool mutated = false;
	const bool applied =
		item_transfer_repository_execute(DB, command, &result, &code, &mutated);
	if (!applied)
		fprintf(stderr, "grant apply failed: mysql=%u errno=%d %s\n", mysql_errno(DB),
			errno, mysql_error(DB));
	assert(applied);
	assert(code == 0 && mutated);
	assert(mysql_query(DB, "COMMIT") == 0);
	if (acknowledge)
	{
		critical_completion completion{};
		completion.operation_id = command.operation_id;
		completion.type = command.type;
		completion.outcome = critical_apply_outcome::applied;
		std::array<uint8_t, ITEM_TRANSFER_RESULT_BYTES> encoded{};
		assert(item_transfer_command_encode_result(result, &encoded));
		completion.result_size = encoded.size();
		std::copy(encoded.begin(), encoded.end(), completion.result_payload.begin());
		grant_completions.push_back(completion);
	}
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
	const bool had_runtime = access("runtime", F_OK) == 0;
	const std::string mode = argv[4];
	pending_domain = mode;
	if (mode == "refuse-boot")
	{
		assert(!locker_recovery_boot());
		return 0;
	}
	assert(locker_recovery_boot());
	if (!had_runtime)
		assert(data_directory_syncs > 0);
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
	auto public_chest = new PublicChest(public_object);
	locker.add(public_chest);
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
	movement = mode == "movement" || mode == "ambiguous-grant" || mode == "late-grant";
	if (movement)
	{
		assert(item_ownership_runtime_hydrate_owner({ item_owner_type::system, 0, 0 }, 0));
		assert(item_ownership_runtime_hydrate_owner({ item_owner_type::player, 42, 0 }, 0));
		auto grant = object(400, ITEM_CONTAINER);
		contained(grant, object(401));
		assert(item_creation_grant_submit_to_player(&user, grant, &user));
		assert(item_movement_transaction_player_busy(&user));
	}
	purchase = mode == "purchase";
	audit = mode == "audit";
	durable = mode != "durability" && mode != "malformed" && mode != "blocked-publish" &&
		  mode != "blocked-io" && mode != "reaped" &&
		  mode.find("cycle") == std::string::npos;
	if (mode == "public-object-missing")
		durable = false;
	const bool external_pending = mode.ends_with("-pending") || mode == "other-fenced";
	if (external_pending)
		durable = false;
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
	if (mode == "public-object-missing")
		public_chest->lose_object();
	if (mode == "room-cycle")
		coins->next_content = coins;
	if (mode == "public-cycle")
		public_object->contains->next_content = public_object->contains;
	if (mode == "holder-cycle")
		holder.carrying->next_content = holder.carrying;
	if (mode == "occupant-cycle")
		user.next_in_room = &user;
	if (mode == "late-grant" || mode == "ambiguous-grant")
		commit_grant(mode == "late-grant");
	if (external_pending)
	{
		assert(mysql_query(DB,
				   "INSERT INTO player_items(pid,vnum,obj_uid) VALUES(42,48,400)") ==
		       0);
		assert(mysql_query(
			       DB,
			       "INSERT INTO item_current_owner(item_uid,root_item_uid,owner_type,owner_id,item_revision,vnum,state) VALUES(400,400,1,42,1,48,1)") ==
		       0);
	}
	if (mode == "blocked-publish")
	{
		// A FIFO at the temporary file makes open(O_EXCL) fail immediately.
		assert(mkfifo("runtime/locker-shutdown/shutdown.pending", 0600) == 0);
	}
	const int calls_before_capture = prepare_calls;
	block_child_io = mode == "blocked-io";
	if (mode == "reaped")
		signal(SIGCHLD, reap_fixture);
	// FINAL_COMPLETION_PUBLICATION
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
