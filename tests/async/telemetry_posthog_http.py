"""Loopback HTTPS delivery fixtures used by test_telemetry_posthog.py.

No real token, external receiver, host environment or live journal is used.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import ssl
import struct
import subprocess
import threading
import time


class Receiver(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        # Deliberately cancelled TLS transfers may disconnect mid-response.
        pass


def http_tests(binary: Path, root: Path, environment: dict[str, str]) -> None:
    root.mkdir(mode=0o700)
    cert, key = root / "cert.pem", root / "key.pem"
    for prefix in ("", "other-"):
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
            "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout", str(root / (prefix + "key.pem")),
            "-out", str(root / (prefix + "cert.pem")),
        ], env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # A synthetic one-second libc DNS stall proves cancellation does not join
    # libcurl's resolver thread. stall.invalid avoids libcurl's localhost
    # shortcut; the marker proves the shim ran. It performs no real DNS lookup.
    shim = root / "dns.c"
    shim.write_text('#include <netdb.h>\n#include <unistd.h>\n'
                    '#include <stdio.h>\n#include <stdlib.h>\n'
                    'int getaddrinfo(const char *n,const char *s,const struct addrinfo *h,'
                    'struct addrinfo **r){(void)n;(void)s;(void)h;(void)r;'
                    'FILE *f=fopen(getenv("DURIS_TEST_DNS_STARTED"),"w");'
                    'if(f){fputs("called\\n",f);fclose(f);}'
                    'usleep(1000000);return EAI_AGAIN;}\n')
    subprocess.run(["cc", "-shared", "-fPIC", str(shim), "-o", str(root / "dns.so")],
                   env=environment, check=True, capture_output=True)

    cases = ("success", "flush", "batches", "bytes", "retry", "pin", "lost-response",
             "retry-after", "retry-date", "long-retry", "overflow-retry", "exhaustion",
             "400", "401", "403", "413", "redirect", "oversized", "headers",
             "tls", "quota", "quota-retry", "storage", "clock", "rollback",
             "expire", "deadline", "dns", "mono")
    for case in cases:
        received: list[bytes] = []
        reserved: list[tuple[int, int]] = []
        journal = root / case
        journal.mkdir(mode=0o700)

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def do_POST(self):
                assert self.path == "/batch/", self.path
                assert self.headers["Content-Type"] == "application/json"
                raw = self.rfile.read(int(self.headers["Content-Length"]))
                received.append(raw)
                # Wire-v2 quota words precede observations: the reservation is
                # already on disk when this independently scheduled receiver runs.
                frame = (journal / "outages.ledger").read_bytes()
                words = struct.unpack_from(">10Q", frame, 32)
                reserved.append((words[-2], words[-1]))
                attempt = len(received)
                status, headers, body = 200, {}, b"{}"
                if case == "lost-response" and attempt == 1:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    self.connection.close()
                    return
                if ((case in {"retry", "pin", "expire", "quota-retry"} and attempt == 1)
                        or (case == "exhaustion" and attempt <= 6)):
                    status = 503
                if case in {"retry-after", "retry-date", "long-retry", "overflow-retry"} and attempt == 1:
                    status = 429
                    headers["Retry-After"] = {
                        "retry-after": "3", "retry-date": "Fri, 04 Oct 2024 00:00:05 GMT",
                        "long-retry": "600", "overflow-retry": "999999999999999999999999999",
                    }[case]
                if case.isdecimal():
                    status = int(case)
                if case == "redirect":
                    status, headers = 307, {"Location": f"https://127.0.0.1:{self.server.server_port}/stolen"}
                if case == "oversized":
                    body = b"x" * 16385
                if case == "headers":
                    headers["X-Large"] = "x" * 16384
                if case == "deadline":
                    time.sleep(0.6)
                self.send_response(status)
                for name, value in headers.items():
                    self.send_header(name, value)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

        server = Receiver(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        env = dict(environment)
        if case == "dns":
            env["LD_PRELOAD"] = str(root / "dns.so")
            env["DURIS_TEST_DNS_STARTED"] = str(journal / "dns-started")
        # Proxy environment must not redirect or expose capture credentials.
        env["HTTPS_PROXY"] = "http://127.0.0.1:1"
        try:
            result = subprocess.run([
                str(binary), "send", case, str(journal), str(server.server_port),
                str(root / "other-cert.pem" if case == "tls" else cert),
            ], env=env, text=True, capture_output=True, timeout=15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        assert result.returncode == 0 and not result.stderr, (case, result)
        health = json.loads(result.stdout)
        assert health["cleanup_usec"] < 100_000, (case, health)
        assert health["longest_pulse_usec"] < 250_000, (case, health)
        assert health["attempted_batches"] == (1 if case in {"tls", "dns", "deadline", "mono"} else len(received)), (case, health, len(received))
        assert len(reserved) == len(received), (case, received, reserved)
        submitted = 0
        for index, raw in enumerate(received):
            value = json.loads(raw)
            assert set(value) == {"api_key", "batch"} and value["api_key"] == "phc_fixture"
            assert 0 < len(value["batch"]) <= 64 and len(raw) <= 256 * 1024
            assert all(row["uuid"] == row["properties"]["duris_event_id"] for row in value["batch"])
            submitted += len(value["batch"])
            assert sum(reserved[index]) >= submitted, (case, reserved, submitted)
            for row in value["batch"]:
                assert row["properties"]["$process_person_profile"] is False
        assert health["reserved_events"] == health["normal_reserved"] + health["health_reserved"]
        assert health["submitted_events"] == health["reserved_events"]
        if case in {"success", "flush", "clock", "batches", "bytes"}:
            assert health["acknowledged"] == health["created"] - health["suppressed"]
            assert health["output_events"] == 0 and health["state"] == 1, (case, health, [len(raw) for raw in received])
        if case == "batches":
            assert [len(json.loads(raw)["batch"]) for raw in received] == [64, 33]
        if case == "bytes":
            assert len(received) >= 2 and any(len(raw) > 220_000 for raw in received), (health, [len(raw) for raw in received])
        if case in {"retry", "pin", "lost-response", "retry-after", "retry-date"}:
            assert received[0] == received[1], case
            assert health["retry_attempts"] == 1 and health["ambiguous"] == 0
            assert health["acknowledged"] == (3 if case == "pin" else 2)
            assert len(received) == (3 if case == "pin" else 2)
        if case == "retry-after":
            assert health["delays"] == [3_000_000]
        if case == "retry-date":
            assert 3_000_000 < health["delays"][0] <= 5_000_000
        if case in {"long-retry", "overflow-retry"}:
            assert len(received) == 1 and health["state"] == 4 and health["ambiguous"] == 2
            assert health["next_attempt"] >= 600_000_000
        if case == "exhaustion":
            assert len(received) == 7 and health["retry_attempts"] == 4
            assert health["retry_exhaustions"] == 2 and health["recovery_probes"] == 2
            assert health["delays"] == [1_000_000, 2_000_000, 4_000_000, 8_000_000, 60_000_000, 60_000_000]
            assert health["acknowledged"] == 1 and health["ambiguous"] == 3
        if case in {"400", "401", "403", "413", "redirect", "oversized", "headers", "tls"}:
            assert health["state"] == 5 and health["acknowledged"] == 0
            assert health["retry_attempts"] == 0
            if case.isdecimal() or case == "redirect":
                assert health["suppressed"] == 2 and health["ambiguous"] == 0
            if case in {"oversized", "headers"}:
                assert health["response_limit_failures"] == 1
        if case == "quota":
            assert len(received) == 1 and health["normal_reserved"] == 0
            assert health["health_reserved"] == 1 and health["suppressed"] == 3
            assert health["acknowledged"] == 1 and health["quota_refusals"] == 1
        if case == "quota-retry":
            assert len(received) == 1 and health["quota_refusals"] == 1
            assert health["ambiguous"] == 2 and health["normal_reserved"] == 2
        if case in {"storage", "rollback"}:
            assert not received and health["reserved_events"] == 0
            assert health["storage_failures" if case == "storage" else "clock_failures"] == 1
        if case == "expire":
            assert len(received) == 1 and health["expired"] == 2 and health["ambiguous"] == 2
        if case in {"deadline", "dns"}:
            assert health["state"] == 8 and health["cancellations"] == 1, (case, health)
            assert health["ambiguous"] == 2 and health["normal_reserved"] == 2
        if case == "dns":
            assert (journal / "dns-started").read_text() == "called\n"
            assert not received
        if case == "mono":
            assert health["clock_failures"] == 1 and health["ambiguous"] == 2
        if case == "clock":
            assert health["clock_failures"] == 1 and health["suppressed"] == 2
    print(f"PostHog HTTPS: {len(cases)} loopback delivery/quota/cancellation scenarios PASS")


def runtime_tests(binary: Path, root: Path) -> None:
    import os
    # Never inherit project tokens, telemetry settings or host database targets.
    environment = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "ENVIRONMENT": "local"}
    root.mkdir(mode=0o700)
    cert, key = root / "cert.pem", root / "key.pem"
    subprocess.run([
        "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
        "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1",
        "-keyout", str(key), "-out", str(cert),
    ], env=environment, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for case in ("success", "restart", "deadline", "quota", "storage", "rollback",
                 "missing-key", "missing-token", "missing-host", "missing-sender",
                 "invalid-host", "invalid-project", "invalid-scope", "missing-scope", "production-scope",
                 "missing-quota", "quota-mismatch", "owner", "400", "401", "403", "503"):
        received: list[dict] = []
        journal = root / case
        journal.mkdir(mode=0o700)

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def do_POST(self):
                value = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                received.extend(value["batch"])
                if case == "deadline" and len(received) == len(value["batch"]):
                    (journal / "request-held").touch()
                    time.sleep(0.6)
                self.send_response(int(case) if case.isdecimal() else 200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")

        server = Receiver(("127.0.0.1", 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        env = dict(environment, POSTHOG_HOST="https://us.i.posthog.com", POSTHOG_API_KEY="phc_fixture",
                   POSTHOG_PROJECT_ID="678214", POSTHOG_SENDER_ID="99", TELEMETRY_TEST_RUN="native-runtime",
                   TELEMETRY_ENVIRONMENT_ID="1000",
                   TELEMETRY_IDENTITY_KEY="01" * 32, DURIS_TEST_POSTHOG_PORT=str(server.server_port),
                   DURIS_TEST_POSTHOG_CA=str(cert))
        try:
            result = subprocess.run([str(binary), case, str(journal)], env=env,
                                    text=True, capture_output=True, timeout=15)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        assert result.returncode == 0 and not result.stderr, (case, result)
        assert "telemetry PostHog runtime path passed" in result.stdout, (case, result)
        if case in {"success", "restart", "deadline"}:
            assert received, (case, result)
            sessions = [row for row in received if row["event"] == "duris_session"]
            if case != "deadline":
                assert len(sessions) == (2 if case == "restart" else 1), (case, sessions)
            summaries = [row["properties"] for row in received if row["event"] == "duris_character_summary"]
            assert summaries, (case, received)
            if case in {"success", "restart"}:
                expected = sum(json.loads(line)["connected"] for line in result.stdout.splitlines() if line.startswith("{"))
                observed = sum(int(row["time"]["connected_usec"]) for row in summaries)
                assert observed == expected > 0, (case, observed, expected)
                for row in summaries:
                    durations = row["time"]
                    assert int(durations["connected_usec"]) == sum(int(durations[name]) for name in ("active_usec", "idle_usec", "unknown_usec"))
                    assert sum(int(bucket["connected_usec"]) for bucket in row["time_allocations"]) == int(durations["connected_usec"])
            assert len({row["uuid"] for row in received}) == len(received), case
            assert all(row["properties"]["duris_test_run"] == "native-runtime" for row in received)
            assert all(int(row["properties"]["duris_environment_id"]) == 1000 for row in received)
        if case in {"missing-key", "missing-token", "missing-host", "missing-sender",
                    "invalid-host", "invalid-project", "invalid-scope", "missing-scope", "production-scope",
                    "missing-quota", "quota-mismatch", "owner", "rollback"}:
            assert not received, (case, received)
        if case == "storage":
            assert all(row["event"] == "duris_telemetry_health" for row in received), case
        if case not in {"storage", "owner", "missing-key", "missing-token", "missing-host",
                        "missing-sender", "invalid-host", "invalid-project", "invalid-scope", "missing-scope", "production-scope",
                        "missing-quota", "quota-mismatch"}:
            import sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/telemetry"))
            from outage import decode
            evidence = decode((journal / "outages.ledger").read_bytes())
            assert evidence["ledger_version"] == 3
            assert evidence["observations"][-1]["backend"] == "posthog"
            assert evidence["observations"][-1]["consumed_records"] > 0
            assert evidence["observations"][-1]["phase"] == "unknown_tail"
        print(f"PostHog native runtime {case}: PASS")
