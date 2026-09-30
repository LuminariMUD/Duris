// Shutdown's 30 s bound holds even while the writer is inside a database call:
// sql_pool_interrupt_borrowed() shuts the borrowed connection's socket down, so a query
// blocked on a locked table returns at once as a lost connection. Without it the query
// waits for the lock (here up to the 20 s lock_wait_timeout; on a live server, up to a
// day). A borrower opening a replacement connection cannot be cut short, so the pool's
// shutdown leaves it. This drives the real pool against a disposable server.
#include "sql/sql.h"
#include "sql/sql_pool.h"

#include <chrono>
#include <condition_variable>
#include <cstdlib>
#include <future>
#include <iostream>
#include <mutex>
#include <string>

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
	MYSQL *connection = open_connection();
	execute(connection, "SET SESSION lock_wait_timeout=20");
	return connection;
}
void logit(const char *, const char *, ...) {}

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
	mysql_close(admin);
	mysql_library_end();
	std::cout << "sql pool interrupt MariaDB leg passed\n";
	return 0;
}
