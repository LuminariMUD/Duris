#include "core/prototypes.h"
#include "core/utils.h"
#include "core/utility.h"
#include "core/files.h"
#include "item/storage_lockers.h"
#include "persistence/locker_async.h"
#include "player/player_save_pipeline.h"
#include "player/player_snapshot_capture.h"
#include "player/player_snapshot_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "telemetry/telemetry_runtime.h"
#include "net/comm.h"
#include "world/epic.h"
#include "sql/sql.h"
#include "magic/spells.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <string>
#include <vector>

P_char character_list;
static room_data rooms[3]{};
P_room world = rooms;
static StorageLocker *active;
static std::deque<persistence_job_write_fn> writer;
static std::vector<std::vector<uint64_t>> written;
static std::vector<uint64_t> carried;
static std::vector<std::string> alerts;
static int saves, conditions, population, ejections, holder_extractions;
static bool refuse_queue, fail_write, fail_capture;
static time_t now = 1000;
extern "C" int sql_pool_is_active(void)
{
	return 1;
}

extern "C" time_t time(time_t *out) noexcept
{
	if (out)
		*out = now;
	return now;
}
void persistence_alert(int, const char *, const char *, const char *, const char *,
		       const char *reason, const char *, ...)
{
	alerts.emplace_back(reason);
}
player_save_worker_health player_save_worker_health_copy()
{
	player_save_worker_health health{};
	health.running = true;
	return health;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t, size_t,
						    persistence_job_write_fn job)
{
	if (refuse_queue)
		return player_save_submit_result::unavailable;
	writer.push_back(std::move(job));
	return player_save_submit_result::accepted;
}
player_snapshot_capture_result
player_item_snapshot_list_capture(P_char holder, bool, bool, bool,
				  std::vector<player_item_snapshot> *items, size_t *bytes)
{
	assert(IS_PC(holder) && GET_PID(holder) == 0);
	if (fail_capture)
		return player_snapshot_capture_result::retryable_allocation_failure;
	for (uint64_t uid : carried)
	{
		player_item_snapshot item{};
		item.object_uid = uid;
		items->push_back(item);
	}
	*bytes = items->size() * sizeof(player_item_snapshot);
	return player_snapshot_capture_result::ok;
}
const char *persistence_mode_flatfile_root()
{
	return nullptr;
}
player_save_apply_result flatfile_locker_snapshot_apply(const std::string &,
							const flatfile_locker_save &, std::string *)
{
	std::abort();
}
player_save_apply_result locker_snapshot_repository_apply_from_pool(const locker_snapshot &snapshot)
{
	if (fail_write)
		return { player_save_apply_outcome::terminal_failure, 0, 0 };
	std::vector<uint64_t> uids;
	for (const auto &item : snapshot.items)
		uids.push_back(item.object_uid);
	written.push_back(std::move(uids));
	return { player_save_apply_outcome::applied, 0, 0 };
}
extern "C" void locker_async_request_resort(P_char, P_char) {}
extern "C" void locker_async_restore_snapshot_view(P_char, P_char) {}
extern "C" int locker_async_prepare_snapshot(P_char, P_char)
{
	return 1;
}
void extract_char(P_char ch)
{
	if (GET_PID(ch) == 0)
		++holder_extractions;
	for (P_char *link = &character_list; *link; link = &(*link)->next)
		if (*link == ch)
		{
			*link = ch->next;
			break;
		}
}
void extract_char_after_terminal_save(P_char ch)
{
	// Boundary representing locker_handle_leave: the full journey exercises it.
	assert(ch == active->GetLockerUser());
	ch->in_room = 2;
	assert(locker_async_mark_dirty(active->GetLockerChar(), ch, 1, "idle-leave"));
	extract_char(ch);
}
telemetry_capture_result telemetry_runtime_game_context(P_char, P_desc)
{
	return {};
}
char *get_player_name_from_pid(int)
{
	return nullptr;
}
bool affected_by_spell(P_char, int)
{
	return false;
}
int gain_condition(P_char ch, int, int)
{
	assert(GET_PID(ch) > 0);
	++conditions;
	return 0;
}
void epic_choose_new_epic_task(P_char) {}
static void display_divine_experience(P_char) {}
void act(const char *, int, P_char, P_obj, void *, int) {}
void send_to_char(const char *, P_char) {}
void loginlog(int, const char *, ...) {}
void statuslog(int, const char *, ...) {}
void sql_log(P_char, const char *, const char *, ...) {}
void update_ingame_racewar(int side)
{
	population += side;
}
void close_socket(P_desc d)
{
	assert(persistence_save_character_terminal(d->character, RENT_CRASH));
	d->character->desc = nullptr;
}
int calculate_save_room(P_char, int, int room)
{
	return room;
}
player_save_pipeline_result player_save_pipeline_request(P_char ch, player_component_mask_t, int,
							 int)
{
	assert(GET_PID(ch) > 0);
	++saves;
	return player_save_pipeline_result::queued;
}
// PRODUCTION_SLOT
static deferred_save_slot *find_deferred_save_slot(int)
{
	return nullptr;
}
static void clear_manual_save_status(int) {}
static void locker_handle_postsave(P_char, StorageLocker *, int);
void locker_post_save_hook(P_char ch)
{
	if (active && ch->in_room == 1)
		locker_handle_postsave(ch, active, 1);
}
int save_locker_char(P_char ch, int)
{
	return locker_async_mark_dirty(active->GetLockerChar(), ch, 0, "postsave");
}
static const char *locker_room_name(int)
{
	return "fixture";
}
static void locker_log_save_failure(StorageLocker *, P_char, P_char, const char *, const char *)
{
	std::abort();
}
static void locker_eject_to_exit(P_char ch, int)
{
	++ejections;
	ch->in_room = 2;
}
void *__malloc(size_t size, const char *, const char *, int)
{
	return calloc(1, size);
}
char *str_dup(const char *value)
{
	return strdup(value);
}
StorageLocker::~StorageLocker()
{
	// No chest contents in this fixture. Only release the constructor's room labels.
	auto desc = world[GetRealRoom()].ex_description;
	free(desc->keyword);
	free(desc->next->keyword);
	free(desc->next);
	free(desc);
	world[GetRealRoom()].ex_description = nullptr;
}
// PRODUCTION_BODIES

static void complete_job()
{
	assert(writer.size() == 1);
	auto job = std::move(writer.front());
	writer.pop_front();
	job();
	locker_async_pulse();
}

int main()
{
	rooms[1].room_flags = ROOM_LOCKER;
	rooms[0].number = 65201;
	rooms[1].number = 65202;
	char locker_name[] = "account.fixture.1.locker";
	char player_name[] = "Differentname", account_name[] = "Fixture";
	acct_entry account{};
	account.acct_name = account_name;
	pc_only_data holder_pc{}, user_pc{};
	user_pc.pid = 7;
	locker_async_init();

	for (bool holder_first : { false, true })
	{
		char_data holder{}, user{};
		holder.player.name = locker_name;
		holder.only.pc = &holder_pc;
		holder.specials.timer = 15;
		user.player.name = player_name;
		user.only.pc = &user_pc;
		user.player.racewar = 1;
		user.in_room = 1;
		descriptor_data desc{};
		desc.connected = CON_PLAYING;
		desc.account = &account;
		desc.character = &user;
		user.desc = &desc;
		StorageLocker locker(1, &holder, &user);
		active = &locker;
		assert(locker.LockerUserIsOwner());
		holder.next = holder_first ? &user : nullptr;
		user.next = holder_first ? nullptr : &holder;
		character_list = holder_first ? &holder : &user;
		carried = { 101 };
		written.clear();
		alerts.clear();
		saves = conditions = population = ejections = holder_extractions = 0;

		// Even an active owner must not lose an aging holder.
		for (int tick = 0; tick < 20; ++tick)
		{
			user.specials.timer = 0;
			point_update();
		}
		assert(holder.specials.timer == 15 && conditions == 20);
		assert(saves == 0 && population == 0 && holder_extractions == 0);
		assert(!persistence_save_character_terminal(&holder, RENT_LINKDEAD));
		assert(persistence_save_all_characters_terminal(RENT_CRASH));
		assert(saves == 1 && alerts.empty());
		locker_async_pulse(); // First generation remains in flight across idle rent.
		assert(writer.size() == 1);
		carried.push_back(202);
		user.specials.timer = 15;
		point_update();
		assert(!user.desc && character_list == &holder);
		assert(saves == 3 && population == -1 && ejections == 0);
		assert(holder_extractions == 0 && locker_async_name_busy(locker_name));
		complete_job();
		assert(holder_extractions == 0 && writer.size() == 1);
		complete_job();
		assert((written == std::vector<std::vector<uint64_t>>{ { 101 }, { 101, 202 } }));
		assert(holder_extractions == 1 && !character_list &&
		       !locker_async_name_busy(locker_name));
		puts("PASS: both idle list orders preserve the latest generation through disconnect");

		// Dirty, queue-refused, capture-failed and write-failed terminal holders
		// all survive point_update until the retry actually commits.
		for (int failure = 0; failure < 3; ++failure)
		{
			holder.next = nullptr;
			character_list = &holder;
			holder.specials.timer = 16;
			holder_extractions = 0;
			refuse_queue = failure == 0;
			fail_capture = failure == 1;
			fail_write = failure == 2;
			assert(locker_async_mark_dirty(&holder, nullptr, 1, "retry"));
			point_update();
			locker_async_pulse();
			if (fail_write)
				complete_job();
			assert(character_list == &holder && holder_extractions == 0);
			assert(locker_async_name_busy(locker_name) && writer.empty());
			refuse_queue = fail_capture = fail_write = false;
			now += 29;
			point_update();
			locker_async_pulse();
			assert(writer.empty());
			now += 1;
			point_update();
			locker_async_pulse();
			assert(writer.size() == 1 && character_list == &holder);
			complete_job();
			assert(holder_extractions == 1 && !character_list);
			assert(written.back() == carried);
		}
		puts("PASS: dirty and retrying holders survive until successful persistence");
	}

	// The owner verdict belongs to one occupancy, never to the holder or name.
	char unknown_locker[] = "account.Unknown.1.locker";
	for (int identity = 0; identity < 6; ++identity)
	{
		char_data holder{}, visitor{};
		holder.player.name = identity == 5 ? unknown_locker : locker_name;
		holder.only.pc = &holder_pc;
		visitor.player.name = player_name;
		visitor.only.pc = &user_pc;
		visitor.player.racewar = identity == 1 ? 2 : 1;
		visitor.in_room = 1;
		visitor.specials.timer = 4;
		descriptor_data desc{};
		acct_entry visitor_account{};
		char other_name[] = "Visitor", empty[] = "";
		visitor_account.acct_name = identity == 0 ? other_name :
					    identity == 4 ? empty :
							    account_name;
		desc.account = identity == 3 ? nullptr : &visitor_account;
		visitor.desc = identity == 2 || identity == 5 ? nullptr : &desc;
		StorageLocker locker(1, &holder, &visitor);
		active = &locker;
		assert(!locker.LockerUserIsOwner());
		visitor.desc = nullptr;
		ejections = 0;
		character_list = &holder;
		locker_handle_postsave(&visitor, &locker, 1);
		assert(ejections == 1);
		locker_async_pulse();
		complete_job();
	}
	puts("PASS: disconnected visitors, wrong side and missing identities remain nonowners");

	// Source loss is unrecoverable; report it instead of treating it as a save.
	char_data missing{};
	missing.player.name = locker_name;
	missing.only.pc = &holder_pc;
	character_list = nullptr;
	alerts.clear();
	assert(locker_async_mark_dirty(&missing, nullptr, 1, "missing"));
	locker_async_pulse();
	assert((alerts == std::vector<std::string>{ "source_missing" }));
	assert(writer.empty());
	puts("PASS: lost snapshot sources raise a persistence alert");
}
