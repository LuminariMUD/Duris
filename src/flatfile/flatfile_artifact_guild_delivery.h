#ifndef FLATFILE_ARTIFACT_GUILD_DELIVERY_H
#define FLATFILE_ARTIFACT_GUILD_DELIVERY_H

#include "flatfile/flatfile_player_domain_repository.h"

flatfile_player_domain_result flatfile_artifact_guild_delivery_initialize(const std::string &root,
									  std::string *error);
flatfile_player_domain_result
flatfile_artifact_guild_delivery_list(const std::string &root,
				      std::vector<critical_command> *commands, std::string *error);
// Run on the native writer after the ordinary entity saves. A durable success
// permits pruning the entity IDs; ambiguous storage failure keeps them intact.
flatfile_player_domain_result
flatfile_artifact_guild_delivery_advance(const std::string &root, const critical_command &command,
					 bool *acknowledged, std::string *error);

#endif
