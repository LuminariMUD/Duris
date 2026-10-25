#include "core/prototypes.h"
#include "core/utils.h"
#include "core/files.h"
#include "core/mm.h"
#include "combat/trap_legacy.h"
#include "account/account_reward_snapshot.h"
#include "sql/item_extra_descr_codec.h"
#include "item/encumbrance_policy.h"
#include "magic/spells.h"
#include <mysql.h>
#include <array>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

static int int_size = sizeof(int), short_size = sizeof(short), long_size = sizeof(long);
static int save_count, obj_vers, corpse_room;
static obj_data prototype = {};
static index_data indexes[1] = {};
P_index obj_index = indexes;
P_obj save_equip[MAX_WEAR] = {};
unsigned long next_obj_uid = 1;
static P_obj placed;
static std::vector<P_obj> placed_objects;
static bool sql_row_read;
static char sql_trap[128];
MYSQL *DB = reinterpret_cast<MYSQL *>(1);

char *str_dup(const char *text)
{
	return text ? strdup(text) : nullptr;
}
void str_free(const char *text)
{
	free(const_cast<char *>(text));
}
void *__malloc(size_t bytes, const char *, const char *, int)
{
	return calloc(1, bytes);
}
void __free(void *ptr, const char *, int)
{
	free(ptr);
}
void extract_obj(P_obj object, int)
{
	if (!object)
		return;
	if (object->str_mask & STRUNG_KEYS)
		free(object->name);
	if (object->str_mask & STRUNG_DESC1)
		free(object->description);
	if (object->str_mask & STRUNG_DESC2)
		free(object->short_description);
	if (object->str_mask & STRUNG_DESC3)
		free(object->action_description);
	assert(!object->ex_description && !object->affects);
	delete object;
}
P_obj read_object(int, int)
{
	return new obj_data(prototype);
}
void persistence_assign_item_uid(P_obj object, const char *)
{
	object->obj_uid = 1234;
}
int obj_affect_time(P_obj, obj_affect *)
{
	return 0;
}
extra_descr_data *find_spell_description(P_obj)
{
	return nullptr;
}
void set_obj_affected(P_obj, int, sh_int, sh_int)
{
	std::abort();
}
void set_obj_affected_extra(P_obj, int, sh_int, sh_int, ulong)
{
	std::abort();
}
int affect_from_obj(P_obj, sh_int)
{
	std::abort();
}
void proclib_obj_event(P_char, P_char, P_obj, void *)
{
	std::abort();
}
P_nevent get_scheduled(P_obj, event_func)
{
	return nullptr;
}
int number(int low, int)
{
	return low;
}
nevent_schedule_result add_event(event_func, int, P_char, P_char, P_obj, int, const void *, int)
{
	std::abort();
}
void obj_to_room(P_obj object, int)
{
	placed = object;
	placed_objects.push_back(object);
}
void obj_to_char_at_end(P_obj, P_char)
{
	std::abort();
}
void obj_to_obj_at_end(P_obj, P_obj)
{
	std::abort();
}
void writeSavedItem(P_obj)
{
	std::abort();
}
MYSQL_RES *db_query(const char *, ...)
{
	sql_row_read = false;
	return reinterpret_cast<MYSQL_RES *>(1);
}
extern "C" MYSQL_ROW mysql_fetch_row(MYSQL_RES *)
{
	if (sql_row_read)
		return nullptr;
	sql_row_read = true;
	static char *row[2];
	row[0] = const_cast<char *>(SQL_ITEM_TRAP_STATE_KEYWORD);
	row[1] = sql_trap;
	return row;
}
extern "C" void mysql_free_result(MYSQL_RES *) {}
static bool sql_merge_duplicate_spellbook(extra_descr_data *, extra_descr_data *)
{
	std::abort();
}
static void sql_load_item_extra_descr_values(const char *, const char *, extra_descr_data *,
					     const char *, int)
{
	std::abort();
}

// FILE_FUNCTIONS
// SQL_FUNCTIONS

struct row
{
	int vnum;
	std::array<int, 4> old, final;
	bool finite;
};
static const row manifest[] = {
	// GOLDEN_ROWS
};

static std::array<int, 4> fields(P_obj object)
{
	return { object->trap_eff, object->trap_dam, object->trap_charge, object->trap_level };
}
static void set(P_obj object, const std::array<int, 4> &state)
{
	object->trap_eff = state[0];
	object->trap_dam = state[1];
	object->trap_charge = state[2];
	object->trap_level = state[3];
}
static void round_trip(P_obj object, const std::array<int, 4> &expected)
{
	const int vnum = indexes[0].virtual_number;
	const bool legacy_container =
		object->trap_level == 60 &&
		((vnum == 142251 && object->trap_eff == 1536 && object->trap_dam == 12) ||
		 (vnum == 142438 && object->trap_eff == 512 && object->trap_dam == 9));
	const int expected_flags = legacy_container && !object->value[1] ? 1 : object->value[1];
	for (int pass = 0; pass < 2; ++pass)
	{
		std::array<char, SAV_MAXSIZE> bytes = {};
		assert(write_one_object(object, bytes.data(), true) > 0);
		P_obj restored = read_one_object(bytes.data());
		assert(restored && fields(restored) == expected);
		assert(restored->value[3] == 7 && restored->value[1] == expected_flags);
		extract_obj(restored, FALSE);
		placed = nullptr;
		placed_objects.clear();
		assert(restoreObjects(bytes.data(), nullptr, 0));
		assert(placed && fields(placed) == expected && placed->value[3] == 7 &&
		       placed->value[1] == expected_flags);
		extract_obj(placed, FALSE);
		placed_objects.clear();
		assert(sql_encode_item_trap_state(object->trap_eff, object->trap_dam,
						  object->trap_charge, object->trap_level, sql_trap,
						  sizeof(sql_trap)));
		restored = read_object(0, REAL);
		assert(sql_load_item_extra_descr_from_table(1, restored, "saved_item"));
		assert(fields(restored) == expected && restored->value[1] == expected_flags);
		extract_obj(restored, FALSE);
		char *json = account_reward_snapshot_serialize(object);
		assert(json);
		restored = read_object(0, REAL);
		assert(account_reward_snapshot_apply(restored, json,
						     ACCOUNT_REWARD_TEMPLATE_VERSION));
		assert(fields(restored) == expected && restored->value[3] == 7 &&
		       restored->value[1] == expected_flags);
		extract_obj(restored, FALSE);
		free(json);
		set(object, expected);
		object->value[1] = expected_flags;
	}
}

static void counted_round_trip(const row &entry, int charge)
{
	indexes[0].virtual_number = entry.vnum;
	set(&prototype, entry.old);
	prototype.trap_charge = charge;
	std::array<char, SAV_MAXSIZE> bytes = {};
	char *cursor = bytes.data();
	ADD_BYTE(cursor, SAV_ITEMVERS);
	ADD_INT(cursor, 2);
	cursor += writeObject(&prototype, O_F_COUNT, 0, 2, 0, cursor);
	ADD_BYTE(cursor, O_F_EOL);
	placed_objects.clear();
	assert(restoreObjects(bytes.data(), nullptr, 0));
	assert(placed_objects.size() == 2);
	auto expected = entry.final;
	if (expected[0])
		expected[2] = entry.finite && (charge == -1 || charge > 1) ? 1 : charge;
	for (P_obj restored : placed_objects)
	{
		assert(fields(restored) == expected && restored->value[3] == 7);
		extract_obj(restored, FALSE);
	}
	placed_objects.clear();
}

int main()
{
	prototype.type = ITEM_CONTAINER;
	prototype.value[3] = 7;
	prototype.name = const_cast<char *>("chest");
	prototype.description = const_cast<char *>("A chest is here.");
	prototype.short_description = const_cast<char *>("a chest");
	prototype.action_description = const_cast<char *>("");
	for (const auto &entry : manifest)
	{
		indexes[0].virtual_number = entry.vnum;
		set(&prototype, entry.old);
		for (int charge : { -2, -1, 0, 1, 2, 100 })
		{
			obj_data object = prototype;
			object.trap_charge = charge;
			auto expected = entry.final;
			if (expected[0])
				expected[2] = entry.finite && (charge == -1 || charge > 1) ? 1 :
											     charge;
			// Test every owner on original stored fields, not only a normalized helper result.
			obj_data original = object;
			normalize_legacy_trap(&object, entry.vnum);
			assert(fields(&object) == expected && object.value[3] == 7);
			normalize_legacy_trap(&object, entry.vnum);
			assert(fields(&object) == expected);
			round_trip(&original, expected);
			for (int changed : { 0, 1, 3 })
			{
				obj_data custom = prototype;
				auto state = entry.old;
				++state[changed];
				state[2] = charge;
				set(&custom, state);
				normalize_legacy_trap(&custom, entry.vnum);
				assert(fields(&custom) == state);
				round_trip(&custom, state);
			}
		}
	}
	for (const auto &entry : manifest)
		for (int charge : { -1, 0, 1, 2, 100 })
			counted_round_trip(entry, charge);
	// A single custom field must force a binary payload and prevent stock grouping.
	for (int field = 0; field < 4; ++field)
	{
		obj_data custom = prototype;
		auto state = fields(&prototype);
		++state[field];
		set(&custom, state);
		assert(ObjUniqueFlags(&custom, &prototype) & O_U_TRAP);
		assert(!ObjectsMatch(&custom, &prototype));
	}
	for (int vnum : { 67803, 142233, 142251, 142438 })
	{
		indexes[0].virtual_number = vnum;
		prototype.trap_eff = vnum == 142251 ? 1536 : 512;
		prototype.trap_dam = vnum == 142251 ? 12 : 9;
		prototype.trap_level = 60;
		prototype.trap_charge = 0;
		for (int flags : { 0, 1, 4, 5, 17, 21 })
		{
			obj_data object = prototype;
			object.value[1] = flags;
			const int expected = (vnum == 142251 || vnum == 142438) && !flags ? 1 :
											    flags;
			normalize_legacy_trap(&object, vnum);
			assert(object.value[1] == expected && object.trap_charge == 0);
			normalize_legacy_trap(&object, vnum);
			assert(object.value[1] == expected);
			object.value[1] = flags;
			// SQL rows and reward/binary snapshots must apply the repair after values[].
			prototype.value[1] = flags;
			round_trip(&object, fields(&object));
		}
	}
}
