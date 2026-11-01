#ifndef DURIS_SHOPKEEPER_BOOT_H
#define DURIS_SHOPKEEPER_BOOT_H

#include <string>

// The directory belongs to this data directory, independently of SQL or Redis.
bool shopkeeper_boot_begin(const std::string &directory, bool recovery, std::string *error);
bool shopkeeper_boot_finish(const std::string &directory, std::string *error);
bool shopkeeper_boot_restock();

#endif
