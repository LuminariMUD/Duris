#!/usr/bin/env python3
"""Real listener failures return to worker cleanup and preserve useful diagnostics."""
from pathlib import Path
import resource
import subprocess
import tempfile

from _paths import ROOT, extract_function

comm = (ROOT / "src/net/comm.c").read_text()
start = comm.index('\telse\n\t{\n\t\tlogit(LOG_STATUS, "Opening mother connection.")')
end = comm.index("\n\t// The JSON bridge", start)
harness = r'''
#include <arpa/inet.h>
#include <sys/socket.h>
#include <fcntl.h>
#include <unistd.h>
#include <atomic>
#include <cassert>
#include <cerrno>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>
#include <thread>

#define LOG_EXIT "exit"
#define LOG_STATUS "status"
#define MIN_SOCKET_BUFFER_SIZE 20480
static constexpr int WS_PORT = 0;
static int _reboot = 0;
static int plain = -1, tls = -1;
static bool entered = false;
static std::string diagnostic;
static std::thread worker;
static std::atomic<bool> stop{false};

void logit(const char *category, const char *format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    if (!strcmp(category, LOG_EXIT)) diagnostic = buffer;
    errno = EIO; // Logging must not replace the captured syscall error.
}
int websocket_init(int) { std::abort(); }
''' + extract_function("comm.c", "void nonblock(") + "\n" + \
    extract_function("comm.c", "bool runtime_listener_address(") + "\n" + \
    extract_function("comm.c", "int init_socket(") + r'''
void open_listeners(int port, int sslport) {
    int s = -1, S = -1, WS = -1;
    if (false) {}
''' + comm[start:end] + r'''
    assert(WS == -1);
    plain = s;
    tls = S;
    entered = true;
}

int socket_port(int fd) {
    sockaddr_in6 address{};
    socklen_t size = sizeof(address);
    assert(getsockname(fd, reinterpret_cast<sockaddr *>(&address), &size) == 0);
    return ntohs(address.sin6_port);
}
int fd_count() {
    int count = 0;
    for (const auto &entry : std::filesystem::directory_iterator("/proc/self/fd")) {
        (void)entry;
        ++count;
    }
    return count;
}
int main(int argc, char **argv) {
    assert(argc == 2);
    unsetenv("DURIS_WEBSOCKET");
    setenv("LISTEN_ADDRESS", "127.0.0.1", 1);
    const std::string mode = argv[1];
    int blocker = -1, port = 0, sslport = 0, expected_error = 0;
    if (mode == "plain" || mode == "tls") {
        blocker = init_socket(0);
        assert(blocker >= 0);
        (mode == "plain" ? port : sslport) = socket_port(blocker);
        expected_error = EADDRINUSE;
    } else if (mode == "unavailable") {
        setenv("LISTEN_ADDRESS", "192.0.2.1", 1);
        expected_error = EADDRNOTAVAIL;
    } else if (mode == "invalid") {
        setenv("LISTEN_ADDRESS", "invalid-address", 1);
    } else {
        assert(mode == "success");
    }
    worker = std::thread([] { while (!stop.load()) std::this_thread::yield(); });
    const int before = fd_count();
    for (int attempt = 0; attempt < 8; ++attempt) {
        open_listeners(port, sslport);
        if (mode == "success") {
            assert(entered && !_reboot && plain >= 0 && tls >= 0);
            assert(socket_port(plain) != socket_port(tls));
            for (int fd : {plain, tls}) {
                int accepting = 0;
                socklen_t size = sizeof(accepting);
                assert(getsockopt(fd, SOL_SOCKET, SO_ACCEPTCONN, &accepting, &size) == 0);
                assert(accepting == 1);
                close(fd);
            }
        } else {
            assert(!entered && _reboot == 1);
            if (expected_error) {
                assert(diagnostic.find(std::strerror(expected_error)) != std::string::npos);
                assert(diagnostic.find("errno=" + std::to_string(expected_error)) != std::string::npos);
                const int failed_port = mode == "tls" ? sslport : port;
                assert(diagnostic.find("]:" + std::to_string(failed_port)) != std::string::npos);
                assert(diagnostic.find(mode == "unavailable" ? "192.0.2.1" : "127.0.0.1") != std::string::npos);
            } else {
                assert(diagnostic.find("LISTEN_ADDRESS") != std::string::npos);
            }
        }
        assert(fd_count() == before); // Includes the first listener when TLS fails.
    }
    stop = true;
    worker.join();
    if (blocker >= 0) close(blocker);
}
'''

with tempfile.TemporaryDirectory(prefix="duris-listener-startup-") as directory:
    work = Path(directory)
    source, binary = work / "test.cpp", work / "test"
    source.write_text(harness)
    subprocess.run(["g++", "-std=c++20", "-Wall", "-Wextra", "-Werror", "-pthread",
                    str(source), "-o", str(binary)], cwd=ROOT, check=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    for mode in ("plain", "tls", "unavailable", "invalid", "success"):
        subprocess.run([str(binary), mode], cwd=work, check=True, timeout=10)

print("listener failures retain errno, release sockets, and return to join live workers")
