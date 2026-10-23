#ifndef ARTIFACT_GUILD_DELIVERY_H
#define ARTIFACT_GUILD_DELIVERY_H

#include "guild/artifact_guild_command.h"
#include "persistence/critical_outbox.h"

bool artifact_guild_delivery_boot();
bool artifact_guild_delivery_reserve(const std::vector<critical_command> &commands);
void artifact_guild_delivery_complete(const std::vector<critical_command> &commands,
				      bool committed);
void artifact_guild_delivery_pulse();
size_t artifact_guild_delivery_pending();
bool artifact_guild_delivery_holds(uint64_t item_uid);
critical_outbox_delivery_result
artifact_guild_delivery_outbox(const critical_outbox_record &record);

#endif
