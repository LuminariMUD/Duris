#ifndef DURIS_FLATFILE_IDENTITY_ADAPTER_H
#define DURIS_FLATFILE_IDENTITY_ADAPTER_H

#include <stdint.h>

#include <string>

bool flatfile_player_identity_exists(const char *name, bool *exists, std::string *error);
bool flatfile_player_identity_pid(const char *name, int32_t *pid, std::string *error);
bool flatfile_player_identity_allocate(int32_t *pid, std::string *error);
bool flatfile_player_identity_highest(int32_t *pid, std::string *error);

#endif
