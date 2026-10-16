#ifndef DURIS_NEWS_H
#define DURIS_NEWS_H

#include <string>

struct news_content
{
	std::string text;
	std::string fingerprint;
};

// Game-thread publication; callers retain the last good value on failure.
const news_content &current_news();
bool publish_news(const std::string &text);
bool load_news_file(const std::string &root, std::string *error);

#endif
