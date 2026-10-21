/****************************************************************************
 *  File: telemetry_posthog.c                                  Part of Duris
 *  Usage: worker-side PostHog encodings
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 ****************************************************************************/

#include "telemetry/telemetry_posthog.h"

#include <algorithm>
#include <charconv>
#include <cstdio>
#include <cstring>
#include <ctime>

#include <openssl/crypto.h>
#include <openssl/hmac.h>
#include <openssl/rand.h>

namespace
{
constexpr char HEX[] = "0123456789abcdef";
constexpr std::string_view CHARACTER_DOMAIN = "duris:posthog:character:v1";

bool has_key(const telemetry_posthog_identity_key &key) noexcept
{
	return std::any_of(key.begin(), key.end(), [](std::uint8_t byte) { return byte != 0U; });
}

int hex_digit(char digit) noexcept
{
	if (digit >= '0' && digit <= '9')
		return digit - '0';
	if (digit >= 'a' && digit <= 'f')
		return digit - 'a' + 10;
	if (digit >= 'A' && digit <= 'F')
		return digit - 'A' + 10;
	return -1;
}

void append_be64(std::uint8_t *output, std::uint64_t value) noexcept
{
	for (unsigned int index = 0U; index < 8U; ++index)
		output[index] = static_cast<std::uint8_t>(value >> ((7U - index) * 8U));
}

bool scoped_id(const char *prefix, telemetry_environment_id environment, telemetry_season_id season,
	       const telemetry_producer_id &producer, telemetry_sequence sequence,
	       telemetry_posthog_scoped_identity &output) noexcept
{
	output.fill('\0');
	if (environment == 0U || season == 0U || !telemetry_producer_id_is_valid(producer) ||
	    sequence == 0U)
		return false;
	std::memcpy(output.data(), prefix, 3U);
	char *cursor = output.data() + 3U;
	for (const auto value :
	     { environment, season, producer.boot_id, producer.process_id, sequence })
	{
		*cursor++ = ':';
		const auto result =
			std::to_chars(cursor, output.data() + output.size() - 1U, value);
		if (result.ec != std::errc{})
		{
			output.fill('\0');
			return false;
		}
		cursor = result.ptr;
	}
	return true;
}

} // namespace

bool telemetry_posthog_parse_identity_key(std::string_view hex,
					  telemetry_posthog_identity_key &output) noexcept
{
	output.fill(0U);
	if (hex.size() != output.size() * 2U)
		return false;
	telemetry_posthog_identity_key parsed{};
	bool valid = true;
	for (std::size_t index = 0U; index < parsed.size(); ++index)
	{
		const int high = hex_digit(hex[index * 2U]);
		const int low = hex_digit(hex[index * 2U + 1U]);
		if (high < 0 || low < 0)
		{
			valid = false;
			break;
		}
		parsed[index] = static_cast<std::uint8_t>(high * 16 + low);
	}
	valid = valid && has_key(parsed);
	if (valid)
		output = parsed;
	OPENSSL_cleanse(parsed.data(), parsed.size());
	return valid;
}

bool telemetry_posthog_character_id(const telemetry_posthog_identity_key &key,
				    telemetry_environment_id environment,
				    telemetry_season_id season, telemetry_subject_id subject,
				    telemetry_posthog_character_identity &output) noexcept
{
	output.fill('\0');
	if (!has_key(key) || environment == 0U || season == 0U || subject == 0U)
		return false;
	std::array<std::uint8_t, CHARACTER_DOMAIN.size() + 24U> message{};
	std::memcpy(message.data(), CHARACTER_DOMAIN.data(), CHARACTER_DOMAIN.size());
	append_be64(message.data() + CHARACTER_DOMAIN.size(), environment);
	append_be64(message.data() + CHARACTER_DOMAIN.size() + 8U, season);
	append_be64(message.data() + CHARACTER_DOMAIN.size() + 16U, subject);
	std::array<unsigned char, EVP_MAX_MD_SIZE> digest{};
	unsigned int length = 0U;
	if (HMAC(EVP_sha256(), key.data(), static_cast<int>(key.size()), message.data(),
		 message.size(), digest.data(), &length) == nullptr ||
	    length != 32U)
		return false;
	std::memcpy(output.data(), "dc1_", 4U);
	for (std::size_t index = 0U; index < length; ++index)
	{
		output[4U + index * 2U] = HEX[digest[index] >> 4U];
		output[5U + index * 2U] = HEX[digest[index] & 0x0FU];
	}
	return true;
}

bool telemetry_posthog_session_id(const telemetry_session_ref &session,
				  telemetry_posthog_scoped_identity &output) noexcept
{
	output.fill('\0');
	if (!telemetry_session_ref_is_valid(session))
		return false;
	return scoped_id("ds1", session.environment_id, session.season_id, session.id.producer,
			 session.id.session_seq, output);
}

bool telemetry_posthog_run_id(telemetry_environment_id environment, telemetry_season_id season,
			      const telemetry_encounter_id &run,
			      telemetry_posthog_scoped_identity &output) noexcept
{
	return scoped_id("dr1", environment, season, run.producer, run.sequence, output);
}

bool telemetry_posthog_event_uuid(telemetry_posthog_uuid &output) noexcept
{
	output.fill('\0');
	std::array<unsigned char, 16U> bytes{};
	if (RAND_bytes(bytes.data(), static_cast<int>(bytes.size())) != 1)
		return false;
	bytes[6] = static_cast<unsigned char>((bytes[6] & 0x0FU) | 0x40U);
	bytes[8] = static_cast<unsigned char>((bytes[8] & 0x3FU) | 0x80U);
	std::size_t offset = 0U;
	for (std::size_t index = 0U; index < bytes.size(); ++index)
	{
		if (index == 4U || index == 6U || index == 8U || index == 10U)
			output[offset++] = '-';
		output[offset++] = HEX[bytes[index] >> 4U];
		output[offset++] = HEX[bytes[index] & 0x0FU];
	}
	return true;
}

bool telemetry_posthog_format_timestamp(telemetry_utc_usec utc,
					telemetry_posthog_timestamp &output) noexcept
{
	output.fill('\0');
	if (utc < -62'135'596'800'000'000LL || utc > 253'402'300'799'999'999LL)
		return false;
	std::int64_t seconds = utc / 1'000'000;
	std::int64_t fractional = utc % 1'000'000;
	if (fractional < 0)
	{
		--seconds;
		fractional += 1'000'000;
	}
	const auto time = static_cast<std::time_t>(seconds);
	if (static_cast<std::int64_t>(time) != seconds)
		return false;
	std::tm calendar{};
	if (gmtime_r(&time, &calendar) == nullptr)
		return false;
	char formatted[128]{};
	const int size = std::snprintf(formatted, sizeof(formatted),
				       "%04d-%02d-%02dT%02d:%02d:%02d.%06uZ",
				       calendar.tm_year + 1900, calendar.tm_mon + 1,
				       calendar.tm_mday, calendar.tm_hour, calendar.tm_min,
				       calendar.tm_sec, static_cast<unsigned int>(fractional));
	if (size != static_cast<int>(output.size() - 1U))
		return false;
	std::memcpy(output.data(), formatted, output.size());
	return true;
}
