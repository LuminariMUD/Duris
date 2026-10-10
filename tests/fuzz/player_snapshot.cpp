// Player save decoding: player_snapshot_decode() and player_item_snapshot_list_decode(), and
// a round trip: what decodes encodes to bytes that decode and encode to the same bytes.
// The first byte picks the decoder: odd for an item list, even for a whole snapshot.
// fuzz-sources: src/player/player_snapshot_codec.c
// fuzz-libs:
// fuzz-max-len: 4194400 (past PLAYER_SNAPSHOT_MAX_BYTES (4 MiB))
#include "player/player_snapshot_codec.h"

#include <cstdint>
#include <cstdlib>
#include <vector>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
	if (size < 1)
		return 0;
	if (data[0] & 1)
	{
		std::vector<player_item_snapshot> items, again;
		std::vector<uint8_t> encoded, reencoded;
		if (player_item_snapshot_list_decode(data + 1, size - 1, &items) !=
		    player_snapshot_codec_result::ok)
			return 0;
		if (player_item_snapshot_list_encode(items, &encoded) !=
			    player_snapshot_codec_result::ok ||
		    player_item_snapshot_list_decode(encoded.data(), encoded.size(), &again) !=
			    player_snapshot_codec_result::ok ||
		    player_item_snapshot_list_encode(again, &reencoded) !=
			    player_snapshot_codec_result::ok ||
		    reencoded != encoded)
			abort();
		return 0;
	}
	player_snapshot snapshot, again;
	std::vector<uint8_t> encoded, reencoded;
	if (player_snapshot_decode(data + 1, size - 1, &snapshot) !=
	    player_snapshot_codec_result::ok)
		return 0;
	if (player_snapshot_encode(snapshot, &encoded) != player_snapshot_codec_result::ok ||
	    player_snapshot_decode(encoded.data(), encoded.size(), &again) !=
		    player_snapshot_codec_result::ok ||
	    player_snapshot_encode(again, &reencoded) != player_snapshot_codec_result::ok ||
	    reencoded != encoded)
		abort();
	return 0;
}
