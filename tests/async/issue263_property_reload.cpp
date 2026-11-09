// Executes real properties.c parsing/commands; unrelated game services are stubs.
#include "world/properties.c"
#include "core/profile.h"
#include "telemetry/telemetry_config_reload.h"
#include "telemetry/telemetry_config_private.h"

#include <array>
#include <cassert>
#include <fstream>
#include <iostream>
#include <string>
#include <filesystem>
#include <csignal>
#include <sys/resource.h>
#include <unistd.h>
#include <fcntl.h>

float hp_mob_con_factor;
float hp_mob_npc_pc_ratio;
int damroll_cap;
int hitroll_cap;
int errand_notch;
static unsigned completed_applies;
static std::string output;
P_char character_list;
static unsigned rebalanced_characters;
static int cached_strength;
static std::string io_failure;
static unsigned saved_logs;

// Inject failures after real I/O so the production error checks must notice them.
extern "C" int __real_fclose(FILE *);
extern "C" int __wrap_fclose(FILE *stream)
{
	bool writing = (fcntl(fileno(stream), F_GETFL) & O_ACCMODE) != O_RDONLY;
	int result = __real_fclose(stream);
	return io_failure == (writing ? "close-target" : "close-source") ? EOF : result;
}
extern "C" int __real_rename(const char *, const char *);
extern "C" int __wrap_rename(const char *from, const char *to)
{
	return io_failure == "rename" ? -1 : __real_rename(from, to);
}
extern "C" char *__real_fgets(char *, int, FILE *);
extern "C" char *__wrap_fgets(char *buf, int size, FILE *stream)
{
	char *result = __real_fgets(buf, size, stream);
	if (result && io_failure == "read")
	{
		// The buffered prefix remains readable, then the real stream sets ferror.
		assert(close(fileno(stream)) == 0);
		io_failure.clear();
	}
	return result;
}
void sql_log(P_char, const char *, const char *format, ...)
{
	if (!strcmp(format, "Saved properties"))
		++saved_logs;
}

void update_item_action_properties() {}
void update_weapon_action_properties() {}
void update_device_action_properties() {}
void update_studio_ability_properties() {}
void update_native_artifact_properties() {}
void update_difficulty_dials() {}
void update_stat_data()
{
	cached_strength = get_property("stats.str.Drider", 100);
}
void balance_affects(P_char character)
{
	character->curr_stats.Str = cached_strength;
	++rebalanced_characters;
}
void update_damage_data() {}
void update_spellpulse_data() {}
void update_racial_shrug_data() {}
void update_racial_exp_mods() {}
void update_racial_exp_mod_victims() {}
void update_exp_mods() {}
void update_exp_table() {}
void update_dam_factors() {}
void update_racial_dam_factors() {}
void update_saving_throws() {}
void update_breath_weapon_properties() {}
void update_regen_properties() {}
void update_misfire_properties()
{
	++completed_applies;
}
void collector_config_reload() {}
void item_actions_reload() {}
void send_to_char(const char *text, P_char)
{
	output += text;
}
char *str_dup(const char *text)
{
	return ::strdup(text);
}
void __free(void *p, const char *, int)
{
	std::free(p);
}
bool studio_abilities_reload_file(std::string &)
{
	return true;
}
bool ws_is_durisweb_mud_gated_hook(const char *)
{
	return false;
}
void ws_broadcast_durisweb_hook_state() {}

struct observations
{
	std::array<float, 16> values{};
	unsigned count{};
	unsigned last_apply{};
};

static void observe(void *opaque) noexcept
{
	auto &state = *static_cast<observations *>(opaque);
	assert(completed_applies > state.last_apply);
	assert(hp_mob_con_factor == get_property("hitpoints.mob.conFactor", 0.4));
	state.last_apply = completed_applies;
	assert(state.count < state.values.size());
	state.values[state.count++] = get_property("epic.touch.PayoutFactor", 1.0);
}

static bool native_property_read(void *, const char *key, float *value) noexcept
{
	if (std::strcmp(key, "exp.zoneTrophy.observe") == 0)
		*value = get_property(key, 0.0);
	else if (std::strcmp(key, "epic.touch.maxPayoutFactor") == 0)
		*value = get_property(key, 10.0);
	else if (std::strcmp(key, "epic.touch.PayoutFactor") == 0)
		*value = get_property(key, 1.0);
	else if (std::strcmp(key, "epic.zone.alignmentMod") == 0 ||
		 std::strcmp(key, "epic.alignment.minPercentage") == 0)
		*value = get_property(key, 0.10);
	else
		return false;
	return true;
}

static bool overflowing_property_read(void *ctx, const char *key, float *value) noexcept
{
	if (std::strcmp(key, "exp.zoneTrophy.observe") == 0)
	{
		*value = 2147483648.0F;
		return true;
	}
	return native_property_read(ctx, key, value);
}

static void command(P_char actor, const char *text)
{
	std::array<char, 256> args{};
	std::snprintf(args.data(), args.size(), "%s", text);
	do_properties(actor, args.data(), 0);
}

static void property_file(float payout, int strength = 95)
{
	std::ofstream file("lib/duris.properties");
	file << "epic.touch.PayoutFactor=" << payout << '\n' << "hitpoints.mob.conFactor=0.75\n";
	file << "stats.str.Drider=" << strength << '\n';
	assert(file.good());
}

static std::string read_file()
{
	std::ifstream file("lib/duris.properties");
	return { std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>() };
}

static void failure_case(P_char actor, const std::string &test)
{
	if (test == "numeric-values")
	{
		for (const char *family :
		     { "str", "dex", "agi", "con", "pow", "int", "wis", "cha", "kar", "luc" })
		{
			for (const char *number : { "100.75", "32767.9", "-32768.9" })
			{
				std::string line = std::string("stats.") + family +
						   ".Probe = " + number + " # retained comment\n";
				const auto original = line;
				struct property parsed
				{
				};
				assert(parse_property(&parsed, line.data()) == 1 &&
				       line == original);
				const auto narrowed = static_cast<sh_int>(parsed.value);
				assert(narrowed == (!strcmp(number, "100.75") ? 100 :
						    number[0] == '-'	      ? -32768 :
										32767));
				FREE(parsed.key);
			}
			for (const char *number : { "32768", "-32769", "32767.9999", "NaN", "Inf",
						    "-Inf", "1e1000", "2junk" })
			{
				std::string line =
					std::string("stats.") + family + ".Probe=" + number + '\n';
				const auto original = line;
				struct property parsed
				{
				};
				assert(parse_property(&parsed, line.data()) == -1 && !parsed.key &&
				       line == original);
			}
		}
		for (const char *text : { "sample=NaN", "sample=Inf", "sample=1e1000",
					  "sample=2junk", "sample 1=2", "=1" })
		{
			std::string line = text;
			struct property parsed
			{
			};
			assert(parse_property(&parsed, line.data()) == -1 && !parsed.key);
		}
		property_file(1.0F);
		assert(initialize_properties());
		const unsigned applies = completed_applies;
		for (const char *value :
		     { "NaN", "Inf", "1e1000", "2junk", "2 extra", "32768", "-32769" })
		{
			output.clear();
			command(actor, (std::string("set * ") + value).c_str());
			assert(get_property("epic.touch.PayoutFactor", 0.0) == 1 &&
			       get_property("stats.str.Drider", 0.0) == 95);
			assert(completed_applies == applies && cached_strength == 95 &&
			       !output.empty());
		}
		const auto baseline = read_file();
		for (const char *value : { "NaN", "32768", "2junk" })
		{
			std::ofstream("lib/duris.properties")
				<< "epic.touch.PayoutFactor=77\nstats.str.Drider=" << value << '\n';
			output.clear();
			command(actor, "reload");
			assert(output.find("reload failed") != std::string::npos);
			assert(get_property("epic.touch.PayoutFactor", 0.0) == 1 &&
			       get_property("stats.str.Drider", 0.0) == 95);
			assert(completed_applies == applies && cached_strength == 95 &&
			       rebalanced_characters == 0);
		}
		std::ofstream("lib/duris.properties") << baseline;
		assert(get_property("absent.key", INT_MAX) == INT_MAX);
		auto *entry = static_cast<struct property *>(
			bsearch("epic.touch.PayoutFactor", duris_properties, properties_count,
				sizeof(struct property), key_property_comp));
		assert(entry);
		for (float value :
		     { std::numeric_limits<float>::quiet_NaN(),
		       std::numeric_limits<float>::infinity(),
		       -std::numeric_limits<float>::infinity(), 2147483648.0F, -2147483904.0F })
		{
			entry->value = value;
			assert(get_property(entry->key, 17) == 17);
		}
		entry->value = 2147483520.0F;
		assert(get_property(entry->key, 0) == 2147483520);
		entry->value = -2147483648.0F;
		assert(get_property(entry->key, 0) == INT_MIN);
		entry->value = 1.75F;
		assert(get_property(entry->key, 0) == 1);
		entry->value = 1.0F;
		return;
	}
	if (test == "keys")
	{
		for (size_t length : { 127, 128, 200 })
		{
			std::string line(length, 'A');
			line += "=1\n";
			struct property parsed
			{
			};
			int result = parse_property(&parsed, line.data());
			assert((result == 1) == (length == 127));
			if (result == 1)
			{
				assert(strlen(parsed.key) == length && parsed.value == 1);
				FREE(parsed.key);
			}
		}
		return;
	}
	property_file(1.0F);
	initialize_properties();
	command(actor, "set epic.touch.PayoutFactor 2");
	const int count = properties_count;
	const unsigned applies = completed_applies;
	const std::string original = read_file();
	const bool reload = test.starts_with("reload-");
	std::string fault = test.substr(test.find('-') + 1);
	if (fault == "missing")
		std::filesystem::rename("lib/duris.properties", "lib/original");
	else if (fault == "open")
		std::filesystem::create_directory("lib/duris.properties.new");
	else if (fault == "malformed" || fault == "limit")
	{
		std::ofstream file("lib/duris.properties");
		file << "epic.touch.PayoutFactor=99\n";
		if (fault == "malformed")
			file << std::string(200, 'A') << "=1\n";
		else
			for (int i = 0; i < MAX_PROPERTIES; ++i)
				file << "key." << i << "=1\n";
	}
	else if (fault == "write" || fault == "flush")
	{
		std::ofstream file("lib/duris.properties", std::ios::app);
		for (int i = 0; i < (fault == "write" ? 20 : 1); ++i)
			file << '#' << std::string(800, 'x') << '\n';
		file.close();
		signal(SIGXFSZ, SIG_IGN);
		struct rlimit limit
		{
		};
		assert(getrlimit(RLIMIT_FSIZE, &limit) == 0);
		limit.rlim_cur = 64;
		assert(setrlimit(RLIMIT_FSIZE, &limit) == 0);
	}
	const std::string before = fault == "missing" ? original : read_file();
	if (fault == "read" || fault.starts_with("close-") || fault == "rename")
		io_failure = fault;
	output.clear();
	command(actor, reload ? "reload" : "save");
	io_failure.clear();
	assert(properties_count == count);
	assert(get_property("epic.touch.PayoutFactor", 0.0) == 2);
	assert(completed_applies == applies && rebalanced_characters == 0);
	assert(saved_logs == 0);
	assert(output.find("failed") != std::string::npos);
	if (fault == "missing")
		std::filesystem::rename("lib/original", "lib/duris.properties");
	assert(read_file() == before);
	if (fault == "open")
		std::filesystem::remove("lib/duris.properties.new");
	assert(!std::filesystem::exists("lib/duris.properties.new"));
	// Both diff and revert must retain the last successful saved baseline.
	output.clear();
	command(actor, "diff");
	assert(output.find("epic.touch.PayoutFactor=2.000(1.000)") != std::string::npos);
	command(actor, "revert");
	assert(get_property("epic.touch.PayoutFactor", 0.0) == 1);
}

PROFILE_DEFINE(random_mob_create)
bool do_profile = false;
P_index mob_index;
static int spawn_attempts;
static P_char next_spawn;
P_char create_random_mob(int theme, int level)
{
	assert(theme == -1 && level == 0);
	++spawn_attempts;
	if (next_spawn)
	{
		next_spawn->next = character_list;
		character_list = next_spawn;
	}
	return next_spawn;
}
#include "training_dummy_is.inc"
#include "spawn_random_mapmob.inc"

static void expect_spawn_attempts(int population, int attempts)
{
	index_data prototype{};
	prototype.virtual_number = 1255;
	mob_index = &prototype;
	npc_only_data npc{};
	std::vector<char_data> roamers(population);
	assert(!character_list);
	for (auto &roamer : roamers)
	{
		roamer.specials.act = ACT_ISNPC;
		roamer.only.npc = &npc;
		roamer.next = character_list;
		character_list = &roamer;
	}
	spawn_attempts = 0;
	spawn_random_mapmob();
	assert(spawn_attempts == attempts);
	character_list = nullptr;
	mob_index = nullptr;
}

static void check_mapmob_population(P_char actor)
{
	std::ofstream("lib/duris.properties") << "random.mapmob.populationCap=45.000\n";
	assert(initialize_properties());
	index_data prototypes[4]{};
	prototypes[0].virtual_number = 1255;
	prototypes[1].virtual_number = 1256;
	prototypes[2].virtual_number = 7;
	prototypes[3].virtual_number = 11;
	mob_index = prototypes;

	char_data player{};
	char_data extras[3]{};
	npc_only_data extra_data[3]{};
	character_list = &player;
	for (int i = 0; i < 3; ++i)
	{
		extra_data[i].R_num = i + 1;
		extra_data[i].training_dummy = i == 1;
		extras[i].specials.act = ACT_ISNPC;
		extras[i].only.npc = &extra_data[i];
		extras[i].next = character_list;
		character_list = &extras[i];
	}
	const auto other_characters = character_list;

	for (int dummies : { 0, 69, 71 })
	{
		std::vector<char_data> targets(dummies);
		std::vector<npc_only_data> profiles(dummies);
		character_list = other_characters;
		for (int i = 0; i < dummies; ++i)
		{
			profiles[i].training_dummy = true;
			profiles[i].training_dummy_fixed = i % 2 == 0;
			targets[i].only.npc = &profiles[i];
			targets[i].specials.act = ACT_ISNPC;
			targets[i].player.name = const_cast<char *>("renamed target");
			targets[i].next = character_list;
			character_list = &targets[i];
		}
		const auto dummy_list = character_list;
		for (int limit : { 45, 2, 60, 0 })
		{
			command(actor, ("set random.mapmob.populationCap " + std::to_string(limit))
					       .c_str());
			for (int population : { 0, std::max(0, limit - 1), limit, limit + 1 })
			{
				std::vector<char_data> roamers(population + 1);
				std::vector<npc_only_data> instances(population + 1);
				for (int i = 0; i <= population; ++i)
				{
					roamers[i].only.npc = &instances[i];
					roamers[i].specials.act = ACT_ISNPC;
					roamers[i].player.name =
						const_cast<char *>("training dummy");
					roamers[i].in_room = i % 2 ? NOWHERE : 1;
				}
				char_link_data pet{};
				pet.type = LNK_PET;
				pet.linking = &roamers.front();
				pet.linked = &player;
				player.linked = &pet;
				roamers.front().linking = &pet;

				character_list = dummy_list;
				for (int i = 0; i < population; ++i)
				{
					roamers[i].next = character_list;
					character_list = &roamers[i];
				}

				spawn_attempts = 0;
				const int allowed = population < limit;
				const auto initial_list = character_list;
				spawn_random_mapmob();
				assert(spawn_attempts == allowed && character_list == initial_list);

				// First generation failed. Try again and insert a roamer.
				next_spawn = &roamers.back();
				spawn_random_mapmob();
				assert(spawn_attempts == 2 * allowed);
				assert(character_list == (allowed ? next_spawn : initial_list));
				next_spawn = nullptr;

				spawn_random_mapmob();
				assert(spawn_attempts ==
				       2 * allowed + (population + allowed < limit));
				player.linked = nullptr;
				for (const auto &profile : profiles)
					assert(profile.training_dummy);
				for (const auto &instance : instances)
					assert(!instance.training_dummy);
			}
		}
	}
	assert(prototypes[0].virtual_number == 1255);
	character_list = nullptr;
	mob_index = nullptr;
}

static void check_mapmob_cap(P_char actor)
{
	assert(initialize_properties()); // Runner supplies the shipped file.
	output.clear();
	command(actor, "show random.mapmob.populationCap");
	assert(output.find("random.mapmob.populationCap: 45.000") != std::string::npos);
	expect_spawn_attempts(44, 1);
	expect_spawn_attempts(45, 0);

	property_file(1.0F);
	assert(initialize_properties()); // Older config with no key.
	expect_spawn_attempts(0, 1);
	expect_spawn_attempts(44, 1);
	expect_spawn_attempts(45, 0);

	const std::string base = read_file() + "random.mapmob.other=3\n";
	const std::string cap = "random.mapmob.populationCap";
	std::ofstream("lib/duris.properties") << base << cap << " = 2.000 \n";
	command(actor, "reload");
	expect_spawn_attempts(1, 1);
	expect_spawn_attempts(2, 0);
	command(actor, "set random.mapmob.populationCAP 60");
	expect_spawn_attempts(59, 1);
	expect_spawn_attempts(60, 0);
	command(actor, "save");
	assert(read_file().find(cap + "=60.000\n") != std::string::npos);
	command(actor, "set random.mapmob.populationCap 0");
	expect_spawn_attempts(0, 0);
	expect_spawn_attempts(2, 0);
	command(actor, "revert");
	expect_spawn_attempts(59, 1);
	command(actor, "set random.mapmob.populationCap 0");
	assert(initialize_properties()); // Same loader as process startup.
	expect_spawn_attempts(59, 1);
	expect_spawn_attempts(60, 0);

	for (const char *bad :
	     { "", "-1", "-0.00000001", "0.00000001", "2.00000001", "NaN", "Inf", "1e1000",
	       "1e-1000", "2147483647", "2147483648", "junk", "2junk", "2 3" })
	{
		output.clear();
		command(actor, (std::string("set random.mapmob.* ") + bad).c_str());
		assert(output.find("requires a nonnegative whole") != std::string::npos);
		assert(get_property("random.mapmob.other", 0.0) == 3);
		expect_spawn_attempts(59, 1);
		expect_spawn_attempts(60, 0);

		// Invalid startup input and reload use the same transactional loader.
		std::ofstream("lib/duris.properties") << base << cap << '=' << bad << '\n';
		output.clear();
		command(actor, "reload");
		assert(output.find("reload failed") != std::string::npos);
		expect_spawn_attempts(59, 1);
		expect_spawn_attempts(60, 0);
	}
	std::ofstream("lib/duris.properties") << base << cap << "=2147483520.000\n";
	command(actor, "reload");
	assert(get_property(cap.c_str(), 0.0) == 2147483520.0F);
	expect_spawn_attempts(60, 1);
}

int main(int argc, char **argv)
{
	char_data actor{};
	actor.player.level = FORGER;
	actor.player.name = const_cast<char *>("PropertyQa");
	if (argc == 2)
	{
		if (std::strcmp(argv[1], "mapmob-cap") == 0)
			check_mapmob_cap(&actor);
		else if (std::strcmp(argv[1], "mapmob-population") == 0)
			check_mapmob_population(&actor);
		else
			failure_case(&actor, argv[1]);
		for (int i = 0; i < properties_count; ++i)
			FREE(duris_properties[i].key);
		std::cout << "property scenario passed: " << argv[1] << '\n';
		return 0;
	}
	observations seen{}, other{};
	property_file(1.0F);
	initialize_properties(); // No observer: existing native behavior.
	assert(get_property("epic.touch.PayoutFactor", 1.0) == 1.0F);
	telemetry_config_property_capture capture{};
	capture.reader = { native_property_read, nullptr };
	capture.mode = telemetry_config_property_capture_mode::require_reader;
	telemetry_config_property_snapshot live_properties{};
	assert(telemetry_config_property_snapshot_capture(&capture, &live_properties) ==
	       telemetry_config_build_outcome::built);
	const auto defaults = telemetry_config_property_snapshot_defaults();
	assert(defaults.property_version == live_properties.property_version);
	capture.reader.read = overflowing_property_read;
	assert(telemetry_config_property_snapshot_capture(&capture, &live_properties) ==
	       telemetry_config_build_outcome::property_registry_invalid);
	capture.reader.read = native_property_read;
	assert(!telemetry_config_reload_register(nullptr, &seen));
	assert(telemetry_config_reload_register(observe, &seen));
	assert(telemetry_config_reload_register(observe, &seen));
	assert(!telemetry_config_reload_register(observe, &other));
	apply_properties();
	assert(seen.count == 1 && seen.values[0] == 1.0F);
	command(&actor, "set epic.touch.PayoutFactor 2.0");
	assert(seen.count == 2 && seen.values[1] == 2.0F);
	command(&actor, "revert");
	assert(seen.count == 3 && seen.values[2] == 1.0F);
	assert(output.find("reverted") != std::string::npos);
	command(&actor, "save");
	assert(seen.count == 3); // Saving without an effective change is not a reload.
	char_data online{}, npc{};
	actor.next = &npc;
	npc.next = &online;
	npc.specials.act = ACT_ISNPC;
	actor.curr_stats.Str = online.curr_stats.Str = npc.curr_stats.Str = 95;
	character_list = &actor;
	property_file(3.0F, 120);
	command(&actor, "reload");
	assert(seen.count == 4 && seen.values[3] == 3.0F);
	assert(rebalanced_characters == 3);
	assert(actor.curr_stats.Str == 120 && online.curr_stats.Str == 120 &&
	       npc.curr_stats.Str == 120);
	character_list = nullptr;
	command(&actor, "set epic.touch.PayoutFactor bad");
	assert(seen.count == 4);
	actor.player.level = 1;
	command(&actor, "set epic.touch.PayoutFactor 4.0");
	assert(seen.count == 4 && get_property("epic.touch.PayoutFactor", 1.0) == 3.0F);
	actor.player.level = FORGER;
	assert(!telemetry_config_reload_unregister(observe, &other));
	assert(telemetry_config_reload_unregister(observe, &seen));
	command(&actor, "set epic.touch.PayoutFactor 4.0");
	assert(seen.count == 4 && get_property("epic.touch.PayoutFactor", 1.0) == 4.0F);
	// Link both actual modules and use the owner's observer through the hook.
	telemetry_config_state owner{};
	telemetry_config_state_config owner_options{};
	assert(telemetry_config_state_init(&owner, &owner_options) ==
	       telemetry_config_state_outcome::accepted);
	assert(telemetry_config_reload_register(telemetry_config_reload_observer, &owner));
	command(&actor, "set epic.touch.PayoutFactor 5.0");
	assert(telemetry_config_reload_requested(&owner));
	assert(telemetry_config_property_snapshot_capture(&capture, &live_properties) ==
	       telemetry_config_build_outcome::built);
	assert(defaults.property_version != live_properties.property_version);
	telemetry_config_reload_request_clear(&owner);
	assert(!telemetry_config_reload_requested(&owner));
	assert(telemetry_config_reload_unregister(telemetry_config_reload_observer, &owner));
	command(&actor, "save");
	assert(saved_logs == 2);
	assert(read_file().find("epic.touch.PayoutFactor=5.000\n") != std::string::npos);
	output.clear();
	command(&actor, "diff");
	assert(output.empty());
	command(&actor, "set epic.touch.PayoutFactor 9");
	command(&actor, "revert");
	assert(get_property("epic.touch.PayoutFactor", 0.0) == 5);
	command(&actor, "reload");
	assert(get_property("epic.touch.PayoutFactor", 0.0) == 5);
	for (int i = 0; i < properties_count; ++i)
		FREE(duris_properties[i].key);
	std::cout
		<< "ISSUE263_PROPERTY_JOURNEY_OK: initialize/set/revert/save/reload; "
		   "post-cache notification; absent observer; ownership; malformed/unauthorized refusal\n";
}
