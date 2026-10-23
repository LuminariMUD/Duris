#include "flatfile/flatfile_artifact_guild_delivery.h"
#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_association_repository.h"
#include "combat/combat_outcome_command.h"
#include "world/zone_touch_command.h"
#include "flatfile/flatfile_player_snapshot_file.h"
#include "flatfile/flatfile_store.h"
#include "guild/artifact_guild_command.h"
#include "guild/artifact_guild_delivery.h"
#include "guild/artifact_guild_state.h"
#include "guild/assocs.h"
#include "player/player_save_worker.h"
#include <algorithm>
#include <chrono>
#include <thread>
#include <set>

#include <cassert>
#include <cstdlib>
#include <filesystem>
#include <iostream>

namespace fs = std::filesystem;
static std::string fixture_root;
static artifact_guild_delivery_ids live_markers;
static unsigned applications, grants, prunes, feedback_count, alerts;
static std::set<uint64_t> native_owners;
bool persistence_mode_requires_mysql()
{
	return false;
}
const char *persistence_mode_flatfile_root()
{
	return fixture_root.c_str();
}
void persistence_alert(int, const char *, const char *, const char *, const char *, const char *,
		       const char *, ...)
{
	++alerts;
}
player_save_submit_result persistence_writer_submit(persistence_job_kind kind, uint64_t owner,
						    size_t bytes, persistence_job_write_fn work)
{
	assert(kind == persistence_job_kind::artifact_delivery && bytes &&
	       native_owners.insert(owner).second);
	work();
	return player_save_submit_result::accepted;
}
// The ordinary game-thread projection/save is a controlled boundary here.
// Real capture/application/snapshots have their separate native runtime tests.
bool artifact_guild_state_apply_delivery(const critical_operation_id &id,
					 const artifact_guild_payload &,
					 artifact_guild_payload *published)
{
	++applications;
	*published = {};
	if (!std::binary_search(live_markers.begin(), live_markers.end(), id.bytes))
	{
		++grants;
		live_markers.insert(std::lower_bound(live_markers.begin(), live_markers.end(),
						     id.bytes),
				    id.bytes);
		published->actor_pid = 42;
		published->artifact_count = 1;
	}
	return true;
}
void artifact_guild_state_forget_delivery(const critical_operation_id &id,
					  const artifact_guild_payload &)
{
	++prunes;
	std::erase(live_markers, id.bytes);
	// Deliberately do not save: model the crash before the pruning capture.
}
void artifact_delivery_markers(int32_t *, critical_operation_id *, artifact_guild_delivery_ids *ids)
{
	*ids = live_markers;
}
void artifact_guild_state_guild_markers(uint32_t *, critical_operation_id *,
					artifact_guild_delivery_ids *ids)
{
	ids->clear();
}
void artifact_guild_transaction_publish_delivery(const artifact_guild_payload &published)
{
	if (published.artifact_count || published.guild_id)
		++feedback_count;
}
template <typename Predicate> void drive_until(Predicate predicate)
{
	const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
	while (!predicate())
	{
		assert(std::chrono::steady_clock::now() < deadline);
		artifact_guild_delivery_pulse();
		std::this_thread::sleep_for(std::chrono::milliseconds(2));
	}
}

int main(int argc, char **argv)
{
	assert(argc == 2 || argc == 3);
	const fs::path root = argv[1];
	fixture_root = root.string();
	for (const auto &path : { root, root / "domains", root / "players", root / "identities",
				  root / "identities/names" })
	{
		fs::create_directories(path);
		fs::permissions(path, fs::perms::owner_all, fs::perm_options::replace);
	}
	std::string error;
	for (int pid : { 42, 43 })
	{
		flatfile_player_domain_record player;
		player.pid = pid;
		player.account_name = "effect";
		player.racewar = pid == 42 ? 1 : 2;
		player.domains.base_stat_revision = 1;
		player.domains.base_stats.fill(50);
		assert(flatfile_player_domain_establish(root, player, &error) ==
		       flatfile_player_domain_result::ok);
	}
	flatfile_artifact_record artifact;
	artifact.vnum = 700;
	artifact.owned = true;
	artifact.location_type = FLATFILE_ARTIFACT_ON_PLAYER;
	artifact.location = artifact.bind_owner_pid = 42;
	artifact.timer = 10000;
	artifact.type = 1;
	artifact.revision = 1;
	artifact.canonical_item_uid = 70001;
	artifact.identity_state = artifact_identity_state::present;
	assert(flatfile_artifact_establish(root, { artifact }, &error) ==
	       flatfile_artifact_result::ok);
	flatfile_association_record guild;
	guild.association_id = 7;
	guild.name = "Delivery";
	guild.prestige = 95;
	guild.revision = 1;
	guild.delivery_identity = artifact_guild_legacy_identity(7);
	assert(flatfile_association_establish(root, { guild }, &error) ==
	       flatfile_association_result::ok);
	assert(flatfile_artifact_guild_delivery_initialize(root, &error) ==
	       flatfile_player_domain_result::ok);

	critical_operation_id parent_id{};
	parent_id.bytes[0] = 1;
	artifact_guild_payload intent{};
	intent.parent_operation_id = parent_id;
	intent.actor_pid = 42;
	intent.guild_id = 7;
	intent.guild_identity = guild.delivery_identity;
	intent.prestige_before = 95;
	intent.prestige_after = 115;
	intent.prestige_delta = 20;
	intent.construction_after = intent.construction_delta = 1;
	intent.construction_notch = 100;
	intent.feeding_cap = 100000;
	intent.artifact_count = 1;
	intent.artifacts[0] = { 700, ARTIFACT_DELTA_FEED, 10000, 10300, 42, 42, 0, 0, 70001, 300 };
	critical_operation_id child_id{};
	assert(critical_operation_id_derive(parent_id, ARTIFACT_GUILD_DERIVATION_DOMAIN, 42,
					    &child_id));
	critical_command child;
	assert(artifact_guild_command_build_prepared(&child, child_id, intent));
	child.accepted_at_usec = 1;
	combat_outcome_payload payload{};
	payload.victim_pid = 43;
	payload.participant_count = 2;
	payload.prepared_at = 150;
	payload.artifact_intents = true;
	payload.artifact_deliveries = { child };
	payload.participants[0].pid = 42;
	payload.participants[0].role = combat_participant_role::killer;
	payload.participants[0].racewar = 1;
	payload.participants[0].flags = COMBAT_PARTICIPANT_IN_ROOM | COMBAT_PARTICIPANT_DIVINE_EPIC;
	payload.participants[0].frag_delta = 1;
	payload.participants[0].epic_delta = 150;
	payload.participants[0].epic_boon_id = 7;
	payload.participants[0].epic_base = 100;
	payload.participants[1].pid = 43;
	payload.participants[1].role = combat_participant_role::victim;
	payload.participants[1].racewar = 2;
	critical_command parent;
	assert(combat_outcome_command_build(&parent, parent_id, payload));
	parent.accepted_at_usec = 1;
	if (argc == 3)
	{
		const std::string mode = argv[2];
		if (mode == "zone")
		{
			zone_touch_payload zone{};
			zone.zone_number = 77;
			zone.toucher_pid = 42;
			zone.boot_time = 100;
			zone.touched_at = 150;
			zone.group_size = ZONE_TOUCH_MAX_PARTICIPANTS;
			zone.stone_uid = 70002;
			zone.prepared_delivery = zone.artifact_intents = true;
			zone.stone_level = 51;
			for (size_t i = 0; i < zone.group_size; ++i)
			{
				const uint32_t pid = 42 + i;
				if (pid > 43)
				{
					flatfile_player_domain_record player;
					player.pid = pid;
					player.account_name = "effect";
					player.racewar = 1;
					player.domains.base_stat_revision = 1;
					player.domains.base_stats.fill(50);
					assert(flatfile_player_domain_establish(root, player,
										&error) ==
					       flatfile_player_domain_result::ok);
				}
				player_snapshot snapshot{};
				snapshot.schema_version = PLAYER_SNAPSHOT_SCHEMA_VERSION;
				snapshot.pid = pid;
				snapshot.revision = 1;
				snapshot.components = PLAYER_CHECKPOINT_COMPONENT_ALL;
				snapshot.encoded_size_bound = 4096;
				std::vector<uint8_t> bytes;
				assert(flatfile_player_snapshot_encode_file(&snapshot, &bytes));
				assert(flatfile_atomic_write(
					(root / "players").string(),
					flatfile_player_snapshot_file::player_filename(pid), bytes,
					&error));
				zone.participant_pids[i] = pid;
				zone.awards[i] = { 150, 0, 0, 7, 100 };
				auto effect = intent;
				effect.actor_pid = pid;
				effect.artifact_count = 0;
				critical_operation_id id{};
				assert(critical_operation_id_derive(
					parent_id, ARTIFACT_GUILD_DERIVATION_DOMAIN, pid, &id));
				critical_command delivery;
				assert(artifact_guild_command_build_prepared(&delivery, id,
									     effect));
				delivery.accepted_at_usec = 1;
				zone.artifact_deliveries.push_back(delivery);
			}
			critical_command touch;
			assert(zone_touch_command_build(&touch, parent_id, zone));
			touch.accepted_at_usec = 1;
			assert(setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1",
				      1) == 0);
			const auto interrupted = flatfile_player_domain_apply(root, touch);
			std::cerr << "zone interrupted outcome="
				  << static_cast<int>(interrupted.outcome)
				  << " error=" << interrupted.error_code << "\n";
			assert(interrupted.outcome == critical_apply_outcome::retryable_failure);
			assert(unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL") ==
			       0);
			assert(flatfile_player_domain_restore_recover(root, &error) ==
			       flatfile_player_domain_result::ok);
			auto replay = flatfile_player_domain_apply(root, touch);
			zone_touch_result result;
			assert(replay.outcome == critical_apply_outcome::already_applied &&
			       zone_touch_command_decode_result(replay.result_payload.data(),
								replay.result_size, &result) &&
			       result.artifact_intents && result.group_size == 15 &&
			       !result.recovered_claim);
			std::vector<critical_command> owed;
			assert(flatfile_artifact_guild_delivery_list(root, &owed, &error) ==
				       flatfile_player_domain_result::ok &&
			       owed.size() == 15);
			// A second parent resolving the same physical stone registers no new intent.
			auto next_parent = parent_id;
			next_parent.bytes[0] = 2;
			zone.artifact_deliveries.clear();
			for (const auto &original : owed)
			{
				artifact_guild_payload effect{};
				assert(artifact_guild_command_decode_payload(original, &effect));
				effect.parent_operation_id = next_parent;
				critical_operation_id id{};
				assert(critical_operation_id_derive(
					next_parent, ARTIFACT_GUILD_DERIVATION_DOMAIN,
					effect.actor_pid, &id));
				critical_command delivery;
				assert(artifact_guild_command_build_prepared(&delivery, id,
									     effect));
				delivery.accepted_at_usec = 1;
				zone.artifact_deliveries.push_back(delivery);
			}
			assert(zone_touch_command_build(&touch, next_parent, zone));
			touch.accepted_at_usec = 1;
			auto recovered = flatfile_player_domain_apply(root, touch);
			assert(recovered.outcome == critical_apply_outcome::applied &&
			       zone_touch_command_decode_result(recovered.result_payload.data(),
								recovered.result_size, &result) &&
			       result.recovered_claim);
			assert(flatfile_artifact_guild_delivery_list(root, &owed, &error) ==
				       flatfile_player_domain_result::ok &&
			       owed.size() == 15);
			std::cout
				<< "PASS full 15-recipient zone compound crash recovery and recovered-claim no-new-intent\n";
			return 0;
		}
		if (mode == "runtime-reservation")
		{
			assert(artifact_guild_delivery_boot());
			std::vector<critical_command> commands;
			for (uint32_t i = 1; i <= ARTIFACT_GUILD_PENDING_MAX + 1; ++i)
			{
				auto effect = intent;
				effect.parent_operation_id.bytes[0] = 9;
				for (size_t b = 0; b < sizeof(i); ++b)
					effect.parent_operation_id.bytes[4 + b] =
						static_cast<uint8_t>(i >> (b * 8));
				critical_operation_id id{};
				assert(critical_operation_id_derive(
					effect.parent_operation_id,
					ARTIFACT_GUILD_DERIVATION_DOMAIN, 42, &id));
				critical_command command;
				assert(artifact_guild_command_build_prepared(&command, id, effect));
				command.accepted_at_usec = 1;
				commands.push_back(std::move(command));
			}
			auto extra = commands.back();
			commands.pop_back();
			assert(artifact_guild_delivery_reserve(commands));
			assert(artifact_guild_delivery_pending() == ARTIFACT_GUILD_PENDING_MAX &&
			       artifact_guild_delivery_holds(70001));
			assert(!artifact_guild_delivery_reserve({ extra }));
			artifact_guild_delivery_pulse();
			assert(applications == 0);
			artifact_guild_delivery_complete(commands, false);
			assert(artifact_guild_delivery_pending() == 0 &&
			       !artifact_guild_delivery_holds(70001));
			assert(!artifact_guild_delivery_reserve({ extra, extra }));
			assert(artifact_guild_delivery_pending() == 0);
			std::cout
				<< "PASS bounded reservations, rejection cleanup and original-target hold\n";
			return 0;
		}
		assert(mode == "runtime-pending" || mode == "runtime-orphan");
		assert(flatfile_player_domain_apply(root, parent).outcome ==
		       critical_apply_outcome::applied);
		auto save_effect = [&]
		{
			artifact.timer = 10300;
			artifact.delivery_ids = { child_id.bytes };
			guild.prestige = 115;
			guild.construction = 1;
			guild.delivery_ids = { child_id.bytes };
			assert(flatfile_artifact_snapshot_apply(root, { artifact }, &error) ==
			       flatfile_artifact_result::ok);
			assert(flatfile_association_save(root, guild, &error) ==
			       flatfile_association_result::ok);
		};
		if (mode == "runtime-orphan")
		{
			save_effect();
			bool ack = false;
			assert(flatfile_artifact_guild_delivery_advance(root, child, &ack,
									&error) ==
				       flatfile_player_domain_result::ok &&
			       ack);
			live_markers =
				artifact.delivery_ids; // Hydrated after the pruning save was lost.
		}
		assert(artifact_guild_delivery_boot());
		if (mode == "runtime-pending")
		{
			drive_until([] { return grants == 1; });
			assert(artifact_guild_delivery_pending() == 1 &&
			       artifact_guild_delivery_holds(70001));
			bool ack = true;
			assert(flatfile_artifact_guild_delivery_advance(root, child, &ack,
									&error) ==
				       flatfile_player_domain_result::ok &&
			       !ack);
			artifact_guild_delivery_complete({ child }, true);
			artifact_guild_delivery_pulse();
			assert(grants == 1 && feedback_count == 1);
			save_effect(); // Release the ordinary immutable entity snapshots.
			drive_until([] { return artifact_guild_delivery_pending() == 0; });
			assert(applications == 1 && grants == 1 && feedback_count == 1 &&
			       live_markers.empty());
		}
		else
		{
			drive_until([] { return prunes != 0; });
			assert(applications == 0 && grants == 0 && live_markers.empty());
		}
		critical_outbox_record stale{};
		stale.operation_id = child_id;
		stale.destination = 7;
		stale.event_type = 2;
		stale.payload_version = 3;
		assert(critical_command_encode(child, &stale.payload) ==
		       critical_command_codec_result::ok);
		const auto before = applications;
		assert(artifact_guild_delivery_outbox(stale) ==
		       critical_outbox_delivery_result::publication_pending);
		drive_until([] { return artifact_guild_delivery_pending() == 0; });
		assert(applications == before && !artifact_guild_delivery_holds(70001));
		assert(alerts == 0);
		std::cout
			<< "PASS " << mode
			<< ": wait for snapshots, durable ACK, orphan pruning and stale handoff without regrant\n";
		return 0;
	}
	assert(setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL", "1", 1) == 0);
	assert(flatfile_player_domain_apply(root, parent).outcome ==
	       critical_apply_outcome::retryable_failure);
	assert(unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_JOURNAL") == 0);
	assert(flatfile_player_domain_restore_recover(root, &error) ==
	       flatfile_player_domain_result::ok);
	std::vector<critical_command> pending;
	assert(flatfile_artifact_guild_delivery_list(root, &pending, &error) ==
		       flatfile_player_domain_result::ok &&
	       pending.size() == 1);
	assert(pending.front().payload == child.payload &&
	       pending.front().operation_id.bytes == child_id.bytes);
	auto replay = flatfile_player_domain_apply(root, parent);
	combat_outcome_result result;
	assert(replay.outcome == critical_apply_outcome::already_applied &&
	       combat_outcome_command_decode_result(replay.result_payload.data(),
						    replay.result_size, &result) &&
	       result.artifact_intents);
	bool acknowledged = true;
	assert(flatfile_artifact_guild_delivery_advance(root, child, &acknowledged, &error) ==
		       flatfile_player_domain_result::ok &&
	       !acknowledged);
	artifact.timer = 10300;
	artifact.delivery_ids = { child_id.bytes };
	assert(flatfile_artifact_snapshot_apply(root, { artifact }, &error) ==
	       flatfile_artifact_result::ok);
	assert(flatfile_artifact_guild_delivery_advance(root, child, &acknowledged, &error) ==
		       flatfile_player_domain_result::ok &&
	       !acknowledged);
	guild.prestige = 115;
	guild.construction = 1;
	guild.delivery_ids = { child_id.bytes };
	assert(flatfile_association_save(root, guild, &error) == flatfile_association_result::ok);
	assert(setenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION", "1", 1) == 0);
	assert(flatfile_artifact_guild_delivery_advance(root, child, &acknowledged, &error) ==
		       flatfile_player_domain_result::io_error &&
	       !acknowledged);
	assert(unsetenv("DURIS_FLATFILE_TEST_INTERRUPT_AFTER_AUTHORITY_OPERATION") == 0);
	assert(flatfile_artifact_guild_delivery_advance(root, child, &acknowledged, &error) ==
		       flatfile_player_domain_result::ok &&
	       acknowledged);
	assert(flatfile_artifact_guild_delivery_list(root, &pending, &error) ==
		       flatfile_player_domain_result::ok &&
	       pending.empty());
	artifact.delivery_ids.clear();
	guild.delivery_ids.clear();
	assert(flatfile_artifact_snapshot_apply(root, { artifact }, &error) ==
	       flatfile_artifact_result::ok);
	assert(flatfile_association_save(root, guild, &error) == flatfile_association_result::ok);
	assert(flatfile_artifact_guild_delivery_advance(root, child, &acknowledged, &error) ==
		       flatfile_player_domain_result::ok &&
	       acknowledged);
	assert(flatfile_player_domain_apply(root, parent).outcome ==
	       critical_apply_outcome::already_applied);
	assert(flatfile_artifact_guild_delivery_list(root, &pending, &error) ==
		       flatfile_player_domain_result::ok &&
	       pending.empty());
	auto changed = intent;
	changed.artifacts[0].feed_seconds = 600;
	changed.artifacts[0].timer = 10600;
	critical_command conflicting;
	assert(artifact_guild_command_build_prepared(&conflicting, child_id, changed));
	conflicting.accepted_at_usec = 1;
	assert(flatfile_artifact_guild_delivery_advance(root, conflicting, &acknowledged, &error) ==
	       flatfile_player_domain_result::conflict);

	parent_id.bytes[0] = 2;
	intent.parent_operation_id = parent_id;
	assert(critical_operation_id_derive(parent_id, ARTIFACT_GUILD_DERIVATION_DOMAIN, 42,
					    &child_id));
	assert(artifact_guild_command_build_prepared(&child, child_id, intent));
	child.accepted_at_usec = 1;
	payload.artifact_deliveries = { child };
	payload.participants[0].expected_frag_revision = 1;
	payload.participants[0].expected_epic_revision = 1;
	assert(combat_outcome_command_build(&parent, parent_id, payload));
	parent.accepted_at_usec = 1;
	assert(flatfile_player_domain_apply(root, parent).outcome ==
	       critical_apply_outcome::applied);
	const auto index = root / "domains/artifact_guild_pending";
	const auto retained = root / "domains/artifact_guild_pending.retained";
	fs::rename(index, retained);
	assert(flatfile_artifact_guild_delivery_initialize(root, &error) ==
	       flatfile_player_domain_result::invalid);
	fs::rename(retained, index);
	assert(flatfile_player_domain_restore_recover(root, &error) ==
	       flatfile_player_domain_result::ok);
	std::cout
		<< "PASS compound primary recovery, partial entity checkpoints, ambiguous ACK, pruning, descriptor binding and missing-index refusal\n";
}
