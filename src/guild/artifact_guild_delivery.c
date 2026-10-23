#include "guild/artifact_guild_delivery.h"

#include "guild/artifact_guild_repository.h"
#include "guild/artifact_guild_state.h"
#include "guild/artifact_guild_transaction.h"
#include "flatfile/flatfile_artifact_guild_delivery.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_worker.h"
#include "sql/sql_async.h"
#include "core/prototypes.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <map>
#include <memory>
#include <mutex>
#include <thread>

namespace
{
struct delivery_check : sql_write_receipt
{
	bool acknowledged = false;
	bool saved = false;
	std::vector<critical_command> commands;
};
struct delivery_context
{
	critical_command command;
	artifact_guild_payload payload{};
	std::atomic<bool> committed{ false };
	std::atomic<bool> saved{ false };
	bool verified = false;
	bool applied = false;
	uint64_t next_check = 0;
	unsigned int last_error = 0;
	std::shared_ptr<delivery_check> check;
};
std::mutex pending_mutex;
std::map<std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES>, std::shared_ptr<delivery_context>> pending;
bool initialized = false, ready = false;
uint64_t native_owner = 0, next_boot_check = 0;
std::array<uint8_t, CRITICAL_COMMAND_ID_BYTES> check_cursor{};
unsigned int boot_error = 0;
std::shared_ptr<delivery_check> bootstrap;
std::shared_ptr<delivery_check> cleanup;
int32_t artifact_cursor = 0;
uint32_t guild_cursor = 0;
critical_operation_id artifact_marker_after{}, guild_marker_after{};
bool next_guild_cleanup = false;
uint64_t next_cleanup = 0;
unsigned int cleanup_error = 0;

uint64_t now_msec()
{
	return std::chrono::duration_cast<std::chrono::milliseconds>(
		       std::chrono::steady_clock::now().time_since_epoch())
		.count();
}
void report(unsigned int error, unsigned int *previous)
{
	if (*previous == error)
		return;
	*previous = error;
	persistence_alert(AVATAR, "artifact_delivery", "redacted", "none", "none", "check_failed",
			  "error=%u", error);
}
std::shared_ptr<delivery_context> capture(const critical_command &command)
{
	auto context = std::make_shared<delivery_context>();
	if (!artifact_guild_command_decode_payload(command, &context->payload) ||
	    !artifact_guild_command_valid_delivery(command, context->payload.parent_operation_id))
		return {};
	context->command = command;
	return context;
}
std::shared_ptr<delivery_context> retain_committed(const critical_command &command)
{
	std::lock_guard<std::mutex> lock(pending_mutex);
	auto found = pending.find(command.operation_id.bytes);
	if (found != pending.end())
	{
		if (!critical_command_equal(found->second->command, command))
		{
			errno = EEXIST;
			return {};
		}
		found->second->committed.store(true, std::memory_order_release);
		return found->second;
	}
	if (pending.size() >= ARTIFACT_GUILD_PENDING_MAX)
	{
		errno = ENOSPC;
		return {};
	}
	auto context = capture(command);
	if (!context)
	{
		errno = EINVAL;
		return {};
	}
	context->committed.store(true, std::memory_order_release);
	pending.emplace(command.operation_id.bytes, context);
	return context;
}

// These native control jobs have their own writer owner kind. Reusing the
// artifact snapshot owner's sequence could replace an unrelated pending save.
bool queue_native(const std::shared_ptr<delivery_check> &check, size_t bytes,
		  std::function<unsigned int()> work)
{
	const auto submitted = persistence_writer_submit(
		persistence_job_kind::artifact_delivery, ++native_owner, bytes,
		[check, work = std::move(work)]()
		{
			unsigned int error = 0;
			try
			{
				error = work();
			}
			catch (const std::bad_alloc &)
			{
				error = ENOMEM;
			}
			catch (...)
			{
				error = EIO;
			}
			check->ok = error == 0;
			check->error_code = error;
			check->finished.store(true, std::memory_order_release);
			return player_save_apply_result{
				error ? player_save_apply_outcome::terminal_failure :
					player_save_apply_outcome::applied,
				0, error
			};
		});
	return submitted == player_save_submit_result::accepted;
}
bool queue_bootstrap(const std::shared_ptr<delivery_check> &check)
{
#ifndef __NO_MYSQL__
	if (persistence_mode_requires_mysql())
		return sql_queue_work(
			[check](MYSQL *connection)
			{
				return artifact_guild_repository_pending_deliveries(
					       connection, &check->commands) ?
					       0U :
					       (mysql_errno(connection) ?
							mysql_errno(connection) :
							static_cast<unsigned int>(errno ? errno :
											  EIO));
			},
			check);
#endif
	const char *configured = persistence_mode_flatfile_root();
	if (!configured)
		return false;
	const std::string root = configured;
	return queue_native(
		check, sizeof(delivery_check) + root.size(),
		[check, root]()
		{
			std::string error;
			const auto initialized =
				flatfile_artifact_guild_delivery_initialize(root, &error);
			if (initialized != flatfile_player_domain_result::ok)
				return static_cast<unsigned int>(
					initialized == flatfile_player_domain_result::io_error ?
						EIO :
						EILSEQ);
			const auto loaded = flatfile_artifact_guild_delivery_list(
				root, &check->commands, &error);
			return loaded == flatfile_player_domain_result::ok ?
				       0U :
				       static_cast<unsigned int>(
					       loaded == flatfile_player_domain_result::io_error ?
						       EIO :
						       EILSEQ);
		});
}
bool queue_check(const std::shared_ptr<delivery_context> &context,
		 const std::shared_ptr<delivery_check> &check)
{
#ifndef __NO_MYSQL__
	if (persistence_mode_requires_mysql())
		return sql_queue_work(
			[context, check](MYSQL *connection)
			{
				bool ok = artifact_guild_repository_delivery_acknowledged(
					connection, context->command, &check->acknowledged);
				if (ok && !check->acknowledged)
					ok = artifact_guild_repository_delivery_saved(
						connection, context->command, &check->saved);
				return ok ? 0U :
					    (mysql_errno(connection) ?
						     mysql_errno(connection) :
						     static_cast<unsigned int>(errno ? errno :
										       EIO));
			},
			check);
#endif
	const char *configured = persistence_mode_flatfile_root();
	if (!configured)
		return false;
	const std::string root = configured;
	return queue_native(
		check, sizeof(delivery_check) + context->command.payload.size() + root.size(),
		[context, check, root]()
		{
			std::string error;
			const auto result = flatfile_artifact_guild_delivery_advance(
				root, context->command, &check->acknowledged, &error);
			return result == flatfile_player_domain_result::ok ?
				       0U :
				       static_cast<unsigned int>(
					       result == flatfile_player_domain_result::io_error ?
						       EIO :
						       EILSEQ);
		});
}
void cleanup_markers(uint64_t now)
{
	if (cleanup && cleanup->finished.load(std::memory_order_acquire))
	{
		// A corrupt marker must not starve independently proved ACKs in this slice.
		for (const auto &command : cleanup->commands)
		{
			artifact_guild_payload payload{};
			if (artifact_guild_command_decode_payload(command, &payload))
				artifact_guild_state_forget_delivery(command.operation_id, payload);
		}
		if (!cleanup->ok)
			report(cleanup->error_code ? cleanup->error_code : EIO, &cleanup_error);
		else
			cleanup_error = 0;
		cleanup.reset();
	}
	if (cleanup || now < next_cleanup)
		return;
	next_cleanup = now + 1000;
	artifact_guild_delivery_ids ids;
	if (!next_guild_cleanup)
		artifact_delivery_markers(&artifact_cursor, &artifact_marker_after, &ids);
	else
		artifact_guild_state_guild_markers(&guild_cursor, &guild_marker_after, &ids);
	next_guild_cleanup = !next_guild_cleanup;
	std::sort(ids.begin(), ids.end());
	ids.erase(std::unique(ids.begin(), ids.end()), ids.end());
	{
		std::lock_guard<std::mutex> lock(pending_mutex);
		std::erase_if(ids, [](const auto &id) { return pending.count(id) != 0; });
	}
	if (ids.empty())
		return;
	auto check = std::make_shared<delivery_check>();
	bool queued = false;
#ifndef __NO_MYSQL__
	if (persistence_mode_requires_mysql())
		queued = sql_queue_work(
			[ids, check](MYSQL *connection)
			{
				unsigned int error = 0;
				for (const auto &id : ids)
				{
					critical_command command;
					bool acknowledged = false;
					if (!artifact_guild_repository_load_delivery(
						    connection, critical_operation_id{ id },
						    &command, &acknowledged))
						error = mysql_errno(connection) ?
								mysql_errno(connection) :
								EILSEQ;
					else if (acknowledged)
						check->commands.push_back(std::move(command));
				}
				return error;
			},
			check);
	else
#endif
	{
		const char *configured = persistence_mode_flatfile_root();
		if (configured)
		{
			const std::string root = configured;
			queued = queue_native(
				check,
				sizeof(delivery_check) + ids.size() * CRITICAL_COMMAND_ID_BYTES,
				[ids, root, check]()
				{
					unsigned int error_code = 0;
					std::string error;
					flatfile_authority_lock lock;
					if (!lock.acquire(root, &error))
						return static_cast<unsigned int>(EIO);
					for (const auto &id : ids)
					{
						critical_command command;
						bool acknowledged = false;
						const auto loaded = flatfile_artifact_delivery_load(
							root, lock, critical_operation_id{ id },
							&command, &acknowledged, &error);
						if (loaded != flatfile_player_domain_result::ok)
							error_code =
								loaded == flatfile_player_domain_result::
											io_error ?
									EIO :
									EILSEQ;
						else if (acknowledged)
							check->commands.push_back(
								std::move(command));
					}
					return error_code;
				});
		}
	}
	if (queued)
		cleanup = std::move(check);
	else
		report(errno ? errno : EIO, &cleanup_error);
}
} // namespace

bool artifact_guild_delivery_reserve(const std::vector<critical_command> &commands)
try
{
	if (commands.empty())
		return true;
	if (!initialized || !ready || commands.size() > ARTIFACT_GUILD_PENDING_MAX)
		return false;
	std::vector<std::shared_ptr<delivery_context>> captured;
	captured.reserve(commands.size());
	for (const auto &command : commands)
	{
		auto context = capture(command);
		if (!context)
			return false;
		captured.push_back(std::move(context));
	}
	std::lock_guard<std::mutex> lock(pending_mutex);
	if (commands.size() > ARTIFACT_GUILD_PENDING_MAX - pending.size())
		return false;
	for (size_t i = 0; i < captured.size(); ++i)
	{
		const auto &id = captured[i]->command.operation_id.bytes;
		if (pending.count(id) ||
		    std::any_of(captured.begin(), captured.begin() + i, [&](const auto &prior)
				{ return prior->command.operation_id.bytes == id; }))
			return false;
	}
	size_t inserted = 0;
	try
	{
		for (const auto &context : captured)
		{
			pending.emplace(context->command.operation_id.bytes, context);
			++inserted;
		}
	}
	catch (const std::bad_alloc &)
	{
		for (size_t i = 0; i < inserted; ++i)
			pending.erase(captured[i]->command.operation_id.bytes);
		return false;
	}
	return true;
}
catch (const std::bad_alloc &)
{
	return false;
}

void artifact_guild_delivery_complete(const std::vector<critical_command> &commands, bool committed)
{
	std::lock_guard<std::mutex> lock(pending_mutex);
	for (const auto &command : commands)
	{
		auto found = pending.find(command.operation_id.bytes);
		if (found == pending.end())
			continue; // An outbox delivery may already have finished and pruned it.
		if (committed)
			found->second->committed.store(true, std::memory_order_release);
		else if (!found->second->committed.load(std::memory_order_acquire))
			pending.erase(found);
	}
}

void artifact_guild_delivery_pulse()
try
{
	if (!initialized)
		return;
	const uint64_t now = now_msec();
	if (!ready)
	{
		if (bootstrap && bootstrap->finished.load(std::memory_order_acquire))
		{
			bool loaded = bootstrap->ok;
			if (loaded)
				for (const auto &command : bootstrap->commands)
					if (!retain_committed(command))
						loaded = false;
			if (loaded)
			{
				ready = true;
				boot_error = 0;
			}
			else
				report(bootstrap->error_code ? bootstrap->error_code : ENOSPC,
				       &boot_error);
			bootstrap.reset();
			next_boot_check = now + 1000;
		}
		if (!ready && !bootstrap && now >= next_boot_check)
		{
			bootstrap = std::make_shared<delivery_check>();
			if (!queue_bootstrap(bootstrap))
			{
				bootstrap.reset();
				next_boot_check = now + 1000;
				report(errno ? errno : EIO, &boot_error);
			}
		}
		if (!ready)
			return;
	}
	cleanup_markers(now);
	std::vector<std::shared_ptr<delivery_context>> contexts;
	{
		std::lock_guard<std::mutex> lock(pending_mutex);
		contexts.reserve(pending.size());
		for (const auto &[id, context] : pending)
			contexts.push_back(context);
	}
	const auto start = std::upper_bound(contexts.begin(), contexts.end(), check_cursor,
					    [](const auto &id, const auto &context)
					    { return id < context->command.operation_id.bytes; });
	std::rotate(contexts.begin(), start, contexts.end());
	size_t checks = 0;
	for (const auto &context : contexts)
	{
		if (!context->committed.load(std::memory_order_acquire))
			continue;
		try
		{
			if (context->check &&
			    context->check->finished.load(std::memory_order_acquire))
			{
				const auto &check = context->check;
				if (check->ok && check->acknowledged)
				{
					artifact_guild_state_forget_delivery(
						context->command.operation_id, context->payload);
					std::lock_guard<std::mutex> lock(pending_mutex);
					pending.erase(context->command.operation_id.bytes);
					continue;
				}
				if (check->ok)
				{
					context->verified = true;
					context->last_error = 0;
					if (check->saved)
						context->saved.store(true,
								     std::memory_order_release);
				}
				else
					report(check->error_code ? check->error_code : EIO,
					       &context->last_error);
				context->check.reset();
			}
			if (context->verified && !context->applied)
			{
				artifact_guild_payload published{};
				context->applied = artifact_guild_state_apply_delivery(
					context->command.operation_id, context->payload,
					&published);
				artifact_guild_transaction_publish_delivery(published);
			}
			if (!context->check && now >= context->next_check && checks < 8)
			{
				++checks;
				check_cursor = context->command.operation_id.bytes;
				context->next_check = now + 1000;
				context->check = std::make_shared<delivery_check>();
				if (!queue_check(context, context->check))
				{
					context->check.reset();
					report(errno ? errno : EIO, &context->last_error);
				}
			}
		}
		catch (const std::bad_alloc &)
		{
			report(ENOMEM, &context->last_error);
		}
	}
}
catch (const std::bad_alloc &)
{
	report(ENOMEM, &boot_error);
}

bool artifact_guild_delivery_boot()
{
	if (!initialized)
		initialized = true;
	artifact_guild_delivery_pulse();
	const uint64_t deadline = now_msec() + 5000;
	while (!ready && now_msec() < deadline)
	{
		artifact_guild_delivery_pulse();
		std::this_thread::sleep_for(std::chrono::milliseconds(1));
	}
	return ready;
}

size_t artifact_guild_delivery_pending()
{
	std::lock_guard<std::mutex> lock(pending_mutex);
	return pending.size() + (initialized && !ready ? 1 : 0);
}
bool artifact_guild_delivery_holds(uint64_t item_uid)
{
	if (initialized && !ready)
		return true;
	std::lock_guard<std::mutex> lock(pending_mutex);
	for (const auto &[id, context] : pending)
		for (size_t i = 0; i < context->payload.artifact_count; ++i)
			if (context->payload.artifacts[i].canonical_item_uid == item_uid)
				return true;
	return false;
}
critical_outbox_delivery_result artifact_guild_delivery_outbox(const critical_outbox_record &record)
{
	critical_command command;
	if (record.destination != 7 || record.event_type != 2 || record.payload_version != 3 ||
	    critical_command_decode(record.payload.data(), record.payload.size(), &command) !=
		    critical_command_codec_result::ok ||
	    command.operation_id.bytes != record.operation_id.bytes)
		return critical_outbox_delivery_result::terminal_failure;
	artifact_guild_payload payload{};
	if (!artifact_guild_command_decode_payload(command, &payload) ||
	    !artifact_guild_command_valid_delivery(command, payload.parent_operation_id))
		return critical_outbox_delivery_result::terminal_failure;
	const auto context = retain_committed(command);
	if (!context)
		return errno == ENOSPC ? critical_outbox_delivery_result::publication_pending :
					 critical_outbox_delivery_result::terminal_failure;
	return context->saved.load(std::memory_order_acquire) ?
		       critical_outbox_delivery_result::delivered :
		       critical_outbox_delivery_result::publication_pending;
}
