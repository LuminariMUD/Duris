#include "redis/redis_world_runtime.c"

#include <cassert>
#include <iostream>
#include <limits>

static void command(const char *format, const std::string &value = {})
{
	redisReply *reply = static_cast<redisReply *>(
		redisCommand(world_context, format, value.data(), value.size()));
	assert(reply && reply->type != REDIS_REPLY_ERROR);
	freeReplyObject(reply);
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

	redisFree(world_context);
	world_context = nullptr;
	world_connection = nullptr;
	redis_connection_settings_destroy(settings);
	std::cout << "strict Redis recovery head and floor UID parsing passed\n";
}
