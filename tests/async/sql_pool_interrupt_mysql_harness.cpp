// Shutdown's 30 s bound holds even while the writer is inside a database call:
// sql_pool_interrupt_borrowed() shuts the borrowed connection's socket down, so a query
// blocked on a locked table returns at once as a lost connection. Without it the query
// waits for the lock (here up to the 20 s lock_wait_timeout; on a live server, up to a
// day). This drives the real pool against a disposable server.
#include "sql/sql.h"
#include "sql/sql_pool.h"

#include <chrono>
#include <cstdlib>
#include <future>
#include <iostream>
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
} // namespace

// The pool opens its connections through the game's factory; here they are plain
// connections with no read timeout, so only the interrupt can end the wait early.
MYSQL *sql_open_configured_connection(unsigned long)
{
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
	mysql_close(admin);
	mysql_library_end();
	std::cout << "sql pool interrupt MariaDB leg passed\n";
	return 0;
}
