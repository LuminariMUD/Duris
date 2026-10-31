#ifndef PRIVATE_CHEST_PURCHASE_H
#define PRIVATE_CHEST_PURCHASE_H
#include "core/structs.h"
#include <functional>
#include <string>
using private_chest_purchase_completion = std::function<void(P_char, int, const std::string &)>;
bool private_chest_purchase_start(P_char actor, int locker_id, const std::string &name,
				  const std::string &hash, private_chest_purchase_completion done);
void private_chest_purchase_pulse(void);
bool private_chest_purchase_locker_busy(int locker_id);
#endif
