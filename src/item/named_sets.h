#ifndef DURIS_NAMED_SETS_H
#define DURIS_NAMED_SETS_H

#include <cstddef>

struct named_set_definition
{
	int zone;
	int proc_spells[3][2]; // Matching pieces, effect ID; unused tiers are zero.
};

extern const named_set_definition named_sets[];
extern const size_t named_set_count;

bool named_set_effect_supported(int effect);
bool validate_named_sets();

#endif
