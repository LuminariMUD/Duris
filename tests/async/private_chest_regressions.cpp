// The production registry, sorting, authorization and receipt code is compiled
// intact. Only world/prototype, capture and writer/SQL services are controlled.
#include "item/storage_lockers.c"
#include "net/unicode.h"
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <deque>

static room_data rooms[2]{};
P_room world = rooms;
extern const int top_of_world = 1;
static index_data indices[1]{};
P_index obj_index = indices;
P_char character_list = NULL;
P_obj object_list = NULL;
persistence_mode persistence_mode_get()
{
	return PERSISTENCE_MODE_MARIADB_PRIMARY;
}
static uint64_t uid = 1;
static int event_ids_before_failure = -1;
static bool refuse_scrap_prototype = false;
extern "C" ssize_t __real_getrandom(void *, size_t, unsigned int);
extern "C" ssize_t __wrap_getrandom(void *data, size_t length, unsigned int flags)
{
	if (event_ids_before_failure == 0)
	{
		errno = EIO;
		return -1;
	}
	if (event_ids_before_failure > 0)
		--event_ids_before_failure;
	return __real_getrandom(data, length, flags);
}
static std::string output;
static bool refuse = false;
static player_save_apply_outcome write_outcome = player_save_apply_outcome::applied;
static std::deque<persistence_job_write_fn> jobs;
static uint64_t saved_owner;
static bool private_event_pending;
static P_char private_event_owner;
static int private_event_room;
static nevent_data private_event{};
P_nevent get_scheduled_excluding_current(P_char, event_func_type)
{
	return private_event_pending ? &private_event : NULL;
}
nevent_schedule_result add_event(event_func fn, int, P_char owner, P_char, P_obj, int,
				 const void *data, int size)
{
	assert(fn == StorageLocker::event_savePrivateChests && size == sizeof(int));
	private_event_pending = true;
	private_event_owner = owner;
	memcpy(&private_event_room, data, sizeof(private_event_room));
	return { nevent_schedule_status::scheduled, { &private_event, 1 } };
}
static void private_tick()
{
	assert(private_event_pending);
	private_event_pending = false;
	StorageLocker::event_savePrivateChests(private_event_owner, NULL, NULL,
					       &private_event_room);
}
static std::vector<int> written_weights;
static bool throw_write;

MYSQL *DB = reinterpret_cast<MYSQL *>(1);
static std::vector<std::pair<std::string, std::shared_ptr<sql_write_receipt>>> audit_writes;
static std::shared_ptr<sql_write_receipt> management_receipt;
static std::function<void(bool, const sql_rows &)> read_done;
static password_completion password_done;
static std::function<void(P_char, const sql_rows &)> log_done;
static std::string log_query;

void logit(const char *, const char *, ...) {}
void *__malloc(size_t n, const char *, const char *, int)
{
	return calloc(1, n);
}
void __free(void *p, const char *, int)
{
	free(p);
}
char *str_dup(const char *s)
{
	return strdup(s);
}
void str_free(const char *s)
{
	free(const_cast<char *>(s));
}
P_obj read_object(int vnum, int)
{
	if (vnum == 9 && refuse_scrap_prototype)
		return NULL;
	auto p = new obj_data{};
	p->type = ITEM_CONTAINER;
	p->loc_p = LOC_NOWHERE;
	p->obj_uid = uid++;
	return p;
}
void obj_to_room(P_obj p, int room)
{
	assert(OBJ_NOWHERE(p));
	p->loc_p = LOC_ROOM;
	p->loc.room = room;
	p->next_content = world[room].contents;
	world[room].contents = p;
}
void obj_from_room(P_obj p)
{
	auto link = &world[p->loc.room].contents;
	while (*link != p)
		link = &(*link)->next_content;
	*link = p->next_content;
	p->next_content = NULL;
	p->loc_p = LOC_NOWHERE;
}
void obj_to_obj(P_obj p, P_obj c)
{
	assert(OBJ_NOWHERE(p));
	p->loc_p = LOC_INSIDE;
	p->loc.inside = c;
	p->next_content = c->contains;
	c->contains = p;
}
void obj_from_obj(P_obj p)
{
	auto link = &p->loc.inside->contains;
	while (*link != p)
		link = &(*link)->next_content;
	*link = p->next_content;
	p->next_content = NULL;
	p->loc_p = LOC_NOWHERE;
}
void extract_obj(P_obj p, int)
{
	if (OBJ_INSIDE(p))
		obj_from_obj(p);
	while (p->contains)
	{
		auto child = p->contains;
		obj_from_obj(child);
		extract_obj(child, TRUE);
	}
	if (p->str_mask & STRUNG_KEYS)
		free(p->name);
	if (p->str_mask & STRUNG_DESC1)
		free(p->description);
	if (p->str_mask & STRUNG_DESC2)
		free(p->short_description);
	if (p->ex_description)
	{
		free(p->ex_description->keyword);
		free(p->ex_description->description);
		free(p->ex_description);
	}
	delete p;
}
void act(const char *, int, P_char, P_obj, void *, int) {}
void set_obj_affected(P_obj, int, sh_int, sh_int) {}
bool falling_obj(P_obj, int, bool)
{
	return false;
}
P_obj unequip_char(P_char, int, bool)
{
	return NULL;
}
int char_in_list(const P_char ch)
{
	return ch == character_list;
}
void obj_from_char(P_obj)
{
	assert(false);
}
int number(int low, int)
{
	return low;
}
void send_to_char_f(P_char, const char *format, ...)
{
	char text[4096];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	output += text;
}
int checked_snprintf_at(const char *, int, char *dest, size_t n, const char *fmt, ...)
{
	va_list args;
	va_start(args, fmt);
	int size = vsnprintf(dest, n, fmt, args);
	va_end(args);
	return size;
}
P_char find_character_by_runtime_id(uint64_t id)
{
	for (auto p = character_list; p; p = p->next)
		if (p->runtime_id == id)
			return p;
	return NULL;
}
int god_check(char *)
{
	return false;
}
const char *get_account_name_safe(P_char)
{
	return "fixture";
}

bool persistence_trace = false;
player_save_submit_result persistence_writer_submit(persistence_job_kind, uint64_t owner, size_t,
						    persistence_job_write_fn write)
{
	saved_owner = owner;
	if (refuse)
		return player_save_submit_result::unavailable;
	jobs.push_back(std::move(write));
	return player_save_submit_result::accepted;
}
player_save_apply_result
locker_chest_snapshot_repository_apply_from_pool(const locker_chest_snapshot &s)
{
	assert(s.locker_id == 7 && s.chest_id == 55);
	if (throw_write)
		throw std::bad_alloc();
	if (!s.items.empty())
		written_weights.push_back(s.items[0].weight);
	return { write_outcome, 0, 0 };
}
player_snapshot_capture_result
player_item_snapshot_contents_capture(P_obj p, std::vector<player_item_snapshot> *items)
{
	for (auto child = p->contains; child; child = child->next_content)
	{
		player_item_snapshot item{};
		item.object_uid = child->obj_uid;
		item.vnum = 1;
		item.weight = child->weight;
		item.parent_index = PLAYER_SNAPSHOT_NO_PARENT;
		items->push_back(item);
	}
	return player_snapshot_capture_result::ok;
}
bool sql_queue_statements_at(persistence_query_site, std::vector<std::string> statements,
			     std::shared_ptr<sql_write_receipt> receipt)
{
	if (refuse)
		return false;
	if (statements[0].find("INSERT IGNORE") == 0)
		audit_writes.emplace_back(statements[0], std::move(receipt));
	else
		management_receipt = std::move(receipt);
	return true;
}
bool sql_read_at(persistence_query_site, std::string,
		 std::function<void(bool, const sql_rows &)> done)
{
	read_done = std::move(done);
	return true;
}
bool sql_read_for_at(persistence_query_site, P_char, std::string query,
		     std::function<void(P_char, const sql_rows &)> done)
{
	log_query = std::move(query);
	log_done = std::move(done);
	return true;
}
bool sql_read_work_at(persistence_query_site, sql_read_work_fn,
		      std::function<void(bool, const sql_rows &)>)
{
	return false;
}
bool password_async_start(P_desc, password_login_job *, const char *, password_completion done)
{
	password_done = std::move(done);
	return true;
}
password_login_job *password_work_submit(const char *, const char *, const char *, int, int)
{
	return NULL;
}
int is_bcrypt_hash(const char *)
{
	return true;
}
char *coins_to_string(int, int, int, int, const char *)
{
	assert(false && "fixture expects item movement, not money conversion");
	return NULL;
}
std::string escape_str(const char *s)
{
	return s;
}
int strn_cmp(const char *a, const char *b, unsigned n)
{
	return strncasecmp(a, b, n);
}
bool is_abbrev(const char *a, const char *b)
{
	return *a && !strncasecmp(a, b, strlen(a));
}
char *one_argument(const char *s, char *dest)
{
	while (isspace(*s))
		++s;
	while (*s && !isspace(*s))
		*dest++ = *s++;
	*dest = 0;
	while (isspace(*s))
		++s;
	return const_cast<char *>(s);
}
std::string sql_format(const char *format, ...)
{
	char text[8192];
	va_list args;
	va_start(args, format);
	vsnprintf(text, sizeof(text), format, args);
	va_end(args);
	return text;
}
unsigned int sql_execute(MYSQL *, const std::string &)
{
	return 0;
}
static void finish_save()
{
	assert(!jobs.empty());
	auto write = std::move(jobs.front());
	jobs.pop_front();
	write();
}
static sql_rows hash_row(const char *hash)
{
	sql_row row;
	row.fields = { hash ? std::optional<std::string>(hash) : std::nullopt };
	return { row };
}
static void finish_management(bool ok, const sql_rows &rows)
{
	management_receipt->ok = ok;
	management_receipt->finished.store(true);
	locker_chest_changes_pulse();
	assert(read_done);
	auto done = std::move(read_done);
	read_done = {};
	done(true, rows);
}

// AUDIT_PRODUCTION
int main()
{
	refuse = true;
	assert(sql_log_chest_activity(7, 55, "owner", CHEST_ACTION_PUT, "an item [uid 9]"));
	assert(sql_chest_log_pending(7));
	refuse = false;
	sql_chest_log_pulse();
	assert(audit_writes.size() == 1);
	auto statement = audit_writes[0].first;
	audit_writes[0].second->finished.store(true);
	sql_chest_log_pulse();
	assert(audit_writes.size() == 2);
	assert(audit_writes[1].first == statement);
	audit_writes[1].second->ok = true;
	audit_writes[1].second->finished.store(true);
	sql_chest_log_pulse();
	assert(!sql_chest_log_pending(7));

	char_data actor{}, guest{}, avatar{};
	descriptor_data desc{}, guest_desc{};
	pc_only_data pc{}, guest_pc{}, avatar_pc{};
	actor.only.pc = &pc;
	guest.only.pc = &guest_pc;
	avatar.only.pc = &avatar_pc;
	actor.player.name = const_cast<char *>("owner");
	guest.player.name = const_cast<char *>("guest");
	avatar.player.name = const_cast<char *>("owner.locker");
	actor.desc = &desc;
	desc.character = &actor;
	desc.connected = CON_PLAYING;
	guest.desc = &guest_desc;
	guest_desc.character = &guest;
	guest_desc.connected = CON_PLAYING;
	actor.runtime_id = 10;
	guest.runtime_id = 11;
	actor.next = &guest;
	character_list = &actor;
	actor.in_room = guest.in_room = 0;
	world[0].room_flags = ROOM_LOCKER;
	{
		StorageLocker locker(0, &avatar, &actor);
		locker.SetLockerId(7);
		locker.SetPublicChestId(8);
		std::string borrowed = "vault";
		auto chest = new PrivateChest(55, borrowed.c_str(), "old");
		borrowed.assign(10000, 'x');
		locker.AddPrivateChest(chest);
		auto object = chest->GetChestObj();
		assert(strstr(object->description, "(locked)"));
		obj_to_room(object, 0);
		auto item = read_object(1, REAL);
		item->weight = 42;
		obj_to_obj(item, object);
		assert(std::string(chest->m_chestKeyword) == "vault");
		for (int pass = 0; pass < 4; ++pass)
		{
			locker.NukeLockerChests();
			char args[] = "custom weapon armor";
			assert(locker.MakeChests(&actor, args));
			assert(locker.GetPrivateChests().size() == 1);
			assert(locker.FindPrivateChest("VAULT") == chest);
			assert(locker.FindChestForObject(object) == chest);
			assert(object->contains == item);
		}
		assert(chest->SaveContents(&locker, false));
		assert(saved_owner == ((55ULL << 32) | 7));
		assert(!locker.PrivateContentsDurable());
		write_outcome = player_save_apply_outcome::terminal_failure;
		finish_save();
		assert(!locker.PrivateContentsDurable());
		assert(object->contains == item);
		write_outcome = player_save_apply_outcome::applied;
		finish_save();
		assert(locker.PrivateContentsDurable());
		++item->weight;
		refuse = true;
		assert(!locker.PrivateContentsDurable());
		assert(object->contains == item);
		refuse = false;
		assert(!locker.PrivateContentsDurable());
		finish_save();
		assert(locker.PrivateContentsDurable());
		written_weights.clear();
		++item->weight;
		const int first_weight = item->weight;
		assert(chest->SaveContents(&locker, false));
		++item->weight;
		const int latest_weight = item->weight;
		assert(chest->SaveContents(&locker, false));
		++item->weight;
		const int coalesced_weight = item->weight;
		assert(chest->SaveContents(&locker, false));
		++item->weight; // unsaved live changes cannot mutate a queued capture
		finish_save();
		private_tick();
		assert(!jobs.empty());
		finish_save();
		private_tick();
		assert((written_weights == std::vector<int>{ first_weight, coalesced_weight }));
		assert(latest_weight != coalesced_weight);
		assert(!locker.PrivateContentsDurable());
		finish_save();
		private_tick();
		assert(locker.PrivateContentsDurable());
		++item->weight;
		throw_write = true;
		assert(chest->SaveContents(&locker, false));
		finish_save();
		throw_write = false;
		private_tick();
		assert(!jobs.empty());
		finish_save();
		private_tick();
		assert(locker.PrivateContentsDurable());
		// Refused writer admission retains the immutable capture for the timer.
		++item->weight;
		const int refused_weight = item->weight;
		refuse = true;
		assert(chest->SaveContents(&locker, false) && jobs.empty());
		++item->weight;
		refuse = false;
		private_tick();
		finish_save();
		private_tick();
		assert(written_weights.back() == refused_weight);
		assert(!locker.PrivateContentsDurable());
		finish_save();
		private_tick();
		assert(locker.PrivateContentsDurable());
		// A failed older generation must yield to its retained successor.
		++item->weight;
		assert(chest->SaveContents(&locker, false));
		++item->weight;
		const int successor_weight = item->weight;
		assert(chest->SaveContents(&locker, false));
		write_outcome = player_save_apply_outcome::terminal_failure;
		finish_save();
		write_outcome = player_save_apply_outcome::applied;
		private_tick();
		finish_save();
		private_tick();
		assert(written_weights.back() == successor_weight &&
		       locker.PrivateContentsDurable());
		assert(!locker_container_access_allowed(&actor, object));
		locker.SetCurrentChestId(55);
		assert(locker_container_access_allowed(&actor, object));
		assert(!locker_container_access_allowed(&guest, object));
		auto nested = read_object(1, REAL);
		obj_to_obj(nested, object);
		assert(locker_container_access_allowed(&actor, nested));
		locker.InvalidateChestAccess();
		assert(!locker_container_access_allowed(&actor, nested));
		locker.SetCurrentChestId(55);
		desc.connected = CON_GET_RACE;
		assert(!locker_container_access_allowed(&actor, nested));
		desc.connected = CON_PLAYING;
		locker_invalidate_chest_access(&actor);
		assert(!locker_container_access_allowed(&actor, nested));
		actor.player.name = const_cast<char *>("visitor");
		char opening[] = "vault secret";
		assert(locker_opencmd(&actor, opening));
		assert(password_done);
		auto delayed = std::move(password_done);
		char close[] = "";
		locker_closecmd(&actor, close);
		delayed(&desc, 1, NULL);
		assert(!locker_container_access_allowed(&actor, object));
		assert(locker_opencmd(&actor, opening));
		delayed = std::move(password_done);
		chest->SetPasswordHash("changed");
		delayed(&desc, 1, NULL);
		assert(!locker_container_access_allowed(&actor, object));
		assert(locker_opencmd(&actor, opening));
		delayed = std::move(password_done);
		delayed(&desc, 1, NULL);
		assert(locker_container_access_allowed(&actor, object));
		actor.player.name = const_cast<char *>("owner");
		// Secure the changed graph before management; admission is not success.
		assert(!locker.PrivateContentsDurable());
		finish_save();
		assert(locker.PrivateContentsDurable());
		refuse = true;
		output.clear();
		locker_change_chest(&actor, &locker, chest, "new", false);
		assert(chest->GetPasswordHash() == "changed");
		assert(!locker.ChestWritePending());
		assert(output.find("Password set") == std::string::npos);
		refuse = false;
		output.clear();
		locker_change_chest(&actor, &locker, chest, "new", false);
		assert(locker.ChestWritePending());
		assert(chest->GetPasswordHash() == "changed");
		assert(!locker_container_access_allowed(&guest, object));
		finish_management(false, hash_row("changed"));
		assert(chest->GetPasswordHash() == "changed");
		assert(!locker.ChestWritePending());
		assert(output.find("Password set") == std::string::npos);
		locker_change_chest(&actor, &locker, chest, "new", false);
		finish_management(true, hash_row("new"));
		assert(chest->GetPasswordHash() == "new");
		assert(output.find("Password set") != std::string::npos);
		// Only acknowledged metadata changes update the password-presence display.
		locker_change_chest(&actor, &locker, chest, "", false);
		assert(chest->GetPasswordHash() == "new" &&
		       strstr(object->description, "(locked)"));
		finish_management(false, hash_row("new"));
		assert(chest->GetPasswordHash() == "new" &&
		       strstr(object->description, "(locked)"));
		locker_change_chest(&actor, &locker, chest, "", false);
		finish_management(true, hash_row(NULL));
		assert(chest->GetPasswordHash().empty() &&
		       !strstr(object->description, "(locked)"));
		locker_change_chest(&actor, &locker, chest, "new", false);
		assert(!strstr(object->description, "(locked)"));
		finish_management(false, hash_row(NULL));
		assert(chest->GetPasswordHash().empty() &&
		       !strstr(object->description, "(locked)"));
		locker_change_chest(&actor, &locker, chest, "new", false);
		finish_management(true, hash_row("new"));
		assert(chest->GetPasswordHash() == "new" &&
		       strstr(object->description, "(locked)"));
		// Preserve the stable UID and complete UTF-8 characters within the SQL bound.
		const std::string prefix = "[uid " + std::to_string(item->obj_uid) + "] ";
		for (const char *character : { "\xC3\xA9", "\xE2\x82\xAC", "\xF0\x9F\x98\x80" })
		{
			const std::string retained = prefix + std::string(255 - prefix.size(), 'x');
			std::string label = retained.substr(prefix.size()) + character + "tail";
			item->short_description = label.data();
			const auto before = audit_writes.size();
			LockerMovementAudit audit(&actor, NULL, object, item);
			assert(audit.Ready());
			audit.Commit();
			assert(audit_writes.size() == before + 1);
			assert(audit_writes.back().first.find("'" + retained + "'") !=
			       std::string::npos);
			for (auto &write : audit_writes)
			{
				write.second->ok = true;
				write.second->finished.store(true);
			}
			sql_chest_log_pulse();
			assert(!sql_chest_log_pending(7));
		}
		item->short_description = NULL;
		// The movement gate must not admit an operation whose audit cannot be retained.
		locker.SetCurrentChestId(55);
		event_ids_before_failure = 0;
		assert(locker_container_access_allowed(&actor, object));
		{
			LockerMovementAudit audit(&actor, NULL, object, item);
			assert(!audit.Ready());
		}
		assert(!sql_chest_log_pending(7));
		event_ids_before_failure = -1;
		// A disconnected database must reject before any movement is published.
		MYSQL *saved_db = DB;
		DB = NULL;
		{
			LockerMovementAudit audit(&actor, object, NULL, item);
			assert(!audit.Ready());
		}
		assert(!sql_chest_log_pending(7));
		DB = saved_db;
		// Scrapping a stored bag reserves the destroyed bag and each spilled root.
		auto bag = read_object(1, REAL);
		bag->name = const_cast<char *>("bag");
		bag->short_description = const_cast<char *>("a damaged bag");
		obj_to_obj(bag, object);
		auto first = read_object(1, REAL);
		auto second = read_object(1, REAL);
		first->short_description = const_cast<char *>("a first item");
		second->short_description = const_cast<char *>("a second item");
		obj_to_obj(first, bag);
		obj_to_obj(second, bag);
		const auto before_scrap = audit_writes.size();
		for (int failure = 0; failure < 3; ++failure)
		{
			event_ids_before_failure = failure;
			assert(!MakeScrap(&actor, bag));
			assert(OBJ_INSIDE(bag) && bag->contains == second &&
			       second->next_content == first);
			assert(!sql_chest_log_pending(7) && audit_writes.size() == before_scrap);
		}
		event_ids_before_failure = -1;
		refuse_scrap_prototype = true;
		assert(!MakeScrap(&actor, bag));
		assert(OBJ_INSIDE(bag) && bag->contains == second && !sql_chest_log_pending(7) &&
		       audit_writes.size() == before_scrap);
		refuse_scrap_prototype = false;
		const uint64_t bag_uid = bag->obj_uid;
		assert(MakeScrap(&actor, bag));
		assert(OBJ_ROOM(first) && OBJ_ROOM(second));
		assert(audit_writes.size() == before_scrap + 3);
		assert(audit_writes[before_scrap].first.find(
			       "[uid " + std::to_string(second->obj_uid) + "]") !=
		       std::string::npos);
		assert(audit_writes[before_scrap + 1].first.find(
			       "[uid " + std::to_string(first->obj_uid) + "]") !=
		       std::string::npos);
		assert(audit_writes[before_scrap + 2].first.find("[uid " + std::to_string(bag_uid) +
								 "]") != std::string::npos);
		for (size_t i = before_scrap; i < audit_writes.size(); ++i)
		{
			audit_writes[i].second->ok = true;
			audit_writes[i].second->finished.store(true);
		}
		sql_chest_log_pulse();
		assert(!sql_chest_log_pending(7));
		// Remove the newly created scraps and the two spilled items from the fixture room.
		auto scraps = world[0].contents;
		while (scraps && (scraps == first || scraps == second || !scraps->name ||
				  !strstr(scraps->name, "scraps")))
			scraps = scraps->next_content;
		assert(scraps && scraps->name && strstr(scraps->name, "scraps"));
		obj_from_room(scraps);
		extract_obj(scraps, TRUE);
		obj_from_room(first);
		extract_obj(first, TRUE);
		obj_from_room(second);
		extract_obj(second, TRUE);
		// An abandoned operation releases its reservation and submits no false event.
		const auto before_cancel = audit_writes.size();
		{
			LockerMovementAudit audit(&actor, object, NULL, item);
			assert(audit.Ready() && sql_chest_log_pending(7));
			sql_chest_log_pulse();
			assert(audit_writes.size() == before_cancel);
		}
		assert(!sql_chest_log_pending(7));
		// Use the registered public wrapper for the supported private-to-public empty.
		P_obj public_object = NULL;
		for (auto candidate = world[0].contents; candidate;
		     candidate = candidate->next_content)
			if (auto registered = locker.FindChestForObject(candidate);
			    registered && !registered->IsPrivateChest())
				public_object = candidate;
		assert(public_object);
		event_ids_before_failure = 1;
		{
			LockerMovementAudit audit(&actor, object, public_object, item);
			assert(!audit.Ready());
		}
		assert(!sql_chest_log_pending(7) && audit_writes.size() == before_cancel);
		event_ids_before_failure = -1;
		{
			LockerMovementAudit audit(&actor, object, public_object, item);
			assert(audit.Ready());
			audit.Commit();
		}
		assert(audit_writes.size() == before_cancel + 2);
		for (auto &write : audit_writes)
		{
			write.second->ok = true;
			write.second->finished.store(true);
		}
		sql_chest_log_pulse();
		assert(!sql_chest_log_pending(7));
		// A two-sided move cannot consume the last slot and leave a false first event.
		std::vector<std::shared_ptr<sql_chest_log_entry>> held;
		for (int i = 0; i < 4095; ++i)
		{
			auto entry = sql_prepare_chest_activity(7, 55, "owner", CHEST_ACTION_PUT,
								"held");
			assert(entry);
			held.push_back(std::move(entry));
		}
		const auto before_full = audit_writes.size();
		{
			LockerMovementAudit audit(&actor, object, public_object, item);
			assert(!audit.Ready());
		}
		for (const auto &entry : held)
			sql_finish_chest_activity(entry, false);
		assert(audit_writes.size() == before_full && !sql_chest_log_pending(7) &&
		       sql_chest_log_available());
		// History renders the stored ID even after a later chest reuses the name.
		locker_logcmd(&actor, NULL);
		assert(log_done);
		assert(log_query.find("ORDER BY l.logged_at DESC, l.id DESC LIMIT 50") !=
		       std::string::npos);
		sql_row row;
		row.fields = { "now", "owner", "3", std::nullopt, "an item", "55" };
		output.clear();
		log_done(&actor, { row });
		assert(output.find("deleted chest #55") != std::string::npos);
		obj_from_obj(item);
		extract_obj(item, TRUE);
		obj_from_obj(nested);
		extract_obj(nested, TRUE);
		assert(!locker.PrivateContentsDurable());
		finish_save();
		assert(locker.PrivateContentsDurable());
		locker_change_chest(&actor, &locker, chest, "", true);
		finish_management(false, hash_row("new"));
		assert(locker.FindPrivateChest("vault") == chest);
		locker_change_chest(&actor, &locker, chest, "", true);
		finish_management(true, {});
		assert(!locker.FindPrivateChest("vault"));
	}
	while (world[0].contents)
	{
		auto p = world[0].contents;
		obj_from_room(p);
		extract_obj(p, TRUE);
	}
	free(world[0].ex_description->next);
	free(world[0].ex_description);
	world[0].ex_description = NULL;
	puts("private chest registry, receipts, actor access, stale opens, management and history PASS");
}
