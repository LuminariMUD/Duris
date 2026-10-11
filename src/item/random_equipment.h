/****************************************************************************
 *
 *  File: random_equipment.h                                    Part of Duris
 *  Usage: random equipment: kill drops, generated items, salvage materials,
 *         encrust stones and the tables they are built from
 *
 *  Copyright 1990, 1991 - see LICENSE for complete information
 *
 *  Additions since 2025 by the Duris maintainers and since 2026 by
 *    LuminariMUD maintainers are public domain (Unlicense, see LICENSE)
 *
 *
 ****************************************************************************/

#ifndef _RANDOM_EQUIPMENT_H_
#define _RANDOM_EQUIPMENT_H_

#include "core/structs.h"

// Table sizes, each checked against its table by a static_assert in
// random_equipment_tables.c.
#define MAX_SLOT 109 // rows in slot_data
#define MAXMATERIAL 43 // rows in material_data
#define MAXPREFIX 56 // the last row of prefix_data, which has MAXPREFIX + 1 rows

// An item shape: a ring, a pair of boots, a long sword.
struct randomeq_slots
{
	int m_number;
	const char *m_name;
	float m_stat;
	float m_ac;
	int wear_bit;
	int numb_material;
	int damage_type;
	int base_weight;
};

// What an item is made of; m_number is its MAT_ material type.
struct randomeq_material
{
	int m_number;
	const char *m_name;
	float m_stat;
	float m_ac;
	float weight_mod;
};

// The adjective in an item's name, which scales its stats, armour and weight.
struct randomeq_prefix
{
	int m_number;
	const char *m_name;
	float m_stat;
	float m_ac;
	float weight_mod;
};

/* Self-targeted entries carry no adjective, so most rows stop after
   self_only and rely on name being an empty string. */
struct random_spells
{
	int s_number = 0;
	int spell = 0;
	bool self_only = false;
	char name[32] = "";
};

extern const struct randomeq_slots slot_data[];
extern struct randomeq_material material_data[];
extern struct randomeq_prefix prefix_data[];
extern struct random_spells spells_data[61];

// random_equipment_drop.c: whether a kill drops something, and the drop itself.
bool check_random_drop(P_char ch, P_char mob, bool piece);
void random_equipment_kill_drop(P_char killer, P_char victim);

// random_equipment.c: the item generator, salvage materials, encrust stones and the
// affect helpers other code borrows.
P_obj create_random_eq(P_char finder, int finder_level, int source_level, int slot, int material);
P_obj create_material(int index);
P_obj create_material(P_char finder, int finder_level, int source_level);
P_obj create_stones(void);
P_obj setsuffix_obj_new(P_obj obj);
void set_encrust_affect(P_obj obj, int proc);
bool identify_random(P_obj obj);

#endif
