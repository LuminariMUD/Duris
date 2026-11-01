#ifndef DURIS_SHOPKEEPER_RESTOCK_H
#define DURIS_SHOPKEEPER_RESTOCK_H

#include "core/structs.h"
#include <vector>

// Select existing boot-created roots without changing either inventory.
std::vector<P_obj> shopkeeper_reboot_stock(P_obj fresh, P_obj saved, int shop);

#endif
