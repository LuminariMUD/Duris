#ifndef DURIS_TRAP_H
#define DURIS_TRAP_H

struct obj_data;

// Definition validity is independent of whether any charges remain.
bool trap_configuration_valid(int vnum, int type, int level);
// Read-only trigger test; traps support north through down, never diagonals.
bool movement_trap_trigger(obj_data *obj, int direction);

#endif
