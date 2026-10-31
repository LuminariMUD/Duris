#include "combat/frag_cap_runtime.h"
#include "combat/frag_cap_config.h"
#include "combat/frag_cap_repository.h"
#include "core/prototypes.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_worker.h"
#include "redis/redis_report_cache.h"
#ifndef __NO_MYSQL__
#include "sql/sql.h"
#include "sql/sql_pool.h"
#endif

#include <atomic>
#include <cerrno>
#include <chrono>
#include <memory>

namespace
{
struct refresh_result
{
	frag_cap_state state;
	bool flatfile;
	std::string root;
	frag_cap_store_result result = frag_cap_store_result::io_error;
	std::atomic<bool> finished = false;
};

frag_cap_state published;
bool ready = false;
bool dirty = false;
bool failed = false;
std::shared_ptr<refresh_result> pending;
std::chrono::steady_clock::time_point retry_at;

player_save_apply_result read_state(const std::shared_ptr<refresh_result> &operation)
try
{
	if (operation->flatfile)
		operation->result = frag_cap_flatfile_load(operation->root, &operation->state);
#ifndef __NO_MYSQL__
	else if (MYSQL *connection = sql_pool_acquire())
	{
		operation->result = frag_cap_sql_load(connection, &operation->state);
		const unsigned error = mysql_errno(connection);
		if (error == 2006 || error == 2013 || error == 2055)
			connection = sql_pool_replace_connection(connection);
		if (connection)
			sql_pool_release(connection);
	}
#endif
	operation->finished.store(true, std::memory_order_release);
	return { player_save_apply_outcome::applied, 0, 0 };
}
catch (const std::bad_alloc &)
{
	operation->result = frag_cap_store_result::io_error;
	operation->finished.store(true, std::memory_order_release);
	return { player_save_apply_outcome::applied, 0, 0 };
}

std::string countdown(int64_t at, int64_t now)
{
	const int64_t seconds = at > now ? (at - now + 999999) / 1000000 : 0;
	return std::to_string(seconds / 86400) + "d " + std::to_string(seconds / 3600 % 24) + "h " +
	       std::to_string(seconds / 60 % 60) + "m " + std::to_string(seconds % 60) + "s";
}
}

bool frag_cap_runtime_boot(int64_t now)
{
	if (pending)
		return false;
	ready = false;
	frag_cap_state loaded;
	const auto policy = frag_cap_config_policy();
	frag_cap_store_result result;
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
	{
		const char *root = persistence_mode_flatfile_root();
		if (!root)
			return false;
		result = frag_cap_flatfile_adopt(root, frag_cap_config_get()->cap_floor_level, now,
						 &loaded, policy);
		if (result == frag_cap_store_result::ok)
			result = frag_cap_flatfile_tick(root, now, policy);
		if (result == frag_cap_store_result::ok)
			result = frag_cap_flatfile_load(root, &loaded);
	}
	else
	{
#ifdef __NO_MYSQL__
		return false;
#else
		if (mysql_query(DB, "START TRANSACTION"))
			return false;
		result = frag_cap_sql_adopt(DB, frag_cap_config_get()->cap_floor_level,
					    frag_cap_config_get()->legacy_maximum_level, now,
					    &loaded, policy);
		const uint64_t revision = loaded.revision;
		if (result == frag_cap_store_result::ok && !frag_cap_settle(&loaded, now, policy))
			result = frag_cap_store_result::invalid;
		if (result == frag_cap_store_result::ok && loaded.revision != revision)
			result = frag_cap_sql_save(DB, loaded);
		if (result != frag_cap_store_result::ok || mysql_query(DB, "COMMIT"))
		{
			mysql_query(DB, "ROLLBACK");
			return false;
		}
#endif
	}
	if (result != frag_cap_store_result::ok)
		return false;
	published = loaded;
	ready = true;
	dirty = failed = false;
	logit(LOG_STATUS,
	      "Faction frag cap restored: good=%d evil=%d top=%d revision=%llu cutoff=%lld deadline=%lld",
	      frag_cap_for_side(published, frag_cap_side::good),
	      frag_cap_for_side(published, frag_cap_side::evil), published.level,
	      static_cast<unsigned long long>(published.revision),
	      static_cast<long long>(published.credit_cutoff),
	      static_cast<long long>(published.deadline));
	return true;
}

void frag_cap_runtime_refresh()
{
	dirty = true;
}

void frag_cap_runtime_pulse()
{
	if (pending && pending->finished.load(std::memory_order_acquire))
	{
		failed = pending->result != frag_cap_store_result::ok;
		if (!failed && (!ready || pending->state.revision > published.revision))
		{
			const auto &next = pending->state;
			if (ready && next.level > published.level)
			{
				char message[192];
				snprintf(
					message, sizeof(message),
					"&+YFaction round complete! Good cap: %d. Evil cap: %d.&n\r\n",
					frag_cap_for_side(next, frag_cap_side::good),
					frag_cap_for_side(next, frag_cap_side::evil));
				send_to_all(message);
			}
			published = pending->state;
			ready = true;
			redis_invalidate_fraglist();
		}
		pending.reset();
		if (failed)
		{
			logit(LOG_STATUS,
			      "Shared frag cap refresh failed; retaining confirmed state and retrying.");
			dirty = true;
			retry_at = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		}
	}
	if (pending || !dirty || std::chrono::steady_clock::now() < retry_at)
		return;
	try
	{
		auto operation = std::make_shared<refresh_result>();
		operation->flatfile = persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY;
		const char *root = persistence_mode_flatfile_root();
		operation->root = root ? root : "";
		const auto submitted = persistence_writer_submit(persistence_job_kind::frag_cap, 1,
								 FRAG_CAP_MAX_BYTES, [operation]
								 { return read_state(operation); });
		if (submitted == player_save_submit_result::accepted ||
		    submitted == player_save_submit_result::replaced)
		{
			pending = std::move(operation);
			dirty = false;
		}
		else
		{
			failed = true;
			retry_at = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		}
	}
	catch (const std::bad_alloc &)
	{
		// Preserve confirmed state and the request until capacity returns.
		failed = true;
		retry_at = std::chrono::steady_clock::now() + std::chrono::seconds(5);
	}
}

const frag_cap_state *frag_cap_runtime_state()
{
	return ready ? &published : nullptr;
}

std::string frag_cap_runtime_status(uint32_t faction, int64_t now)
{
	if (!ready)
		return "Faction cap unavailable; progression is awaiting durable state.\r\n";
	const int good = frag_cap_for_side(published, frag_cap_side::good);
	const int evil = frag_cap_for_side(published, frag_cap_side::evil);
	std::string text = "&+YFaction level caps: Good " + std::to_string(good) + " / Evil " +
			   std::to_string(evil) + "&n.\r\n";
	if (faction == 1 || faction == 2)
		text += "Your normal cap: " + std::to_string(faction == 1 ? good : evil) + ".\r\n";
	if (published.level == FRAG_CAP_MAXIMUM_LEVEL)
		return text +
		       "All mortal levels are open. Normal XP and epic-stone requirements still apply.\r\n";
	if (failed)
		text += "Status refresh pending; showing the last confirmed state.\r\n";
	char scores[160];
	snprintf(scores, sizeof(scores),
		 "Recorded round frags: Good %llu.%02llu / Evil %llu.%02llu.\r\n",
		 static_cast<unsigned long long>(published.earned[0] / 100),
		 static_cast<unsigned long long>(published.earned[0] % 100),
		 static_cast<unsigned long long>(published.earned[1] / 100),
		 static_cast<unsigned long long>(published.earned[1] % 100));
	text += scores;
	text += published.earned[0] == published.earned[1] ? "The round is tied. " :
		published.earned[0] > published.earned[1]  ? "Good currently leads. " :
							     "Evil currently leads. ";
	text += "Result in " + countdown(published.deadline, now) + ".\r\n";
	text += "Scores are provisional until the deadline. Ties raise each existing cap; circle levels open to both sides.\r\n";
	if (now >= published.deadline)
		text += "The result is due; awaiting durable maintenance and publication.\r\n";
	return text;
}
