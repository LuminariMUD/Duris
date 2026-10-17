#include "guild/artifact.c"
#include "sql/sql.h"
#include "core/prototypes.h"
#include "player/player_save_worker.h"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <cerrno>

namespace fs = std::filesystem;

namespace
{
std::string state_root;
bool booting = true;
int admission_error = 0;
std::vector<persistence_job_write_fn> writes;

void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << message << '\n';
		exit(1);
	}
}
} // namespace

const char *persistence_mode_flatfile_root()
{
	return state_root.c_str();
}

bool redis_invalidate_artifact_cache()
{
	return true;
}

bool sql_async_booting()
{
	return booting;
}

const object_template *find_object_template(int vnum)
{
	static const object_template prototype = []
	{
		object_template value;
		value.extra_flags = ITEM_ARTIFACT;
		value.short_description = "a fixture artifact";
		return value;
	}();
	return vnum == 600 || vnum == 602 ? &prototype : nullptr;
}

void send_to_char_f(P_char, const char *, ...) {}

player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t, size_t,
						    persistence_job_write_fn write)
{
	require(kind == persistence_job_kind::artifact,
		"flat artifact bypassed its writer job kind");
	if (admission_error)
	{
		errno = admission_error;
		return player_save_submit_result::unavailable;
	}
	writes.push_back(std::move(write));
	return player_save_submit_result::accepted;
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

	int owner_pid = 99;
	int timer = 99;
	require(!sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 0 && timer == 0,
		"missing flat artifact authority did not fail closed");
	std::string error;
	const flatfile_artifact_record artifact = { 600,  true,	 FLATFILE_ARTIFACT_ON_PLAYER,
						    42,	  5000,	 1,
						    1000, 42,	 4000,
						    1,	  60001, artifact_identity_state::present };
	const flatfile_artifact_record second = { 602,	true,  FLATFILE_ARTIFACT_ON_PLAYER,
						  75,	6000,  2,
						  1000, 84,    3000,
						  1,	60201, artifact_identity_state::present };
	require(flatfile_artifact_establish(state_root, { artifact, second }, &error) ==
			flatfile_artifact_result::ok,
		"could not establish runtime artifact authority: " + error);
	require(artifacts_load(), "could not hydrate flat artifact memory");
	require(sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 42 && timer == 4000,
		"SQL-compatible bind lookup did not read flat authority");
	owner_pid = 77;
	timer = 4100;
	sql_update_bind_data(600, &owner_pid, &timer);
	require(sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 77 && timer == 4100,
		"SQL-compatible bind update did not persist flat authority");
	require(!sql_get_bind_data(601, &owner_pid, &timer) && owner_pid == 0 && timer == 0,
		"SQL-compatible bind lookup synthesized a missing artifact");
	booting = false;
	owner_pid = 88;
	timer = 4200;
	sql_update_bind_data(600, &owner_pid, &timer);
	flatfile_artifact_record stored;
	require(writes.size() == 1 && sql_get_bind_data(600, &owner_pid, &timer) &&
			owner_pid == 88 &&
			flatfile_artifact_get(state_root, 600, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.bind_owner_pid == 77,
		"live binding waited for storage or wrote synchronously after boot");
	owner_pid = 99;
	timer = 4300;
	sql_update_bind_data(600, &owner_pid, &timer);
	require(writes.size() == 2 && writes[0]().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 1 &&
			sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 99,
		"old flat capture acknowledgement cleaned or changed newer live state");
	require(writes[1]().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 0 &&
			flatfile_artifact_get(state_root, 600, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.bind_owner_pid == 99 && stored.canonical_item_uid == 60001 &&
			stored.timer == 5000,
		"ordered flat captures lost UID/timer/soul coherence");
	writes.clear();
	int durable_owner = 99;
	for (const int refused : { ESHUTDOWN, ENOSPC })
	{
		admission_error = refused;
		const int next_owner = durable_owner - 1;
		owner_pid = next_owner;
		timer = 4400;
		sql_update_bind_data(600, &owner_pid, &timer);
		require(writes.empty() && artifact_save_pulse(false) == 1 &&
				flatfile_artifact_get(state_root, 600, &stored, &error) ==
					flatfile_artifact_result::ok &&
				stored.bind_owner_pid == durable_owner &&
				sql_get_bind_data(600, &owner_pid, &timer) &&
				owner_pid == next_owner,
			"writer refusal rolled back memory or used synchronous flat fallback");
		admission_error = 0;
		artifact_save_pulse(true);
		require(writes.size() == 1 &&
				writes.back()().outcome == player_save_apply_outcome::applied &&
				artifact_save_pulse(false) == 0,
			"flat admission retry did not save current state");
		writes.clear();
		durable_owner = next_owner;
	}
	fs::permissions(root / "domains", fs::perms::owner_read, fs::perm_options::replace);
	owner_pid = 96;
	timer = 4450;
	sql_update_bind_data(600, &owner_pid, &timer);
	require(sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 96 && writes.size() == 1,
		"unavailable storage blocked a live flat binding change");
	const auto unavailable = writes.back()();
	fs::permissions(root / "domains", fs::perms::owner_all, fs::perm_options::replace);
	require(unavailable.outcome == player_save_apply_outcome::retryable_failure &&
			artifact_save_pulse(true) == 1 && writes.size() == 1,
		"retryable flat failure lost the retained capture or queued another one");
	require(writes.back()().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 0,
		"retained flat capture could not recover after storage healed");
	writes.clear();

	const fs::path authority = root / "domains/artifact_catalog";
	std::ifstream healthy_input(authority, std::ios::binary);
	const std::string healthy{ std::istreambuf_iterator<char>(healthy_input), {} };
	std::fstream corrupt(authority, std::ios::in | std::ios::out | std::ios::binary);
	require(corrupt.good(), "could not open artifact authority for corruption test");
	corrupt.seekg(-1, std::ios::end);
	char byte = 0;
	corrupt.read(&byte, 1);
	byte ^= 0x5a;
	corrupt.seekp(-1, std::ios::end);
	corrupt.write(&byte, 1);
	corrupt.close();
	owner_pid = 88;
	timer = 88;
	require(sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 96 && timer == 4450,
		"storage corruption changed authoritative live binding state");
	require(!artifacts_load() && sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 96,
		"failed hydration replaced authoritative binding state");
	owner_pid = 12;
	timer = 4200;
	sql_update_bind_data(600, &owner_pid, &timer);
	require(sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 12 && timer == 4200 &&
			artifact_save_pulse(false) == 1,
		"failed persistence undid the live binding update or lost its dirty state");
	require(flatfile_artifact_get(state_root, 600, &stored, &error) ==
			flatfile_artifact_result::invalid,
		"SQL-compatible bind update overwrote corrupt authority");
	require(writes.size() == 1 &&
			writes.back()().outcome == player_save_apply_outcome::terminal_failure &&
			artifact_save_pulse(false) == 1,
		"terminal flat capture failure lost dirty state");
	{
		std::ofstream restored(authority, std::ios::binary | std::ios::trunc);
		restored.write(healthy.data(), healthy.size());
	}
	artifact_save_pulse(true);
	require(writes.size() == 2 &&
			writes.back()().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 0 && artifacts_load() &&
			sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 12 &&
			timer == 4200,
		"flat retry/reload did not preserve the current binding");
	writes.clear();
	require(artifact_binds_reset(-1) && writes.size() == 1 && artifact_save_pulse(false) == 2,
		"flat all-souls reset did not share one captured batch/receipt");
	owner_pid = 55;
	timer = 5000;
	sql_update_bind_data(600, &owner_pid, &timer);
	require(writes.size() == 2 && writes[0]().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 1 &&
			sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 55,
		"shared reset acknowledgement cleaned a later binding capture");
	require(writes[1]().outcome == player_save_apply_outcome::applied &&
			artifact_save_pulse(false) == 0 &&
			flatfile_artifact_get(state_root, 602, &stored, &error) ==
				flatfile_artifact_result::ok &&
			stored.bind_owner_pid == -1 && stored.canonical_item_uid == 60201 &&
			stored.timer == 6000 && artifacts_load() &&
			sql_get_bind_data(600, &owner_pid, &timer) && owner_pid == 55,
		"flat shared reset lost unrelated identity/timer or later current state");
	writes.clear();
	char_data god = {};
	god.player.level = FORGER;
	char clear_arg[] = "600";
	for (const auto state :
	     { artifact_identity_state::unresolved, artifact_identity_state::present,
	       artifact_identity_state::retired })
	{
		auto &row = artifact_rows.at(600);
		row.identity_state = state;
		row.canonical_item_uid = state == artifact_identity_state::unresolved ? 0 : 60001;
		arti_clear_sql(&god, clear_arg);
		require(writes.empty() && !row.removed && row.identity_state == state,
			"flat clear erased unresolved/present/retired identity");
	}
	artifact_rows.at(600).identity_state = artifact_identity_state::absent;
	artifact_rows.at(600).canonical_item_uid = 0;
	for (int repeat = 0; repeat < 2; ++repeat)
	{
		arti_clear_sql(&god, clear_arg);
		require(writes.size() == 1 && artifact_rows.at(600).removed &&
				writes.back()().outcome == player_save_apply_outcome::applied &&
				artifact_save_pulse(false) == 0 && artifacts_load() &&
				artifact_rows.at(600).removed &&
				flatfile_artifact_get(state_root, 600, &stored, &error) ==
					flatfile_artifact_result::ok &&
				stored.identity_state == artifact_identity_state::absent &&
				!stored.canonical_item_uid && !stored.owned && !stored.timer,
			"flat clear lost proven absence across its captured write/reload");
		writes.clear();
	}

	// Stage through the actual artifact authority. No partial result, store
	// call, or second identity map may change timers or soul bindings.
	booting = true;
	auto &legacy = artifact_rows.at(600);
	legacy.owned = true;
	legacy.removed = false;
	legacy.timer = 1234;
	legacy.locType = ARTIFACT_ON_PC;
	legacy.location = 88;
	legacy.identity_state = artifact_identity_state::unresolved;
	artifact_binds[600] = { 88, 2345 };
	std::vector<artifact_population_template> prototypes = { { 600, ITEM_ARTIFACT },
								 { 602, ITEM_ARTIFACT },
								 { 603, ITEM_ARTIFACT } };
	std::vector<artifact_payload_projection> population;
	for (const auto &[vnum, uid] :
	     { std::pair{ 600, uint64_t{ 60001 } }, std::pair{ 602, uint64_t{ 60201 } } })
	{
		artifact_payload_projection row = {};
		row.domain = artifact_payload_domain::player;
		row.row_id = row.item_uid = uid;
		row.vnum = vnum;
		row.quantity = 1;
		row.extra_flags_present = true;
		row.extra_flags = ITEM_ARTIFACT;
		row.owner_reference = 88;
		row.payload_owner = { item_owner_type::player, 88, 0 };
		row.custody_examined = row.custody_found = true;
		row.custody = { uid, uid, 0,	row.payload_owner,
				1,   1,	  vnum, item_custody_state::active };
		population.push_back(row);
	}
	require(artifacts_stage_population(population, prototypes, false) && writes.empty() &&
			artifact_rows.at(600).identity_state ==
				artifact_identity_state::unresolved &&
			artifact_rows.at(602).canonical_item_uid == 60201 &&
			artifact_rows.at(602).canonical_payloads.size() == 1,
		"partial population erased established qualification or granted a new identity");
	require(artifacts_stage_population(population, prototypes, true) && writes.empty() &&
			artifact_rows.at(600).canonical_item_uid == 60001 &&
			artifact_rows.at(600).canonical_payloads.size() == 1 &&
			artifact_rows.at(600).canonical_payloads[0].payload_owner.id == 88 &&
			artifact_rows.at(600).timer == 1234 &&
			artifact_binds.at(600).owner_pid == 88 &&
			artifact_binds.at(600).timer == 2345 && artifact_rows.at(603).removed &&
			artifact_rows.at(603).identity_state == artifact_identity_state::absent,
		"population did not stage into the existing authority without changing legacy state");
	const auto generation = arti_cache_generation;
	prototypes.push_back(prototypes.front());
	require(!artifacts_stage_population({}, prototypes, true) &&
			arti_cache_generation == generation &&
			artifact_rows.at(600).canonical_item_uid == 60001 &&
			artifact_rows.at(600).canonical_payloads.size() == 1 && writes.empty(),
		"invalid population published a prefix or invalidated the current cache");
	prototypes.pop_back();
	booting = false;
	require(!artifacts_stage_population({}, prototypes, true) &&
			artifact_rows.at(600).canonical_item_uid == 60001 &&
			arti_cache_generation == generation,
		"boot classifier replaced live identity");
	require(artifact_save_pulse(true) == 2 && writes.size() == 2,
		"classified identities did not use normal dirty writer captures");
	for (auto &write : writes)
		require(write().outcome == player_save_apply_outcome::applied,
			"classified flat identity capture failed");
	require(!artifact_save_pulse(false) && artifacts_load() &&
			artifact_rows.at(600).canonical_item_uid == 60001 &&
			artifact_rows.at(600).timer == 1234 &&
			artifact_binds.at(600).owner_pid == 88 &&
			artifact_binds.at(600).timer == 2345 && artifact_rows.at(603).removed &&
			artifact_rows.at(600).canonical_payloads.empty(),
		"classified identity/timer/soul did not survive existing capture/reload");

	std::cout << "flat-file artifact bind runtime passed\n";
	return 0;
}
