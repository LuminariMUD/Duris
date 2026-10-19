#include <string>
using namespace std;

#include "cmd/wikihelp.h"

#include <cstdlib>
#include <iostream>

/** Provide the logging symbol required by the isolated help runtime. */

/** Exit the test harness with a diagnostic when a requirement fails. */
static void require(bool condition, const string &message)
{
	if (!condition)
	{
		cerr << message << '\n';
		exit(1);
	}
}

/** Exercise flat-file help lookup, including the supported No Locate aliases. */
int main()
{
	const string default_help = wiki_help("");
	require(default_help.find("temporarily disabled") == string::npos &&
			default_help.find("help") != string::npos,
		"default help did not use the flat catalog");
	const string exact = wiki_help("cHaRiSmA");
	require(exact.find("major attributes") != string::npos,
		"exact help did not render flat content");
	const string multiple = wiki_help("celest");
	require(multiple.find("following help topics") != string::npos,
		"multiple-match help did not render a topic list");
	const string missing = wiki_help("definitely missing topic");
	require(missing.find("no help topics") != string::npos,
		"missing help did not preserve the user-facing result");
	const string ptell = wiki_help("ptell");
	for (const char *disclosure : { "staff-only Discord", "sender and target", "Someone",
					"cannot become game replies", "best effort" })
		require(ptell.find(disclosure) != string::npos,
			"canonical PTELL help omitted the Discord privacy disclosure");
	for (const char *query : { "nolocate", "no locate", "no-locate", "toggle_nolocate" })
	{
		const string no_locate = wiki_help(query);
		require(no_locate.find("introduction system") != string::npos,
			"No Locate help alias did not render the dedicated topic");
	}
	require(wiki_help("web-spray").find("innate web_spray") != string::npos,
		"Web Spray alias did not render its innate topic");
	require(wiki_help("quickstep").find("powerful blow") != string::npos,
		"Quickstep alias did not render Quick Step");
	const string seadog = wiki_help("seadog");
	for (const char *meaning :
	     { "passive seafaring", "owner with Seadog", "anywhere aboard",
	       "person operating the panel", "bonus will not persist", "10% more proceeds" })
		require(seadog.find(meaning) != string::npos,
			"Seadog did not render its owner/panel and cargo-sale rules");
	cout << "flat-file help runtime passed\n";
	return 0;
}
