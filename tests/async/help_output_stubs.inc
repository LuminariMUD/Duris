#include "cmd/help_cache.h"
#include "cmd/wikihelp.h"

static help_catalog output_help_pages;
static bool output_help_ready = true;
static unsigned attribute_help_calls;
const help_catalog *help_cache_get()
{
	return output_help_ready ? &output_help_pages : nullptr;
}
char *attrib_help(char *)
{
	++attribute_help_calls;
	return nullptr;
}
// These tests exercise ordinary authored pages. Existing class/spell tests
// cover their separately generated details; they must not be reached here.
string wiki_classes(string)
{
	assert(false);
	return {};
}
string wiki_racial_stats(string)
{
	assert(false);
	return {};
}
string wiki_specs(string)
{
	assert(false);
	return {};
}
string wiki_multiclass(string)
{
	assert(false);
	return {};
}
string wiki_pcraces(string)
{
	assert(false);
	return {};
}
string wiki_innates(string, int)
{
	assert(false);
	return {};
}
string wiki_races(string, int)
{
	assert(false);
	return {};
}
string wiki_skills(string, int)
{
	assert(false);
	return {};
}
string wiki_spells(string, int)
{
	assert(false);
	return {};
}
