/* Test-link wrapper for existing game-thread timing seams. Samples stay in fixed
 * memory during gameplay; only orderly process exit writes the fixture artifact. */
#include "persistence/latency_trace.h"

#include <array>
#include <atomic>
#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>

namespace
{

struct samples
{
	const char *name;
	std::array<std::uint64_t, 16384> values{};
	std::size_t count = 0;
	std::size_t overflow = 0;
};

struct measurement
{
	std::array<samples, 3> sections{ { { "total_tick" }, { "ne_events" }, { "commands" } } };
	std::array<std::uint64_t, 16384> fsync_values{};
	std::atomic<std::size_t> fsync_count{ 0 };
	std::uint64_t first_tick = LATENCY_TRACE_TICK_UNAVAILABLE;

	~measurement()
	{
		const char *path = std::getenv("DURIS_TEST_LATENCY_FILE");
		if (!path)
			return;
		FILE *output = std::fopen(path, "w");
		if (!output)
			std::abort();
		for (const auto &section : sections)
		{
			std::fprintf(output, "%s %zu", section.name, section.overflow);
			for (std::size_t i = 0; i < section.count; ++i)
				std::fprintf(output, " %llu",
					     (unsigned long long)section.values[i]);
			std::fputc('\n', output);
		}
		const auto count = fsync_count.load();
		std::fprintf(output, "fsync %zu",
			     count > fsync_values.size() ? count - fsync_values.size() : 0);
		for (std::size_t i = 0; i < count && i < fsync_values.size(); ++i)
			std::fprintf(output, " %llu", (unsigned long long)fsync_values[i]);
		std::fputc('\n', output);
		if (std::fclose(output))
			std::abort();
	}
} measured;

} // namespace

extern "C" int __real_fsync(int);

extern "C" int __wrap_fsync(int fd)
{
	const auto started = latency_trace_monotonic_us();
	const int result = __real_fsync(fd);
	const int saved_errno = errno;
	const auto finished = latency_trace_monotonic_us();
	const auto index = measured.fsync_count.fetch_add(1);
	if (index < measured.fsync_values.size())
		measured.fsync_values[index] = latency_trace_elapsed_us(started, finished);
	errno = saved_errno;
	return result;
}

extern "C" void __real__Z20latency_trace_recordPKcmm(const char *, std::uint64_t, std::uint64_t);

extern "C" void __wrap__Z20latency_trace_recordPKcmm(const char *name, std::uint64_t duration,
						     std::uint64_t tick)
{
	__real__Z20latency_trace_recordPKcmm(name, duration, tick);
	if (tick == LATENCY_TRACE_TICK_UNAVAILABLE)
		return;
	if (measured.first_tick == LATENCY_TRACE_TICK_UNAVAILABLE)
		measured.first_tick = tick;
	// Match the two runs after forty warm-up pulses (ten seconds).
	if (tick - measured.first_tick < 40)
		return;
	for (auto &section : measured.sections)
	{
		if (std::strcmp(name, section.name))
			continue;
		if (duration == LATENCY_TRACE_DURATION_INVALID ||
		    section.count == section.values.size())
			++section.overflow;
		else
			section.values[section.count++] = duration;
		return;
	}
}
