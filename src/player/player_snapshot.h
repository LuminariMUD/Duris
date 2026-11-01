/****************************************************************************
 *
 *  File: player_snapshot.h                                     Part of Duris
 *  Usage: player snapshot value types
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef PLAYER_SNAPSHOT_H
#define PLAYER_SNAPSHOT_H

#include "player/player_revision_state.h"
#include "player/pet_restore_state.h"

#include <array>
#include <cstdint>
#include <string>
#include <vector>

constexpr uint32_t PLAYER_SNAPSHOT_SCHEMA_VERSION = 14;
constexpr size_t PLAYER_SNAPSHOT_MAX_BYTES = 4 * 1024 * 1024;
constexpr size_t PLAYER_SNAPSHOT_MAX_ROWS = 8192;
constexpr size_t PLAYER_SNAPSHOT_MAX_OBJECTS = 4096;
constexpr size_t PLAYER_SNAPSHOT_MAX_DEPTH = 32;
// Above every string the world gives an item: some extra descriptions pass 8 KiB.
constexpr size_t PLAYER_SNAPSHOT_MAX_STRING_BYTES = 16384;
constexpr int32_t PLAYER_SNAPSHOT_NO_PARENT = -1;

enum class player_snapshot_capture_result : uint8_t
{
	ok,
	invalid_identity,
	retryable_allocation_failure,
	limit_exceeded,
	object_cycle,
	malformed_source,
};

enum class player_status_field : uint16_t
{
	class_primary,
	class_secondary,
	specialization,
	race,
	racewar,
	level,
	sex,
	weight,
	height,
	size,
	hometown,
	birthplace,
	original_birthplace,
	birth_time,
	played_time,
	base_strength,
	base_dexterity,
	base_agility,
	base_constitution,
	base_power,
	base_intelligence,
	base_wisdom,
	base_charisma,
	base_karma,
	base_luck,
	mana,
	base_mana,
	hit_difference,
	base_hit,
	vitality,
	base_vitality,
	extra_memorization,
	copper,
	silver,
	gold,
	platinum,
	experience,
	epics,
	epic_skill_points,
	skill_points,
	spell_bind_used,
	action_flags,
	action_flags_2,
	action_flags_3,
	vote,
	alignment,
	prestige,
	guild_id,
	guild_status,
	time_left_guild,
	times_left_guild,
	time_unspecialized,
	frags,
	old_frags,
	deaths,
	echo,
	prompt,
	wizard_invisibility,
	wimpy,
	aggressive,
	highest_level,
	screen_length,
	last_ip,
	learned_flight_stops,
	divine_boon_delivery_seq,
	quest_origin_room,
	quest_replacement_due,
	quest_reward_item_count,
};

constexpr size_t PLAYER_STATUS_INTEGER_COUNT =
	static_cast<size_t>(player_status_field::quest_reward_item_count) + 1;

enum class player_status_string_field : uint8_t
{
	name,
	short_description,
	long_description,
	description,
	title,
	poof_in,
	poof_out,
	last_read_news_hash,
};

struct player_snapshot_integer
{
	player_status_field field;
	int64_t signed_value;
	uint64_t unsigned_value;
	bool is_unsigned;
};

struct player_snapshot_string
{
	player_status_string_field field;
	std::string value;
};

struct player_index_value_snapshot
{
	int32_t index;
	int64_t value;
	uint64_t auxiliary;
};

struct player_skill_snapshot
{
	int32_t skill_id;
	uint8_t learned;
	uint8_t taught;
};

struct player_affect_snapshot
{
	int16_t type;
	int32_t duration;
	uint32_t flags;
	int32_t modifier;
	uint8_t location;
	uint16_t level;
	std::array<uint64_t, 5> bitvectors;
	std::string wear_off_character;
	std::string wear_off_room;
};

struct player_item_extra_description_snapshot
{
	std::string keyword;
	std::string description;
	bool spellbook;
	std::vector<int32_t> spell_ids;
};

struct player_item_dynamic_affect_snapshot
{
	int16_t type;
	int16_t data;
	uint64_t extra2;
};

struct player_item_snapshot
{
	int32_t parent_index;
	int16_t equipment_slot;
	uint64_t object_uid;
	int64_t generated_key;
	int32_t vnum;
	int8_t type;
	uint8_t string_mask;
	std::string name;
	std::string short_description;
	std::string description;
	std::string action_description;
	std::array<int32_t, 8> values;
	std::array<int64_t, 6> timers;
	uint32_t wear_flags;
	uint32_t extra_flags;
	uint32_t anti_flags;
	uint32_t anti2_flags;
	uint32_t extra2_flags;
	int32_t weight;
	int8_t material;
	int32_t cost;
	int16_t condition;
	int16_t craftsmanship;
	std::array<uint64_t, 5> bitvectors;
	std::array<std::array<int16_t, 2>, 4> affects;
	std::vector<player_item_dynamic_affect_snapshot> dynamic_affects;
	std::vector<player_item_extra_description_snapshot> extra_descriptions;
};

struct player_pet_snapshot
{
	uint64_t pet_uid = 0;
	int32_t mob_vnum;
	int32_t order;
	int32_t hit;
	int32_t max_hit;
	int32_t mana;
	int32_t max_mana;
	int32_t vitality;
	int32_t max_vitality;
	int32_t charm_duration;
	int32_t room_vnum;
	std::vector<player_item_snapshot> items;
	std::string restore_state;
	pet_hold_reason hold_reason = pet_hold_reason::none;
};

struct player_shape_snapshot
{
	int32_t mob_vnum;
	int32_t times_researched;
	int64_t last_researched;
	int64_t last_shapechanged;
};

struct player_trophy_snapshot
{
	int32_t zone_number;
	int32_t experience;
};

struct player_retained_item_row
{
	uint64_t source_row_id = 0;
	uint64_t root_item_uid = 0;
};

// Owned in-process save intent, not encoded in player files. SQL keeps these
// source rows in place; flat saves retain the matching stored roots after claims.
struct player_item_retention
{
	std::vector<player_retained_item_row> rows;
	size_t bytes = 0;
};

// A capture made before a prepared trade's game-thread completion can still
// leave on logout. Its writer resolves this receipt before saving the purse.
struct player_pending_trade_snapshot
{
	std::array<uint8_t, 16> operation{};
	std::array<uint8_t, 32> command_hash{};
	int64_t payment = 0;
	uint64_t wallet_revision = 0;
	bool has_cargo_effect = false;
	player_affect_snapshot cargo_effect{};
};
constexpr int16_t PLAYER_TRADE_CARGO_AFFECT = 2110;
constexpr int PLAYER_WORLD_QUEST_REWARD_PENDING = 2;
constexpr int PLAYER_WORLD_QUEST_KILL_REWARD_PENDING = 3;
// Last kill credited, but item creation/save admission still needs a bartender retry.
constexpr int PLAYER_WORLD_QUEST_KILL_REWARD_UNSECURED = 4;
// Final kill XP is credited; remaining reward values are retained for history retry.
constexpr int PLAYER_WORLD_QUEST_KILL_HISTORY_PENDING = 5;

struct player_world_quest_reward
{
	int32_t experience = 0;
	int32_t epic = 0;
	int32_t money = 0;
};

// An admitted quest completion travels with its player's status after-image.
// It is applied in the same SQL transaction as that status, not independently.
struct player_pending_world_quest
{
	bool present = false;
	int32_t target = 0;
	int32_t level = 0;
	int32_t giver = 0;
	int32_t reward_vnum = 0;
	int64_t occurred_at = 0;
	std::string player_name;
	std::string reward_description;
	// A completed task may still need its reward after a restart.
	bool awaiting_reward = false;
	bool final_kill_reward = false;
	player_world_quest_reward reward{};
	int32_t escrow_fee = 0;
	// The pre-completion state lets unrelated changes remain durable when the
	// completion transaction fails. Used only by the save repositories.
	bool fallback_only = false;
	std::array<int32_t, 14> before_quest{};
	int32_t before_origin = 0;
	int32_t before_replacement_due = 0;
	std::array<int64_t, 4> before_wallet{};
	uint64_t before_wallet_revision = 0;
	// Detached reward roots are claimed with the same player after-image.
	std::vector<player_item_snapshot> reward_items{};
	size_t reward_encoded_size = 0;
};

struct player_snapshot
{
	uint32_t schema_version;
	int32_t pid;
	player_revision_t revision;
	player_component_mask_t components;
	int32_t save_intent;
	int32_t room_vnum;
	size_t encoded_size_bound;
	std::vector<player_snapshot_integer> status_integers;
	std::vector<player_snapshot_string> status_strings;
	std::array<int32_t, 5> conditions;
	std::array<int32_t, 14> quest_values;
	std::vector<player_index_value_snapshot> languages;
	std::vector<player_index_value_snapshot> introductions;
	std::vector<player_index_value_snapshot> timers;
	std::vector<player_index_value_snapshot> undead_slots;
	std::vector<player_index_value_snapshot> forged_items;
	std::vector<int32_t> granted_commands;
	std::vector<player_skill_snapshot> skills;
	std::vector<player_affect_snapshot> affects;
	std::vector<player_item_snapshot> items;
	player_item_retention retained_items;
	std::vector<player_pet_snapshot> pets;
	std::vector<player_shape_snapshot> shapes;
	std::vector<player_trophy_snapshot> trophies;
	bool recipes_are_external;
	std::string output_preferences;
	// Revision of the in-memory wallet captured with STATUS. Persisting this
	// existing counter prevents an older capture overwriting a committed payment.
	uint64_t wallet_revision = 0;
	player_pending_trade_snapshot pending_trade{};
	player_pending_world_quest pending_world_quest{};
};

#endif
