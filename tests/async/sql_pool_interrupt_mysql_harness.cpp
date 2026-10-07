// Shutdown's 30 s bound holds even while the writer is inside a database call:
// sql_pool_interrupt_borrowed() shuts the borrowed connection's socket down, so a query
// blocked on a locked table returns at once as a lost connection. Without it the query
// waits for the lock (here up to the 20 s lock_wait_timeout; on a live server, up to a
// day). A borrower opening a replacement connection cannot be cut short, so the pool's
// shutdown leaves it. A pooled connection the server closed for idling is replaced for
// its next borrower, without losing the runtime lock; once the lock is lost, the pool
// says so. This drives the real pool against a disposable server.
#include "sql/sql.h"
#include "sql/sql_exclusion_guard.h"
#include "sql/sql_pool.h"

#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <future>
#include <iostream>
#include <mutex>
#include <string>
#include <thread>

namespace
{
void require(bool condition, const std::string &message)
{
	if (!condition)
	{
		std::cerr << "FAILED: " << message << '\n';
		std::exit(1);
	}
}

std::string environment(const char *name, const char *fallback)
{
	const char *value = std::getenv(name);
	return value && *value ? value : fallback;
}

MYSQL *open_connection()
{
	MYSQL *connection = mysql_init(nullptr);
	require(connection != nullptr, "could not allocate a MySQL connection");
	const unsigned int port = static_cast<unsigned int>(
		std::strtoul(environment("DB_PORT", "3306").c_str(), nullptr, 10));
	require(mysql_real_connect(connection, environment("DB_HOST", "127.0.0.1").c_str(),
				   environment("DB_USER", "root").c_str(),
				   environment("DB_PASSWD", "").c_str(),
				   environment("DB_NAME", "sql_pool_interrupt_test").c_str(), port,
				   nullptr, 0) != nullptr,
		std::string("could not connect: ") + mysql_error(connection));
	return connection;
}

void execute(MYSQL *connection, const char *sql)
{
	require(mysql_query(connection, sql) == 0,
		std::string(sql) + ": " + mysql_error(connection));
}

// While set, opening a connection hangs, as a connect to an unreachable host does.
std::mutex connect_mutex;
std::condition_variable connect_changed;
bool hold_connects = false;
bool connect_held = false;
// When set, the server closes a new connection after this many idle seconds.
int idle_seconds = 0;
// While set, opening a connection fails, as it does while the server is down.
bool refuse_connects = false;

void select_one(MYSQL *connection)
{
	execute(connection, "SELECT 1");
	mysql_free_result(mysql_store_result(connection));
}
} // namespace

// The pool opens its connections through the game's factory; here they are plain
// connections with no read timeout, so only the interrupt can end the wait early.
MYSQL *sql_open_configured_connection(unsigned long)
{
	{
		std::unique_lock<std::mutex> lock(connect_mutex);
		connect_held = hold_connects;
		connect_changed.notify_all();
		connect_changed.wait(lock, [] { return !hold_connects; });
	}
	if (refuse_connects)
		return nullptr;
	MYSQL *connection = open_connection();
	execute(connection, "SET SESSION lock_wait_timeout=20");
	if (idle_seconds)
		execute(connection,
			("SET SESSION wait_timeout=" + std::to_string(idle_seconds)).c_str());
	return connection;
}
std::string logged;
void logit(const char *, const char *format, ...)
{
	logged += format;
}

int main()
{
	require(!mysql_library_init(0, nullptr, nullptr), "could not initialize the MySQL client");
	MYSQL *admin = open_connection();
	execute(admin, "CREATE TABLE held (id INT PRIMARY KEY)");
	require(sql_pool_init(1) == 0, "the pool did not start");
	MYSQL *borrowed = sql_pool_acquire();
	require(borrowed != nullptr, "no pooled connection");

	execute(admin, "LOCK TABLES held WRITE");
	// The borrower blocks on the locked table, as the writer does on a stalled database.
	auto blocked = std::async(
		std::launch::async,
		[borrowed]()
		{
			const auto started = std::chrono::steady_clock::now();
			const int rc = mysql_query(borrowed, "SELECT COUNT(*) FROM held");
			const unsigned int error = rc ? mysql_errno(borrowed) : 0;
			if (!rc)
				mysql_free_result(mysql_store_result(borrowed));
			return std::make_pair(error, std::chrono::steady_clock::now() - started);
		});
	require(blocked.wait_for(std::chrono::milliseconds(1500)) == std::future_status::timeout,
		"the query was not blocked by the table lock");

	sql_pool_interrupt_borrowed();
	require(blocked.wait_for(std::chrono::seconds(3)) == std::future_status::ready,
		"the interrupt did not end the blocked query");
	const auto [error, waited] = blocked.get();
	require(error == 2013 || error == 2006,
		"the interrupted query must fail as a lost connection, not " +
			std::to_string(error));
	require(waited < std::chrono::seconds(5), "the interrupted query waited too long");
	require(sql_pool_acquire() == nullptr, "a closing pool must not lend connections");

	sql_pool_release(borrowed);
	execute(admin, "UNLOCK TABLES");
	sql_pool_shutdown();

	// A borrower replacing its lost connection when the interrupt comes is stuck in a
	// connect nothing can cut short. Shutdown leaves it instead of waiting.
	require(sql_pool_init(1) == 0, "the pool did not start again");
	MYSQL *repairing = sql_pool_acquire();
	require(repairing != nullptr, "no pooled connection to repair");
	{
		std::lock_guard<std::mutex> lock(connect_mutex);
		hold_connects = true;
	}
	auto repair = std::async(std::launch::async,
				 [repairing]() { return sql_pool_replace_connection(repairing); });
	{
		std::unique_lock<std::mutex> lock(connect_mutex);
		require(connect_changed.wait_for(lock, std::chrono::seconds(5),
						 [] { return connect_held; }),
			"the replacement connect did not start");
	}
	sql_pool_interrupt_borrowed();
	auto closing = std::async(std::launch::async, []() { sql_pool_shutdown(); });
	const bool closed = closing.wait_for(std::chrono::seconds(3)) == std::future_status::ready;
	{
		std::lock_guard<std::mutex> lock(connect_mutex);
		hold_connects = false;
		connect_changed.notify_all();
	}
	require(closed, "shutdown waited for a borrower opening a connection");
	require(repair.get() == nullptr, "a replacement must not join a pool that has shut down");
	sql_pool_release(repairing);
	mysql_close(repairing);

	// MariaDB closes a pooled connection left idle past wait_timeout. The runtime lock,
	// held on another connection, is not lost when the guard's probe fails on it, and the
	// borrower gets a new connection. A reconnect that fails keeps the slot for the next.
	MYSQL *owner = open_connection();
	require(duris_sql_exclusion_guard_acquire(owner), "the runtime lock was not taken");
	idle_seconds = 1;
	require(sql_pool_init(1) == 0, "the pool did not start again");
	std::this_thread::sleep_for(std::chrono::milliseconds(2500));
	MYSQL *renewed = sql_pool_acquire();
	require(renewed != nullptr, "the pool lent nothing after the server closed its connection");
	select_one(renewed);
	sql_pool_release(renewed);
	std::this_thread::sleep_for(std::chrono::milliseconds(2500));
	refuse_connects = true;
	require(sql_pool_acquire() == nullptr, "the pool lent a connection it could not open");
	require(!duris_sql_exclusion_guard_state_ref().lost,
		"a pooled connection the server closed lost the runtime lock");
	refuse_connects = false;
	MYSQL *recovered = sql_pool_acquire();
	require(recovered != nullptr, "a failed reconnect lost its pool slot");
	select_one(recovered);
	sql_pool_release(recovered);

	// Once the lock is lost (the server restarted, or ended the owner's session), the pool
	// lends nothing, says so once, and reports itself inactive, so /health fails.
	execute(admin, ("KILL " + std::to_string(mysql_thread_id(owner))).c_str());
	// KILL returns before the server has ended the session, and the lock goes only with
	// the session: wait until the server no longer shows it held.
	const auto lock_held = [admin]()
	{
		execute(admin,
			"SELECT IS_USED_LOCK(" DURIS_SQL_EXCLUSION_LOCK_EXPRESSION ") IS NOT NULL");
		MYSQL_RES *result = mysql_store_result(admin);
		MYSQL_ROW row = result ? mysql_fetch_row(result) : nullptr;
		const bool held = row && row[0] && std::string(row[0]) == "1";
		mysql_free_result(result);
		return held;
	};
	const auto killed_by = std::chrono::steady_clock::now() + std::chrono::seconds(10);
	while (lock_held())
	{
		require(std::chrono::steady_clock::now() < killed_by,
			"the killed session kept the runtime lock");
		std::this_thread::sleep_for(std::chrono::milliseconds(20));
	}
	require(sql_pool_acquire() == nullptr, "the pool lent a connection without the lock");
	require(sql_pool_acquire() == nullptr, "the pool lent a connection without the lock");
	require(!sql_pool_is_active(), "the pool reported itself active without the lock");
	const size_t lost = logged.find("runtime database lock is lost");
	require(lost != std::string::npos &&
			logged.find("runtime database lock is lost", lost + 1) == std::string::npos,
		"the pool did not log the lost lock once");
	sql_pool_shutdown();
	duris_sql_exclusion_guard_release();
	mysql_close(owner);
	mysql_close(admin);
	mysql_library_end();
	std::cout << "sql pool interrupt MariaDB leg passed\n";
	return 0;
}
