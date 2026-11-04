#ifndef ITEM_AFFECT_ROWS_H
#define ITEM_AFFECT_ROWS_H

#include "player/player_snapshot.h"

#include <sstream>

// Store every fixed slot. A zero pair is an explicit override of the prototype.
inline std::string sql_item_affect_insert(const char *table, unsigned long long item_id,
					  const decltype(player_item_snapshot::affects) &affects)
{
	std::ostringstream sql;
	sql << "INSERT INTO " << table << " (item_id, affect_slot, location, modifier) VALUES ";
	for (size_t slot = 0; slot < affects.size(); ++slot)
		sql << (slot ? ",(" : "(") << item_id << ',' << slot << ',' << affects[slot][0]
		    << ',' << affects[slot][1] << ')';
	return sql.str();
}

#endif
