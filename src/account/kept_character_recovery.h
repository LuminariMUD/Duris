#ifndef KEPT_CHARACTER_RECOVERY_H
#define KEPT_CHARACTER_RECOVERY_H

#include "account/account.h"
#include <cstdint>
#include <string>

struct kept_character_recovery_record
{
	struct acct_chars projection
	{
	};
	int pid = 0;
	std::string name;
	std::string owner;
	std::string mapping_owner;
	uint64_t revision = 0;
	uint64_t catalog_revision = 0;
	uint64_t flags = 0;
	int level = 0;
	bool exists = false;
	bool active = false;
	bool snapshot = false;
	bool domains = false;
	bool mapping = false;
	bool conflict = false;
	bool tombstone = false;
};

bool kept_character_recovery_pending(int pid);
bool kept_character_recovery_owner_pending(const char *account);
bool kept_character_recovery_releasable(const kept_character_recovery_record &record);

#include <mysql/mysql.h>
unsigned int kept_character_recovery_read(MYSQL *connection, int pid, const std::string &name,
					  kept_character_recovery_record *record, bool lock);
unsigned int kept_character_recovery_release_guard(MYSQL *connection,
						   const kept_character_recovery_record &expected);

#endif
