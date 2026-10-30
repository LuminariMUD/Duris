// Production purchase transaction and controller against disposable InnoDB.
#include "item/private_chest_purchase.c"
#include "sql/sql_player.h"
#include <cassert>
#include <cstdarg>
#include <cstdlib>
#include <cstdio>
#include <cstring>

MYSQL *DB;
static char_data actor{};
static pc_only_data pc{};
static P_char live_actor = &actor;
static bool reserved, refuse, fail_wallet;
static sql_read_work_fn queued;
static std::function<void(bool, const sql_rows &)> completed;
static currency_command_payload payment{};
static uint8_t sequence;
static int result_id;
static bool result_offline;

std::string sql_format(const char *fmt, ...)
{
	char text[8192];
	va_list args;
	va_start(args, fmt);
	vsnprintf(text, sizeof(text), fmt, args);
	va_end(args);
	return text;
}
std::string escape_str(const char *s)
{
	std::string escaped(strlen(s) * 2 + 1, '\0');
	escaped.resize(mysql_real_escape_string(DB, escaped.data(), s, strlen(s)));
	return escaped;
}
unsigned int sql_execute(MYSQL *db, const std::string &s)
{
	if (fail_wallet && s.find("UPDATE player_data") == 0)
		return 1644;
	return mysql_real_query(db, s.data(), s.size()) ? mysql_errno(db) : 0;
}
unsigned int sql_select(MYSQL *db, const std::string &s, sql_rows *rows)
{
	if (auto error = sql_execute(db, s))
		return error;
	auto result = mysql_store_result(db);
	if (!result)
		return mysql_errno(db);
	while (auto fields = mysql_fetch_row(result))
	{
		sql_row row;
		for (unsigned i = 0; i < mysql_num_fields(result); ++i)
			row.fields.emplace_back(fields[i] ? std::optional<std::string>(fields[i]) :
							    std::nullopt);
		rows->push_back(std::move(row));
	}
	mysql_free_result(result);
	return 0;
}
static void execute(const char *s)
{
	assert(sql_execute(DB, s) == 0);
}
static int scalar(const char *s)
{
	sql_rows rows;
	assert(!sql_select(DB, s, &rows));
	assert(!rows.empty() && rows[0][0]);
	return atoi(rows[0][0]);
}
bool sql_read_work_at(persistence_query_site, sql_read_work_fn work,
		      std::function<void(bool, const sql_rows &)> done)
{
	if (refuse)
		return false;
	assert(!queued);
	queued = std::move(work);
	completed = std::move(done);
	return true;
}
// Currency calculation has its own executable tests. This boundary supplies the
// exact prepared vectors, allowing transaction/lifetime faults independently.
bool currency_transaction_prepare_identify(P_char ch, int64_t cost, critical_command *cmd)
{
	assert(ch == &actor && cost == 500000);
	cmd->operation_id.bytes[0] = ++sequence;
	return !reserved;
}
bool currency_command_decode_payload(const critical_command &, currency_command_payload *out)
{
	*out = payment;
	return true;
}
bool critical_operation_id_to_hex(const critical_operation_id &id, char *dest, size_t n)
{
	assert(n >= 33);
	for (int i = 0; i < 16; ++i)
		snprintf(dest + i * 2, 3, "%02x", id.bytes[i]);
	return true;
}
bool currency_transaction_reserve_chest(P_char)
{
	assert(!reserved);
	reserved = true;
	return true;
}
void currency_transaction_release_chest(uint32_t pid)
{
	assert(pid == 1 && reserved);
	reserved = false;
}
P_char find_player_by_pid(int pid)
{
	assert(pid == 1);
	return live_actor;
}
const char *get_account_name_safe(P_char)
{
	return "buyer";
}
void mark_player_dirty_components(int, uint64_t) {}
void gmcp_char_vitals(P_char) {}
void publish_account_bank_balances_revision(const char *, int, const AccountBankBalances *bank,
					    uint64_t revision)
{
	GET_BALANCE_COPPER(&actor) = bank->copper;
	GET_BALANCE_SILVER(&actor) = bank->silver;
	GET_BALANCE_GOLD(&actor) = bank->gold;
	GET_BALANCE_PLATINUM(&actor) = bank->platinum;
	pc.bank_revision = revision;
}
void currency_transaction_publish_chest(P_char ch, const currency_command_result &result,
					bool bank_changes)
{
	if (ch)
	{
		GET_COPPER(ch) = result.wallet.amount[0];
		GET_SILVER(ch) = result.wallet.amount[1];
		GET_GOLD(ch) = result.wallet.amount[2];
		GET_PLATINUM(ch) = result.wallet.amount[3];
		ch->only.pc->wallet_revision = result.wallet_revision;
	}
	if (bank_changes)
	{
		AccountBankBalances b{ static_cast<int>(result.bank.amount[0]),
				       static_cast<int>(result.bank.amount[1]),
				       static_cast<int>(result.bank.amount[2]),
				       static_cast<int>(result.bank.amount[3]) };
		publish_account_bank_balances_revision("buyer", 1, &b, result.bank_revision);
	}
}
static void finish(bool lose_reply = false, bool disconnect = false)
{
	assert(queued);
	execute("START TRANSACTION");
	sql_rows rows;
	auto work = std::move(queued);
	queued = {};
	auto error = work(DB, &rows);
	execute(error ? "ROLLBACK" : "COMMIT");
	if (disconnect)
		live_actor = NULL;
	auto done = std::move(completed);
	completed = {};
	done(!error && !lose_reply, rows);
}
static void start(const char *name)
{
	result_id = -1;
	result_offline = false;
	assert(private_chest_purchase_start(&actor, 7, name, "",
					    [](P_char buyer, int id, const std::string &)
					    {
						    result_id = id;
						    result_offline = buyer == NULL;
					    }));
	assert(reserved && private_chest_purchase_locker_busy(7));
}
static void reset()
{
	assert(!pending);
	execute("DELETE FROM private_chests");
	execute("UPDATE player_data SET copper=0,silver=0,gold=0,platinum=1000,wallet_revision=0");
	execute("UPDATE account_banks SET bank_copper=0,bank_silver=0,bank_gold=0,bank_platinum=1000,bank_revision=0");
	pc = {};
	actor.only.pc = &pc;
	pc.pid = 1;
	GET_RACEWAR(&actor) = 1;
	GET_PLATINUM(&actor) = 1000;
	GET_BALANCE_PLATINUM(&actor) = 1000;
	live_actor = &actor;
	payment = {};
	payment.pid = 1;
	payment.racewar = 1;
	strcpy(payment.account_name.data(), "buyer");
	payment.wallet_delta.amount[3] = -500;
}
int main()
{
	DB = mysql_init(NULL);
	assert(DB);
	assert(mysql_real_connect(DB, getenv("TEST_DB_HOST"), getenv("TEST_DB_USER"),
				  getenv("TEST_DB_PASSWORD"), getenv("CHEST_TEST_DB"),
				  static_cast<unsigned>(atoi(getenv("TEST_DB_PORT"))), NULL, 0));
	assert(mysql_set_character_set(DB, "utf8mb4") == 0);
	execute("CREATE TABLE lockers(id INT PRIMARY KEY) ENGINE=InnoDB");
	execute("INSERT INTO lockers VALUES(7)");
	execute("CREATE TABLE private_chests(id INT PRIMARY KEY AUTO_INCREMENT,locker_id INT,chest_name VARCHAR(32) COLLATE utf8mb4_unicode_ci,password_hash VARCHAR(64),is_public TINYINT,purchase_operation BINARY(16) UNIQUE,UNIQUE(locker_id,chest_name)) ENGINE=InnoDB");
	execute("CREATE TABLE player_data(pid INT PRIMARY KEY,copper INT,silver INT,gold INT,platinum INT,wallet_revision BIGINT UNSIGNED) ENGINE=InnoDB");
	execute("INSERT INTO player_data VALUES(1,0,0,0,1000,0)");
	execute("CREATE TABLE account_banks(account_name VARCHAR(64),racewar INT,bank_copper INT,bank_silver INT,bank_gold INT,bank_platinum INT,bank_revision BIGINT UNSIGNED,PRIMARY KEY(account_name,racewar)) ENGINE=InnoDB");
	execute("INSERT INTO account_banks VALUES('buyer',1,0,0,0,1000,0)");
	reset();
	start("vault");
	finish(true);
	assert(result_id == -1 && reserved);
	assert(scalar("SELECT platinum FROM player_data") == 500);
	pending->retry = {};
	private_chest_purchase_pulse();
	finish();
	assert(result_id > 0 && !reserved && GET_PLATINUM(&actor) == 500);
	assert(scalar("SELECT COUNT(*) FROM private_chests") == 1);
	assert(scalar("SELECT wallet_revision FROM player_data") == 1);
	reset();
	start("failure");
	fail_wallet = true;
	finish();
	fail_wallet = false;
	assert(result_id == -1 && reserved);
	assert(scalar("SELECT COUNT(*) FROM private_chests") == 0 &&
	       scalar("SELECT platinum FROM player_data") == 1000);
	pending->retry = {};
	private_chest_purchase_pulse();
	finish(false, true);
	assert(result_id > 0 && result_offline && !reserved);
	assert(scalar("SELECT platinum FROM player_data") == 500);
	reset();
	refuse = true;
	start("refused");
	assert(!queued && result_id == -1);
	assert(scalar("SELECT COUNT(*) FROM private_chests") == 0);
	refuse = false;
	pending->retry = {};
	private_chest_purchase_pulse();
	finish();
	assert(result_id > 0);
	reset();
	execute("INSERT INTO private_chests(locker_id,chest_name,is_public) VALUES(7,'vault',0)");
	start("VAULT");
	finish();
	assert(result_id == 0 && !reserved && scalar("SELECT platinum FROM player_data") == 1000);
	reset();
	execute("INSERT INTO private_chests(locker_id,chest_name,is_public) VALUES(7,'caf\xC3\xA9',0)");
	start("cafe");
	finish();
	assert(result_id == 0 && !reserved && !pending && !queued);
	assert(scalar("SELECT COUNT(*) FROM private_chests") == 1 &&
	       scalar("SELECT platinum FROM player_data") == 1000);
	start("available");
	finish();
	assert(result_id > 0 && !reserved);

	reset();
	execute("INSERT INTO private_chests(locker_id,chest_name,is_public) VALUES(7,'a',0),(7,'b',0),(7,'c',0),(7,'d',0),(7,'e',0)");
	start("sixth");
	finish();
	assert(result_id == 0 && scalar("SELECT COUNT(*) FROM private_chests") == 5 &&
	       scalar("SELECT platinum FROM player_data") == 1000);
	reset();
	execute("UPDATE player_data SET wallet_revision=9");
	start("stale");
	finish();
	assert(result_id == 0 && !reserved && scalar("SELECT COUNT(*) FROM private_chests") == 0);
	reset();
	GET_PLATINUM(&actor) = 0;
	GET_COPPER(&actor) = 100;
	GET_BALANCE_COPPER(&actor) = 1;
	GET_BALANCE_SILVER(&actor) = 2;
	GET_BALANCE_GOLD(&actor) = 3;
	GET_BALANCE_PLATINUM(&actor) = 500;
	execute("UPDATE player_data SET copper=100,platinum=0");
	execute("UPDATE account_banks SET bank_copper=1,bank_silver=2,bank_gold=3,bank_platinum=500");
	payment.wallet_delta.amount = { 1, 2, 3, 0 };
	payment.bank_delta.amount = { -1, -2, -3, -500 };
	start("bank");
	finish(true);
	pending->retry = {};
	private_chest_purchase_pulse();
	finish();
	assert(result_id > 0 && GET_COPPER(&actor) == 101 && GET_SILVER(&actor) == 2 &&
	       GET_GOLD(&actor) == 3);
	assert(scalar("SELECT bank_platinum FROM account_banks") == 0 &&
	       scalar("SELECT bank_revision FROM account_banks") == 1);
	mysql_close(DB);
	puts("private chest atomic wallet/bank purchase, rollback, refusal, lost reply, offline completion, duplicate and limit PASS");
}
