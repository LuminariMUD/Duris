#ifndef DURIS_TRAP_LEGACY_H
#define DURIS_TRAP_LEGACY_H

struct obj_data;

// Run after all stored fields are applied. Preserve custom traps and spent state.
void normalize_legacy_trap(obj_data *object, int vnum);

#endif
