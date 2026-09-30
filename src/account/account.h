// account.h
//

#ifndef DURIS_ACCOUNT_H
#define DURIS_ACCOUNT_H

#include "account/racewar_admission.h"

#include <stddef.h>
#include <stdint.h>

#include <functional>

#ifndef _DE_
#include "core/structs.h"
#endif

/* Forward-declares struct descriptor_data.  Prototypes below spell the struct out
 * because core/structs.h includes this header before its descriptor typedef exists. */
#include "account/account_recovery.h"

#define USE_ACCOUNT

#define ACCT_IMMORTAL 0
#define ACCT_GOOD 1
#define ACCT_EVIL 2

/* Persisted before account deletion crosses its cancellation boundary. */
#define ACCOUNT_BLOCK_DELETION 2

#define MAX_CHARS_PER_ACCOUNT 16

struct acct_ip
{ // Account IP Information
	char *hostname;
	char *ip_address;
	unsigned long int count;
	struct acct_ip *next;
};

struct acct_chars
{ // Account Character Entry
	int pid;
	char *charname;
	unsigned long int count;
	long int last;
	char blocked;
	/* The racewar the account admits the character by (account_admission_racewar()). */
	char racewar;
	int level;
	int race;
	unsigned int m_class;
	unsigned int secondary_class;
	int last_room;
	long last_save;
	/* The character's own racewar (RACEWAR_*). It keys the flat-file identity, wallet
	 * and bank, as GET_RACEWAR() keys the MariaDB bank; 0 when not yet known. */
	char player_racewar;
	struct acct_chars *next;
};

#ifndef _DE_
/* Immortals are exempt from racewar admission; everyone else is admitted as good or
 * evil. */
inline char account_admission_racewar(int player_racewar, bool immortal)
{
	return immortal ? ACCT_IMMORTAL : player_racewar == RACEWAR_EVIL ? ACCT_EVIL : ACCT_GOOD;
}
#endif

struct acct_entry
{ // Main Account Structure
	char *acct_name;
	char *acct_email;
	char *acct_password;
	char *acct_confirmation;

	int num_ips;
	int num_chars;

	struct acct_ip *acct_unique_ips;
	struct acct_chars *acct_character_list;

	char acct_blocked;
	char acct_confirmed;
	char acct_confirmation_sent;

	long int acct_last;
	long int acct_good;
	long int acct_evil;

	unsigned long int acct_flags1;
	unsigned long int acct_flags2;
	unsigned long int acct_flags3;
	unsigned long int acct_flags4;
	uint64_t persistence_revision;

	struct acct_entry *next;
};

struct acct_list_entry
{ // List of loaded accounts
	struct acct_entry *account;
	struct acct_list_entry *next;
};

void cleanup_temp_char(struct char_data *ch);
int is_valid_email(const char *email);
bool is_email_taken(const char *email);

account_racewar_admission account_check_racewar_admission(struct descriptor_data *d, int racewar,
							  bool blocked, bool immortal);
bool account_commit_character_admission(struct descriptor_data *d, struct char_data *character,
					bool blocked, account_racewar_admission *result);
void account_format_racewar_denial(const account_racewar_admission *result, char *buffer,
				   size_t buffer_size);

/* Login account-name prompt, preceded by the enabled-mode banner (login_mode_banner.h). */
void send_account_name_prompt(struct descriptor_data *d);
/* Login password prompt (enabled/disabled recovery variant); sets CON_GET_ACCT_PASSWD. */
void send_account_password_prompt(struct descriptor_data *d);
/* True while a login check is pending, including the pulse that completes it. */
bool account_login_password_pulse(struct descriptor_data *d);
/* Close every session on acct_name except one, sending notice (may be NULL) first. */
void close_account_sessions_named(const char *acct_name, struct descriptor_data *except,
				  const char *notice);
/* Account recovery on a freshly read account: fence + fingerprint checks, hash swap,
 * write, kick others. */
account_recovery_apply_outcome account_apply_recovered_password(
	struct acct_entry *fresh, const char *bcrypt_hash,
	const unsigned char expected_fingerprint[ACCOUNT_RECOVERY_FINGERPRINT_LEN],
	struct descriptor_data *keep_session);
/* Reads the named account: on the writer, behind the saves queued before it, while d
 * waits with its input held (MariaDB), or at once (flat-file). done runs while d is still
 * connected, with the account, which it then owns, or null when there is none; ok is
 * false when the read failed. */
using account_read_done =
	std::function<void(struct descriptor_data *d, bool ok, struct acct_entry *account)>;
void account_read(struct descriptor_data *d, const char *name, account_read_done done);

#endif // DURIS_ACCOUNT_H
