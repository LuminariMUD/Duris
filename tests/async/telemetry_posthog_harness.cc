#include "telemetry/telemetry_posthog.h"

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <cstring>

namespace
{

template <typename Number> bool parse(const char *text, Number &number)
{
	const auto result = std::from_chars(text, text + std::strlen(text), number);
	return result.ec == std::errc{} && *result.ptr == '\0';
}

template <std::size_t Size> int report(bool valid, const std::array<char, Size> &output)
{
	if (!valid)
		return std::all_of(output.begin(), output.end(),
				   [](char value) { return value == '\0'; }) ?
			       1 :
			       2;
	std::puts(output.data());
	return 0;
}

} // namespace

int main(int argc, char **argv)
{
	if (argc == 2 && std::strcmp(argv[1], "uuid") == 0)
	{
		telemetry_posthog_uuid output{};
		output.fill('x');
		const bool valid = telemetry_posthog_event_uuid(output);
		return report(valid, output);
	}
	if (argc == 3 && std::strcmp(argv[1], "timestamp") == 0)
	{
		telemetry_utc_usec utc{};
		if (!parse(argv[2], utc))
			return 2;
		telemetry_posthog_timestamp output{};
		output.fill('x');
		const bool valid = telemetry_posthog_format_timestamp(utc, output);
		return report(valid, output);
	}
	if (argc == 6 && std::strcmp(argv[1], "character") == 0)
	{
		telemetry_posthog_identity_key key{};
		key.fill(0xFFU);
		telemetry_environment_id environment{};
		telemetry_season_id season{};
		telemetry_subject_id subject{};
		if (!parse(argv[3], environment) || !parse(argv[4], season) ||
		    !parse(argv[5], subject))
			return 2;
		telemetry_posthog_character_identity output{};
		output.fill('x');
		if (!telemetry_posthog_parse_identity_key(argv[2], key))
		{
			if (!std::all_of(key.begin(), key.end(),
					 [](std::uint8_t byte) { return byte == 0U; }))
				return 2;
			/* Parsing failure must not leave a usable key or raw-ID fallback. */
			const bool valid = telemetry_posthog_character_id(key, environment, season,
									  subject, output);
			return valid ? 2 : report(valid, output);
		}
		const bool valid =
			telemetry_posthog_character_id(key, environment, season, subject, output);
		return report(valid, output);
	}
	if (argc == 7 && (std::strcmp(argv[1], "session") == 0 || std::strcmp(argv[1], "run") == 0))
	{
		telemetry_environment_id environment{};
		telemetry_season_id season{};
		telemetry_producer_id producer{};
		telemetry_sequence sequence{};
		if (!parse(argv[2], environment) || !parse(argv[3], season) ||
		    !parse(argv[4], producer.boot_id) || !parse(argv[5], producer.process_id) ||
		    !parse(argv[6], sequence))
			return 2;
		telemetry_posthog_scoped_identity output{};
		output.fill('x');
		const telemetry_session_ref session = {
			{ producer, sequence }, 44U, 55, season, environment
		};
		const bool valid = std::strcmp(argv[1], "session") == 0 ?
					   telemetry_posthog_session_id(session, output) :
					   telemetry_posthog_run_id(environment, season,
								    { producer, sequence }, output);
		return report(valid, output);
	}
	return 2;
}
