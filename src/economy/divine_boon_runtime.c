#include "economy/divine_boon_runtime.h"
#include "economy/divine_trade_runtime.h"

#include "economy/divine_boon_repository.h"
#include "economy/boon_reward_transaction.h"
#include "persistence/persistence_mode.h"
#include "persistence/maintenance_scheduler.h"
#include "player/player_save_worker.h"

#ifndef __NO_MYSQL__
#include "sql/sql.h"
#include "sql/sql_pool.h"
#endif

#include <atomic>
#include <cerrno>
#include <chrono>
#include <limits>
#include <memory>
#include <new>

extern unsigned long long ne_event_tick;

namespace
{
using store_result = divine_boon_store_result;
struct pending_write
{
	divine_boon_state next;
	uint64_t expected_revision;
	std::string flatfile_root;
	bool flatfile;
	store_result result = store_result::io_error;
	std::atomic<bool> finished = false;
};

divine_boon_state published;
bool ready = false;
std::shared_ptr<pending_write> pending;
bool submitted = false;
std::chrono::steady_clock::time_point retry_at;

player_save_apply_result write_state(const std::shared_ptr<pending_write> &operation)
try
{
	store_result result;
	if (operation->flatfile)
		result = divine_boon_flatfile_save(operation->flatfile_root,
						   operation->expected_revision, operation->next);
	else
	{
#ifdef __NO_MYSQL__
		result = store_result::invalid;
#else
		MYSQL *connection = sql_pool_acquire();
		if (!connection)
			result = store_result::io_error;
		else
		{
			result = divine_boon_sql_save(connection, operation->expected_revision,
						      operation->next);
			const unsigned error = mysql_errno(connection);
			if (result == store_result::io_error &&
			    (error == 2006 || error == 2013 || error == 2055))
			{
				connection = sql_pool_replace_connection(connection);
				if (connection)
					sql_pool_release(connection);
			}
			else
				sql_pool_release(connection);
		}
#endif
	}
	const bool applied = result == store_result::ok || result == store_result::already_applied;
	const unsigned error = applied				? 0 :
			       result == store_result::conflict ? ESTALE :
			       result == store_result::invalid	? EBADMSG :
								  EIO;
	const player_save_apply_result completion = {
		applied ? player_save_apply_outcome::applied :
			  player_save_apply_outcome::terminal_failure,
		applied ? operation->next.revision : 0, error
	};
	operation->result = result;
	operation->finished.store(true, std::memory_order_release);
	return completion;
}
catch (const std::bad_alloc &)
{
	operation->result = store_result::io_error;
	operation->finished.store(true, std::memory_order_release);
	return { player_save_apply_outcome::terminal_failure, 0, ENOMEM };
}

bool submit_pending()
{
	try
	{
		std::vector<uint8_t> bytes;
		if (!divine_boon_state_encode(pending->next, &bytes))
			return false;
		const auto operation = pending;
		const auto result = persistence_writer_submit(persistence_job_kind::divine_boon, 1,
							      bytes.size(), [operation]
							      { return write_state(operation); });
		submitted = result == player_save_submit_result::accepted ||
			    result == player_save_submit_result::replaced;
		return submitted;
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
}

bool stage(const divine_boon_state &next, uint64_t expected_revision)
{
	try
	{
		pending = std::make_shared<pending_write>();
		pending->next = next;
		pending->expected_revision = expected_revision;
		pending->flatfile = persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY;
		const char *root = persistence_mode_flatfile_root();
		pending->flatfile_root = root ? root : "";
		if (submit_pending())
			return true;
		pending.reset();
	}
	catch (const std::bad_alloc &)
	{
		pending.reset();
	}
	return false;
}
}

bool divine_boon_runtime_boot(int64_t now)
{
	if (pending || now < 0 || now > std::numeric_limits<int64_t>::max() - 8 * DIVINE_BOON_HOUR)
		return false;
	ready = false;
	divine_boon_state loaded;
	store_result result;
	if (persistence_mode_get() == PERSISTENCE_MODE_FLATFILE_PRIMARY)
	{
		const char *root = persistence_mode_flatfile_root();
		result = divine_boon_flatfile_load(root ? root : "", &loaded);
	}
	else
	{
#ifdef __NO_MYSQL__
		return false;
#else
		result = divine_boon_sql_load(DB, &loaded);
#endif
	}
	if (result == store_result::not_found)
	{
		loaded.last_opportunity = now - now % DIVINE_BOON_HOUR;
		return divine_trade_runtime_boot(0) && stage(loaded, 0);
	}
	if (result != store_result::ok)
		return false;
	uint64_t cargo_boon = 0;
	for (const auto &slot : loaded.slots)
		if (slot.category == divine_boon_category::cargo)
			cargo_boon = slot.id;
	if (!divine_trade_runtime_boot(cargo_boon))
		return false;
	published = loaded;
	if (divine_boon_reconcile(&loaded, now))
		return stage(loaded, published.revision);
	ready = true;
	return true;
}

void divine_boon_runtime_pulse()
{
	if (!pending)
		return;
	if (!submitted)
	{
		if (std::chrono::steady_clock::now() >= retry_at && !submit_pending())
			retry_at = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		return;
	}
	if (!pending->finished.load(std::memory_order_acquire))
		return;
	const auto result = pending->result;
	if (result == store_result::ok || result == store_result::already_applied)
	{
		published = std::move(pending->next);
		ready = true;
		pending.reset();
	}
	else
	{
		ready = false;
		if (result == store_result::io_error)
		{
			// Retain the exact choice. Retry outside the writer so disk errors do
			// not indefinitely prevent unrelated player saves from progressing.
			pending->finished.store(false, std::memory_order_release);
			submitted = false;
			retry_at = std::chrono::steady_clock::now() + std::chrono::seconds(5);
		}
		else
			pending.reset(); // Invalid/conflicting authority needs reconciliation.
	}
}

const divine_boon_state *divine_boon_runtime_state()
{
	return ready ? &published : nullptr;
}

bool divine_boon_runtime_pending()
{
	return pending != nullptr;
}

bool divine_boon_legacy_admissions_allowed()
{
	return ready && published.mode == divine_boon_mode::legacy &&
	       (!pending || pending->next.mode == divine_boon_mode::legacy);
}

bool divine_boon_runtime_queue(const divine_boon_state &next)
{
	if (!ready || pending || published.revision == std::numeric_limits<uint64_t>::max() ||
	    next.revision != published.revision + 1 || !divine_boon_state_valid(next) ||
	    next.mode < published.mode ||
	    static_cast<unsigned>(next.mode) > static_cast<unsigned>(published.mode) + 1)
		return false;
	// Accepted rewards can submit nested level completions during publication.
	// Keep their gate open, including every scan page/retry, until they finish.
	if (published.mode == divine_boon_mode::legacy && next.mode != published.mode &&
	    (boon_reward_transaction_health_copy().pending ||
	     maintenance_scheduler_health_copy(ne_event_tick)
		     .jobs[static_cast<size_t>(maintenance_job_id::boon_scan)]
		     .work_id))
		return false;
	return stage(next, published.revision);
}
