/****************************************************************************
 *
 *  File: skills.h                                              Part of Duris
 *  Usage: skill interface
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *  Created by: Duris, LuminariMUD, Zusuk                  Date: 2026-09-23
 *
 ****************************************************************************/

#ifndef __SKILLS_H__
#define __SKILLS_H__

#if defined(_DE_) || defined(_PFILE_)
void SKILL_CREATE(const char *Name, int Index, unsigned int Type);
#else
#include <source_location>
void SKILL_CREATE(const char *Name, int Index, unsigned int Type,
		  std::source_location site = std::source_location::current());
#endif

void initialize_skills();

#endif // __SKILLS_H__
