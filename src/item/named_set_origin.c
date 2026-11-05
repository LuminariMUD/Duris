#include "item/named_set_origin.h"

#include "core/prototypes.h"
#include "core/utils.h"
#include "item/random_equipment.h"
#include "sql/item_extra_descr_codec.h"
#include "world/db.h"
#include "world/vnum.obj.h"

extern P_index obj_index;
extern int top_of_zone_table;

named_set_identity named_set_origin(const obj_data *object)
{
	if (!object)
		return {};
	int origin = 0;
	for (const extra_descr_data *description = object->ex_description; description;
	     description = description->next)
	{
		int zone = 0;
		const auto status = sql_decode_named_set_origin(
			description->keyword ? description->keyword : "",
			description->description ? description->description : "", &zone);
		if (status == sql_named_set_origin_decode_status::invalid ||
		    (status == sql_named_set_origin_decode_status::decoded && origin))
			return { -1, {} };
		if (status == sql_named_set_origin_decode_status::decoded)
			origin = zone;
	}
	if (origin)
		return { origin, {} };
	if (object->R_num < 0 || !object->short_description || !zone_table ||
	    (obj_index[object->R_num].virtual_number != VOBJ_RANDOM_ARMOR &&
	     obj_index[object->R_num].virtual_number != VOBJ_RANDOM_WEAPON))
		return {};
	const char *tag = strstr(object->short_description, " &+rfrom ");
	if (!tag)
		return {};
	const std::string title = strip_ansi(tag + strlen(" &+rfrom "));
	std::string suffix;
	if (object->value[5])
		for (const auto &spell : spells_data)
			if (spell.spell == object->value[5] && *spell.name)
			{
				suffix = " of " + strip_ansi(spell.name);
				break;
			}
	// c79fde573 replaced #150 with #3000. Their indistinguishable old tags
	// cannot prove either origin, even if one producer is no longer loaded.
	constexpr const char *misty_legacy_title = "The Chasm of the Misty Vale";
	if (title == misty_legacy_title ||
	    (!suffix.empty() && title == std::string(misty_legacy_title) + suffix))
		return { 0, misty_legacy_title };
	std::string matched_title;
	int matches = 0;
	int legacy_group = 0;
	for (int i = 0; i <= top_of_zone_table; ++i)
	{
		if (zone_table[i].number <= 0 || !zone_table[i].name)
			continue;
		const std::string candidate = strip_ansi(zone_table[i].name);
		if (title != candidate && (suffix.empty() || title != candidate + suffix))
			continue;
		origin = zone_table[i].number;
		if (!legacy_group || origin < legacy_group)
			legacy_group = origin;
		matched_title = matches && matched_title != candidate ? title : candidate;
		++matches;
	}
	if (matches == 1)
		return { origin, {} };
	if (matches > 1)
		return { 0, matched_title, legacy_group };
	return {};
}

bool set_named_set_origin(obj_data *object, int zone)
{
	if (!object || zone <= 0)
		return false;
	for (const extra_descr_data *description = object->ex_description; description;
	     description = description->next)
		if (description->keyword &&
		    !strcmp(description->keyword, SQL_ITEM_NAMED_SET_ORIGIN_KEYWORD))
			return named_set_origin(object).zone == zone;
	extra_descr_data *description;
	CREATE(description, extra_descr_data, 1, MEM_TAG_EXDESCD);
	description->keyword = str_dup(SQL_ITEM_NAMED_SET_ORIGIN_KEYWORD);
	description->description = str_dup(std::to_string(zone).c_str());
	description->next = object->ex_description;
	object->ex_description = description;
	object->str_mask |= STRUNG_EDESC;
	return true;
}
