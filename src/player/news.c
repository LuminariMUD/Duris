#include "player/news.h"
#include "flatfile/flatfile_help_catalog.h"
#include "core/prototypes.h"
#include "core/files.h"
#include "core/utils.h"
#include "player/player_save_pipeline.h"
#include "world/db.h"

#include <new>
#include <openssl/sha.h>
#include <utility>

namespace
{
news_content published;

P_char news_owner(P_char recipient)
{
	if (!recipient)
		return nullptr;
	P_char owner = GET_PLYR(recipient);
	return owner && IS_PC(owner) && owner->only.pc ? owner : nullptr;
}
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

bool has_unread_news(P_char recipient)
{
	P_char owner = news_owner(recipient);
	return owner && !published.fingerprint.empty() &&
	       published.fingerprint != owner->only.pc->last_read_news_hash;
}

bool acknowledge_news(P_char recipient, const std::string &fingerprint)
{
	P_char owner = news_owner(recipient);
	if (!owner || GET_PID(owner) <= 0 || fingerprint.size() != 64)
		return false;
	if (fingerprint == owner->only.pc->last_read_news_hash)
		return true;
	char before[65];
	memcpy(before, owner->only.pc->last_read_news_hash, sizeof(before));
	memcpy(owner->only.pc->last_read_news_hash, fingerprint.c_str(), fingerprint.size() + 1);
	const int room = owner->in_room == NOWHERE ? NOWHERE : world[owner->in_room].number;
	const auto result =
		player_save_pipeline_request(owner, PLAYER_COMPONENT_STATUS, RENT_CRASH, room);
	if (result == player_save_pipeline_result::queued ||
	    result == player_save_pipeline_result::coalesced)
		return true;
	memcpy(owner->only.pc->last_read_news_hash, before, sizeof(before));
	return false;
}
