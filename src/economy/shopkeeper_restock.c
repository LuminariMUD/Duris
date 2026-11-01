#include "economy/shopkeeper_restock.h"
#include "core/prototypes.h"

std::vector<P_obj> shopkeeper_reboot_stock(P_obj fresh, P_obj saved, int shop)
{
	std::vector<P_obj> missing;
	for (P_obj item = fresh; item; item = item->next_content)
	{
		if (shop_producing(item, shop))
			continue;
		size_t held = 0;
		for (P_obj existing = saved; existing; existing = existing->next_content)
			if (existing->R_num == item->R_num)
				++held;
		size_t supplied = 0;
		for (P_obj previous = fresh; previous != item; previous = previous->next_content)
			if (previous->R_num == item->R_num)
				++supplied;
		if (supplied >= held)
			missing.push_back(item);
	}
	return missing;
}
