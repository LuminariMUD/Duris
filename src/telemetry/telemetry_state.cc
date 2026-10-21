#include "telemetry/telemetry_outage_private.h"

#include <charconv>
#include <chrono>
#include <cstdio>
#include <cstring>

namespace
{
template <typename Number> bool parse(const char *text, Number &value)
{
	const auto end = text + std::strlen(text);
	const auto parsed = std::from_chars(text, end, value);
	return parsed.ec == std::errc{} && parsed.ptr == end;
}
}

int main(int argc, char **argv)
{
	const bool initialize = argc == 10 && std::strcmp(argv[1], "initialize") == 0;
	const bool exhaust = argc == 10 && std::strcmp(argv[1], "exhaust-day") == 0;
	const bool rollover = argc == 10 && std::strcmp(argv[1], "rollover-season") == 0;
	telemetry_quota_binding binding{};
	if ((!initialize && !exhaust && !rollover) || !parse(argv[3], binding.project_id) ||
	    !parse(argv[4], binding.sender_id) || !parse(argv[5], binding.environment_id) ||
	    !parse(argv[6], binding.season_id) || !parse(argv[7], binding.total_limit) ||
	    !parse(argv[8], binding.normal_limit) || !parse(argv[9], binding.health_limit))
	{
		std::fputs(
			"Usage: telemetry-state initialize|exhaust-day|rollover-season DIRECTORY PROJECT SENDER ENVIRONMENT SEASON TOTAL NORMAL HEALTH\n",
			stderr);
		return 2;
	}
	telemetry_outage_journal journal{};
	auto result = telemetry_outage_read(&journal, argv[2]);
	if (result == telemetry_outage_result::ready)
	{
		const auto utc = std::chrono::duration_cast<std::chrono::microseconds>(
					 std::chrono::system_clock::now().time_since_epoch())
					 .count();
		if (initialize)
			result = telemetry_outage_quota_initialize(&journal, binding, utc);
		else if (rollover)
			result = telemetry_outage_quota_rollover(&journal, binding, utc);
		else
			result = telemetry_outage_quota_exhaust_day(&journal, binding, utc);
	}
	const auto &quota = journal.quota;
	std::printf(
		"{\"result\":%u,\"error_code\":%u,\"generation\":\"%llu\",\"utc_day\":%lld,"
		"\"normal_reserved\":%u,\"health_reserved\":%u,\"normal_limit\":%u,\"health_limit\":%u,\"total_limit\":%u}\n",
		static_cast<unsigned int>(result), journal.error_code,
		static_cast<unsigned long long>(journal.generation),
		static_cast<long long>(quota.day), quota.normal_reserved, quota.health_reserved,
		quota.binding.normal_limit, quota.binding.health_limit, quota.binding.total_limit);
	telemetry_outage_close(&journal);
	return result == telemetry_outage_result::ready ? 0 : 2;
}
