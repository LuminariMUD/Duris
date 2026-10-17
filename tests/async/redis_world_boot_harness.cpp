#include <hiredis/hiredis.h>
#include <functional>
#include <string>
#include <utility>

static std::function<void()> after_floor_values;
static void *observed_argv(redisContext *context, int argc, const char **argv,
			   const size_t *lengths)
{
	void *reply = redisCommandArgv(context, argc, argv, lengths);
	if (argc && std::string(argv[0], lengths[0]) == "HMGET" && after_floor_values)
	{
		auto mutation = std::exchange(after_floor_values, {});
		mutation(); // external write after the real read, before WATCH seals
	}
	return reply;
}
#define redisCommandArgv observed_argv
#include "redis/redis_world_runtime.c"
#undef redisCommandArgv

#include <cassert>
#include <iostream>
#include <limits>
#include <zlib.h>
#include <sys/socket.h>

static int generation_failure_phase = 0;
static int generation_failures_left = 0;
static int generation_read_attempts = 0;
extern "C" void *__real_redisvCommand(redisContext *, const char *, va_list);
extern "C" void *__wrap_redisvCommand(redisContext *context, const char *format, va_list arguments)
{
	bool injected = false;
	if (context != world_context && (!strcmp(format, "GET %s") || !strcmp(format, "STRLEN %s")))
	{
		va_list inspected;
		va_copy(inspected, arguments);
		const char *key = va_arg(inspected, const char *);
		va_end(inspected);
		const bool manifest = !strcmp(key, "mud:season:42:world_state:generation:1");
		if (manifest && !strcmp(format, "STRLEN %s"))
			++generation_read_attempts;
		if (generation_failures_left && !strcmp(format, "GET %s") &&
		    ((generation_failure_phase == 1 && manifest) ||
		     (generation_failure_phase == 2 && !manifest)))
		{
			--generation_failures_left;
			assert(world_context && !world_context->err && !context->err);
			assert(shutdown(context->fd, SHUT_RD) == 0);
			injected = true;
		}
	}
	void *reply = __real_redisvCommand(context, format, arguments);
	if (injected)
		assert(!reply && context->err && world_context && !world_context->err);
	return reply;
}

static void command(const char *format, const std::string &value = {})
{
	redisReply *reply = static_cast<redisReply *>(
		redisCommand(world_context, format, value.data(), value.size()));
	assert(reply && reply->type != REDIS_REPLY_ERROR);
	freeReplyObject(reply);
}

// REAL_GENERATION_VALIDATE

static int restore_calls = 0;
static bool restore_succeeds = true;
static std::vector<unsigned char> restored_generation;
static std::vector<std::vector<unsigned char>> restored_floors;
bool world_recovery_restore_with_floor(const unsigned char *data, size_t size, int age,
				       uint64_t sequence, const unsigned char *const *floor_records,
				       const size_t *floor_sizes, size_t floor_count,
				       world_recovery_header *header)
{
	++restore_calls;
	assert(world_recovery_validate(data, size, age, sequence, header));
	restored_generation.assign(data, data + size);
	restored_floors.clear();
	for (size_t index = 0; index < floor_count; ++index)
		restored_floors.emplace_back(floor_records[index],
					     floor_records[index] + floor_sizes[index]);
	return restore_succeeds;
}

static std::vector<unsigned char> floor_value(uint64_t uid, int vnum = 900)
{
	world_recovery_object_record object = { 1200, 1 };
	world_recovery_item_snapshot item = {};
	item.item_uid = item.root_item_uid = uid;
	item.vnum = vnum;
	item.extra_flags = 1U << 28;
	std::vector<unsigned char> native(sizeof object + sizeof item);
	memcpy(native.data(), &object, sizeof object);
	memcpy(native.data() + sizeof object, &item, sizeof item);
	std::vector<unsigned char> encoded;
	assert(world_recovery_encode_floor_object(native.data(), native.size(), &encoded));
	return encoded;
}

static std::vector<unsigned char> generation_value(uint64_t sequence)
{
	const auto object = floor_value(101);
	const size_t payload_size = WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES + object.size() -
				    WORLD_RECOVERY_FLOOR_PREFIX_BYTES;
	std::vector<unsigned char> bytes(WORLD_RECOVERY_WIRE_HEADER_BYTES + payload_size);
	assert(world_recovery_encode_record_header(world_recovery_record_type::object,
						   object.size() -
							   WORLD_RECOVERY_FLOOR_PREFIX_BYTES,
						   bytes.data() + WORLD_RECOVERY_WIRE_HEADER_BYTES,
						   WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES));
	memcpy(bytes.data() + WORLD_RECOVERY_WIRE_HEADER_BYTES +
		       WORLD_RECOVERY_WIRE_RECORD_HEADER_BYTES,
	       object.data() + WORLD_RECOVERY_FLOOR_PREFIX_BYTES,
	       object.size() - WORLD_RECOVERY_FLOOR_PREFIX_BYTES);
	world_recovery_header header = {};
	memcpy(header.magic, "WR12", 4);
	header.schema_version = WORLD_RECOVERY_SCHEMA_VERSION;
	header.header_size = WORLD_RECOVERY_WIRE_HEADER_BYTES;
	header.sequence = sequence;
	header.timestamp = time(nullptr);
	header.payload_size = payload_size;
	header.checksum = crc32(0, bytes.data() + WORLD_RECOVERY_WIRE_HEADER_BYTES, payload_size);
	header.object_count = 1;
	header.complete = 1;
	assert(world_recovery_encode_header(&header, bytes.data(), bytes.size()));
	return bytes;
}

static void put_floor(redisContext *context, uint64_t uid, const std::vector<unsigned char> &bytes)
{
	auto *reply = static_cast<redisReply *>(
		redisCommand(context, "HSET mud:season:42:floor_drops %llu %b",
			     static_cast<unsigned long long>(uid), bytes.data(), bytes.size()));
	assert(reply && reply->type == REDIS_REPLY_INTEGER);
	freeReplyObject(reply);
	reply = static_cast<redisReply *>(redisCommand(context,
						       "ZADD mud:season:42:floor_drop_index 0 %llu",
						       static_cast<unsigned long long>(uid)));
	assert(reply && reply->type == REDIS_REPLY_INTEGER);
	freeReplyObject(reply);
}

static void reset_boot()
{
	world_boot_prepared = false;
	world_boot_restored = false;
	world_boot_result = redis_world_boot_result::failed;
	world_boot_snapshot = {};
	clean_restart_boot = false;
	restore_calls = 0;
	restore_succeeds = true;
}

static void pinning_checks(redisContext *other, int port)
{
	world_authentication_secret = "world-recovery-authentication-secret-0001";
	setenv("REDIS_WORLD_STATE", "TRUE", 1);
	const auto config = redis_world_store_config_copy();
	constexpr const char *writer = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
	const auto first = generation_value(1), second = generation_value(2);
	const auto floor = floor_value(202), replacement = floor_value(202, 901);
	auto publish = [&](const auto &value, uint64_t sequence)
	{
		world_recovery_header header = {};
		assert(world_recovery_validate(value.data(), value.size(), world_state_max_age,
					       sequence, &header));
		assert(redis_world_store_publish(&config, writer, 600000, value.data(),
						 value.size(), sequence, header.timestamp,
						 header.checksum));
	};
	auto seeded = [&]
	{
		reset_boot();
		if (!world_context || world_context->err)
			assert(redis_reconnect());
		command("FLUSHDB");
		assert(redis_world_store_claim_fence(&config, writer, 600000));
		publish(first, 1);
		put_floor(other, 202, floor);
	};
	for (int phase : { 1, 2 })
	{
		seeded();
		generation_read_attempts = 0;
		generation_failure_phase = phase;
		generation_failures_left = 1;
		assert(redis_world_prepare_boot() == redis_world_boot_result::ready &&
		       "a dedicated generation read failure bypassed boot retry");
		assert(generation_read_attempts == 2 && !generation_failures_left &&
		       redis_world_boot_evidence()->generation == first);
	}
	seeded();
	generation_read_attempts = 0;
	generation_failure_phase = 1;
	generation_failures_left = WORLD_BOOT_READ_ATTEMPTS;
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       generation_read_attempts == WORLD_BOOT_READ_ATTEMPTS &&
	       !redis_world_boot_evidence());
	generation_failure_phase = 0;
	seeded();
	clean_shutdown_sequence = 1;
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready);
	const auto *pinned = redis_world_boot_evidence();
	assert(pinned && pinned->sequence == 1 && pinned->generation == first &&
	       pinned->floor_records.size() == 1 && pinned->floor_records[0] == floor &&
	       restore_calls == 0 && redis_world_clean_restart_boot());
	// Advancing the real head also clears/replaces the floor in Redis. Preparation
	// remains idempotent and the load still receives the original sealed bytes.
	publish(second, 2);
	put_floor(other, 202, replacement);
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready &&
	       redis_world_boot_evidence() == pinned);
	assert(redis_load_world_state() && restore_calls == 1 && restored_generation == first &&
	       restored_floors.size() == 1 &&
	       restored_floors[0] ==
		       std::vector<unsigned char>(floor.begin() + WORLD_RECOVERY_FLOOR_PREFIX_BYTES,
						  floor.end()));
	assert(!redis_load_world_state() && restore_calls == 1);
	assert(!redis_consume_world_state());
	uint64_t sequence = 0;
	assert(redis_world_boot_sequence(&sequence) && sequence == 2);
	std::vector<std::vector<unsigned char>> current_floors;
	assert(redis_read_floor_records(&current_floors, WORLD_RECOVERY_MAX_FLOOR_BYTES) &&
	       current_floors[0] == replacement);

	seeded();
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready &&
	       redis_load_world_state());
	put_floor(other, 202, replacement); // same hash/index count, different bytes
	assert(!redis_consume_world_state());
	assert(redis_world_boot_sequence(&sequence) && sequence == 1);
	put_floor(other, 202, floor);
	assert(redis_consume_world_state() && !redis_consume_world_state());
	assert(redis_world_boot_sequence(&sequence) && !sequence);
	assert(redis_read_floor_records(&current_floors, WORLD_RECOVERY_MAX_FLOOR_BYTES) &&
	       current_floors.empty());

	seeded();
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready);
	restore_succeeds = false;
	assert(!redis_load_world_state() && !redis_consume_world_state());
	assert(redis_world_boot_sequence(&sequence) && sequence == 1);
	restore_succeeds = true;
	assert(redis_load_world_state() && redis_consume_world_state());

	seeded();
	auto wrong_generation = first;
	wrong_generation.back() ^= 1;
	assert(!redis_world_store_consume_generation(&config, 1, wrong_generation, { floor }));
	assert(redis_world_boot_sequence(&sequence) && sequence == 1);
	put_floor(other, 303, floor_value(303));
	// Repeating one expected UID must not satisfy the count and delete an
	// unexamined second value. Reject the contradictory consume input intact.
	assert(!redis_world_store_consume_generation(&config, 1, first, { floor, floor }));
	assert(redis_read_floor_records(&current_floors, WORLD_RECOVERY_MAX_FLOOR_BYTES) &&
	       current_floors.size() == 2);
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready &&
	       redis_load_world_state() && redis_consume_world_state());

	// Replace a value after its actual HMGET reply. The original count checks
	// still pass, but WATCH must abort, publish no prefix and leave Redis intact.
	seeded();
	after_floor_values = [&] { put_floor(other, 202, replacement); };
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       !redis_world_boot_evidence());
	assert(!redis_load_world_state() && restore_calls == 0);
	assert(redis_read_floor_records(&current_floors, WORLD_RECOVERY_MAX_FLOOR_BYTES) &&
	       current_floors[0] == replacement);
	// Failure stays failed for this boot, even when storage is repaired later.
	put_floor(other, 202, floor);
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed);

	seeded();
	after_floor_values = [&] { publish(second, 2); };
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       !redis_world_boot_evidence());
	assert(redis_world_boot_sequence(&sequence) && sequence == 2);

	seeded();
	redisReply *id = static_cast<redisReply *>(redisCommand(world_context, "CLIENT ID"));
	assert(id && id->type == REDIS_REPLY_INTEGER);
	const auto connection_id = id->integer;
	freeReplyObject(id);
	after_floor_values = [&]
	{
		auto *killed = static_cast<redisReply *>(
			redisCommand(other, "CLIENT KILL ID %lld", connection_id));
		assert(killed && killed->type == REDIS_REPLY_INTEGER && killed->integer == 1);
		freeReplyObject(killed);
	};
	assert(redis_world_prepare_boot() == redis_world_boot_result::ready &&
	       redis_world_boot_evidence()->floor_records[0] == floor);

	seeded();
	assert(redis_status(
		static_cast<redisReply *>(redisCommand(
			other, "ACL SETUSER pin-reader on >fixture-password +@all -exec ~*")),
		"OK"));
	const auto *original_connection = world_connection;
	redis_connection_options restricted_options = {
		"127.0.0.1",	    port,  250,	    100,     0,	    "pin-reader",
		"fixture-password", false, nullptr, nullptr, false, nullptr
	};
	auto *restricted = redis_connection_settings_create(&restricted_options);
	assert(restricted);
	redisFree(world_context);
	world_connection = restricted;
	world_context = redis_connection_open(restricted);
	assert(world_context && !world_context->err);
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       !redis_world_boot_evidence());
	if (!world_context || world_context->err)
	{
		if (world_context)
			redisFree(world_context);
		world_context = redis_connection_open(restricted);
	}
	assert(redis_status(static_cast<redisReply *>(redisCommand(world_context, "PING")),
			    "PONG"));
	redisFree(world_context);
	world_connection = original_connection;
	world_context = redis_connection_open(world_connection);
	redis_connection_settings_destroy(restricted);
	assert(world_context && !world_context->err);
	auto *deleted = static_cast<redisReply *>(redisCommand(other, "ACL DELUSER pin-reader"));
	assert(deleted && deleted->type == REDIS_REPLY_INTEGER && deleted->integer == 1);
	freeReplyObject(deleted);

	reset_boot();
	command("FLUSHDB");
	assert(redis_world_prepare_boot() == redis_world_boot_result::absent &&
	       redis_world_boot_evidence() && !redis_world_boot_evidence()->sequence);
	reset_boot();
	put_floor(other, 202, floor);
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       !redis_world_boot_evidence());
	reset_boot();
	command("FLUSHDB");
	command("SET mud:season:42:world_state:current %b", "-1");
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed);
	seeded();
	command("SET mud:season:42:world_state:generation:1 %b", "bad manifest");
	generation_read_attempts = 0;
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       generation_read_attempts == 1);
	seeded();
	command("HSET mud:season:42:floor_drops 202 %b", "bad floor");
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed);
	reset_boot();
	world_enabled = false;
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed);
	reset_boot();
	setenv("REDIS_WORLD_STATE", "FALSE", 1);
	assert(redis_world_prepare_boot() == redis_world_boot_result::disabled &&
	       !redis_world_boot_evidence());
	world_enabled = true;
	setenv("REDIS_WORLD_STATE", "TRUE", 1);
	command("FLUSHDB");
	std::cout
		<< "pinned boot evidence, real concurrent changes, exact-byte load and atomic consume passed\n";
}

int main(int argc, char **argv)
{
	assert(argc == 2);
	redis_connection_options options = { "127.0.0.1", atoi(argv[1]), 250,	  100,
					     0,		  nullptr,	 nullptr, false,
					     nullptr,	  nullptr,	 false,	  nullptr };
	redis_connection_settings *settings = redis_connection_settings_create(&options);
	assert(settings);
	world_connection = settings;
	world_context = redis_connection_open(settings);
	assert(world_context && !world_context->err);
	world_runtime_epoch = 42;
	world_key_namespace = "mud";
	// Startup configuration can fail before the world runtime starts.
	setenv("REDIS", "TRUE", 1);
	setenv("REDIS_WORLD_STATE", "TRUE", 1);
	world_enabled = false;
	reset_boot();
	assert(redis_world_prepare_boot() == redis_world_boot_result::failed &&
	       "requested recovery was reported disabled after startup failure");
	reset_boot();
	setenv("REDIS", "FALSE", 1);
	assert(redis_world_prepare_boot() == redis_world_boot_result::disabled);
	setenv("REDIS", "TRUE", 1);
	reset_boot();
	world_enabled = true;
	command("DEL mud:season:42:world_state:current");
	uint64_t sequence = 99;
	assert(redis_world_boot_sequence(&sequence) && sequence == 0);
	for (const std::string &value : { std::string("1"), std::string("18446744073709551615") })
	{
		command("SET mud:season:42:world_state:current %b", value);
		assert(redis_world_boot_sequence(&sequence));
		assert(sequence == (value == "1" ? 1 : std::numeric_limits<uint64_t>::max()));
	}
	for (const std::string &value :
	     std::vector<std::string>{ "", "0", "-1", "+1", " 1", "1 ", "1x",
				       "18446744073709551616", std::string("1\0x", 3) })
	{
		command("SET mud:season:42:world_state:current %b", value);
		sequence = 99;
		assert(!redis_world_boot_sequence(&sequence));
		assert(sequence == 0);
	}
	command("DEL mud:season:42:world_state:current");
	command("LPUSH mud:season:42:world_state:current bad");
	sequence = 99;
	assert(!redis_world_boot_sequence(&sequence) && sequence == 0);
	command("DEL mud:season:42:world_state:current");
	// The previous strtoull path accepted -1 as UINT64_MAX. Use an actual
	// encoded maximum-UID record so refusal cannot be explained by a UID mismatch.
	world_recovery_object_record object = { 1200, 1 };
	world_recovery_item_snapshot item = {};
	item.item_uid = item.root_item_uid = std::numeric_limits<uint64_t>::max();
	item.vnum = 900;
	std::vector<unsigned char> native(sizeof(object) + sizeof(item));
	memcpy(native.data(), &object, sizeof(object));
	memcpy(native.data() + sizeof(object), &item, sizeof(item));
	std::vector<unsigned char> encoded;
	assert(world_recovery_encode_floor_object(native.data(), native.size(), &encoded));
	for (const std::string &field : std::vector<std::string>{
		     "18446744073709551615", "-1", "+18446744073709551615", "18446744073709551615x",
		     std::string("18446744073709551615\0x", 22) })
	{
		command("DEL mud:season:42:floor_drops mud:season:42:floor_drop_index");
		redisReply *reply = static_cast<redisReply *>(
			redisCommand(world_context, "HSET mud:season:42:floor_drops %b %b",
				     field.data(), field.size(), encoded.data(), encoded.size()));
		assert(reply && reply->type == REDIS_REPLY_INTEGER && reply->integer == 1);
		freeReplyObject(reply);
		reply = static_cast<redisReply *>(
			redisCommand(world_context, "ZADD mud:season:42:floor_drop_index 0 %b",
				     field.data(), field.size()));
		assert(reply && reply->type == REDIS_REPLY_INTEGER && reply->integer == 1);
		freeReplyObject(reply);
		std::vector<std::vector<unsigned char>> records;
		const bool valid = field == "18446744073709551615";
		assert(redis_read_floor_records(&records, WORLD_RECOVERY_MAX_FLOOR_BYTES) == valid);
		assert(records.size() == (valid ? 1 : 0));
	}
	command("DEL mud:season:42:floor_drops mud:season:42:floor_drop_index");

	redisContext *other = redis_connection_open(settings);
	assert(other && !other->err);
	pinning_checks(other, atoi(argv[1]));
	redisFree(other);
	redisFree(world_context);
	world_context = nullptr;
	world_connection = nullptr;
	redis_connection_settings_destroy(settings);
	std::cout << "strict Redis recovery head and floor UID parsing passed\n";
}
