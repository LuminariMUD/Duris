#ifndef DIVINE_BOON_MATH_H
#define DIVINE_BOON_MATH_H

#include <charconv>

// Existing configuration caches percentages as float. Recover their shortest
// decimal value before precise reward arithmetic: 0.9 must produce 180 from
// 100 + 100 at 90%, rather than 179 from the float representation's small error.
inline double divine_boon_modifier(float value)
{
	char text[32]; // More than any float's shortest decimal representation.
	const auto encoded = std::to_chars(text, text + sizeof(text), value);
	double result = value;
	std::from_chars(text, encoded.ptr, result);
	return result;
}

#endif
