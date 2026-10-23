#!/usr/bin/env python3
"""Generate the production ship save capture for the disposable SQL regression."""
import sys
from pathlib import Path
from _paths import extract_function
source=r'''
#include "sql/sql_player.h"
#include "sql/sql_async.h"
#include "ships/ships.h"
#include "economy/divine_trade_runtime.h"
#undef sql_queue_statements
#include <cstdarg>
#include <cstdio>
#include <cmath>
#include <map>
#include <cassert>
#include <strings.h>
#include <cerrno>
static int ship_next_db_id=1000;
static std::vector<divine_trade_book> captured_books;
static std::vector<std::string> captured_statements;
static std::shared_ptr<sql_write_receipt> last_receipt;
static P_ship captured_ship=nullptr;
static int acknowledged=0,retries=0;
static bool queue_admits=true;
std::string escape_str(const char *value) {return value ? value : "";}
std::string sql_format(const char *format,...)
{char text[4096];va_list args;va_start(args,format);vsnprintf(text,sizeof(text),format,args);va_end(args);return text;}
std::vector<divine_trade_book> divine_trade_runtime_ship_books(uint32_t id) {return id ? captured_books : std::vector<divine_trade_book>{};}
bool divine_trade_runtime_busy(const ShipData *) {return false;}
uint64_t divine_trade_runtime_ship_revision(uint32_t) {return captured_books.empty() ? 0 : captured_books.front().revision;}
void divine_trade_runtime_ship_saved(uint32_t) {++acknowledged;}
P_ship find_ship_by_runtime_ref(ShipRuntimeRef) {return captured_ship;}
void queue_ship_save(P_ship ship,const char *) {++retries;ship->save_pending=true;}
struct stored_rows {sql_rows ship;};
static std::vector<std::pair<std::string,stored_rows>> stored_ships;
auto stored_ship(const char *owner) {return std::find_if(stored_ships.begin(),stored_ships.end(),
 [owner](const auto &entry) {return !strcasecmp(entry.first.c_str(),owner);});}
static uint32_t retired_unplaced=0;
void divine_trade_runtime_ship_deleted(uint32_t id) {retired_unplaced=id;}
void redis_invalidate_ship_snapshot(const char *) {}
bool sql_queue_statements(std::vector<std::string> statements)
{captured_statements=std::move(statements);return queue_admits;}
bool sql_queue_statements(std::vector<std::string> statements,std::shared_ptr<sql_write_receipt> receipt)
{captured_statements=std::move(statements);last_receipt=std::move(receipt);return queue_admits;}
'''
for signature in ["static bool sql_append_trade_books(","static std::vector<std::string> sql_save_ship_statements(P_ship ship)\n{",
                 ]:
    # The stub backend has another sql_save_ship; select the actual definition.
    source+=extract_function("sql/sql_player.c",signature)+"\n"
# Select the maintained SQL implementation, past the no-MySQL stub.
from _paths import source as production_source
sql=production_source("sql/sql_player.c").read_text()
start=sql.index("struct divine_ship_save_receipt")
source+=sql[start:sql.index("/* The stored rows of one ship:",start)]
source+=extract_function("sql/sql_player.c","std::string sql_delete_ship_statement(")+"\n"
start=sql.index("/* Delete a ship's rows on the writer")
source+=sql[start:sql.index("/* One guild's statements:",start)]

source+=r'''
bool fixture_ship_delete(P_ship ship,const std::vector<divine_trade_book> &books,std::vector<std::string> *statements)
{captured_books=books;*statements={sql_delete_ship_statement(ship->ownername)};return sql_append_trade_books(ship->db_id,statements);}
bool fixture_ship_save(P_ship ship,const std::vector<divine_trade_book> &books,std::vector<std::string> *statements)
{captured_books=books;captured_ship=ship;if(!sql_save_ship(ship)) return false;*statements=captured_statements;return true;}
bool fixture_ship_receipt_tests()
{
 ShipData ship{};ship.db_id=101;ship.ownername=const_cast<char *>("capture");captured_ship=&ship;
 divine_trade_book book;book.revision=1;book.account=9;book.boon_id=17;book.first_ship_id=101;book.first_full_hold=10;
 captured_books={book};
 queue_admits=false;assert(!sql_save_ship(&ship));assert(!acknowledged);
 queue_admits=true;assert(sql_save_ship(&ship));assert(!sql_ship_write_pulse());assert(!acknowledged);
 last_receipt->ok=false;last_receipt->finished.store(true,std::memory_order_release);
 assert(!sql_ship_write_pulse());assert(!acknowledged && retries==1 && ship.save_pending);
 assert(sql_save_ship(&ship));last_receipt->ok=true;last_receipt->finished.store(true,std::memory_order_release);
 assert(sql_ship_write_pulse());assert(acknowledged==1);
 assert(sql_save_ship(&ship));++captured_books[0].revision;
 last_receipt->ok=true;last_receipt->finished.store(true,std::memory_order_release);
 sql_ship_write_pulse();assert(acknowledged==1 && retries==2);
 assert(sql_save_ship(&ship));auto older=last_receipt;
 assert(sql_save_ship(&ship));older->ok=true;older->finished.store(true,std::memory_order_release);
 sql_ship_write_pulse();assert(acknowledged==1);
 last_receipt->ok=true;last_receipt->finished.store(true,std::memory_order_release);
 sql_ship_write_pulse();assert(acknowledged==2);
 assert(!sql_delete_ship("capture",101));assert(acknowledged==2);
 last_receipt->ok=false;last_receipt->finished.store(true,std::memory_order_release);
 assert(!sql_delete_ship("capture",101));assert(!sql_delete_ship("capture",101));
 last_receipt->ok=true;last_receipt->finished.store(true,std::memory_order_release);
 assert(sql_delete_ship("capture",101) && acknowledged==3);
 captured_books.clear();captured_ship=nullptr;
 sql_row unplaced;unplaced.fields.emplace_back("202");
 stored_ships.push_back({"unplaced",{sql_rows{unplaced}}});
 queue_admits=false;assert(!sql_delete_ship("unplaced",202) && !retired_unplaced && stored_ships.size()==1);
 // The owning delete already committed: memory cleanup must work with no writer slot.
 sql_forget_ship("unplaced");assert(retired_unplaced==202 && stored_ships.empty());
 sql_row another;another.fields.emplace_back("203");
 stored_ships.push_back({"another",{sql_rows{another}}});
 queue_admits=true;assert(sql_delete_ship("another",203) && retired_unplaced==203 && stored_ships.empty());
 return true;
}

'''
Path(sys.argv[1]).write_text(source)
