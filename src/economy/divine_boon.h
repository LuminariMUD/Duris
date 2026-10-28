#ifndef DIVINE_BOON_H
#define DIVINE_BOON_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <vector>

constexpr size_t DIVINE_BOON_SLOTS = 8;
// Three dedicated Experience and three dedicated Epic slots, plus one each for Cargo and PvP.
constexpr size_t DIVINE_BOON_EXPERIENCE_SLOTS = 3;
constexpr size_t DIVINE_BOON_EPIC_SLOTS = 3;
constexpr size_t DIVINE_BOON_ZONE_SLOTS = DIVINE_BOON_EXPERIENCE_SLOTS + DIVINE_BOON_EPIC_SLOTS;
constexpr int64_t DIVINE_BOON_HOUR = 3600;
constexpr int64_t DIVINE_BOON_REPEAT_WINDOW = 12 * DIVINE_BOON_HOUR;
// Each hour can retire two PvE objectives, each recorded for both sides;
// allow twelve hours of turnover plus the already active objectives.
constexpr size_t DIVINE_BOON_HISTORY_MAX = 64;

enum class divine_boon_category : uint8_t
{
	none,
	experience,
	epic,
	cargo,
	pvp,
};

enum class divine_boon_mode : uint8_t
{
	legacy,
	draining,
	divine,
};

struct divine_boon_slot
{
	uint64_t id = 0;
	divine_boon_category category = divine_boon_category::none;
	int64_t starts_at = 0;
	int64_t expires_at = 0;
	// Persisted Good/Evil zone fields. New PvE boons assign the same zone to both.
	// Legacy snapshots may contain distinct or missing side-specific targets.
	std::array<int32_t, 2> zones = { -1, -1 };
	int32_t source_port = -1;
	int32_t destination_port = -1;
	int32_t cargo_commodity = -1;
	int32_t contraband_commodity = -1;
	bool operator==(const divine_boon_slot &) const = default;
};

// Resolve legacy two-target snapshots to one shared hotspot until they expire.
// No saved-state migration, format change, or duration/ID reset is required.
inline int32_t divine_boon_target_zone(const divine_boon_slot &slot)
{
	return slot.zones[0] >= 0 ? slot.zones[0] : slot.zones[1];
}

struct divine_boon_zone_history
{
	int32_t zone;
	uint8_t side;
	int64_t expired_at;
	bool operator==(const divine_boon_zone_history &) const = default;
};

// Bounded staff history; the separate zone history drives the repeat preference.
struct divine_boon_retired
{
	divine_boon_slot objective;
	int64_t ended_at = 0;
	bool operator==(const divine_boon_retired &) const = default;
};
constexpr size_t DIVINE_BOON_RECENT_MAX = 16;

struct divine_boon_state
{
	uint64_t revision = 1;
	uint64_t next_id = 1;
	int64_t last_opportunity = 0;
	divine_boon_mode mode = divine_boon_mode::legacy;
	bool paused = false;
	std::array<divine_boon_slot, DIVINE_BOON_SLOTS> slots = {};
	std::vector<divine_boon_zone_history> history;
	std::vector<divine_boon_retired> recent;
	bool operator==(const divine_boon_state &) const = default;
};

int64_t divine_boon_duration(divine_boon_category category);
unsigned divine_boon_bonus_percent(divine_boon_category category);
bool divine_boon_active(const divine_boon_slot &slot, int64_t now);
bool divine_boon_state_valid(const divine_boon_state &state);

// Prepare a replacement state, then persist it before publishing it to gameplay.
// False preserves the input. The runtime owns target safety/access validation.
bool divine_boon_set_mode(divine_boon_state *state, divine_boon_mode mode, int64_t now);
bool divine_boon_reconcile(divine_boon_state *state, int64_t now);
// Retire seasonal objectives/preferences without reusing IDs or erasing staff history.
// True includes an already-cleared state.
bool divine_boon_reset_season(divine_boon_state *state, int64_t now);
bool divine_boon_set_paused(divine_boon_state *state, bool paused, int64_t now);
bool divine_boon_replace(divine_boon_state *state, size_t slot, int64_t now);
// No choice (null or zero count) durably consumes an empty opportunity. Each
// choice fills the next empty slot. Choice identity/times must be unset; they
// are assigned here. A replay cannot consume the hour again.
bool divine_boon_rotate(divine_boon_state *state, int64_t now, const divine_boon_slot *choices,
			size_t count = 1);

// Shared, versioned, checksummed snapshot for both persistence backends.
bool divine_boon_state_encode(const divine_boon_state &state, std::vector<uint8_t> *bytes);
bool divine_boon_state_decode(const std::vector<uint8_t> &bytes, divine_boon_state *state);

#endif
