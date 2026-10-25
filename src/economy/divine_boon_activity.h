#ifndef DIVINE_BOON_ACTIVITY_H
#define DIVINE_BOON_ACTIVITY_H

#include <array>
#include <cstdint>
#include <string>
#include <unordered_map>
#include <vector>

struct char_data;

struct divine_boon_actor
{
	uint32_t pid = 0;
	std::string account;
	uint8_t side = 0; // Good=0, Evil=1; unaffiliated actors are not observed.
	uint16_t level = 0;
	bool eligible = true;
};

struct divine_boon_population
{
	std::array<unsigned, 4> brackets = {}; // 1-20, 21-35, 36-50, 51+
	unsigned active_accounts = 0;
	unsigned pvp_accounts = 0;
	std::vector<uint16_t> levels; // One per eligible online account.
};

// In-memory only: process replacement warms from newly observed gameplay.
// The caller supplies monotonic seconds and current online/AFK/staff eligibility.
class divine_boon_activity_history
{
    public:
	bool observe(const divine_boon_actor &actor, int64_t now);
	std::array<divine_boon_population, 2>
	population(const std::vector<divine_boon_actor> &current, int64_t now) const;

    private:
	struct history
	{
		int64_t last = -1;
		uint32_t last_pid = 0;
		std::array<int64_t, 60> minutes;
		history() { minutes.fill(-1); }
	};
	std::unordered_map<std::string, std::array<history, 2>> accounts;
	int64_t last_prune_minute = -1;
};

struct divine_boon_input_activity
{
	uint64_t runtime_id = 0;
	uint32_t pid = 0;
	std::array<int64_t, 15> before = {};
	bool inspect_inventory = false;
};

// Wrap only the real playing-input dispatcher. End resolves the runtime ID
// afresh, so quit, extraction or body replacement cannot leave a stale pointer.
divine_boon_input_activity divine_boon_activity_begin(char_data *body, int command);
void divine_boon_activity_end(const divine_boon_input_activity &input);
std::array<divine_boon_population, 2> divine_boon_activity_population();

#endif
