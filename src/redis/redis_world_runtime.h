/****************************************************************************
 *
 *  File: redis_world_runtime.h                                 Part of Duris
 *  Usage: Redis world runtime configuration and interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef REDIS_WORLD_RUNTIME_H
#define REDIS_WORLD_RUNTIME_H

#include "core/structs.h"

#include <stdint.h>
#include <vector>

struct redis_connection_settings;

struct redis_world_runtime_config
{
	const struct redis_connection_settings *connection;
	const char *key_namespace;
	uint64_t season_epoch;
	const char *host;
	int port;
	bool unix_socket;
};

bool redis_world_runtime_start(const struct redis_world_runtime_config *config);
void redis_world_runtime_shutdown(bool pwipe);
bool redis_world_runtime_enabled(void);
bool redis_world_recovery_boot_active(void);
void redis_world_recovery_boot_set(bool active);
bool redis_world_clean_restart_boot(void);
void redis_world_recovery_boot_clear(void);

bool redis_save_world_state(void);
bool redis_load_world_state(void);
enum class redis_world_boot_result
{
	disabled,
	absent,
	ready,
	failed
};
struct redis_world_boot_snapshot
{
	uint64_t sequence = 0;
	std::vector<unsigned char> generation;
	// Complete encoded floor values, including their wire prefix.
	std::vector<std::vector<unsigned char>> floor_records;
};
// Absent means a sealed missing head plus empty floor, disabled means not requested,
// and configured-but-unavailable/invalid evidence fails. Capture once before boot_db.
// This source cut is not complete population proof. Returned bytes
// remain immutable until boot clear/shutdown; loading never rereads Redis.
redis_world_boot_result redis_world_prepare_boot(void);
const redis_world_boot_snapshot *redis_world_boot_evidence(void);
bool redis_consume_world_state(void);
void event_save_world_state(P_char ch, P_char victim, P_obj obj, void *data);
void redis_world_recovery_pulse(void);
bool redis_world_recovery_drain(uint64_t timeout_msec);
bool redis_world_recovery_quiesce(void);
// A copyover gives the lease up before its exec; the image it starts claims it at boot. If
// the exec fails, this process takes it again at its next renewal.
void redis_world_writer_release(void);

#endif
