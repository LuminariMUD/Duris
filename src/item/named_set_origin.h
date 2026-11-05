#ifndef DURIS_NAMED_SET_ORIGIN_H
#define DURIS_NAMED_SET_ORIGIN_H

#include <string>

struct obj_data;

struct named_set_identity
{
	int zone = 0; // Positive virtual ID; -1 means invalid metadata.
	std::string legacy_title; // Only ambiguous, unmarked historical items group by title.
};

named_set_identity named_set_origin(const obj_data *object);
bool set_named_set_origin(obj_data *object, int zone);

#endif
