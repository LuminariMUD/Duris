#include "net/discord_bridge.h"

#include <algorithm>
#include <cassert>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include <arpa/inet.h>
#include <cjson/cJSON.h>
#include <fcntl.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

static int send_error = 0, recv_error = 0, poll_error = 0, accept_error = 0;
static unsigned send_calls = 0, recv_calls = 0;
static std::size_t received_bytes = 0;
static std::size_t send_limit = 0;
static bool endless_interrupt = false;
static int accepted_fd = -1, listener_fd = -1;
static time_t monotonic_seconds = 1000;

extern "C" ssize_t __real_send(int, const void *, size_t, int);
extern "C" ssize_t __real_recv(int, void *, size_t, int);
extern "C" int __real_poll(pollfd *, nfds_t, int);
extern "C" int __real_accept4(int, sockaddr *, socklen_t *, int);
extern "C" int __real_clock_gettime(clockid_t, timespec *);

extern "C" int __wrap_clock_gettime(clockid_t clock, timespec *now)
{
	if (clock != CLOCK_MONOTONIC)
		return __real_clock_gettime(clock, now);
	*now = { monotonic_seconds, 0 };
	return 0;
}

extern "C" ssize_t __wrap_send(int fd, const void *data, size_t bytes, int flags)
{
	++send_calls;
	if (send_error || endless_interrupt)
	{
		errno = endless_interrupt ? EINTR : send_error;
		send_error = 0;
		return -1;
	}
	return __real_send(fd, data, send_limit ? std::min(bytes, send_limit) : bytes, flags);
}

extern "C" ssize_t __wrap_recv(int fd, void *data, size_t bytes, int flags)
{
	++recv_calls;
	if (recv_error || endless_interrupt)
	{
		errno = endless_interrupt ? EINTR : recv_error;
		recv_error = 0;
		return -1;
	}
	const auto result = __real_recv(fd, data, bytes, flags);
	if (result > 0)
		received_bytes += result;
	return result;
}

extern "C" int __wrap_poll(pollfd *fds, nfds_t count, int timeout)
{
	assert(timeout == 0);
	if (poll_error)
	{
		errno = poll_error;
		poll_error = 0;
		return -1;
	}
	// Allow loopback connect/write/close transitions to become readable before
	// assertions; the production call above must still request zero wait.
	return __real_poll(fds, count, 10);
}

extern "C" int __wrap_accept4(int fd, sockaddr *address, socklen_t *size, int flags)
{
	listener_fd = fd;
	if (accept_error)
	{
		errno = accept_error;
		accept_error = 0;
		return -1;
	}
	const int result = __real_accept4(fd, address, size, flags);
	if (result >= 0)
		accepted_fd = result;
	return result;
}

static void configure(const char *limit = "1048576", const char *secret = "")
{
	discord_bridge_shutdown();
	int reserve = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
	assert(reserve >= 0);
	sockaddr_in address{};
	address.sin_family = AF_INET;
	address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	assert(bind(reserve, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
	socklen_t size = sizeof(address);
	assert(getsockname(reserve, reinterpret_cast<sockaddr *>(&address), &size) == 0);
	setenv("DURIS_DISCORD_ENABLED", "TRUE", 1);
	setenv("DURIS_DISCORD_PORT", std::to_string(ntohs(address.sin_port)).c_str(), 1);
	setenv("DURIS_DISCORD_MAX_RECORD_BYTES", limit, 1);
	setenv("DURIS_DISCORD_AUTH_TOKEN", secret, 1);
	close(reserve);
	assert(discord_bridge_init());
}

static int connect_peer()
{
	int peer = socket(AF_INET, SOCK_STREAM | SOCK_CLOEXEC, 0);
	assert(peer >= 0);
	sockaddr_in address{};
	address.sin_family = AF_INET;
	address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	address.sin_port = htons(discord_bridge_get_status().port);
	assert(connect(peer, reinterpret_cast<sockaddr *>(&address), sizeof(address)) == 0);
	assert(fcntl(peer, F_SETFL, O_NONBLOCK) == 0);
	int nodelay = 1;
	setsockopt(peer, IPPROTO_TCP, TCP_NODELAY, &nodelay, sizeof(nodelay));
	discord_bridge_poll();
	return peer;
}

static void controls(int peer, const std::string &wire)
{
	const auto expected_bytes = received_bytes + wire.size();
	std::size_t offset = 0;
	while (offset < wire.size())
	{
		ssize_t bytes = write(peer, wire.data() + offset, wire.size() - offset);
		if (bytes < 0)
			assert(errno == EAGAIN || errno == EINTR);
		else
			offset += bytes;
		discord_bridge_poll();
	}
	// A successful local write does not mean the endpoint is readable yet.
	for (unsigned attempt = 0; received_bytes < expected_bytes && attempt < 1000; ++attempt)
	{
		usleep(1000);
		discord_bridge_poll();
	}
	assert(received_bytes == expected_bytes);
}

static std::string drain(int peer)
{
	const auto expected_bytes = discord_bridge_get_status().queued_bytes;
	std::string result;
	char buffer[16384];
	for (unsigned iteration = 0; iteration < 20000; ++iteration)
	{
		discord_bridge_flush();
		ssize_t bytes = read(peer, buffer, sizeof(buffer));
		if (bytes > 0)
			result.append(buffer, bytes);
		else if (!discord_bridge_get_status().queued_events &&
			 result.size() >= expected_bytes)
			return result;
		else
		{
			assert(bytes < 0 && (errno == EAGAIN || errno == EINTR));
			pollfd descriptor{ peer, POLLIN, 0 };
			assert(__real_poll(&descriptor, 1, 1000) > 0);
		}
	}
	assert(!"endpoint failed to drain within its bounded test deadline");
	return result;
}

static void verify_event(const std::string &wire, const char *name, const char *message)
{
	assert(!wire.empty() && wire.back() == '\n');
	cJSON *record = cJSON_ParseWithOpts(wire.c_str(), nullptr, true);
	assert(record);
	assert(strcmp(cJSON_GetObjectItemCaseSensitive(record, "channel")->valuestring,
		      "petition") == 0);
	assert(strcmp(cJSON_GetObjectItemCaseSensitive(record, "name")->valuestring, name) == 0);
	assert(strcmp(cJSON_GetObjectItemCaseSensitive(record, "message")->valuestring, message) ==
	       0);
	assert(cJSON_GetObjectItemCaseSensitive(record, "emoted")->valueint == 0);
	cJSON_Delete(record);
}

static void check_configuration()
{
	unsetenv("DURIS_DISCORD_ENABLED");
	assert(discord_bridge_init());
	assert(!discord_bridge_publish("A", "disabled"));
	assert(discord_bridge_get_status().dropped_events == 0);
	discord_bridge_poll();
	discord_bridge_flush();
	setenv("DURIS_DISCORD_ENABLED", "yes", 1);
	assert(!discord_bridge_init());
	setenv("DURIS_DISCORD_ENABLED", "TRUE", 1);
	for (const char *invalid : { "-1", "0", "65536", "123x", " 12", "9999999999999999999999" })
	{
		setenv("DURIS_DISCORD_PORT", invalid, 1);
		assert(!discord_bridge_init());
	}
	setenv("DURIS_DISCORD_PORT", "8181", 1);
	for (const char *invalid : { "0", "127", "1048577" })
	{
		setenv("DURIS_DISCORD_MAX_RECORD_BYTES", invalid, 1);
		assert(!discord_bridge_init());
	}
	setenv("DURIS_DISCORD_MAX_RECORD_BYTES", "128", 1);
	setenv("DURIS_DISCORD_AUTH_TOKEN", std::string(128, 'x').c_str(), 1);
	assert(!discord_bridge_init());
	setenv("DURIS_DISCORD_ENABLED", "FALSE", 1);
	assert(discord_bridge_init());
}

static void check_parser_and_auth()
{
	configure("128", "秘密🔥");
	assert(!discord_bridge_publish("A", "no client"));
	int peer = connect_peer();
	assert(!discord_bridge_publish("A", "before auth"));
	assert(discord_bridge_get_status().dropped_events == 2);
	controls(peer, "{\"channel\":\"auth\",\"message\":\"秘密🔥\\u0000suffix\"}\n");
	assert(!discord_bridge_get_status().authenticated);
	const std::string auth = "{\"channel\":\"auth\",\"message\":\"秘密🔥\"}\r\n";
	for (char byte : auth)
		controls(peer, std::string(1, byte));
	assert(discord_bridge_get_status().authenticated);
	const auto rejected = discord_bridge_get_status().rejected_records;
	controls(peer, "\n \t\r\n{\"channel\":\"heartbeat\",\"message\":\"ping\"}\n");
	assert(discord_bridge_get_status().rejected_records == rejected);
	controls(peer, "null\n[]\n{bad}\n{\"channel\":\"petition\",\"message\":\"do harm\"}\n");
	assert(discord_bridge_get_status().rejected_records == rejected + 4);
	std::string exact = "{\"channel\":\"heartbeat\",\"message\":\"ping\"}";
	exact.resize(128, ' ');
	controls(peer, exact + "\n" + exact + " \n" + auth);
	assert(discord_bridge_get_status().rejected_records == rejected + 5);
	assert(discord_bridge_get_status().authenticated);
	controls(peer, std::string(129, 'x'));
	controls(peer, "tail\n" + auth);
	assert(discord_bridge_get_status().rejected_records == rejected + 6);
	assert(discord_bridge_publish("Zoë -> A", "你好 🔥 \"quote\" \\ @everyone $"));
	verify_event(drain(peer), "Zoë -> A", "你好 🔥 \"quote\" \\ @everyone $");
	int extra = connect_peer();
	assert(discord_bridge_get_status().rejected_clients == 1);
	char byte;
	pollfd closed_extra{ extra, POLLIN, 0 };
	assert(__real_poll(&closed_extra, 1, 1000) > 0);
	assert(read(extra, &byte, 1) == 0);
	close(extra);
	controls(peer, "{\"channel\":\"auth\",\"message\":\"wrong\"}\n");
	assert(!discord_bridge_get_status().connected);
	assert(discord_bridge_get_status().auth_failures == 1);
	close(peer);
	peer = connect_peer();
	assert(!discord_bridge_get_status().authenticated);
	controls(peer, auth);
	assert(discord_bridge_get_status().authenticated);
	close(peer);
	discord_bridge_poll();
	assert(!discord_bridge_get_status().connected);
	// Neither an oversized discard state nor an unfinished UTF-8 record may
	// survive to a new connection. Authentication also resets every time.
	for (const std::string &fragment : { std::string(129, 'x'), auth.substr(0, 30) })
	{
		peer = connect_peer();
		controls(peer, fragment);
		close(peer);
		discord_bridge_poll();
		peer = connect_peer();
		assert(!discord_bridge_get_status().authenticated);
		controls(peer, auth);
		assert(discord_bridge_get_status().authenticated);
		close(peer);
		discord_bridge_poll();
	}
}

static void check_record_budget()
{
	const std::string auth = "{\"channel\":\"auth\",\"message\":\"secret\"}\n";
	for (bool authenticated : { false, true })
	{
		configure("128", "secret");
		int peer = connect_peer();
		if (authenticated)
		{
			controls(peer, auth);
			assert(discord_bridge_publish("A", "must be dropped on flooding"));
		}
		std::string burst;
		for (unsigned i = 0; i < 32; ++i)
			burst += "{}\n";
		controls(peer, burst);
		assert(discord_bridge_get_status().connected);
		assert(discord_bridge_get_status().rejected_records == 32);
		// The next pulse gets a fresh budget, but cannot parse a whole flood.
		controls(peer, burst + burst + burst);
		const auto flooded = discord_bridge_get_status();
		assert(!flooded.connected && !flooded.authenticated);
		assert(flooded.rejected_records == 65);
		assert(flooded.queued_events == 0 && flooded.queued_bytes == 0);
		assert(flooded.dropped_events == (authenticated ? 1u : 0u));
		close(peer);
		peer = connect_peer();
		controls(peer, auth);
		assert(discord_bridge_get_status().authenticated);
		assert(drain(peer).empty());
		assert(discord_bridge_publish("A", "after flood"));
		verify_event(drain(peer), "A", "after flood");
		close(peer);
	}
}

static void check_connection_deadlines()
{
	const std::string auth = "{\"channel\":\"auth\",\"message\":\"secret\"}\n";
	const std::string heartbeat = "{\"channel\":\"heartbeat\",\"message\":\"ping\"}\n";
	// Silence, unauthenticated heartbeats, and partial/invalid records must not
	// retain the only slot beyond the authentication deadline.
	for (const std::string &traffic :
	     { std::string(), heartbeat, std::string("{bad}\n{\"channel\":") })
	{
		configure("128", "secret");
		int peer = connect_peer();
		monotonic_seconds += 9;
		controls(peer, traffic);
		discord_bridge_poll();
		assert(discord_bridge_get_status().connected);
		++monotonic_seconds;
		discord_bridge_poll(); // no readable descriptor is needed for expiry
		assert(!discord_bridge_get_status().connected);
		close(peer);
		peer = connect_peer();
		controls(peer, auth);
		assert(discord_bridge_get_status().authenticated);
		assert(discord_bridge_publish("A", "replacement"));
		verify_event(drain(peer), "A", "replacement");
		close(peer);
	}

	for (const char *secret : { "secret", "" })
	{
		configure("128", secret);
		int peer = connect_peer();
		if (*secret)
		{
			monotonic_seconds += 9;
			controls(peer, auth);
		}
		// The companion Node bridge sends a heartbeat every 240 seconds.
		for (unsigned i = 0; i < 3; ++i)
		{
			monotonic_seconds += 240;
			controls(peer, heartbeat);
			assert(discord_bridge_get_status().authenticated);
		}
		monotonic_seconds += 299;
		controls(peer, "{bad}\n{\"channel\":\"petition\",\"message\":\"forged\"}\n{");
		assert(discord_bridge_get_status().connected);
		// Outbound traffic cannot demonstrate that this peer is still alive.
		assert(discord_bridge_publish("A", "delivered before expiry"));
		verify_event(drain(peer), "A", "delivered before expiry");
		assert(discord_bridge_publish("A", "must be dropped on expiry"));
		++monotonic_seconds;
		discord_bridge_poll();
		const auto expired = discord_bridge_get_status();
		assert(!expired.connected && !expired.authenticated);
		assert(expired.queued_events == 0 && expired.queued_bytes == 0);
		assert(expired.dropped_events == 1);
		close(peer);
		peer = connect_peer();
		if (*secret)
			controls(peer, auth);
		assert(drain(peer).empty());
		assert(discord_bridge_publish("A", "fresh connection"));
		verify_event(drain(peer), "A", "fresh connection");
		close(peer);
	}
}

static void check_queues_and_faults()
{
	configure();
	int peer = connect_peer();
	const int endpoint_client = accepted_fd;
	assert(fcntl(endpoint_client, F_GETFD) & FD_CLOEXEC);
	assert(fcntl(listener_fd, F_GETFD) & FD_CLOEXEC);
	assert(fcntl(endpoint_client, F_GETFL) & O_NONBLOCK);
	assert(fcntl(listener_fd, F_GETFL) & O_NONBLOCK);
	assert(discord_bridge_publish("A", "one"));
	send_error = EAGAIN;
	discord_bridge_flush();
	assert(discord_bridge_get_status().queued_events == 1);
	endless_interrupt = true;
	send_calls = 0;
	discord_bridge_flush();
	assert(send_calls == 32);
	endless_interrupt = false;
	send_error = EINTR;
	send_limit = 1;
	discord_bridge_flush();
	assert(discord_bridge_get_status().queued_events == 1);
	verify_event(drain(peer), "A", "one");
	send_limit = 0;
	for (unsigned i = 0; i < 256; ++i)
		assert(discord_bridge_publish("A", "queued"));
	assert(!discord_bridge_publish("A", "overflow"));
	assert(discord_bridge_get_status().queued_events == 256);
	close(peer);
	discord_bridge_poll();
	assert(discord_bridge_get_status().queued_events == 0);
	assert(discord_bridge_get_status().dropped_events == 257);
	peer = connect_peer();
	char byte;
	assert(read(peer, &byte, 1) < 0 && errno == EAGAIN);
	std::string huge(900000, 'x');
	for (unsigned i = 0; i < 4; ++i)
		assert(discord_bridge_publish("A", huge.c_str()));
	assert(!discord_bridge_publish("A", huge.c_str()));
	const auto before = discord_bridge_get_status().queued_bytes;
	discord_bridge_flush();
	assert(discord_bridge_get_status().queued_bytes == before); // retained partial front
	send_error = EPIPE;
	discord_bridge_flush();
	assert(!discord_bridge_get_status().connected);
	close(peer);
	peer = connect_peer();
	assert(read(peer, &byte, 1) < 0 && errno == EAGAIN);
	assert(discord_bridge_publish("A", "fresh after partial failure"));
	verify_event(drain(peer), "A", "fresh after partial failure");
	assert(!discord_bridge_publish("A", std::string(1048576, 'x').c_str()));
	assert(!discord_bridge_publish(nullptr, "bad"));
	const char heartbeat[] = "{\"channel\":\"heartbeat\",\"message\":\"ping\"}\n";
	assert(write(peer, heartbeat, sizeof(heartbeat) - 1) > 0);
	poll_error = EINTR;
	discord_bridge_poll();
	endless_interrupt = true;
	recv_calls = 0;
	discord_bridge_poll();
	assert(recv_calls == 32);
	endless_interrupt = false;
	recv_error = EINTR;
	discord_bridge_poll();
	assert(discord_bridge_get_status().rejected_records == 0);
	assert(write(peer, heartbeat, sizeof(heartbeat) - 1) > 0);
	recv_error = EAGAIN;
	discord_bridge_poll();
	discord_bridge_poll();
	assert(discord_bridge_get_status().rejected_records == 0);
	close(accepted_fd); // an actual invalid descriptor, reported by poll as POLLNVAL
	discord_bridge_poll();
	assert(!discord_bridge_get_status().connected);
	close(peer);
	accept_error = EINTR;
	peer = connect_peer();
	assert(discord_bridge_get_status().connected);
	assert(discord_bridge_publish("A", "after failure"));
	verify_event(drain(peer), "A", "after failure");
	// A failed exec does not close CLOEXEC sockets or clear pending output.
	assert(discord_bridge_publish("A", "failed exec retained"));
	execl("/no/such/duris-copyover-executable", "missing", nullptr);
	assert(errno == ENOENT);
	verify_event(drain(peer), "A", "failed exec retained");
	discord_bridge_shutdown();
	pollfd closed_peer{ peer, POLLIN, 0 };
	assert(__real_poll(&closed_peer, 1, 1000) > 0);
	assert(read(peer, &byte, 1) == 0);
	close(peer);
}

static void check_high_descriptors()
{
	std::vector<int> fillers;
	int fd = -1;
	while (fd < 1100)
	{
		fd = open("/dev/null", O_RDONLY | O_CLOEXEC);
		assert(fd >= 0);
		fillers.push_back(fd);
	}
	configure();
	int peer = connect_peer();
	assert(listener_fd > 1024 && accepted_fd > 1024);
	assert(discord_bridge_publish("A", "high fd"));
	verify_event(drain(peer), "A", "high fd");
	close(listener_fd);
	discord_bridge_poll();
	assert(!discord_bridge_get_status().listening);
	close(peer);
	for (int filler : fillers)
		close(filler);
}

int main(int argc, char **argv)
{
	if (argc == 4 && strcmp(argv[1], "--after-exec") == 0)
	{
		assert(fcntl(atoi(argv[2]), F_GETFD) == -1 && errno == EBADF);
		assert(fcntl(atoi(argv[3]), F_GETFD) == -1 && errno == EBADF);
		assert(discord_bridge_init()); // same port from the inherited environment
		int peer = connect_peer();
		assert(discord_bridge_publish("A", "new process"));
		verify_event(drain(peer), "A", "new process");
		close(peer);
		discord_bridge_shutdown();
		return 0;
	}
	check_configuration();
	check_parser_and_auth();
	check_record_budget();
	check_connection_deadlines();
	check_queues_and_faults();
	check_high_descriptors();
	pid_t child = fork();
	assert(child >= 0);
	if (child == 0)
	{
		configure();
		connect_peer();
		assert(discord_bridge_publish("A", "must not replay after exec"));
		const auto listener_arg = std::to_string(listener_fd);
		const auto client_arg = std::to_string(accepted_fd);
		execl(argv[0], argv[0], "--after-exec", listener_arg.c_str(), client_arg.c_str(),
		      nullptr);
		_exit(99);
	}
	int result;
	assert(waitpid(child, &result, 0) == child);
	assert(WIFEXITED(result) && WEXITSTATUS(result) == 0);
	puts("Discord bridge real-socket runtime harness passed");
}
