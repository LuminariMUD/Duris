#ifndef DURIS_LEGACY_OBJECT_IDENTITY_H
#define DURIS_LEGACY_OBJECT_IDENTITY_H

#include <cstddef>
#include <cstdint>

struct legacy_object_identity
{
	int32_t vnum = 0;
	uint64_t item_uid = 0;
	uint32_t extra_flags = 0;
	bool extra_flags_present = false;
};

// Inspect exactly one write_one_object() frame, with an optional trailing NUL.
// Uses the legacy native-width/native-endian wire contract. No template lookup,
// materialization, UID assignment or gameplay mutation. Failure preserves output.
bool legacy_object_identity_read(const unsigned char *data, size_t size,
				 legacy_object_identity *identity);

#endif
