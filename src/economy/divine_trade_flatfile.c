#include "economy/divine_trade_repository.h"

#include "flatfile/flatfile_player_domain_repository.h"
#include "flatfile/flatfile_store.h"
#include "flatfile/flatfile_cargo_repository.h"

#include <algorithm>
#include <cerrno>
#include <charconv>
#include <filesystem>
#include <openssl/crypto.h>
#include <openssl/sha.h>

namespace
{
constexpr std::array<uint8_t, 8> receipt_magic{ 'D', 'U', 'R', 'D', 'T', 'R', 'R', '2' };
constexpr size_t receipt_size = 8 + 4 + CRITICAL_COMMAND_ID_BYTES + SHA256_DIGEST_LENGTH +
				DIVINE_TRADE_RESULT_BYTES + SHA256_DIGEST_LENGTH;
constexpr size_t legacy_receipt_size = receipt_size - CRITICAL_COMMAND_ID_BYTES;

std::string book_filename(uint64_t account, uint64_t boon)
{
	return "divine-trade-" + std::to_string(boon) + "-" + std::to_string(account) + ".book";
}

bool digest_command(const critical_command &command,
		    std::array<uint8_t, SHA256_DIGEST_LENGTH> *digest)
{
	std::vector<uint8_t> bytes;
	if (critical_command_encode(command, &bytes) != critical_command_codec_result::ok)
		return false;
	SHA256(bytes.data(), bytes.size(), digest->data());
	return true;
}

bool encode_receipt(const critical_operation_id &operation,
		    const std::array<uint8_t, SHA256_DIGEST_LENGTH> &command_digest,
		    const divine_trade_result &result, unsigned error, std::vector<uint8_t> *bytes)
{
	std::array<uint8_t, DIVINE_TRADE_RESULT_BYTES> encoded;
	if (!divine_trade_result_encode(result, &encoded))
		return false;
	std::vector<uint8_t> value(receipt_magic.begin(), receipt_magic.end());
	for (unsigned i = 0; i < 4; ++i)
		value.push_back(static_cast<uint8_t>(error >> (i * 8)));
	value.insert(value.end(), operation.bytes.begin(), operation.bytes.end());
	value.insert(value.end(), command_digest.begin(), command_digest.end());
	value.insert(value.end(), encoded.begin(), encoded.end());
	std::array<uint8_t, SHA256_DIGEST_LENGTH> checksum;
	SHA256(value.data(), value.size(), checksum.data());
	value.insert(value.end(), checksum.begin(), checksum.end());
	*bytes = std::move(value);
	return true;
}

critical_apply_result replay(const std::vector<uint8_t> &bytes,
			     const critical_operation_id &operation,
			     const std::array<uint8_t, SHA256_DIGEST_LENGTH> &command_digest)
{
	const bool legacy = bytes.size() == legacy_receipt_size && bytes[7] == '1';
	if ((!legacy && bytes.size() != receipt_size) ||
	    !std::equal(receipt_magic.begin(), receipt_magic.end() - 1, bytes.begin()) ||
	    (!legacy && bytes[7] != '2'))
		return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
	const size_t digest_offset = 12 + (legacy ? 0 : CRITICAL_COMMAND_ID_BYTES);
	if (!legacy &&
	    CRYPTO_memcmp(operation.bytes.data(), bytes.data() + 12, operation.bytes.size()))
		return { critical_apply_outcome::terminal_failure, 0, EEXIST };
	std::array<uint8_t, SHA256_DIGEST_LENGTH> checksum;
	SHA256(bytes.data(), bytes.size() - checksum.size(), checksum.data());
	if (CRYPTO_memcmp(checksum.data(), bytes.data() + bytes.size() - checksum.size(),
			  checksum.size()))
		return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
	if (CRYPTO_memcmp(command_digest.data(), bytes.data() + digest_offset,
			  command_digest.size()))
		return { critical_apply_outcome::terminal_failure, 0, EEXIST };
	unsigned error = 0;
	for (unsigned i = 0; i < 4; ++i)
		error |= static_cast<unsigned>(bytes[8 + i]) << (i * 8);
	const auto *data = bytes.data() + digest_offset + SHA256_DIGEST_LENGTH;
	divine_trade_result result;
	if (!divine_trade_result_decode(data, DIVINE_TRADE_RESULT_BYTES, &result))
		return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
	critical_apply_result applied{ error ? critical_apply_outcome::terminal_failure :
					       critical_apply_outcome::already_applied,
				       error ? 0 : result.generation, error };
	applied.result_size = DIVINE_TRADE_RESULT_BYTES;
	std::copy_n(data, DIVINE_TRADE_RESULT_BYTES, applied.result_payload.begin());
	return applied;
}
bool read_book(const std::string &root, const std::string &name, divine_trade_book *book,
	       std::string *error)
{
	constexpr size_t prefix = sizeof("divine-trade-") - 1;
	const auto separator = name.find('-', prefix);
	if (separator == std::string::npos || !name.ends_with(".book"))
		return false;
	uint64_t boon = 0, account = 0;
	const char *first = name.data() + prefix;
	const char *middle = name.data() + separator;
	const char *last = name.data() + name.size() - 5;
	const auto parsed_boon = std::from_chars(first, middle, boon);
	const auto parsed_account = std::from_chars(middle + 1, last, account);
	std::vector<uint8_t> bytes;
	return parsed_boon.ec == std::errc{} && parsed_boon.ptr == middle && boon &&
	       parsed_account.ec == std::errc{} && parsed_account.ptr == last && account &&
	       name == book_filename(account, boon) &&
	       flatfile_read(root + "/domains", name, CRITICAL_COMMAND_MAX_PAYLOAD_BYTES, &bytes,
			     error) == flatfile_read_result::ok &&
	       divine_trade_book_decode(bytes, book) && book->account == account &&
	       book->boon_id == boon;
}
}

critical_apply_result divine_trade_flatfile_apply(const std::string &root,
						  const critical_command &command)
try
{
	divine_trade_payload p;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> command_digest;
	if (!divine_trade_command_decode(command, &p) || !digest_command(command, &command_digest))
		return { critical_apply_outcome::terminal_failure, 0, EINVAL };
	std::string error;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, &error))
		return { critical_apply_outcome::retryable_failure, 0, EIO };
	const auto recovered = flatfile_authority_transaction_recover(root, lock, &error);
	if (recovered != flatfile_authority_transaction_result::ok)
		return { recovered == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EIO };
	char operation_hex[CRITICAL_COMMAND_ID_HEX_SIZE];
	critical_operation_id_to_hex(command.operation_id, operation_hex, sizeof(operation_hex));
	const std::string receipt_name =
		std::string("divine-trade-command-") + operation_hex + ".receipt";
	std::vector<uint8_t> retained;
	auto read = flatfile_read(root + "/domains", receipt_name, receipt_size, &retained, &error);
	if (read == flatfile_read_result::ok)
	{
		auto applied = replay(retained, command.operation_id, command_digest);
		if (retained.size() == legacy_receipt_size &&
		    applied.result_size == DIVINE_TRADE_RESULT_BYTES)
		{
			// The original command proves the old digest's operation identity.
			// Upgrade only after that proof; a restore must never guess it.
			divine_trade_result result;
			flatfile_authority_operation upgrade;
			upgrade.filename = receipt_name;
			if (!divine_trade_result_decode(applied.result_payload.data(),
							applied.result_size, &result) ||
			    !encode_receipt(command.operation_id, command_digest, result,
					    applied.error_code, &upgrade.bytes))
				return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
			if (flatfile_authority_transaction_commit_operations(root, lock,
									     { upgrade }, &error) !=
			    flatfile_authority_transaction_result::ok)
				return { critical_apply_outcome::retryable_failure, 0, EIO };
		}
		return applied;
	}
	if (read != flatfile_read_result::not_found)
		return { read == flatfile_read_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EIO };
	if (command.payload_version < 3)
		return { critical_apply_outcome::terminal_failure, 0, EPROTONOSUPPORT };
	const std::string book_name = book_filename(p.book_after.account, p.book_after.boon_id);
	std::vector<uint8_t> before_bytes;
	read = flatfile_read(root + "/domains", book_name, CRITICAL_COMMAND_MAX_PAYLOAD_BYTES,
			     &before_bytes, &error);
	divine_trade_book before;
	if (read == flatfile_read_result::ok && !divine_trade_book_decode(before_bytes, &before))
		return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
	if (read != flatfile_read_result::ok && read != flatfile_read_result::not_found)
		return { read == flatfile_read_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EIO };
	unsigned result_code = divine_trade_book_transition_valid(before, p) ? 0 : ESTALE;
	divine_trade_result result{ p.pid,
				    p.ship_id,
				    p.generation + 1,
				    p.wallet_revision + 1,
				    p.book_after.revision,
				    p.payment,
				    p.qualifying_quantity };
	std::vector<flatfile_authority_operation> operations;
	if (!result_code)
	{
		std::array<uint64_t, 4> wallet;
		for (size_t i = 0; i < wallet.size(); ++i)
			wallet[i] = static_cast<uint64_t>(p.wallet_after.amount[i]);
		const auto prepared = flatfile_player_domain_prepare_wallet(
			root, lock, p.pid, p.wallet_revision, p.book_after.account, wallet,
			&operations, &error);
		if (prepared == flatfile_player_domain_result::io_error)
			return { critical_apply_outcome::retryable_failure, 0, EIO };
		if (prepared != flatfile_player_domain_result::ok)
			result_code = prepared == flatfile_player_domain_result::conflict ? ESTALE :
											    EILSEQ;
	}
	if (!result_code)
	{
		flatfile_authority_operation ship;
		const auto prepared = flatfile_ship_prepare_trade(root, lock, p.ship_id,
								  p.ship_owner_pid, p.slots_before,
								  p.crew_before, p.slots_after,
								  p.crew_after, &ship, &error);
		if (prepared == flatfile_ship_result::io_error)
			return { critical_apply_outcome::retryable_failure, 0, EIO };
		if (prepared != flatfile_ship_result::ok)
			result_code = prepared == flatfile_ship_result::conflict ? ESTALE : EILSEQ;
		else
			operations.push_back(std::move(ship));
	}
	if (!result_code)
	{
		flatfile_authority_operation market;
		errno = 0;
		if (!flatfile_cargo_prepare_trade(root, lock, p.generation, p.market_after, &market,
						  &error))
		{
			if (errno == EIO)
				return { critical_apply_outcome::retryable_failure, 0, EIO };
			result_code = errno == ESTALE ? ESTALE : EILSEQ;
		}
		else
			operations.push_back(std::move(market));
	}
	if (result_code)
		operations.clear(); // Rejection records only its permanent retry receipt.
	else
	{
		flatfile_authority_operation book;
		book.filename = book_name;
		if (!divine_trade_book_encode(p.book_after, &book.bytes))
			return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
		operations.push_back(std::move(book));
	}
	flatfile_authority_operation receipt;
	receipt.filename = receipt_name;
	if (!encode_receipt(command.operation_id, command_digest, result, result_code,
			    &receipt.bytes))
		return { critical_apply_outcome::terminal_failure, 0, EILSEQ };
	retained = receipt.bytes;
	operations.push_back(std::move(receipt));
	const auto committed =
		flatfile_authority_transaction_commit_operations(root, lock, operations, &error);
	if (committed != flatfile_authority_transaction_result::ok)
		return { committed == flatfile_authority_transaction_result::io_error ?
				 critical_apply_outcome::retryable_failure :
				 critical_apply_outcome::terminal_failure,
			 0, EIO };
	auto applied = replay(retained, command.operation_id, command_digest);
	if (!result_code)
		applied.outcome = critical_apply_outcome::applied;
	return applied;
}
catch (const std::bad_alloc &)
{
	return { critical_apply_outcome::retryable_failure, 0, ENOMEM };
}

bool divine_trade_flatfile_books(const std::string &root, uint64_t boon_id,
				 std::vector<divine_trade_book> *books)
{
	if (!boon_id || !books)
		return false;
	std::string error;
	flatfile_authority_lock lock;
	if (!lock.acquire(root, &error) ||
	    flatfile_authority_transaction_recover(root, lock, &error) !=
		    flatfile_authority_transaction_result::ok)
		return false;
	const std::string prefix = "divine-trade-" + std::to_string(boon_id) + "-";
	std::error_code ec;
	std::filesystem::directory_iterator current(root + "/domains", ec), end;
	std::vector<divine_trade_book> restored;
	while (!ec && current != end)
	{
		const std::string name = current->path().filename().string();
		if (name.starts_with(prefix) && name.ends_with(".book"))
		{
			divine_trade_book book;
			if (!read_book(root, name, &book, &error))
				return false;
			restored.push_back(std::move(book));
		}
		current.increment(ec);
	}
	if (ec)
		return false;
	std::sort(restored.begin(), restored.end(),
		  [](const auto &a, const auto &b) { return a.account < b.account; });
	*books = std::move(restored);
	return true;
}

bool divine_trade_flatfile_restore_validate(const std::string &root, std::string *error)
{
	flatfile_authority_lock lock;
	if (!lock.acquire(root, error) ||
	    flatfile_authority_transaction_recover(root, lock, error) !=
		    flatfile_authority_transaction_result::ok)
		return false;
	std::error_code ec;
	std::filesystem::directory_iterator current(root + "/domains", ec), end;
	for (; !ec && current != end; current.increment(ec))
	{
		const auto name = current->path().filename().string();
		if (!name.starts_with("divine-trade-"))
			continue;
		if (name.ends_with(".book"))
		{
			divine_trade_book book;
			if (!read_book(root, name, &book, error))
				return false;
		}
		else if (name.starts_with("divine-trade-command-") && name.ends_with(".receipt"))
		{
			constexpr size_t prefix = sizeof("divine-trade-command-") - 1;
			const auto key = name.substr(prefix, name.size() - prefix - 8);
			critical_operation_id operation;
			char canonical[CRITICAL_COMMAND_ID_HEX_SIZE];
			if (!critical_operation_id_from_hex(key.c_str(), &operation))
				return false;
			critical_operation_id_to_hex(operation, canonical, sizeof(canonical));
			if (key != canonical)
				return false;
			std::vector<uint8_t> bytes;
			if (flatfile_read(root + "/domains", name, receipt_size, &bytes, error) !=
				    flatfile_read_result::ok ||
			    bytes.size() != receipt_size)
				return false;
			std::array<uint8_t, SHA256_DIGEST_LENGTH> digest;
			std::copy_n(bytes.begin() + 12 + CRITICAL_COMMAND_ID_BYTES, digest.size(),
				    digest.begin());
			if (replay(bytes, operation, digest).result_size !=
			    DIVINE_TRADE_RESULT_BYTES)
				return false;
		}
	}
	return !ec;
}
