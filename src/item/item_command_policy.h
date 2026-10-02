#ifndef ITEM_COMMAND_POLICY_H
#define ITEM_COMMAND_POLICY_H

#include "core/structs.h"

/* Command-facing item checks shared by get, put and empty. */
bool item_command_object_is_takeable(P_char actor, P_obj object);
bool item_command_container_is_valid(P_obj container);

#endif
