#include "economy/divine_boon_activity.h"

#include "core/prototypes.h"
#include "core/utils.h"

#include <algorithm>
#include <chrono>
#include <map>
#include <new>
#include <set>
#include <utility>

extern P_desc descriptor_list;

namespace
{
constexpr size_t maximum_accounts = 4096;

bool canonical_account(const std::string &account, std::string *key)
{
	if (account.empty() || account.size() > 64)
		return false;
	*key = account;
	for (char &letter : *key)
	{
		if (letter >= 'A' && letter <= 'Z')
			letter += 'a' - 'A';
		if (letter <= ' ' || static_cast<unsigned char>(letter) >= 127)
			return false;
	}
	return true;
}

bool actor_valid(const divine_boon_actor &actor)
{
	return actor.eligible && actor.pid && actor.side < 2 && actor.level;
}

int64_t monotonic_seconds()
{
	return std::chrono::duration_cast<std::chrono::seconds>(
		       std::chrono::steady_clock::now().time_since_epoch())
		.count();
}

bool live_actor(P_char body, divine_boon_actor *identity)
{
	if (!body || !identity)
		return false;
	P_char player = GET_PLYR(body);
	P_desc descriptor = body->desc ? body->desc : player->desc;
	if (!IS_PC(player) || !player->only.pc || !descriptor || descriptor->character != body ||
	    descriptor->connected != CON_PLAYING || descriptor->str || descriptor->showstr_count ||
	    !descriptor->account || !descriptor->account->acct_name || GET_LEVEL(player) < 1 ||
	    GET_LEVEL(player) > MAXLVLMORTAL || IS_SET(player->specials.act, PLR_AFK) ||
	    IS_SET(body->specials.act, PLR_AFK) || GET_PID(player) <= 0)
		return false;
	for (const acct_chars *character = descriptor->account->acct_character_list; character;
	     character = character->next)
		if (character->racewar == ACCT_IMMORTAL || character->level > MAXLVLMORTAL)
			return false;
	if (!IS_RACEWAR_GOOD(player) && !IS_RACEWAR_EVIL(player))
		return false;
	*identity = { static_cast<uint32_t>(GET_PID(player)), descriptor->account->acct_name,
		      static_cast<uint8_t>(IS_RACEWAR_GOOD(player) ? 0 : 1),
		      static_cast<uint16_t>(GET_LEVEL(player)), true };
	return true;
}

std::array<int64_t, 12> fingerprint(P_char body)
{
	P_char player = GET_PLYR(body);
	P_char opponent = GET_OPPONENT(body);
	return { body->in_room,
		 GET_EXP(player),
		 GET_HIT(body),
		 body->points.cash[0],
		 body->points.cash[1],
		 body->points.cash[2],
		 body->points.cash[3],
		 IS_CARRYING_N(body),
		 opponent ? static_cast<int64_t>(opponent->runtime_id) : 0,
		 opponent ? GET_HIT(opponent) : 0,
		 GET_MANA(body),
		 IS_AFFECTED2(body, AFF2_CASTING) ? 1 : 0 };
}

divine_boon_activity_history observed;
}

bool divine_boon_activity_history::observe(const divine_boon_actor &actor, int64_t now)
{
	std::string account;
	if (!actor_valid(actor) || now < 0 || !canonical_account(actor.account, &account))
		return false;
	const int64_t minute = now / 60;
	if (minute != last_prune_minute)
	{
		std::erase_if(accounts,
			      [now](const auto &entry)
			      {
				      return std::all_of(entry.second.begin(), entry.second.end(),
							 [now](const auto &side) {
								 return side.last < 0 ||
									(now >= side.last &&
									 now - side.last >= 3600);
							 });
			      });
		last_prune_minute = minute;
	}
	if (!accounts.contains(account) && accounts.size() >= maximum_accounts)
		return false;
	auto &entry = accounts[account][actor.side];
	if (now < entry.last)
		return false;
	auto &sample = entry.minutes[static_cast<size_t>(minute % 60)];
	if (sample < 0 || sample / 60 != minute)
		sample = now;
	entry.last = now;
	entry.last_pid = actor.pid;
	return true;
}

std::array<divine_boon_population, 2>
divine_boon_activity_history::population(const std::vector<divine_boon_actor> &current,
					 int64_t now) const
{
	std::array<divine_boon_population, 2> result = {};
	if (now < 0)
		return result;
	struct representative
	{
		uint16_t level = 0;
		bool last_actor = false;
	};
	std::map<std::pair<std::string, uint8_t>, representative> present;
	for (const auto &actor : current)
	{
		std::string account;
		if (!actor_valid(actor) || !canonical_account(actor.account, &account))
			continue;
		const auto found = accounts.find(account);
		if (found == accounts.end())
			continue;
		const auto &entry = found->second[actor.side];
		if (entry.last < 0 || now < entry.last || now - entry.last >= 900)
			continue;
		auto &choice = present[{ account, actor.side }];
		const bool latest = actor.pid == entry.last_pid;
		if (latest || (!choice.last_actor && (!choice.level || actor.level < choice.level)))
			choice = { actor.level, latest };
	}
	std::array<std::set<std::string>, 2> pvp;
	for (const auto &[key, player] : present)
	{
		const auto &entry = accounts.at(key.first)[key.second];
		auto &side = result[key.second];
		++side.active_accounts;
		const size_t bracket = player.level <= 20 ? 0 :
				       player.level <= 35 ? 1 :
				       player.level <= 50 ? 2 :
							    3;
		++side.brackets[bracket];
		unsigned minutes = 0;
		int64_t first = entry.last;
		for (int64_t sample : entry.minutes)
			if (sample >= 0 && sample <= now && now - sample < 3600)
			{
				++minutes;
				first = std::min(first, sample);
			}
		if (minutes >= 5 && entry.last - first >= 300)
			pvp[key.second].insert(key.first);
	}
	for (size_t side = 0; side < result.size(); ++side)
		for (const auto &account : pvp[side])
			if (!pvp[1 - side].contains(account))
				++result[side].pvp_accounts;
	// Assign a cross-side account once, keeping any genuinely distinct opposing
	// population usable. A single account alone can never supply both sides.
	for (const auto &account : pvp[0])
		if (pvp[1].contains(account))
		{
			const auto &entry = accounts.at(account);
			const size_t side =
				result[0].pvp_accounts == result[1].pvp_accounts ?
					(entry[1].last > entry[0].last ? 1 : 0) :
					(result[0].pvp_accounts < result[1].pvp_accounts ? 0 : 1);
			++result[side].pvp_accounts;
		}
	return result;
}

divine_boon_input_activity divine_boon_activity_begin(P_char body)
try
{
	divine_boon_actor actor;
	if (!body || !body->runtime_id || !live_actor(body, &actor))
		return {};
	return { body->runtime_id, actor.pid, fingerprint(body) };
}
catch (const std::bad_alloc &)
{
	return {};
}

void divine_boon_activity_end(const divine_boon_input_activity &input)
try
{
	if (!input.runtime_id)
		return;
	P_char body = find_character_by_runtime_id(input.runtime_id);
	divine_boon_actor actor;
	if (live_actor(body, &actor) && actor.pid == input.pid && fingerprint(body) != input.before)
		observed.observe(actor, monotonic_seconds());
}
catch (const std::bad_alloc &)
{
	// Missing evidence cannot qualify an account or add gameplay I/O.
	return;
}

std::array<divine_boon_population, 2> divine_boon_activity_population()
try
{
	std::vector<divine_boon_actor> current;
	for (P_desc descriptor = descriptor_list; descriptor; descriptor = descriptor->next)
	{
		divine_boon_actor actor;
		if (live_actor(descriptor->character, &actor))
			current.push_back(std::move(actor));
	}
	return observed.population(current, monotonic_seconds());
}
catch (const std::bad_alloc &)
{
	return {};
}
