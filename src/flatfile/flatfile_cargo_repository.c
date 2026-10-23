#include "flatfile/flatfile_cargo_repository.h"
#include "flatfile/flatfile_store.h"

#include <algorithm>
#include <bit>
#include <cerrno>
#include <cmath>
#include <limits>
#include <new>
#include <openssl/crypto.h>
#include <openssl/sha.h>
#include <set>

namespace
{
constexpr std::array<uint8_t, 8> cargo_magic = { 'D', 'U', 'R', 'C', 'A', 'R', 'G', 'O' };
constexpr uint32_t cargo_version = 2;
constexpr size_t cargo_value_count = FLATFILE_CARGO_PORTS * FLATFILE_CARGO_PORTS;
constexpr size_t cargo_record_size = cargo_magic.size() + sizeof(uint32_t) + sizeof(uint64_t) * 2 +
				     cargo_value_count * sizeof(uint32_t) * 2 +
				     SHA256_DIGEST_LENGTH;
constexpr const char *cargo_filename = "cargo_market";
constexpr const char *cargo_lock_filename = "cargo_market.lock";

/*
 * Whether `value` is a believable market modifier: finite and within
 * [0, 1000].  Every modifier that crosses the persistence boundary is checked
 * against this, so a corrupt file cannot inject an infinity or a negative
 * price into the live market.
 */
bool valid_market_modifier(float value)
{
	return std::isfinite(value) && value >= 0.0f && value <= 1000.0f;
}

/*
 * Append `value` to `bytes` as 4 little-endian octets.  The record format is
 * explicitly byte-ordered so a saved market survives a move between hosts.
 */
void append_u32(std::vector<uint8_t> *bytes, uint32_t value)
{
	for (size_t offset = 0; offset < sizeof(value); ++offset)
	{
		bytes->push_back(static_cast<uint8_t>(value & 0xff));
		value >>= 8;
	}
}

/*
 * Append `value` to `bytes` as 8 little-endian octets.  See append_u32().
 */
void append_u64(std::vector<uint8_t> *bytes, uint64_t value)
{
	for (size_t offset = 0; offset < sizeof(value); ++offset)
	{
		bytes->push_back(static_cast<uint8_t>(value & 0xff));
		value >>= 8;
	}
}

/*
 * Read a little-endian uint32 from `bytes`.  The caller must already have
 * checked that at least 4 octets are available.
 */
uint32_t read_u32(const uint8_t *bytes)
{
	uint32_t value = 0;
	for (size_t offset = 0; offset < sizeof(value); ++offset)
		value |= static_cast<uint32_t>(bytes[offset]) << (offset * 8);
	return value;
}

/*
 * Read a little-endian uint64 from `bytes`.  The caller must already have
 * checked that at least 8 octets are available.
 */
uint64_t read_u64(const uint8_t *bytes)
{
	uint64_t value = 0;
	for (size_t offset = 0; offset < sizeof(value); ++offset)
		value |= static_cast<uint64_t>(bytes[offset]) << (offset * 8);
	return value;
}

/*
 * Whether `record` is safe to write out or to load into the live market:
 * a non-zero revision and every one of its modifiers plausible.
 */
bool valid_flat_cargo_record(const flat_cargo_record &record)
{
	if (!record.revision)
		return false;
	for (float value : record.cargo)
		if (!valid_market_modifier(value))
			return false;
	for (float value : record.contraband)
		if (!valid_market_modifier(value))
			return false;
	return true;
}

/*
 * Serialise `record` into `bytes`: magic, version, revision, the two
 * modifier matrices, then a SHA-256 of everything before it.
 *
 * Returns false for a bad output pointer, an implausible record, or an
 * allocation failure -- never a partially written buffer.
 */
bool encode_flat_cargo(const flat_cargo_record &record, std::vector<uint8_t> *bytes)
{
	static_assert(sizeof(float) == sizeof(uint32_t));
	if (!bytes || !valid_flat_cargo_record(record))
		return false;
	try
	{
		bytes->clear();
		bytes->reserve(cargo_record_size);
		bytes->insert(bytes->end(), cargo_magic.begin(), cargo_magic.end());
		append_u32(bytes, cargo_version);
		append_u64(bytes, record.revision);
		append_u64(bytes, record.trade_generation);
		for (float value : record.cargo)
			append_u32(bytes, std::bit_cast<uint32_t>(value));
		for (float value : record.contraband)
			append_u32(bytes, std::bit_cast<uint32_t>(value));
		std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
		SHA256(bytes->data(), bytes->size(), digest.data());
		bytes->insert(bytes->end(), digest.begin(), digest.end());
	}
	catch (const std::bad_alloc &)
	{
		bytes->clear();
		return false;
	}
	return bytes->size() == cargo_record_size;
}

/*
 * Parse and verify a serialised market record.
 *
 * Checks length, magic, version and the trailing SHA-256 digest before
 * accepting anything, then validates the decoded modifiers.  Returns false
 * and leaves `record` untouched on any failure, so a damaged file degrades
 * to "no record" rather than to a corrupt market.
 */
bool decode_flat_cargo(const std::vector<uint8_t> &bytes, flat_cargo_record *record)
{
	if (!record ||
	    (bytes.size() != cargo_record_size &&
	     bytes.size() != cargo_record_size - sizeof(uint64_t)) ||
	    !std::equal(cargo_magic.begin(), cargo_magic.end(), bytes.begin()))
		return false;
	const uint32_t wire_version = read_u32(bytes.data() + cargo_magic.size());
	if ((wire_version != 1 && wire_version != cargo_version) ||
	    bytes.size() != cargo_record_size - (wire_version == 1 ? sizeof(uint64_t) : 0))
		return false;
	std::array<uint8_t, SHA256_DIGEST_LENGTH> digest = {};
	SHA256(bytes.data(), bytes.size() - digest.size(), digest.data());
	if (CRYPTO_memcmp(bytes.data() + bytes.size() - digest.size(), digest.data(),
			  digest.size()))
		return false;
	flat_cargo_record decoded;
	size_t offset = cargo_magic.size() + sizeof(uint32_t);
	decoded.revision = read_u64(bytes.data() + offset);
	offset += sizeof(uint64_t);
	if (wire_version >= 2)
	{
		decoded.trade_generation = read_u64(bytes.data() + offset);
		offset += sizeof(uint64_t);
	}
	for (float &value : decoded.cargo)
	{
		value = std::bit_cast<float>(read_u32(bytes.data() + offset));
		offset += sizeof(uint32_t);
	}
	for (float &value : decoded.contraband)
	{
		value = std::bit_cast<float>(read_u32(bytes.data() + offset));
		offset += sizeof(uint32_t);
	}
	if (offset + digest.size() != bytes.size() || !valid_flat_cargo_record(decoded))
		return false;
	*record = decoded;
	return true;
}

/*
 * Read and decode the market record from `directory`, assuming the caller
 * already holds the store lock.
 *
 * Returns ok, not_found when the file is absent, invalid when it fails to
 * decode, or io_error.  `error` receives a human-readable reason.
 */
flat_cargo_result read_flat_cargo_unlocked(const std::string &directory, flat_cargo_record *record,
					   std::string *error)
{
	std::vector<uint8_t> bytes;
	const auto result =
		flatfile_read(directory, cargo_filename, cargo_record_size, &bytes, error);
	if (result == flatfile_read_result::not_found)
		return flat_cargo_result::not_found;
	if (result == flatfile_read_result::io_error)
		return flat_cargo_result::io_error;
	if (result != flatfile_read_result::ok || !decode_flat_cargo(bytes, record))
	{
		if (error && error->empty())
			*error = "cargo market authority is corrupt";
		return flat_cargo_result::invalid;
	}
	return flat_cargo_result::ok;
}

} // namespace

/*
 * Take the store lock and read the market record.  The locked wrapper around
 * read_flat_cargo_unlocked(); same return values.
 */
flat_cargo_result flatfile_cargo_load(const std::string &root, flat_cargo_record *record,
				      std::string *error)
{
	const std::string directory = root.empty() ? std::string() : root + "/metadata";
	if (directory.empty() || !record)
		return flat_cargo_result::invalid;
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error) ||
	    flatfile_authority_transaction_recover(root, authority, error) !=
		    flatfile_authority_transaction_result::ok)
		return flat_cargo_result::io_error;
	int lock_fd = -1;
	if (!flatfile_lock_acquire(directory, cargo_lock_filename, &lock_fd, error))
		return flat_cargo_result::io_error;
	const auto result = read_flat_cargo_unlocked(directory, record, error);
	flatfile_lock_release(lock_fd);
	return result;
}

/*
 * Write `record` out under the store lock, bumping its revision past
 * whatever is already on disk.
 *
 * Re-reading first is what makes the revision monotonic even if another
 * writer got there in between; the write itself goes through the flat-file
 * store's atomic replace, so a crash mid-save leaves the previous market
 * intact rather than a truncated one.
 */
flat_cargo_result flatfile_cargo_save(const std::string &root, flat_cargo_record record,
				      std::string *error)
{
	const std::string directory = root.empty() ? std::string() : root + "/metadata";
	if (directory.empty())
		return flat_cargo_result::invalid;
	flatfile_authority_lock authority;
	if (!authority.acquire(root, error) ||
	    flatfile_authority_transaction_recover(root, authority, error) !=
		    flatfile_authority_transaction_result::ok)
		return flat_cargo_result::io_error;
	int lock_fd = -1;
	if (!flatfile_lock_acquire(directory, cargo_lock_filename, &lock_fd, error))
		return flat_cargo_result::io_error;
	flat_cargo_record existing;
	const auto loaded = read_flat_cargo_unlocked(directory, &existing, error);
	if (loaded == flat_cargo_result::ok)
	{
		if (record.trade_generation != existing.trade_generation)
		{
			flatfile_lock_release(lock_fd);
			return flat_cargo_result::stale;
		}
		if (existing.revision == std::numeric_limits<uint64_t>::max())
		{
			flatfile_lock_release(lock_fd);
			return flat_cargo_result::invalid;
		}
		record.revision = existing.revision + 1;
	}
	else if (loaded == flat_cargo_result::not_found)
		record.revision = 1;
	else
	{
		flatfile_lock_release(lock_fd);
		return loaded;
	}
	std::vector<uint8_t> bytes;
	const bool encoded = encode_flat_cargo(record, &bytes);
	flatfile_authority_operation operation;
	operation.store = flatfile_authority_store::metadata;
	operation.filename = cargo_filename;
	operation.bytes = std::move(bytes);
	const bool stored = encoded && flatfile_authority_transaction_commit_operations(
					       root, authority, { operation }, error) ==
					       flatfile_authority_transaction_result::ok;
	flatfile_lock_release(lock_fd);
	return stored  ? flat_cargo_result::ok :
	       encoded ? flat_cargo_result::io_error :
			 flat_cargo_result::invalid;
}

/*
 * Apply a Divine trade's market cells to the stored record and prepare its
 * after-image for the caller's authority transaction.  The caller holds the
 * authority lock; the trade generation must match and advances by one.
 * On failure errno is EIO for a read error or ESTALE when the generation
 * moved; any other failure is a missing/corrupt record or an invalid cell.
 */
bool flatfile_cargo_prepare_trade(const std::string &root, const flatfile_authority_lock &lock,
				  uint64_t expected_generation,
				  const std::vector<divine_trade_market_cell> &cells,
				  flatfile_authority_operation *operation, std::string *error)
{
	if (!lock.matches(root) || !operation || cells.empty() || cells.size() > 16 ||
	    expected_generation == UINT64_MAX)
		return false;
	flat_cargo_record record;
	const auto loaded = read_flat_cargo_unlocked(root + "/metadata", &record, error);
	if (loaded != flat_cargo_result::ok)
	{
		errno = loaded == flat_cargo_result::io_error ? EIO : EILSEQ;
		return false;
	}
	if (record.trade_generation != expected_generation || record.revision == UINT64_MAX)
	{
		errno = ESTALE;
		return false;
	}
	std::set<std::array<uint8_t, 3>> changed;
	for (const auto &cell : cells)
	{
		if (cell.port >= FLATFILE_CARGO_PORTS || cell.commodity >= FLATFILE_CARGO_PORTS ||
		    !valid_market_modifier(cell.modifier) ||
		    (cell.goods != divine_trade_goods::cargo &&
		     cell.goods != divine_trade_goods::contraband) ||
		    !changed.insert({ cell.port, cell.commodity, static_cast<uint8_t>(cell.goods) })
			     .second)
			return false;
		(cell.goods == divine_trade_goods::cargo ?
			 record.cargo :
			 record.contraband)[cell.port * FLATFILE_CARGO_PORTS + cell.commodity] =
			cell.modifier;
	}
	++record.revision;
	++record.trade_generation;
	flatfile_authority_operation prepared;
	prepared.store = flatfile_authority_store::metadata;
	prepared.filename = cargo_filename;
	if (!encode_flat_cargo(record, &prepared.bytes))
		return false;
	*operation = std::move(prepared);
	return true;
}
