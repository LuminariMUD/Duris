#include "account/kept_character_recovery.h"
#include "account/account.h"
#include "core/prototypes.h"
#include "core/utils.h"
#include "flatfile/flatfile_account_repository.h"
#include "flatfile/flatfile_identity_repository.h"
#include "flatfile/flatfile_player_repository.h"
#include "flatfile/flatfile_player_domain_repository.h"
#include "item/starter_kit_intent.h"
#include "persistence/critical_command_coordinator.h"
#include "persistence/persistence_mode.h"
#include "player/player_save_pipeline.h"
#include "player/player_load_pipeline.h"
#include "sql/sql.h"
#include "sql/sql_async.h"
#include "sql/sql_player.h"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <memory>
#include <map>
#include <mutex>
#include <sstream>

extern P_char character_list;
extern P_desc descriptor_list;

namespace
{
std::map<int, std::string> pending;
std::mutex pending_mutex;

#ifndef __NO_MYSQL__
std::string escape_value(MYSQL *connection, const std::string &value)
{
	std::string escaped(value.size() * 2 + 1, '\0');
	escaped.resize(
		mysql_real_escape_string(connection, escaped.data(), value.c_str(), value.size()));
	return escaped;
}
#endif

bool same(const std::string &a, const std::string &b)
{
	return !strcasecmp(a.c_str(), b.c_str());
}

bool busy(int pid)
{
	if (account_creation_pending(pid) || player_save_pipeline_load_held(pid) ||
	    player_save_worker_pid_pending(pid) || player_load_pipeline_pid_pending(pid) ||
	    critical_command_coordinator_is_fenced(
		    { critical_entity_type::player, static_cast<uint64_t>(pid) }, nullptr))
		return true;
	for (P_char actor = character_list; actor; actor = actor->next)
		if (IS_PC(actor) && GET_PID(actor) == pid)
			return true;
	for (P_desc d = descriptor_list; d; d = d->next)
		if ((d->character && IS_PC(d->character) && GET_PID(d->character) == pid) ||
		    (d->original && IS_PC(d->original) && GET_PID(d->original) == pid))
			return true;
	critical_command command;
	const auto state = starter_kit_intent_read(pid, &command);
	return state == starter_kit_state::pending || state == starter_kit_state::invalid;
}

void report(P_desc d, const kept_character_recovery_record &r)
{
	if (!d || !d->character)
		return;
	send_to_char_f(
		d->character,
		"Kept PID %d name=%s owner=%s mapping=%s active=%d tombstone=%d level=%d revision=%llu snapshot=%d domains=%d conflict=%d pending/live=%d\r\n",
		r.pid, r.name.c_str(), r.owner.empty() ? "-" : r.owner.c_str(),
		r.mapping_owner.empty() ? "-" : r.mapping_owner.c_str(), r.active, r.tombstone,
		r.level, static_cast<unsigned long long>(r.revision), r.snapshot, r.domains,
		r.conflict, busy(r.pid));
}

#ifdef __NO_MYSQL__
bool native_read(int pid, const std::string &name, kept_character_recovery_record *r)
{
	*r = {};
	r->pid = pid;
	r->name = name;
	r->projection.pid = pid;
	r->projection.count = 1;
	r->projection.last = time(nullptr);
	const std::string root = persistence_mode_flatfile_root();
	std::string error;
	flatfile_identity_record identity;
	const auto found = flatfile_identity_lookup_pid(root, pid, &identity, &error);
	if (found != flatfile_identity_result::ok && found != flatfile_identity_result::not_found)
		return false;
	r->catalog_revision = identity.catalog_revision;
	if (found == flatfile_identity_result::ok)
	{
		r->exists = true;
		r->active = identity.active;
		r->tombstone = !identity.active;
		r->name = identity.name;
		r->owner = identity.account;
		r->level = identity.level;
		r->mapping = identity.active && !identity.account.empty();
		r->projection.count = identity.login_count;
		r->projection.last = identity.last_login;
		r->projection.blocked = identity.blocked;
		r->mapping_owner = identity.account;
		r->conflict = !same(identity.name, name);
	}
	player_snapshot snapshot;
	const auto loaded = flatfile_player_snapshot_read(root, pid, &snapshot, &error);
	if (loaded == flatfile_player_load_result::not_found)
	{
		flatfile_player_domain_record domains;
		r->domains = !r->owner.empty() &&
			     flatfile_player_domain_load(root, pid, r->owner, identity.racewar,
							 &domains, &error) ==
				     flatfile_player_domain_result::ok;
		return r->exists;
	}
	if (loaded != flatfile_player_load_result::ok)
	{
		r->conflict = true;
		return r->exists;
	}
	r->exists = r->snapshot = true;
	r->revision = snapshot.revision;
	int racewar = 0;
	bool named = false;
	for (const auto &field : snapshot.status_strings)
		if (field.field == player_status_string_field::name)
		{
			named = true;
			r->name = field.value;
			if (!same(field.value, name))
				r->conflict = true;
		}
	if (!named)
		r->conflict = true;
	for (const auto &field : snapshot.status_integers)
	{
		const int64_t value = field.is_unsigned ?
					      static_cast<int64_t>(field.unsigned_value) :
					      field.signed_value;
		if (field.field == player_status_field::level)
			r->level = value;
		if (field.field == player_status_field::action_flags_3)
			r->flags = value;
		if (field.field == player_status_field::racewar)
			racewar = value;
		if (field.field == player_status_field::race)
			r->projection.race = value;
		if (field.field == player_status_field::class_primary)
			r->projection.m_class = value;
		if (field.field == player_status_field::class_secondary)
			r->projection.secondary_class = value;
		if (field.field == player_status_field::specialization)
			r->projection.spec = value;
	}
	r->projection.level = r->level;
	r->projection.player_racewar = racewar;
	r->projection.racewar = account_admission_racewar(racewar, false);
	if (found == flatfile_identity_result::not_found)
		r->owner = snapshot.creation_account;
	flatfile_player_domain_record domains;
	r->domains = !r->owner.empty() &&
		     flatfile_player_domain_load(root, pid, r->owner, racewar, &domains, &error) ==
			     flatfile_player_domain_result::ok;
	return true;
}

bool native_attach(const kept_character_recovery_record &expected, const std::string &account)
{
	const std::string root = persistence_mode_flatfile_root();
	std::string error;
	flatfile_player_snapshot_lock snapshot_lock;
	flatfile_identity_lock identity_lock;
	if (!snapshot_lock.acquire(root, expected.pid, &error) ||
	    !identity_lock.acquire(root, &error))
		return false;
	player_snapshot snapshot;
	if (flatfile_player_snapshot_read(root, expected.pid, &snapshot, &error) !=
		    flatfile_player_load_result::ok ||
	    snapshot.revision != expected.revision)
		return false;
	flatfile_account_record owner;
	if (flatfile_account_load(root, account, &owner, &error) != flatfile_account_result::ok ||
	    owner.blocked)
		return false;
	flatfile_identity_record record;
	record.pid = expected.pid;
	record.name = expected.name;
	record.account = account;
	record.active = true;
	for (const auto &field : snapshot.status_integers)
	{
		const int64_t value = field.is_unsigned ?
					      static_cast<int64_t>(field.unsigned_value) :
					      field.signed_value;
		switch (field.field)
		{
		case player_status_field::level:
			record.level = value;
			break;
		case player_status_field::race:
			record.race = value;
			break;
		case player_status_field::racewar:
			record.racewar = value;
			break;
		case player_status_field::class_primary:
			record.primary_class = value;
			break;
		case player_status_field::class_secondary:
			record.secondary_class = value;
			break;
		default:
			break;
		}
	}
	if (record.level != 0 ||
	    (!snapshot.creation_account.empty() && !same(snapshot.creation_account, account)))
		return false;
	flatfile_player_domain_record domains;
	if (flatfile_player_domain_load(root, expected.pid, account, record.racewar, &domains,
					&error) != flatfile_player_domain_result::ok)
		return false;
	flatfile_authority_lock authority;
	if (!authority.acquire(root, &error))
		return false;
	flatfile_authority_operation operation;
	const auto prepared = flatfile_identity_prepare_recovered_kept(root, identity_lock,
								       authority, record,
								       expected.catalog_revision,
								       &operation, &error);
	if (prepared == flatfile_identity_result::unchanged)
		return true;
	return prepared == flatfile_identity_result::ok &&
	       flatfile_authority_transaction_commit_operations(root, authority, { operation },
								&error) ==
		       flatfile_authority_transaction_result::ok;
}
#endif
}

bool kept_character_recovery_pending(int pid)
{
	std::lock_guard<std::mutex> lock(pending_mutex);
	return pending.count(pid) != 0;
}
bool kept_character_recovery_owner_pending(const char *account)
{
	std::lock_guard<std::mutex> lock(pending_mutex);
	if (!account)
		return false;
	for (const auto &[pid, owner] : pending)
	{
		(void)pid;
		if (same(owner, account))
			return true;
	}
	return false;
}

bool kept_character_recovery_releasable(const kept_character_recovery_record &r)
{
	return r.exists && !r.conflict && !r.tombstone && r.level == 0 &&
	       !((r.flags & PLR3_KEPT_CHARACTER) && !(r.flags & PLR3_APPROVAL_PENDING)) &&
	       !(r.snapshot && r.domains && !r.owner.empty() && r.mapping);
}

#ifndef __NO_MYSQL__
unsigned int kept_character_recovery_read(MYSQL *connection, int pid, const std::string &name,
					  kept_character_recovery_record *r, bool lock)
{
	*r = {};
	r->pid = pid;
	r->name = name;
	r->projection.pid = pid;
	r->projection.count = 1;
	r->projection.last = time(nullptr);
	const std::string suffix = lock ? " FOR UPDATE" : "";
	sql_rows rows;
	if (const unsigned int error = sql_select(
		    connection,
		    sql_format(
			    "SELECT name,COALESCE(account_name,''),active,level,save_revision,act3,race,racewar,m_class,secondary_class,spec FROM player_data WHERE pid=%d%s",
			    pid, suffix.c_str()),
		    &rows))
		return error;
	if (!rows.empty())
	{
		r->exists = true;
		r->name = rows[0][0] ? rows[0][0] : name;
		r->owner = rows[0][1] ? rows[0][1] : "";
		r->active = rows[0][2] && atoi(rows[0][2]);
		r->tombstone = !r->active;
		r->level = rows[0][3] ? atoi(rows[0][3]) : -1;
		r->revision = rows[0][4] ? strtoull(rows[0][4], nullptr, 10) : 0;
		r->flags = rows[0][5] ? strtoull(rows[0][5], nullptr, 10) : 0;
		r->snapshot = r->revision > 0;
		r->conflict = !rows[0][0] || !same(rows[0][0], name);
		r->projection.level = r->level;
		r->projection.race = rows[0][6] ? atoi(rows[0][6]) : 0;
		r->projection.player_racewar = rows[0][7] ? atoi(rows[0][7]) : 0;
		r->projection.racewar =
			account_admission_racewar(r->projection.player_racewar, false);
		r->projection.m_class = rows[0][8] ? strtoul(rows[0][8], nullptr, 10) : 0;
		r->projection.secondary_class = rows[0][9] ? strtoul(rows[0][9], nullptr, 10) : 0;
		r->projection.spec = rows[0][10] ? atoi(rows[0][10]) : 0;
	}
	rows.clear();
	if (const unsigned int error = sql_select(
		    connection,
		    sql_format(
			    "SELECT pid,char_name,account_name,deleted_at,login_count,UNIX_TIMESTAMP(last_login),blocked FROM account_characters WHERE pid=%d OR LOWER(char_name)=LOWER('%s')%s",
			    pid, escape_value(connection, name).c_str(), suffix.c_str()),
		    &rows))
		return error;
	for (const auto &row : rows)
	{
		r->exists = true;
		if (!row[0] || atoi(row[0]) != pid || !row[1] || !same(row[1], name) || r->mapping)
			r->conflict = true;
		if (row[3])
			r->tombstone = true;
		else
			r->mapping = true;
		r->mapping_owner = row[2] ? row[2] : "";
		r->projection.count = row[4] ? strtoul(row[4], nullptr, 10) : 0;
		r->projection.last = row[5] ? strtol(row[5], nullptr, 10) : 0;
		r->projection.blocked = row[6] ? atoi(row[6]) : 0;
		if (!r->owner.empty() && !same(r->owner, r->mapping_owner))
			r->conflict = true;
	}
	rows.clear();
	if (const unsigned int error = sql_select(
		    connection,
		    sql_format(
			    "SELECT (SELECT COUNT(*) FROM currency_wallet_baseline WHERE pid=%d)+(SELECT COUNT(*) FROM epic_balance_baseline WHERE pid=%d)+(SELECT COUNT(*) FROM combat_frag_baseline WHERE pid=%d)",
			    pid, pid, pid),
		    &rows))
		return error;
	r->domains = !rows.empty() && rows[0][0] && atoi(rows[0][0]) == 3;
	return r->exists ? 0 : ENOENT;
}

unsigned int kept_character_recovery_release_guard(MYSQL *connection,
						   const kept_character_recovery_record &expected)
{
	kept_character_recovery_record current;
	if (const unsigned int error = kept_character_recovery_read(connection, expected.pid,
								    expected.name, &current, true))
		return error;
	if (current.tombstone && !current.conflict && !current.snapshot && !current.mapping &&
	    !current.level && (current.owner.empty() || same(current.owner, expected.owner)) &&
	    !((current.flags & PLR3_KEPT_CHARACTER) && !(current.flags & PLR3_APPROVAL_PENDING)) &&
	    same(current.mapping_owner,
		 expected.mapping_owner.empty() ? expected.owner : expected.mapping_owner))
		return 0;
	return kept_character_recovery_releasable(current) &&
			       current.revision == expected.revision &&
			       same(current.owner, expected.owner) &&
			       same(current.mapping_owner, expected.mapping_owner) &&
			       current.mapping == expected.mapping ?
		       0 :
		       ESTALE;
}
#endif

void do_keptchar(P_char staff, char *argument, int /*cmd*/)
{
	if (!staff || IS_NPC(staff) || !staff->desc || !IS_TRUSTED(staff) ||
	    GET_LEVEL(staff) < OVERLORD)
		return;
	std::string action, pid_text, name, account, evidence, extra;
	std::istringstream input(argument ? argument : "");
	input >> action >> pid_text >> name >> account >> evidence >> extra;
	int pid = 0;
	const auto parsed =
		std::from_chars(pid_text.data(), pid_text.data() + pid_text.size(), pid);
	const bool inspect = action == "inspect";
	const bool attach = action == "attach";
	const bool release = action == "release";
	auto token = [](const std::string &s)
	{
		return !s.empty() && s.size() <= 100 &&
		       std::all_of(s.begin(), s.end(),
				   [](unsigned char c) {
					   return isalnum(c) || c == '-' || c == '_' || c == '#' ||
						  c == ':' || c == '/' || c == '.';
				   });
	};
	if ((!inspect && !attach && !release) || parsed.ec != std::errc{} ||
	    parsed.ptr != pid_text.data() + pid_text.size() || pid <= 0 || !token(name) ||
	    !std::all_of(name.begin(), name.end(), [](unsigned char c)
			 { return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'); }) ||
	    !extra.empty() || (inspect ? !account.empty() : (!token(account) || !token(evidence))))
	{
		send_to_char(
			"keptchar inspect <pid> <expected-name>\r\nkeptchar attach <pid> <expected-name> <verified-account> <evidence-ref>\r\nkeptchar release <pid> <expected-name> <expected-owner-or--> <evidence-ref>\r\n",
			staff);
		return;
	}
	if (!inspect && (busy(pid) || pfile_exists("Players/Accepted", name.data())))
	{
		send_to_char(
			"Refused: live/pending work, unavailable grant evidence, or an accepted character.\r\n",
			staff);
		return;
	}
	const uint64_t request = wait_for_writer(staff->desc);
	const std::string actor = GET_NAME(staff);
	auto record = std::make_shared<kept_character_recovery_record>();
	auto complete = [request, pid, actor, action, account, evidence, record](bool ok)
	{
		if (ok && action == "attach")
			for (P_desc d = descriptor_list; d; d = d->next)
				if (d->account && same(d->account->acct_name, account))
					account_publish_kept_character(d->account,
								       record->projection,
								       record->name.c_str());
		{
			std::lock_guard<std::mutex> lock(pending_mutex);
			pending.erase(pid);
		}
		if (P_desc d = writer_replied(request))
			send_to_char(
				ok ? "Kept recovery committed. Re-login to reload account membership.\r\n" :
				     "Kept recovery refused or failed; inspect again before retrying.\r\n",
				d->character);
		logit(LOG_WIZ,
		      "keptchar actor=%s operation=%s pid=%d account=%s evidence=%s committed=%d",
		      actor.c_str(), action.c_str(), pid, account.c_str(), evidence.c_str(), ok);
	};
	auto inspected = [=](bool ok)
	{
		if (inspect)
		{
			if (P_desc d = writer_replied(request))
			{
				if (ok)
					report(d, *record);
				else
					send_to_char(
						"No safe readable record for that exact PID/name.\r\n",
						d->character);
			}
			return;
		}
		if (!ok || record->conflict || record->level != 0 || record->tombstone ||
		    ((record->flags & PLR3_KEPT_CHARACTER) &&
		     !(record->flags & PLR3_APPROVAL_PENDING)) ||
		    (attach &&
		     (!record->snapshot ||
		      (!record->owner.empty() && !same(record->owner, account)) ||
		      (!record->mapping_owner.empty() && !same(record->mapping_owner, account)))) ||
		    (release && (!kept_character_recovery_releasable(*record) ||
				 !same(record->owner.empty() ? "-" : record->owner, account))))
		{
			complete(false);
			return;
		}
		if (release)
		{
			delete_kept_character(
				*record, [complete](character_delete_result result)
				{ complete(result == character_delete_result::deleted); });
			return;
		}
#ifdef __NO_MYSQL__
		complete(native_attach(*record, account));
#else
		if (!sql_read_work(
			    [=](MYSQL *connection, sql_rows *) -> unsigned int
			    {
				    kept_character_recovery_record current;
				    if (const auto error = kept_character_recovery_read(
						connection, pid, name, &current, true))
					    return error;
				    if (!current.conflict && !current.tombstone &&
					current.snapshot && !current.level &&
					current.revision == record->revision && current.domains &&
					current.mapping && same(current.owner, account) &&
					same(current.mapping_owner, account))
					    return 0;
				    if (current.conflict || current.tombstone ||
					!current.snapshot || current.level ||
					((current.flags & PLR3_KEPT_CHARACTER) &&
					 !(current.flags & PLR3_APPROVAL_PENDING)) ||
					current.revision != record->revision ||
					!same(current.owner, record->owner) ||
					(!current.mapping_owner.empty() &&
					 !same(current.mapping_owner, account)))
					    return ESTALE;
				    sql_rows target;
				    const std::string escaped = escape_value(connection, account);
				    if (const auto error = sql_select(
						connection,
						sql_format(
							"SELECT blocked FROM accounts WHERE LOWER(account_name)=LOWER('%s') FOR UPDATE",
							escaped.c_str()),
						&target))
					    return error;
				    if (target.size() != 1 || !target[0][0] || atoi(target[0][0]))
					    return EACCES;
				    if (const auto error = sql_execute(
						connection,
						sql_format(
							"UPDATE player_data SET account_name='%s' WHERE pid=%d",
							escaped.c_str(), pid)))
					    return error;
				    int repaired = 0;
				    if (const auto error = sql_repair_account_character_projection(
						connection, escaped, &repaired, pid))
					    return error;
				    kept_character_recovery_record after;
				    if (const auto error = kept_character_recovery_read(
						connection, pid, name, &after, true))
					    return error;
				    return after.domains && after.mapping && !after.conflict &&
							   same(after.mapping_owner, account) ?
						   0 :
						   EINVAL;
			    },
			    [complete](bool committed, const sql_rows &) { complete(committed); },
			    true))
			complete(false);
#endif
	};
	if (!inspect)
	{
		std::lock_guard<std::mutex> lock(pending_mutex);
		pending.emplace(pid, account);
	}
#ifdef __NO_MYSQL__
	inspected(native_read(pid, name, record.get()));
#else
	if (!sql_read_work(
		    [=](MYSQL *connection, sql_rows *) {
			    return kept_character_recovery_read(connection, pid, name, record.get(),
								false);
		    },
		    [inspected](bool ok, const sql_rows &) { inspected(ok); }))
	{
		if (inspect)
		{
			writer_replied(request);
			send_to_char("Recovery inspection unavailable.\r\n", staff);
		}
		else
			complete(false);
	}
#endif
}
