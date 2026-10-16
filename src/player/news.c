#include "player/news.h"
#include "flatfile/flatfile_help_catalog.h"

#include <new>
#include <openssl/sha.h>
#include <utility>

namespace
{
news_content published;
}

const news_content &current_news()
{
	return published;
}

bool publish_news(const std::string &text)
{
	if (text == published.text)
		return true;
	if (text.find('\0') != std::string::npos)
		return false;
	try
	{
		news_content candidate;
		candidate.text = text;
		if (!text.empty())
		{
			unsigned char digest[SHA256_DIGEST_LENGTH];
			if (!SHA256(reinterpret_cast<const unsigned char *>(text.data()),
				    text.size(), digest))
				return false;
			constexpr char hex[] = "0123456789abcdef";
			candidate.fingerprint.reserve(SHA256_DIGEST_LENGTH * 2);
			for (unsigned char byte : digest)
			{
				candidate.fingerprint += hex[byte >> 4];
				candidate.fingerprint += hex[byte & 15];
			}
		}
		published = std::move(candidate);
		return true;
	}
	catch (const std::bad_alloc &)
	{
		return false;
	}
}

bool load_news_file(const std::string &root, std::string *error)
{
	std::string text;
	if (!flatfile_information_read(root, "news", &text, error))
		return false;
	if (publish_news(text))
		return true;
	if (error)
		*error = "could not publish news";
	return false;
}
