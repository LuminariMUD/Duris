#ifndef DURIS_NAMED_SET_ORIGIN_H
#define DURIS_NAMED_SET_ORIGIN_H

#include <string>

struct obj_data;

struct named_set_identity
{
	int zone = 0; // Positive virtual ID; -1 means invalid metadata.
	std::string legacy_title; // Only unproved, unmarked historical items group by title.
	int legacy_group = 0; // Identifies that group; used only as a negative HP context.
};

named_set_identity named_set_origin(const obj_data *object);
bool set_named_set_origin(obj_data *object, int zone);

#endif
