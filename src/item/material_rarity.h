/****************************************************************************
 *
 *  File: material_rarity.h                                     Part of Duris
 *  Usage: material composition report interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Zusuk                                      Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef MATERIAL_RARITY_H
#define MATERIAL_RARITY_H

/*
 * Write a read-only, static object-template composition report.  The report
 * counts one contribution for every distinct material ingredient needed by a
 * qualifying template; declared recipe quantities remain available in the
 * per-template CSV for later supply/demand modelling.
 */
void write_material_rarity_report(const char *output_dir);

#endif
