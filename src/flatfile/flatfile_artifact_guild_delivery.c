#include "flatfile/flatfile_artifact_guild_delivery.h"

#include "flatfile/flatfile_artifact_repository.h"
#include "flatfile/flatfile_association_repository.h"
#include "guild/artifact_guild_command.h"

#include <algorithm>

flatfile_player_domain_result
flatfile_artifact_guild_delivery_list(const std::string &root,
				      std::vector<critical_command> *commands, std::string *error)
{
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	return flatfile_artifact_deliveries_list(root, lock, commands, error);
}

flatfile_player_domain_result flatfile_artifact_guild_delivery_initialize(const std::string &root,
									  std::string *error)
{
	std::vector<critical_command> pending;
	const auto loaded = flatfile_artifact_guild_delivery_list(root, &pending, error);
	if (loaded != flatfile_player_domain_result::not_found)
		return loaded;
	// A missing index is only an upgrade if no retained child remains unACKed.
	// This scan is needed once for old stores, or when required proof is missing.
	const auto qualified = flatfile_player_domain_restore_recover(root, error);
	if (qualified != flatfile_player_domain_result::ok)
		return qualified;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	std::vector<flatfile_authority_operation> writes;
	const auto prepared = flatfile_artifact_deliveries_prepare(root, lock, {}, &writes, error);
	if (prepared != flatfile_player_domain_result::ok)
		return prepared;
	const auto saved =
		flatfile_authority_transaction_commit_operations(root, lock, writes, error);
	return saved == flatfile_authority_transaction_result::ok ?
		       flatfile_player_domain_result::ok :
	       saved == flatfile_authority_transaction_result::io_error ?
		       flatfile_player_domain_result::io_error :
		       flatfile_player_domain_result::invalid;
}

flatfile_player_domain_result
flatfile_artifact_guild_delivery_advance(const std::string &root, const critical_command &command,
					 bool *acknowledged, std::string *error)
{
	if (!acknowledged)
		return flatfile_player_domain_result::invalid;
	*acknowledged = false;
	artifact_guild_payload payload{};
	if (!artifact_guild_command_decode_payload(command, &payload) ||
	    !artifact_guild_command_valid_delivery(command, payload.parent_operation_id))
		return flatfile_player_domain_result::invalid;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error))
		return flatfile_player_domain_result::io_error;
	const auto checked =
		flatfile_artifact_delivery_acknowledged(root, lock, command, acknowledged, error);
	if (checked != flatfile_player_domain_result::ok || *acknowledged)
		return checked;
	for (size_t i = 0; i < payload.artifact_count; ++i)
	{
		const auto &entry = payload.artifacts[i];
		flatfile_artifact_record record;
		const auto loaded =
			flatfile_artifact_get_locked(root, lock, entry.vnum, &record, error);
		if (loaded != flatfile_artifact_result::ok)
			return loaded == flatfile_artifact_result::io_error ?
				       flatfile_player_domain_result::io_error :
				       flatfile_player_domain_result::invalid;
		if (record.identity_state == artifact_identity_state::unresolved)
			return flatfile_player_domain_result::ok;
		if (record.identity_state == artifact_identity_state::present &&
		    record.canonical_item_uid == entry.canonical_item_uid &&
		    !std::binary_search(record.delivery_ids.begin(), record.delivery_ids.end(),
					command.operation_id.bytes))
			return flatfile_player_domain_result::ok;
	}
	if (payload.guild_id)
	{
		std::vector<flatfile_association_record> guilds;
		const auto loaded = flatfile_association_list_locked(root, lock, &guilds, error);
		if (loaded != flatfile_association_result::ok)
			return loaded == flatfile_association_result::io_error ?
				       flatfile_player_domain_result::io_error :
				       flatfile_player_domain_result::invalid;
		const auto guild = std::lower_bound(guilds.begin(), guilds.end(), payload.guild_id,
						    [](const auto &record, uint32_t id)
						    { return record.association_id < id; });
		if (guild != guilds.end() && guild->association_id == payload.guild_id)
		{
			const auto identity =
				critical_operation_id_is_zero(guild->delivery_identity) ?
					artifact_guild_legacy_identity(guild->association_id) :
					guild->delivery_identity;
			if (identity.bytes == payload.guild_identity.bytes &&
			    !std::binary_search(guild->delivery_ids.begin(),
						guild->delivery_ids.end(),
						command.operation_id.bytes))
				return flatfile_player_domain_result::ok;
		}
	}
	std::vector<flatfile_authority_operation> writes;
	const auto prepared =
		flatfile_artifact_delivery_prepare_ack(root, lock, command, &writes, error);
	if (prepared != flatfile_player_domain_result::ok)
		return prepared;
	const auto saved =
		flatfile_authority_transaction_commit_operations(root, lock, writes, error);
	if (saved != flatfile_authority_transaction_result::ok)
		return saved == flatfile_authority_transaction_result::io_error ?
			       flatfile_player_domain_result::io_error :
			       flatfile_player_domain_result::invalid;
	*acknowledged = true;
	return flatfile_player_domain_result::ok;
}
