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
	for (const char *query : { "boon", "divine boons" })
	{
		const string boons = wiki_help(query);
		for (const char *rule : { "200%", "+25%", "three times", "FIRST qualifying ship",
					  "Spill Blood", "220", "160", "automatic" })
			require(boons.find(rule) != string::npos,
				"Divine help omitted a required rule");
		require(boons.find("boon shop stat") == string::npos,
			"Legacy shop directions survived");
		for (const char *rule :
		     { "three Experience", "three Epic", "Good and Evil", "one", "shared" })
			require(boons.find(rule) != string::npos,
				"Canonical Divine help still describes faction-specific targets");
		require(boons.find("six for zone EXP") == string::npos &&
				boons.find("Good-side objectives") == string::npos,
			"Overridden Divine Boon help still describes the old rotation");
	}
	require(wiki_help("divineboon").find("unconsumed hourly opportunity") != string::npos &&
			wiki_help("divineboon").find("shared") != string::npos,
		"Canonical staff help missing the shared rotation or force timing");

	for (const char *topic : { "air affinity", "water affinity", "fire affinity",
				   "earth affinity", "astral affinity" })
	{
		const string affinity = wiki_help(topic);
		for (const char *rule : { "level 51", "remember", "Groupmates, pets", "VNUMs" })
			require(affinity.find(rule) != string::npos,
				"Planar affinity lookup omitted its level, memory or personal limits");
	}
	require(wiki_help("planar affinity").find("19826-19886") != string::npos,
		"Planar affinity overview omitted the excluded astral side rooms");
	for (const char *topic : { "air form", "earth form", "fire form", "water form" })
	{
		const string form = wiki_help(topic);
		for (const char *rule : { "Self only", "circle-10", "8 affect-duration units",
					  "Ice Aura", "dispelled" })
			require(form.find(rule) != string::npos,
				"Elemental form lookup omitted its duration, targets or conflicts");
	}

	require(wiki_help("stone skin").find("newest layer only") != string::npos,
		"Stone Skin did not render the dedicated parsed layering topic");
	require(wiki_help("earthen maul").find("including Druids") != string::npos,
		"Earthen Maul did not render shared terrain-independent access");
	require(wiki_help("ethereal recharge").find("100 actual HP") != string::npos,
		"Ethereal Recharge omitted its final Air self-healing cap");
	require(wiki_help("dimension door").find("3 seconds") != string::npos &&
			wiki_help("relocate").find("5 seconds") != string::npos,
		"Air travel help omitted its post-cast waits");
	require(wiki_help("conjure water").find("5-minute cooldown") != string::npos,
		"Conjure Water omitted its successful-use cooldown");
	require(wiki_help("water to life").find("232 at") != string::npos,
		"Water to Life did not render the dedicated parsed formula topic");
	require(wiki_help("water form").find("5 seconds BEFORE") != string::npos &&
			wiki_help("water form").find("25% less") != string::npos,
		"Water Form omitted its shoreline timing and movement discount");
	require(wiki_help("fireball").find("100%") != string::npos &&
			wiki_help("solar flare").find("exactly 10%") != string::npos,
		"Fire spell help omitted the approved unlock or damage increase");
	for (const char *topic : { "conjure elemental", "conjure greater elemental" })
		require(wiki_help(topic).find("no Fireshield") != string::npos,
			"Elemental summon help omitted the optional mephit behavior");

	cout << "flat-file help runtime passed\n";
	return 0;
}
