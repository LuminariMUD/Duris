#include "item/legacy_object_identity.h"

#include "core/files.h"

namespace
{
struct cursor
{
	const unsigned char *data;
	size_t remaining;

	template <typename T> bool read(T *value)
	{
		if (sizeof(T) > remaining)
			return false;
		memcpy(value, data, sizeof(T));
		data += sizeof(T);
		remaining -= sizeof(T);
		return true;
	}

	bool skip(size_t count)
	{
		if (count > remaining)
			return false;
		data += count;
		remaining -= count;
		return true;
	}

	bool string()
	{
		uint16_t size = 0;
		return read(&size) && skip(size);
	}
};
} // namespace

bool legacy_object_identity_read(const unsigned char *data, size_t size,
				 legacy_object_identity *identity)
{
	static_assert(sizeof(int) == 4 && sizeof(short) == 2);
	if (!data || !identity || !size || size > SAV_MAXSIZE)
		return false;
	cursor input{ data, size };
	legacy_object_identity staged;
	uint8_t version = 0, flags = 0;
	uint32_t count = 0, unique = 0;
	if (!input.read(&version) || version > SAV_ITEMVERS || !input.read(&count) || count != 1 ||
	    !input.read(&flags) || (flags & (O_F_WORN | O_F_CONTAINS | O_F_EOL)) ||
	    !input.read(&staged.vnum) || staged.vnum <= 0 || !input.skip(sizeof(short) * 2))
		return false;
	if (flags & O_F_UID)
		if (version < 36 || !input.read(&staged.item_uid))
			return false;
	if (flags & O_F_COUNT)
	{
		uint16_t quantity = 0;
		if (!input.read(&quantity) || quantity != 1)
			return false;
	}
	if (flags & O_F_AFFECTS)
	{
		uint8_t affects = 0;
		if (!input.read(&affects) || !input.skip(static_cast<size_t>(affects) *
							 (sizeof(int) * 2 + sizeof(short) * 2)))
			return false;
	}
	if (flags & O_F_UNIQUE)
	{
		if (!input.read(&unique))
			return false;
		for (const uint32_t bit : { O_U_KEYS, O_U_DESC1, O_U_DESC2, O_U_DESC3 })
			if ((unique & bit) && !input.string())
				return false;
		if (unique & O_U_EDESC)
		{
			uint16_t descriptions = 0;
			if (!input.read(&descriptions))
				return false;
			for (uint16_t index = 0; index < descriptions; ++index)
				if (!input.string() || !input.string())
					return false;
		}
		for (const uint32_t bit : { O_U_VAL0, O_U_VAL1, O_U_VAL2, O_U_VAL3, O_U_VAL4,
					    O_U_VAL5, O_U_VAL6, O_U_VAL7 })
			if ((unique & bit) && !input.skip(sizeof(int)))
				return false;
		if ((unique & O_U_TIMER) && !input.skip(sizeof(int) * 4))
			return false;
		if ((unique & O_U_TRAP) && !input.skip(sizeof(short) * 4))
			return false;
		if ((unique & O_U_TYPE) && !input.skip(1))
			return false;
		if ((unique & O_U_WEAR) && !input.skip(sizeof(int)))
			return false;
		if (unique & O_U_EXTRA)
		{
			if (!input.read(&staged.extra_flags))
				return false;
			staged.extra_flags_present = true;
		}
		for (const uint32_t bit : { O_U_ANTI, O_U_ANTI2, O_U_EXTRA2, O_U_WEIGHT })
			if ((unique & bit) && !input.skip(sizeof(int)))
				return false;
		if ((unique & O_U_MATERIAL) && !input.skip(1))
			return false;
		if ((unique & O_U_COST) && !input.skip(sizeof(int)))
			return false;
		for (const uint32_t bit : { O_U_BV1, O_U_BV2, O_U_BV3, O_U_BV4, O_U_BV5 })
			if ((unique & bit) && !input.skip(sizeof(long)))
				return false;
		if ((unique & O_U_AFFS) && !input.skip(MAX_OBJ_AFFECT * 2))
			return false;
	}
	if (flags & O_F_SPELLBOOK)
	{
		uint32_t bytes = 0;
		if (!input.read(&bytes) || !input.skip(bytes))
			return false;
	}
	uint8_t end = 0;
	if (!input.read(&end) || end != O_F_EOL ||
	    (input.remaining && (input.remaining != 1 || *input.data != 0)))
		return false;
	*identity = staged;
	return true;
}
