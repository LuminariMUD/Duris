#include "account/pwipe_launch.h"

#include <cerrno>
#include <cstdio>
#include <fstream>
#include <strings.h>
#include <vector>

static bool loaded;
static bool enabled;
static time_t opens_at;
static std::string opens_utc;
static std::vector<std::string> allowed_accounts;

static std::string trim(const std::string &text)
{
	const size_t first = text.find_first_not_of(" \t\r");
	return first == std::string::npos ?
		       "" :
		       text.substr(first, text.find_last_not_of(" \t\r") - first + 1);
}

static bool parse_utc(const std::string &text, time_t &result)
{
	if (text.size() != 20)
		return false;
	for (size_t i = 0; i < text.size(); ++i)
	{
		const char expected = i == 4 || i == 7	 ? '-' :
				      i == 10		 ? 'T' :
				      i == 13 || i == 16 ? ':' :
				      i == 19		 ? 'Z' :
							   '\0';
		if (expected ? text[i] != expected : text[i] < '0' || text[i] > '9')
			return false;
	}
	struct tm date = {};
	int year, month;
	if (sscanf(text.c_str(), "%4d-%2d-%2dT%2d:%2d:%2dZ", &year, &month, &date.tm_mday,
		   &date.tm_hour, &date.tm_min, &date.tm_sec) != 6 ||
	    year < 1970)
		return false;
	date.tm_year = year - 1900;
	date.tm_mon = month - 1;
	errno = 0;
	result = timegm(&date);
	if (errno == EOVERFLOW)
		return false;
	struct tm roundtrip = {};
	char formatted[32];
	return gmtime_r(&result, &roundtrip) &&
	       strftime(formatted, sizeof(formatted), "%Y-%m-%dT%H:%M:%SZ", &roundtrip) &&
	       text == formatted;
}

bool pwipe_launch_load(const char *path, std::string &error)
{
	loaded = false;
	error.clear();
	std::ifstream input(path);
	if (!input)
	{
		error = "required pwipe launch configuration is missing or unreadable";
		return false;
	}
	unsigned seen = 0;
	std::string line;
	allowed_accounts.clear();
	while (std::getline(input, line))
	{
		line = trim(line);
		if (line.empty() || line[0] == '#')
			continue;
		const size_t separator = line.find('=');
		const std::string key = trim(line.substr(0, separator));
		const std::string value =
			separator == std::string::npos ? "" : trim(line.substr(separator + 1));
		const unsigned field = key == "enabled"		 ? 1 :
				       key == "opens_at_utc"	 ? 2 :
				       key == "allowed_accounts" ? 4 :
								   0;
		if (separator == std::string::npos || !field || (seen & field))
		{
			error = "malformed, unknown or duplicate pwipe launch setting";
			return false;
		}
		seen |= field;
		if (field == 1)
		{
			if (value != "true" && value != "false")
			{
				error = "pwipe launch enabled must be true or false";
				return false;
			}
			enabled = value == "true";
		}
		else if (field == 2)
		{
			if (!parse_utc(value, opens_at))
			{
				error = "pwipe launch requires a valid YYYY-MM-DDTHH:MM:SSZ UTC date";
				return false;
			}
			opens_utc = value;
		}
		else if (!value.empty())
		{
			size_t start = 0;
			do
			{
				const size_t end = value.find(',', start);
				const std::string name = trim(value.substr(start, end - start));
				// Telnet accepts 2..12 letters; native WS also accepts '_' and 14.
				if (name.size() < 2 || name.size() > 14 ||
				    name.find_first_not_of(
					    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ_") !=
					    std::string::npos)
				{
					error = "invalid pwipe launch account name";
					return false;
				}
				for (const auto &other : allowed_accounts)
					if (!strcasecmp(name.c_str(), other.c_str()))
					{
						error = "duplicate pwipe launch account name";
						return false;
					}
				allowed_accounts.push_back(name);
				if (end == std::string::npos)
					break;
				start = end + 1;
			} while (true);
		}
	}
	if (input.bad() || seen != 7 || (enabled && allowed_accounts.empty()))
	{
		error = "incomplete pwipe launch configuration or empty enabled allowlist";
		return false;
	}
	loaded = true;
	return true;
}

bool pwipe_launch_closed_at(time_t now)
{
	return !loaded || (enabled && now < opens_at);
}

bool pwipe_launch_allows_at(const char *account_name, time_t now)
{
	if (!loaded)
		return false;
	if (!pwipe_launch_closed_at(now))
		return true;
	if (account_name && *account_name)
		for (const auto &name : allowed_accounts)
			if (!strcasecmp(account_name, name.c_str()))
				return true;
	return false;
}

const std::string &pwipe_launch_opens_utc()
{
	return opens_utc;
}

std::string pwipe_launch_status(time_t now)
{
	return std::string("Pwipe launch: enabled=") + (enabled ? "true" : "false") +
	       " opens_at_utc=" + opens_utc +
	       " state=" + (pwipe_launch_closed_at(now) ? "closed" : "open") +
	       " allowed_accounts=" + std::to_string(allowed_accounts.size());
}
