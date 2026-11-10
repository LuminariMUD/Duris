#ifndef DURIS_CONFIG_PARSE_H
#define DURIS_CONFIG_PARSE_H

#include <cerrno>
#include <climits>
#include <cmath>
#include <cstdlib>

// Callers trim values and own their domain ranges and diagnostics.
// Outputs change only after the whole value has parsed successfully.
inline bool config_parse_int(const char *text, int &result)
{
	char *end;
	errno = 0;
	const long value = std::strtol(text, &end, 10);
	if (errno || end == text || *end || value < INT_MIN || value > INT_MAX)
		return false;
	result = static_cast<int>(value);
	return true;
}

inline bool config_parse_double(const char *text, double &result)
{
	char *end;
	errno = 0;
	const double value = std::strtod(text, &end);
	if (errno || end == text || *end || !std::isfinite(value))
		return false;
	result = value;
	return true;
}

inline bool config_parse_float(const char *text, float &result)
{
	char *end;
	// Overflow parses as infinity; underflow is a legitimate tiny value.
	const float value = std::strtof(text, &end);
	if (end == text || *end || !std::isfinite(value))
		return false;
	result = value;
	return true;
}

#endif
