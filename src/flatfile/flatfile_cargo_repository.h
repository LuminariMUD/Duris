#ifndef FLATFILE_CARGO_REPOSITORY_H
#define FLATFILE_CARGO_REPOSITORY_H

#include "economy/divine_trade_command.h"

constexpr size_t FLATFILE_CARGO_PORTS = 10;
enum class flat_cargo_result
{
	ok,
	not_found,
	invalid,
	io_error,
	stale
};
struct flat_cargo_record
{
	uint64_t revision = 0;
	uint64_t trade_generation = 0;
	std::array<float, FLATFILE_CARGO_PORTS * FLATFILE_CARGO_PORTS> cargo = {};
	std::array<float, FLATFILE_CARGO_PORTS * FLATFILE_CARGO_PORTS> contraband = {};
};
flat_cargo_result flatfile_cargo_load(const std::string &root, flat_cargo_record *record,
				      std::string *error);
flat_cargo_result flatfile_cargo_load(const std::string &root,
				      const flatfile_authority_lock &authority,
				      flat_cargo_record *record, std::string *error);
flat_cargo_result flatfile_cargo_save(const std::string &root, flat_cargo_record record,
				      std::string *error);
bool flatfile_cargo_prepare_trade(const std::string &root, const flatfile_authority_lock &lock,
				  uint64_t expected_generation,
				  const std::vector<divine_trade_market_cell> &cells,
				  flatfile_authority_operation *operation, std::string *error);

#endif
