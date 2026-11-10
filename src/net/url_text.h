#pragma once

#include "net/ansi.h"
#include <string_view>

// Shared lexical rules for color parsing and URL recognition. ASCII schemes
// are case-insensitive; labels may contain arbitrary Unicode code points.
template <typename Char>
inline size_t output_url_scheme_length(std::basic_string_view<Char> text, size_t begin)
{
	for (std::string_view scheme : { "https://", "http://" })
	{
		if (begin > text.size() || scheme.size() > text.size() - begin)
			continue;
		size_t i = 0;
		while (i < scheme.size())
		{
			auto c = GET_CHAR(text[begin + i]);
			if (c >= 'A' && c <= 'Z')
				c += 'a' - 'A';
			if (c != scheme[i])
				break;
			++i;
		}
		if (i == scheme.size())
			return i;
	}
	return 0;
}

inline bool output_url_boundary(wchar_t c)
{
	return !((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9') ||
		 c == '_');
}

inline bool output_url_delimiter(wchar_t c)
{
	return c <= ' ' || (c >= 127 && c <= 159) || c == '<' || c == '>' || c == '"' ||
	       c == '\'' || c == '`' || c == '\\';
}

// In URL text, a query/matrix parameter spelling takes precedence over Duris
// color markup. Existing literal-& escapes still contain a second ampersand.
inline bool output_url_parameter(const char *ampersand, bool query)
{
	if (query && (ampersand[1] == 'n' || ampersand[1] == 'N'))
	{
		const auto next = static_cast<unsigned char>(ampersand[2]);
		if ((next >= 'a' && next <= 'z') || (next >= 'A' && next <= 'Z') ||
		    (next >= '0' && next <= '9') || next >= 128 || next == '_' || next == '-' ||
		    next == '%')
			return true; // Bare query flags such as &no-cache are literal too.
	}
	for (const unsigned char *p = reinterpret_cast<const unsigned char *>(ampersand + 1); *p;
	     ++p)
	{
		if (*p == '=')
			return true;
		if (*p <= ' ' || *p == 127 || *p == '&' || *p == '/' || *p == '?' || *p == '#' ||
		    *p == '<' || *p == '>' || *p == '"' || *p == '\'' || *p == '`' || *p == '\\')
			return false;
	}
	return false;
}
