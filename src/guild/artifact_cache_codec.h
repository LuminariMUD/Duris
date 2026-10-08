/****************************************************************************
 *
 *  File: artifact_cache_codec.h                                Part of Duris
 *  Usage: artifact cache codec interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef ARTIFACT_CACHE_CODEC_H
#define ARTIFACT_CACHE_CODEC_H

#include <cjson/cJSON.h>

constexpr int ARTIFACT_CACHE_SCHEMA_VERSION = 1;

bool artifact_cache_payload_valid(const cJSON *root, int expected_type, bool expected_godlist);

#endif
