#include "cmd/last.h"
#include "core/prototypes.h"
#include "core/utility.h"
#include "core/utils.h"

#ifndef __NO_MYSQL__
#include "sql/sql_async.h"

#include <algorithm>
#include <charconv>
#include <cstdint>
#include <ctime>
#include <sstream>
#include <string>

namespace
{
constexpr uint32_t PAGE_SIZE = 20;
constexpr const char *USAGE =
	"Usage: last [<character> | unique] [<number>h | <number>d] [page <number>]\r\n"
	"Examples: last, last 24h, last 7d page 2, last Veridian 7d, last unique 7d\r\n";

bool positive_number(const std::string &text, uint32_t *value)
{
	const auto parsed = std::from_chars(text.data(), text.data() + text.size(), *value);
	return parsed.ec == std::errc{} && parsed.ptr == text.data() + text.size() && *value > 0;
}
} // namespace
#endif

void do_last(P_char ch, char *argument, int /*cmd*/)
{
	if (!ch || !IS_TRUSTED(ch))
		return;
#ifdef __NO_MYSQL__
	(void)argument;
	send_to_char("Login history requires MariaDB support.\r\n", ch);
#else
	std::istringstream input(argument ? argument : "");
	std::string token, name, period;
	bool unique = false, has_page = false;
	uint32_t page = 1;
	int64_t seconds = 0;
	while (input >> token)
	{
		if (!strcasecmp(token.c_str(), "unique"))
		{
			if (unique || !name.empty())
			{
				send_to_char(USAGE, ch);
				return;
			}
			unique = true;
		}
		else if (!strcasecmp(token.c_str(), "page"))
		{
			if (has_page || !(input >> token) || !positive_number(token, &page))
			{
				send_to_char(USAGE, ch);
				return;
			}
			has_page = true;
		}
		else if (token.front() >= '0' && token.front() <= '9')
		{
			uint32_t amount = 0;
			const char unit = LOWER(token.back());
			if (!period.empty() || (unit != 'h' && unit != 'd') ||
			    !positive_number(token.substr(0, token.size() - 1), &amount))
			{
				send_to_char(USAGE, ch);
				return;
			}
			seconds = static_cast<int64_t>(amount) * (unit == 'h' ? 3600 : 86400);
			period = std::to_string(amount) + unit;
		}
		else if (!strcasecmp(token.c_str(), "help") || !name.empty() || unique)
		{
			send_to_char(USAGE, ch);
			return;
		}
		else
			name = token;
	}

	int pid = 0;
	if (!name.empty())
	{
		pid = get_player_pid_from_name(name.data());
		if (pid < 1)
		{
			send_to_char("No such character. Use its current name.\r\n", ch);
			return;
		}
	}

	const int64_t now = time(nullptr);
	std::string events = "SELECT pid,account_name,occurred_at,operation_id";
	if (unique)
		events += ",ROW_NUMBER() OVER (PARTITION BY account_name ORDER BY occurred_at DESC,"
			  "operation_id DESC) AS account_row";
	events += sql_format(" FROM session_audit_outcome WHERE event_type=1 "
			     "AND occurred_at<=FROM_UNIXTIME(%lld)",
			     static_cast<long long>(now));
	if (seconds)
		events += sql_format(" AND occurred_at>=FROM_UNIXTIME(%lld)",
				     static_cast<long long>(std::max<int64_t>(0, now - seconds)));
	if (pid)
		events += sql_format(" AND pid=%d", pid);
	if (unique)
		events += " AND NULLIF(account_name,'') IS NOT NULL";

	std::string query =
		"SELECT UNIX_TIMESTAMP(s.occurred_at),p.name,s.account_name,s.pid FROM (" + events +
		") s LEFT JOIN player_data p ON p.pid=s.pid";
	if (unique)
		query += " WHERE s.account_row=1";
	query += sql_format(" ORDER BY s.occurred_at DESC,s.operation_id DESC LIMIT %u OFFSET %llu",
			    PAGE_SIZE + 1, static_cast<unsigned long long>(page - 1) * PAGE_SIZE);

	std::string command = "last";
	if (unique)
		command += " unique";
	else if (!name.empty())
		command += " " + name;
	if (!period.empty())
		command += " " + period;
	if (!sql_read_for(
		    ch, std::move(query),
		    [command, period, unique, page](P_char live, const sql_rows &rows)
		    {
			    // The requester may have lost staff access while the read was queued.
			    if (!IS_TRUSTED(live))
				    return;
			    send_to_char_f(live,
					   "Login history (%s%s), page %u. Times are UTC.\r\n",
					   period.empty() ? "all retained history" : "last ",
					   period.c_str(), page);
			    if (unique)
				    send_to_char(
					    "Latest login per recorded account; unknown accounts "
					    "are omitted.\r\n",
					    live);
			    if (rows.empty())
				    send_to_char("No logins on this page.\r\n", live);
			    else
				    send_to_char(
					    "Time (UTC)          | Character            | Account | PID\r\n",
					    live);
			    for (size_t i = 0; i < std::min<size_t>(rows.size(), PAGE_SIZE); ++i)
			    {
				    const sql_row &row = rows[i];
				    const time_t occurred = strtoll(row[0], nullptr, 10);
				    struct tm utc;
				    char timestamp[32];
				    gmtime_r(&occurred, &utc);
				    strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S",
					     &utc);
				    send_to_char_f(live, "%s | %-20s | %s | %s\r\n", timestamp,
						   row[1] ? row[1] : "(deleted)",
						   row[2] && *row[2] ? row[2] : "(unknown)",
						   row[3]);
			    }
			    if (page > 1)
				    send_to_char_f(live, "Previous: %s page %u\r\n",
						   command.c_str(), page - 1);
			    if (rows.size() > PAGE_SIZE)
				    send_to_char_f(live, "Next: %s page %llu\r\n", command.c_str(),
						   static_cast<unsigned long long>(page) + 1);
			    else
				    send_to_char("End of login history.\r\n", live);
		    }))
		send_to_char("Login history is unavailable right now.\r\n", ch);
#endif
}
