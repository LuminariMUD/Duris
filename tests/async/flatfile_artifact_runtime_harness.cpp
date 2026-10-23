#include "flatfile/flatfile_artifact_repository.h"
#include "core/prototypes.h"
#include "sql/sql.h"
#include "world/object_template.h"
#include "guild/artifact_admission.h"
#include "guild/artifact_guild_state.h"
#include "guild/artifact_population_repository.h"
#include "item/item_ownership_runtime.h"
#include "flatfile/flatfile_identity_repository.h"

#include <cstdlib>
#include <algorithm>
#include <climits>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;
void list_artifacts_sql(P_char, int, bool, bool);
void arti_player_sql(P_char, char *);

void artifact_update_sql(int vnum, bool owned, int location_type, int location, time_t timer,
			 int type);
void artifact_update_sql(P_obj artifact, char owned, time_t timer);

namespace
{
std::string state_root;
int read_count;
int room_load_count;
int mob_load_count;
int extract_count;
std::vector<std::string> feedback;

void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}
} // namespace

room_data rooms[2] = {};
P_room world = rooms;
extern const int top_of_world = 1;
index_data mob_indices[1] = {};
P_index mob_index = mob_indices;
index_data obj_indices[1] = {};
P_index obj_index = obj_indices;
char_data boot_mob = {};
npc_only_data boot_mob_data = {};
P_char character_list = &boot_mob;
bool redis_enabled = false;

void send_to_char(const char *text, P_char)
{
	feedback.emplace_back(text);
}

char *get_player_name_from_pid(int)
{
	static char name[] = "Fixture";
	return name;
}

bool redis_report_cache_enabled()
{
	return false;
}

const char *persistence_mode_flatfile_root()
{
	return state_root.c_str();
}

bool redis_invalidate_artifact_cache()
{
	return true;
}

const object_template *find_object_template(int vnum)
{
	static const object_template artifact = []
	{
		object_template result;
		result.extra_flags = ITEM_ARTIFACT;
		result.short_description = "a report artifact";
		return result;
	}();
	static const object_template ordinary;
	return vnum == 701 ? &artifact : vnum == 703 ? &ordinary : nullptr;
}
std::string pad_ansi(const char *text, int, bool)
{
	return text;
}
int get_player_pid_from_name(char *)
{
	return 77;
}
flatfile_identity_result flatfile_identity_lookup_pid(const std::string &, int,
						      flatfile_identity_record *, std::string *)
{
	return flatfile_identity_result::not_found;
}

P_obj read_object(int vnum, int)
{
	++read_count;
	P_obj object = new obj_data{};
	object->g_key = vnum;
	return object;
}

int real_room(const int vnum)
{
	if (vnum == 1201)
		return 0;
	if (vnum == 1202)
		return 1;
	return -1;
}

int real_room0(const int vnum)
{
	return real_room(vnum);
}

void obj_to_room(P_obj object, int room)
{
	require(object && room >= 0 && room <= top_of_world, "invalid boot room placement");
	require(object->obj_uid == static_cast<unsigned long>(object->g_key * 100 + 1),
		"ground canonical UID lost");
	++room_load_count;
	delete object;
}

void obj_to_char(P_obj object, P_char character)
{
	require(object && character == &boot_mob, "invalid boot NPC placement");
	require(object->obj_uid == static_cast<unsigned long>(object->g_key * 100 + 1),
		"NPC canonical UID lost");
	++mob_load_count;
	delete object;
}

void extract_obj(P_obj object, int)
{
	++extract_count;
	delete object;
}

static void register_fixture(P_obj object, uint64_t pid)
{
	artifact_payload_projection source = {};
	source.domain = artifact_payload_domain::player;
	source.row_id = 1;
	source.item_uid = source.payload_root_item_uid = object->obj_uid;
	source.owner_reference = pid;
	source.payload_owner = { item_owner_type::player, pid, 0 };
	source.vnum = 701;
	source.extra_flags = ITEM_ARTIFACT;
	source.extra_flags_present = true;
	source.quantity = 1;
	source.custody_examined = source.custody_found = source.custody_owner_revision_found = true;
	source.custody = {
		object->obj_uid,	   object->obj_uid, 0, source.payload_owner, 1, 1, 701,
		item_custody_state::active
	};
	require(item_ownership_runtime_hydrate(source.custody),
		"could not hydrate fixture custody");
	require(artifact_begin_recovery(object, source),
		"qualified runtime fixture could not register");
	artifact_object_placed(object);
}

int main(int argc, char **argv)
{
	require(argc == 2, "state root argument required");
	state_root = argv[1];
	const fs::path root = state_root;
	fs::create_directories(root / "domains");
	fs::create_directories(root / "players");
	fs::create_directories(root / "identities/names");
	fs::permissions(root, fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "players", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "identities", fs::perms::owner_all, fs::perm_options::replace);
	fs::permissions(root / "identities/names", fs::perms::owner_all, fs::perm_options::replace);

	arti_data data = {};
	require(!get_artifact_data_sql(700, &data),
		"missing flat authority unexpectedly exposed artifact data");
	artifact_update_sql(700, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, 5000, 1);
	std::vector<flatfile_artifact_record> records;
	std::string error;
	require(flatfile_artifact_list(state_root, &records, &error) ==
			flatfile_artifact_result::not_found,
		"runtime update synthesized a missing flat artifact authority");

	const flatfile_artifact_record unowned = {
		700, false, FLATFILE_ARTIFACT_ON_GROUND, 1201, 4000, 2, 1000, 42, 3000, 5
	};
	const flatfile_artifact_record ground = { 702,	true,  FLATFILE_ARTIFACT_ON_GROUND,
						  1201, 4100,  1,
						  1000, 0,     0,
						  1,	70201, artifact_identity_state::present };
	const flatfile_artifact_record inactive_ground = {
		703, false, FLATFILE_ARTIFACT_ON_GROUND, 1201, 4200, 1, 1000, 0, 0, 1
	};
	const flatfile_artifact_record npc = { 704,  true,  FLATFILE_ARTIFACT_ON_NPC,
					       8100, 4300,  1,
					       1000, 0,	    0,
					       1,    70401, artifact_identity_state::present };
	const flatfile_artifact_record missing_npc = {
		705, true,  FLATFILE_ARTIFACT_ON_NPC,	     9999, 4400, 1, 1000, 0, 0,
		1,   70501, artifact_identity_state::present
	};
	const flatfile_artifact_record bad_ground = {
		706, true,  FLATFILE_ARTIFACT_ON_GROUND,     9999, 4500, 1, 1000, 0, 0,
		1,   70601, artifact_identity_state::present
	};
	require(flatfile_artifact_establish(state_root,
					    { unowned, ground, inactive_ground, npc, missing_npc,
					      bad_ground },
					    &error) == flatfile_artifact_result::ok,
		"could not establish runtime artifact authority: " + error);
	require(artifacts_load(), "could not hydrate flat artifact memory");
	require(!get_artifact_data_sql(700, &data) && data.vnum == 700 && !data.owned &&
			data.locType == FLATFILE_ARTIFACT_ON_GROUND && data.location == 1201 &&
			data.timer == 4000 && data.type == 2 && data.next == nullptr,
		"runtime artifact read did not preserve unowned database semantics");

	artifact_update_sql(700, true, FLATFILE_ARTIFACT_ON_PLAYER, 77, 6000, 3);
	require(get_artifact_data_sql(700, &data) && data.owned &&
			data.locType == FLATFILE_ARTIFACT_ON_PLAYER && data.location == 77 &&
			data.timer == 6000 && data.type == 3,
		"runtime artifact update did not round trip through the compatibility reader");
	flatfile_artifact_record stored;
	require(flatfile_artifact_get(state_root, 700, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.bind_owner_pid == 42 && stored.bind_timer == 3000 &&
			stored.revision == 6,
		"runtime artifact update did not preserve binding or revision state");

	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_GROUND, 1202, 7000, 1);
	require(get_artifact_data_sql(701, &data) && data.vnum == 701 && data.owned &&
			data.location == 1202 && data.timer == 7000 && data.type == 1,
		"runtime artifact update did not insert a newly tracked artifact");
	require(flatfile_artifact_get(state_root, 701, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.bind_owner_pid == 0 && stored.bind_timer == 0 &&
			stored.revision == 1,
		"newly tracked runtime artifact did not receive binding defaults");
	// This behavior fixture now identifies the physical canonical item explicitly;
	// unresolved vnum-only rows cannot authorize removal of an arbitrary object.
	stored.canonical_item_uid = 70101;
	stored.identity_state = artifact_identity_state::present;
	require(flatfile_artifact_snapshot_apply(state_root, { stored }, &error) ==
				flatfile_artifact_result::ok &&
			artifacts_load(),
		"could not establish canonical identity for the removal control");
	P_obj removed = new obj_data{};
	obj_indices[0].virtual_number = 701;
	removed->R_num = 0;
	removed->obj_uid = 70101;
	removed->extra_flags = ITEM_ARTIFACT;
	removed->name = const_cast<char *>("artifact");
	register_fixture(removed, 42);
	require(remove_owned_artifact_sql(removed),
		"runtime owned-artifact removal rejected flat persistence");
	artifact_object_extracted(removed, false);
	delete removed;
	require(flatfile_artifact_get(state_root, 701, &stored, &error) ==
				flatfile_artifact_result::ok &&
			!stored.owned && stored.location_type == FLATFILE_ARTIFACT_NOT_IN_GAME &&
			stored.location == -1 && stored.timer == 7000 && stored.type == 1 &&
			stored.bind_owner_pid == -1 && stored.bind_timer == 0 &&
			stored.revision >= 2,
		"runtime owned-artifact removal did not persist its complete outcome");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_GROUND, 1202, 7000, 1);
	P_obj fed = new obj_data{};
	fed->R_num = 0;
	fed->obj_uid = 70101;
	fed->extra_flags = ITEM_ARTIFACT;
	fed->name = const_cast<char *>("artifact");
	const time_t minimum_timer = time(NULL) + 120 * 60;
	register_fixture(fed, 42);
	artifact_feed_to_min_sql(fed, 120);
	artifact_object_extracted(fed, false);
	delete fed;
	require(flatfile_artifact_get(state_root, 701, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.timer >= minimum_timer && stored.timer <= minimum_timer + 2 &&
			stored.owned && stored.location_type == FLATFILE_ARTIFACT_ON_GROUND &&
			stored.location == 1202 && stored.type == 1 &&
			stored.bind_owner_pid == -1 && stored.bind_timer == 0,
		"runtime minimum feed did not extend only the canonical flat timer");

	mob_indices[0].virtual_number = 8100;
	boot_mob_data.R_num = 0;
	boot_mob.only.npc = &boot_mob_data;
	boot_mob.specials.act = ACT_ISNPC;
	setupMortArtiList_sql();
	addOnGroundArtis_sql();
	addOnMobArtis_sql();
	require(read_count == 0 && room_load_count == 0 && mob_load_count == 0 &&
			extract_count == 0,
		"tracking-only boot rows constructed unqualified physical bodies");

	char_data owner = {};
	pc_only_data pc = {};
	owner.only.pc = &pc;
	owner.player.level = 51;
	pc.pid = 42;
	obj_data worn = {};
	worn.obj_uid = 70101;
	worn.extra_flags = ITEM_ARTIFACT;
	worn.loc_p = LOC_WORN;
	worn.loc.wearing = &owner;
	worn.short_description = const_cast<char *>("fixture artifact");
	register_fixture(&worn, 42);
	const std::string satisfaction = "&+RYou feel a sense of satisfaction from above.&n\r\n";
	const time_t feed_start = time(nullptr) + 100;
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, feed_start, 1);
	for (int seconds : { 60, 13 * 3600 })
	{
		feedback.clear();
		artifact_feed_sql(&owner, &worn, seconds);
		require(feedback == std::vector<std::string>{ satisfaction },
			"direct light/deep feed did not publish the requested wording once");
	}
	require(get_artifact_data_sql(701, &data) && data.timer == feed_start + 60 + 13 * 3600,
		"direct positive feed changed its timer calculation");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 42,
			    time(nullptr) + ARTIFACT_BLOOD_DAYS * SECS_PER_REAL_DAY, 1);
	feedback.clear();
	artifact_feed_sql(&owner, &worn, 60);
	require(feedback == std::vector<std::string>{ satisfaction },
		"valid capped direct feed lost its positive feedback");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 77, feed_start, 1);
	feedback.clear();
	artifact_feed_sql(&owner, &worn, 60);
	require(feedback == std::vector<std::string>{ satisfaction } &&
			get_artifact_data_sql(701, &data) && data.timer == feed_start + 60 &&
			data.location == 42,
		"qualified player custody did not repair stale tracking before feeding");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 77, feed_start, 1);
	item_ownership_runtime_entry disputed = {};
	require(item_ownership_runtime_lookup(worn.obj_uid, &disputed), "missing fixture custody");
	disputed.owner.id = 77;
	require(item_ownership_runtime_hydrate(disputed), "could not seed disputed custody");
	feedback.clear();
	artifact_feed_sql(&owner, &worn, 60);
	require(feedback.empty() && get_artifact_data_sql(701, &data) && data.timer == feed_start &&
			data.location == 77,
		"rejected cross-owner direct feed changed state or published satisfaction");
	disputed.owner.id = 42;
	require(item_ownership_runtime_hydrate(disputed), "could not restore fixture custody");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, feed_start, 1);
	feedback.clear();
	owner.player.level = 62;
	artifact_feed_sql(&owner, &worn, 60);
	owner.player.level = 51;
	require(feedback.empty() && get_artifact_data_sql(701, &data) && data.timer == feed_start,
		"trusted direct feed changed state or published feedback");
	int rejected_soul = 77, rejected_timer = 0;
	sql_update_bind_data(701, &rejected_soul, &rejected_timer);
	artifact_feed_sql(&owner, &worn, 60, true);
	require(feedback.empty() && get_artifact_data_sql(701, &data) && data.timer == feed_start,
		"rejected-soul direct feed changed state or published satisfaction");
	artifact_feed_sql(&owner, &worn, -60);
	require(feedback ==
			std::vector<std::string>{
				"&+BYou hear a distant cry in the back of your mind...&n\n\r" },
		"negative direct feed lost its existing feedback");
	require(get_artifact_data_sql(701, &data) && data.timer == feed_start - 60,
		"negative direct feed increased the timer instead of reducing it");
	const time_t cap = time(nullptr) + ARTIFACT_BLOOD_DAYS * SECS_PER_REAL_DAY;
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, cap + 200, 1);
	artifact_feed_sql(&owner, &worn, 60);
	require(get_artifact_data_sql(701, &data) && data.timer >= cap && data.timer <= cap + 2,
		"direct feed above the cap increased the timer instead of clamping it");
	artifact_update_sql(701, true, FLATFILE_ARTIFACT_ON_PLAYER, 42, feed_start, 1);
	artifact_feed_sql(&owner, &worn, INT_MIN);
	require(get_artifact_data_sql(701, &data) && data.timer == 1,
		"extreme negative feed overflowed or restarted an expired artifact timer");
	artifact_feed_sql(&owner, &worn, INT_MAX);
	require(get_artifact_data_sql(701, &data) && data.timer >= cap && data.timer <= cap + 2,
		"extreme positive feed failed to clamp to the feed cap");
	feedback.clear();
	artifact_update_sql(701, false, FLATFILE_ARTIFACT_ON_PLAYER, 42, feed_start, 1);
	artifact_feed_sql(&owner, &worn, 60);
	require(feedback == std::vector<std::string>{ satisfaction } &&
			get_artifact_data_sql(701, &data) && data.owned && data.location == 42 &&
			data.timer == feed_start + 60,
		"newly tracked direct feed did not publish the requested wording once");
	std::cout << "direct feed wording and accepted/rejected feedback passed\n";

	const fs::path authority = root / "domains/artifact_catalog";
	// The corpse transaction still expects player custody during death's
	// unequip-to-inventory step. GET_ID returns -2 for this dead character.
	char_data dying = {};
	pc_only_data dying_pc = {};
	dying.only.pc = &dying_pc;
	dying_pc.pid = 77;
	dying.specials.position = STAT_DEAD;
	obj_data held = {};
	held.obj_uid = 70101;
	held.R_num = 0;
	held.extra_flags = ITEM_ARTIFACT;
	held.loc_p = LOC_CARRIED;
	held.loc.carrying = &dying;
	artifact_object_extracted(&worn, false);
	register_fixture(&held, 77);
	artifact_update_sql(&held, 'Y', 7000);
	require(flatfile_artifact_get(state_root, 701, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.location_type == FLATFILE_ARTIFACT_ON_PLAYER &&
			stored.location == 77,
		"death inventory update lost the persistent artifact owner before corpse transfer");
	const int before_reads = read_count, before_extracts = extract_count;
	feedback.clear();
	list_artifacts_sql(&owner, 1, true, true);
	require(read_count == before_reads && extract_count == before_extracts,
		"flat artifact list constructed a gameplay object for inspection");
	require(std::any_of(feedback.begin(), feedback.end(), [](const std::string &line)
			    { return line.find("a report artifact") != std::string::npos; }),
		"flat artifact list omitted its cached template label");
	feedback.clear();
	char player[] = "77";
	arti_player_sql(&owner, player);
	require(read_count == before_reads && extract_count == before_extracts,
		"flat player artifact report constructed a gameplay object for inspection");
	require(std::any_of(feedback.begin(), feedback.end(), [](const std::string &line)
			    { return line.find("a report artifact") != std::string::npos; }),
		"flat player artifact report omitted its cached template label");
	std::cout << "flat artifact list/player reports inspect templates without objects\n";

	critical_operation_id delivery{};
	bool newly_applied = false;
	delivery.bytes.back() = 1;
	artifact_guild_delta delta{};
	delta.vnum = 702;
	delta.canonical_item_uid = 70201;
	delta.feed_seconds = 300;
	require(artifact_apply_delivery(delivery, delta, 100000, &newly_applied),
		"prepared artifact delivery failed");
	artifact_feed_set_timer(702, 4500); // A later ordinary change keeps the marker.
	require(artifacts_load() &&
			artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			get_artifact_data_sql(702, &data) && data.timer == 4500,
		"saved effect replay duplicated feed or erased later timer state");
	require(flatfile_artifact_get(state_root, 702, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.delivery_ids == artifact_guild_delivery_ids{ delivery.bytes },
		"effect ID was not saved with the artifact timer");
	delivery.bytes.back() = 2;
	require(artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			get_artifact_data_sql(702, &data) && data.timer == 4800,
		"new delivery did not add its own feed");
	const fs::path retained = root / "domains/artifact_catalog.retained";
	fs::rename(authority, retained);
	fs::create_directory(authority);
	delivery.bytes.back() = 3;
	require(artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			get_artifact_data_sql(702, &data) && data.timer == 5100,
		"unavailable artifact save lost the live effect");
	fs::remove(authority);
	fs::rename(retained, authority);
	require(artifacts_load() && get_artifact_data_sql(702, &data) && data.timer == 4800 &&
			artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			get_artifact_data_sql(702, &data) && data.timer == 5100,
		"restart did not recover the unsaved effect exactly once");
	artifact_forget_delivery(702, delivery);
	require(artifacts_load() &&
			flatfile_artifact_get(state_root, 702, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.timer == 5100 && stored.delivery_ids.size() == 2,
		"ACK marker pruning changed the saved reward");
	delta.canonical_item_uid = 99999;
	delivery.bytes.back() = 4;
	require(artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			get_artifact_data_sql(702, &data) && data.timer == 5100,
		"retired physical identity fed a different canonical artifact");
	// Retained canonical identity can outlive its legacy gameplay projection.
	// Deliver to that original UID without inventing a physical body or row.
	stored.identity_only = true;
	require(flatfile_artifact_snapshot_apply(state_root, { stored }, &error) ==
				flatfile_artifact_result::ok &&
			artifacts_load(),
		"could not seed domain-only original identity");
	delta.canonical_item_uid = 70201;
	delta.timer_before = 5100;
	delta.timer = 5400;
	delivery.bytes.back() = 5;
	require(artifact_apply_delivery(delivery, delta, 100000, &newly_applied) && newly_applied &&
			flatfile_artifact_get(state_root, 702, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.identity_only && stored.timer == 5400 &&
			std::binary_search(stored.delivery_ids.begin(), stored.delivery_ids.end(),
					   delivery.bytes),
		"original domain-only artifact lost its owed effect or materialized a legacy projection");
	require(artifacts_load() &&
			artifact_apply_delivery(delivery, delta, 100000, &newly_applied) &&
			!newly_applied &&
			flatfile_artifact_get(state_root, 702, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.timer == 5400,
		"domain-only original effect replayed after restart");
	std::cout
		<< "prepared artifact snapshots recover saved and unsaved effects without replaying later state\n";

	std::fstream corrupt(authority, std::ios::in | std::ios::out | std::ios::binary);
	require(corrupt.good(), "could not open artifact authority for corruption test");
	corrupt.seekg(-1, std::ios::end);
	char byte = 0;
	corrupt.read(&byte, 1);
	byte ^= 0x5a;
	corrupt.seekp(-1, std::ios::end);
	corrupt.write(&byte, 1);
	corrupt.close();
	require(get_artifact_data_sql(700, &data) && data.location == 77,
		"storage corruption changed authoritative artifact memory");
	artifact_update_sql(700, true, FLATFILE_ARTIFACT_ON_PLAYER, 88, 8000, 2);
	require(flatfile_artifact_get(state_root, 700, &stored, &error) ==
			flatfile_artifact_result::invalid,
		"runtime artifact update overwrote corrupt authority");

	std::cout << "flat-file artifact gameplay runtime passed\n";
	return 0;
}
