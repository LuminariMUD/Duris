#ifndef DURIS_OBJECT_BINDINGS_H
#define DURIS_OBJECT_BINDINGS_H

#include "core/structs.h"
#include <span>

// The two boot stages that currently assign compiled object specials.
enum class object_proc_binding_stage
{
	objects,
	rooms
};

struct object_proc_binding
{
	int vnum;
	obj_proc_type proc;
	const char *name;
};

std::span<const object_proc_binding> object_proc_bindings(object_proc_binding_stage stage);
// Only object-index assignments: no room/mobile setup or callback invocation.
void assign_object_proc_bindings(object_proc_binding_stage stage);

#endif
