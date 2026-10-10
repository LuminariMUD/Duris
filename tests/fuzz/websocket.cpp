// The WebSocket upgrade request and frames: websocket_parse_handshake() and
// websocket_parse_frame(). Any client reaches them before logging in. The first byte picks
// the parser: odd for the HTTP upgrade (bit 4 makes the peer a trusted proxy, whose
// X-Forwarded-For is read), even for the frames that follow (bit 2 turns on compression
// with the inflater a negotiated connection gets, so a message spans frames).
// fuzz-sources: src/net/websocket.c
// fuzz-libs: -lcjson -lssl -lcrypto -lz
#include "core/structs.h"
#include "net/websocket.h"

#include <cjson/cJSON.h>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <zlib.h>

extern "C"
{
	descriptor_data *descriptor_list = nullptr;
	int sql_pool_is_active(void)
	{
		return 0;
	}
}

void close_socket(descriptor_data *) {}
bool persistence_mode_requires_mysql(void)
{
	return false;
}
void banlog(int, const char *, ...) {}
int bannedsite(char *, int)
{
	return 0;
}
int checked_snprintf_at(const char *, int, char *destination, size_t destination_size,
			const char *format, ...)
{
	va_list arguments;
	va_start(arguments, format);
	const int result = vsnprintf(destination, destination_size, format, arguments);
	va_end(arguments);
	return result;
}
int is_desc_valid(descriptor_data *)
{
	return 1;
}
void write_to_q(const char *, txt_q *, int) {}
void ws_send_system(descriptor_data *, const char *, const char *) {}
void gmcp_handle_input(descriptor_data *, const char *, size_t) {}
void ws_handle_command(descriptor_data *, const char *, cJSON *) {}
char *json_build_gmcp_message(const char *, const char *)
{
	return nullptr;
}
void resolve_descriptor_hostname_async(const char *, int) {}
static int trusted_proxy;
int proxy_peer_is_trusted(int)
{
	return trusted_proxy;
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size)
{
	if (size < 1)
		return 0;
	descriptor_data d{};
	d.descriptor = -1;
	const char *input = reinterpret_cast<const char *>(data + 1);
	if (data[0] & 1)
	{
		trusted_proxy = data[0] & 4;
		websocket_parse_handshake(&d, input, size - 1);
	}
	else
	{
		d.websocket = 1;
		d.ws_handshake_done = 1;
		d.ws_state = WS_STATE_OPEN;
		if (data[0] & 2)
		{
			// As websocket_complete_handshake() sets it up for permessage-deflate.
			z_stream *inflater = static_cast<z_stream *>(calloc(1, sizeof(z_stream)));
			if (inflater && inflateInit2(inflater, -15) == Z_OK)
			{
				d.ws_inflate_stream = inflater;
				d.ws_compress = 1;
			}
			else
				free(inflater);
		}
		for (size_t offset = 0; offset < size - 1;)
		{
			char *payload = nullptr;
			size_t payload_len = 0;
			int opcode = 0, fin = 0;
			const int used = websocket_parse_frame(&d, input + offset,
							       size - 1 - offset, &payload,
							       &payload_len, &opcode, &fin);
			free(payload);
			if (used <= 0)
				break;
			offset += used;
		}
	}
	websocket_free(&d);
	return 0;
}
