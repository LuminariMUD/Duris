#include "item/legacy_object_identity.h"
#include "core/files.h"
#include "sql/item_extra_descr_codec.h"

#include <array>
#include <cassert>
#include <cstring>
#include <iostream>

static int int_size = sizeof(int), short_size = sizeof(short), long_size = sizeof(long);
static int save_count = 0, template_reads = 0, extractions = 0;
static obj_data prototype = {};
static index_data indices[1] = {};
P_index obj_index = indices;
static std::array<char, (MAX_SKILLS / 8) + 1> bitmap = {};
static extra_descr_data spell_description = {};

P_obj read_object(int, int)
{
	++template_reads;
	return &prototype;
}
void extract_obj(P_obj object, int)
{
	assert(object == &prototype);
	++extractions;
}
void persistence_assign_item_uid(P_obj object, const char *)
{
	if (!object->obj_uid)
		object->obj_uid = 1234;
}
int obj_affect_time(P_obj, obj_affect *)
{
	return 50;
}
extra_descr_data *find_spell_description(P_obj object)
{
	return object->type == ITEM_SPELLBOOK ? &spell_description : nullptr;
}

// LEGACY_WRITER_FUNCTIONS

static void inspect(const obj_data &object, bool include_uid, bool flags_present,
		    uint32_t expected_flags)
{
	std::array<char, SAV_MAXSIZE> bytes = {};
	obj_data captured = object;
	const int size = write_one_object(&captured, bytes.data(), include_uid);
	assert(size > 0);
	const int reads = template_reads, extracted = extractions;
	const auto *data = reinterpret_cast<const unsigned char *>(bytes.data());
	legacy_object_identity identity;
	assert(legacy_object_identity_read(data, size, &identity));
	assert(identity.vnum == 91234 && identity.item_uid == (include_uid ? captured.obj_uid : 0));
	assert(identity.extra_flags_present == flags_present &&
	       identity.extra_flags == expected_flags);
	assert(legacy_object_identity_read(data, size + 1, &identity));
	for (int length = 0; length < size; ++length)
	{
		identity = { -7, 99, 77, true };
		assert(!legacy_object_identity_read(data, length, &identity));
		assert(identity.vnum == -7 && identity.item_uid == 99 &&
		       identity.extra_flags == 77 && identity.extra_flags_present);
	}
	assert(!legacy_object_identity_read(data, SAV_MAXSIZE + 1, &identity));
	const auto original_flags = bytes[1 + sizeof(int)];
	for (const auto invalid : { O_F_CONTAINS, O_F_WORN })
	{
		bytes[1 + sizeof(int)] = static_cast<char>(original_flags | invalid);
		assert(!legacy_object_identity_read(data, size, &identity));
	}
	bytes[1 + sizeof(int)] = original_flags;
	const uint32_t count = 2;
	memcpy(bytes.data() + 1, &count, sizeof(count));
	assert(!legacy_object_identity_read(data, size, &identity));
	const uint32_t single = 1;
	memcpy(bytes.data() + 1, &single, sizeof(single));
	bytes[size] = 1;
	assert(!legacy_object_identity_read(data, size + 1, &identity));
	bytes[0] = SAV_ITEMVERS + 1;
	assert(!legacy_object_identity_read(data, size, &identity));
	if (!include_uid)
	{
		bytes[0] = 35;
		assert(legacy_object_identity_read(data, size, &identity));
	}
	else
	{
		bytes[0] = 35;
		assert(!legacy_object_identity_read(data, size, &identity));
	}
	assert(template_reads == reads && extractions == extracted);
}

int main()
{
	indices[0].virtual_number = 91234;
	prototype.R_num = 0;
	prototype.name = const_cast<char *>("stock");
	prototype.description = const_cast<char *>("Stock is here.");
	prototype.short_description = const_cast<char *>("stock");
	prototype.action_description = const_cast<char *>("");
	obj_data object = prototype;
	inspect(object, false, false, 0);
	inspect(object, true, false, 0);
	prototype.type = ITEM_SPELLBOOK;
	object = prototype;
	spell_description.description = bitmap.data();
	inspect(object, false, false, 0);
	inspect(object, true, false, 0);
	prototype.type = 0;
	object = prototype;
	prototype.extra_flags = ITEM_ARTIFACT;
	object.extra_flags = 0;
	inspect(object, true, true, 0);
	prototype.extra_flags = 0;
	object.extra_flags = ITEM_ARTIFACT;
	object.obj_uid = UINT64_MAX;
	object.name = const_cast<char *>("changed name");
	object.description = const_cast<char *>("Changed description.");
	object.short_description = const_cast<char *>("changed short");
	object.action_description = const_cast<char *>("changed action");
	object.str_mask = O_U_KEYS | O_U_DESC1 | O_U_DESC2 | O_U_DESC3 | STRUNG_EDESC;
	extra_descr_data description = {};
	description.keyword = const_cast<char *>("runes");
	description.description = const_cast<char *>("changed runes");
	object.ex_description = &description;
	object.type = ITEM_SPELLBOOK;
	spell_description.description = bitmap.data();
	for (int index = 0; index < 8; ++index)
		object.value[index] = index + 10;
	for (int index = 0; index < 4; ++index)
		object.timer[index] = index + 20;
	object.trap_charge = 1;
	object.wear_flags = 1;
	object.anti_flags = 1;
	object.anti2_flags = 2;
	object.extra2_flags = 3;
	object.weight = 4;
	object.material = 1;
	object.cost = 5;
	object.bitvector = 1;
	object.bitvector2 = 2;
	object.bitvector3 = 3;
	object.bitvector4 = 4;
	object.bitvector5 = 5;
	object.affected[0].location = 1;
	object.affected[0].modifier = -2;
	obj_affect affect = {};
	object.affects = &affect;
	inspect(object, false, true, ITEM_ARTIFACT);
	inspect(object, true, true, ITEM_ARTIFACT);
	std::cout
		<< "legacy identity inspection matches the actual serializer, preserves flag overrides, "
		   "rejects every truncation and performs no materialization\n";
}
