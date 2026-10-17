/****************************************************************************
 *
 *  File: artifact_guild_state.c                                Part of Duris
 *  Usage: game-thread artifact state: timers, souls, and hydration
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#include "guild/artifact_guild_state.h"

#include "guild/assocs.h"
#include "guild/artifact_admission.h"
#include "world/db.h"
#include "world/epic.h"
#include "economy/nexus_stones.h"
#include "core/prototypes.h"
#include "world/difficulty.h"
#include "persistence/persistence_mode.h"
#include "magic/spells.h"
#include "core/utils.h"

#include <algorithm>
#include <cerrno>
#include <ctime>
#include <cmath>
#include <climits>

namespace
{
// Location value shared by the legacy artifact record and its domain mirror.
constexpr int ARTIFACT_ON_PC = 3;

bool checked_seconds(double value, int *seconds)
{
	if (!std::isfinite(value) || value < INT_MIN || value > INT_MAX)
		return false;
	*seconds = static_cast<int>(value);
	return true;
}

bool artifact_feed_seconds(P_char character, int epics, int epic_type, int *output)
{
	int seconds = 0;
	if (!checked_seconds(static_cast<double>(epics) *
				     get_property("artifact.feeding.epic.point.seconds", 3600),
			     &seconds))
		return false;
	double modifier = 1.0;
	switch (epic_type)
	{
	case EPIC_ZONE:
		modifier = get_property("artifact.feeding.epic.typeMod.zone", 1.0);
		break;
	case EPIC_PVP:
		modifier = get_property("artifact.feeding.epic.typeMod.pvp", 2.0);
		break;
	case EPIC_SHIP_PVP:
		modifier = get_property("artifact.feeding.epic.typeMod.pvpShip", 2.0);
		break;
	case EPIC_ELITE_MOB:
		modifier = get_property("artifact.feeding.epic.typeMod.eliteMob", 1.0);
		break;
	case EPIC_QUEST:
		modifier = get_property("artifact.feeding.epic.typeMod.quest", 1.0);
		break;
	case EPIC_RANDOM_ZONE:
		modifier = get_property("artifact.feeding.epic.typeMod.randomZone", 1.0);
		break;
	case EPIC_NEXUS_STONE:
		modifier = get_property("artifact.feeding.epic.typeMod.nexusStone", 1.0);
		break;
	case EPIC_BOON:
		modifier = get_property("artifact.feeding.epic.typeMod.boon", 0.25);
		break;
	case EPIC_STRAHDME:
	case EPIC_RANDOMMOB:
		break;
	default:
		modifier = 0;
		break;
	}
	if (!checked_seconds(seconds * modifier, &seconds))
		return false;
	seconds = difficulty_scale_int(seconds, difficulty_multiplier(DIFFICULTY_ARTIFACT_FEEDING));
	if (affected_by_spell(character, TAG_PLR_RECENT_FRAG))
	{
		const int64_t boosted = static_cast<int64_t>(seconds) * 3 / 2;
		if (boosted < INT_MIN || boosted > INT_MAX)
			return false;
		seconds = static_cast<int>(boosted);
	}
	*output = seconds;
	return true;
}
} // namespace

artifact_guild_capture_status
artifact_guild_state_capture(P_char character, int epics, int epic_type,
			     const critical_operation_id &parent_operation_id,
			     artifact_guild_payload *payload)
{
	if (!character || IS_NPC(character) || !payload || epics <= 0 ||
	    !persistence_mode_requires_mysql() ||
	    critical_operation_id_is_zero(parent_operation_id))
		return artifact_guild_capture_status::unavailable;
	*payload = {};
	const int64_t now = time(nullptr);
	if (now < 0 || now > INT64_MAX - ARTIFACT_BLOOD_DAYS * SECS_PER_REAL_DAY)
		return artifact_guild_capture_status::invalid;
	payload->parent_operation_id = parent_operation_id;
	payload->actor_pid = static_cast<uint32_t>(GET_PID(character));

	Guild *guild = GET_ASSOC(character);
	if (guild && epics >= static_cast<int>(get_property("prestige.epicsMinimum", 4.0)))
	{
		int members = 1;
		for (struct group_list *entry = character->group; entry; entry = entry->next)
			if (entry->ch != character && IS_PC(entry->ch) &&
			    entry->ch->in_room == character->in_room &&
			    GET_ASSOC(entry->ch) == guild)
				++members;
		if (members >=
		    static_cast<int>(get_property("prestige.guildedInGroupMinimum", 3.0)))
		{
			const uint32_t guild_id = guild->get_id();
			int prestige =
				(epic_type == EPIC_PVP || epic_type == EPIC_SHIP_PVP) ?
					static_cast<int>(get_property("prestige.gain.pvp", 20)) :
					static_cast<int>(get_property("prestige.gain.default", 10));
			prestige = std::max(0, check_nexus_bonus(character, prestige,
								 NEXUS_BONUS_PRESTIGE));
			const uint64_t notch = static_cast<uint64_t>(std::max(
				1, get_property("prestige.constructionPoints.notch", 100)));
			payload->guild_id = guild_id;
			payload->prestige_delta = prestige;
			payload->prestige_before = guild->get_prestige();
			payload->construction_before = guild->get_construction();
			if (static_cast<uint64_t>(prestige) > UINT64_MAX - payload->prestige_before)
				return artifact_guild_capture_status::invalid;
			payload->prestige_after = payload->prestige_before + prestige;
			payload->construction_delta = static_cast<int64_t>(
				payload->prestige_after / notch - payload->prestige_before / notch);
			if (static_cast<uint64_t>(payload->construction_delta) >
			    UINT64_MAX - payload->construction_before)
				return artifact_guild_capture_status::invalid;
			payload->construction_after =
				payload->construction_before + payload->construction_delta;
		}
	}

	if (!IS_TRUSTED(character))
	{
		int feed_seconds = 0;
		if (!artifact_feed_seconds(character, epics, epic_type, &feed_seconds))
			return artifact_guild_capture_status::invalid;
		const int64_t maximum = now + ARTIFACT_BLOOD_DAYS * SECS_PER_REAL_DAY;
		for (int slot = 0; slot < MAX_WEAR && feed_seconds &&
				   payload->artifact_count < payload->artifacts.size();
		     ++slot)
		{
			P_obj object = character->equipment[slot];
			if (!object || !IS_ARTIFACT(object))
				continue;
			// Current game-thread state, including every preceding award.
			const int32_t vnum = OBJ_VNUM(object);
			arti_data tracked = {};
			const char *conflict = nullptr;
			if (!artifact_is_canonical(object))
				conflict = "noncanonical_identity";
			else if (!OBJ_WORN(object) || object->loc.wearing != character)
				conflict = "invalid_custody";
			else if (!get_artifact_data_sql(vnum, &tracked) ||
				 tracked.locType != ARTIFACT_ON_PC ||
				 tracked.location != GET_PID(character))
				conflict = "owner_mismatch";
			if (conflict)
			{
				// The existing reporter bounds staff notices and retains searchable
				// detail. An opaque source reference avoids logging player data.
				uint64_t reference = 0;
				for (size_t byte = 0; byte < sizeof(reference); ++byte)
					reference = (reference << 8) |
						    parent_operation_id.bytes[byte];
				persistence_alert(AVATAR, "artifact_reward/capture", "redacted",
						  "none", "none", conflict,
						  "vnum=%d reference=%016llx", vnum,
						  static_cast<unsigned long long>(reference));
				continue;
			}
			// A canonical object referenced by more than one slot still feeds once.
			if (std::any_of(payload->artifacts.begin(),
					payload->artifacts.begin() + payload->artifact_count,
					[vnum](const auto &entry) { return entry.vnum == vnum; }))
				continue;
			int64_t timer = 0, bind_timer = 0;
			int32_t bind_owner_pid = 0;
			if (!artifact_feed_state(vnum, &timer, &bind_owner_pid, &bind_timer))
			{
				logit(LOG_FILE,
				      "artifact_guild: stage=capture reason=missing_state entity=artifact vnum=%d",
				      vnum);
				continue;
			}
			if (timer < 0 || bind_timer < 0 ||
			    (feed_seconds > 0 && timer > INT64_MAX - feed_seconds))
				return artifact_guild_capture_status::invalid;
			const bool soul_check = epic_type == EPIC_PVP || epic_type == EPIC_SHIP_PVP;
			if (soul_check && bind_owner_pid != -1 &&
			    bind_owner_pid != GET_PID(character))
				continue;
			int64_t target = timer + feed_seconds;
			if (target > maximum)
				target = maximum;
			if (target < 0)
				target = 0;
			payload->artifacts[payload->artifact_count++] = {
				.vnum = vnum,
				.flags = ARTIFACT_DELTA_FEED,
				.timer_before = timer,
				.timer = target,
				.bind_owner_before = bind_owner_pid,
				.bind_owner_pid = bind_owner_pid,
				.bind_timer_before = bind_timer,
				.bind_timer = bind_timer,
			};
		}
	}
	if (!payload->guild_id && !payload->artifact_count)
		return artifact_guild_capture_status::no_effect;
	return artifact_guild_payload_valid(*payload) ? artifact_guild_capture_status::ready :
							artifact_guild_capture_status::invalid;
}

// Called only for a new source award, immediately after capture on the game thread.
// History delivery, retry and replay never enter this path.
void artifact_guild_state_apply(P_char character, const artifact_guild_payload &payload)
{
	for (size_t index = 0; index < payload.artifact_count; ++index)
		artifact_feed_set_timer(payload.artifacts[index].vnum,
					payload.artifacts[index].timer);
	if (payload.guild_id)
	{
		Guild *guild = GET_ASSOC(character);
		guild->publish_outcome_totals(payload.prestige_after, payload.construction_after);
		guild->save();
	}
}
