#!/usr/bin/env python3
"""Immutable post-baseline migration manifest and success-last runner."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import hmac
import json
import os
import re
import secrets
import select
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "migrations" / "migration_manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_MIGRATION_BYTES = 8 * 1024 * 1024
MAX_PRODUCTION_BACKUP_AGE_SECONDS = 2 * 60 * 60
MANIFEST_FIELDS = {"manifest_version", "runner_version", "baseline", "migrations"}
BASELINE_FIELDS = {
    "id", "required_table_count", "required_table_fingerprint", "required_tables",
}
MIGRATION_FIELDS = {
    "id", "sequence", "description", "apply", "apply_checksum", "verify",
    "verify_checksum", "compatibility",
}
# A migration's verifier for an engine its sealed verifier does not know. The verifiers of
# 0031 and 0032 accept only MariaDB 10.11 and MySQL 8.0, and a sealed file cannot change:
# its checksum is in every database's history. The history keeps the sealed checksum.
ENGINE_VERIFIER_FIELDS = {"migration", "engine", "verify", "verify_checksum"}
ENGINE_VERSIONS = {"mariadb-11.8": r"11\.8\.[0-9]+-MariaDB.*"}
ONLINE_LEVEL_CAP_ID = "0039_level_cap_sides"
ONLINE_LEVEL_CAP_APPLY = "4c343e649e77e70cf9cf66fcaaca714e35b2f1c0ed0f9922f988a947c4a78f3e"
ONLINE_LEVEL_CAP_VERIFY = "a9cbde7decfc928629dc2a88baead64305c55a67b919b2dbe5ce3c20d0d3d652"
ONLINE_COMBAT_ALLIES_ID = "0040_combat_outcome_allies"
ONLINE_COMBAT_ALLIES_APPLY = "a773ccf7be009953a432bec85132313cd372424720465616738e419588e7b05e"
ONLINE_COMBAT_ALLIES_VERIFY = "da0f8d40b37af4333c56bfd930babd20cd06e745b480c548dc9fb48859d7cffa"
ONLINE_NEXUS_ID = "0046_nexus_phase1"
ONLINE_NEXUS_APPLY = "40177ee8fa931b8f06150dd96194e680517f7567192f22bb68c78d285735d2b6"
ONLINE_NEXUS_VERIFY = "bae36e32b7c3deef76d308c34a5ca1f4f5a2ed9f91f5e3d1eafe86f98882f35f"
ONLINE_ARTIFACT_REJECTIONS_ID = "0047_artifact_rejected_identities"
ONLINE_ARTIFACT_REJECTIONS_APPLY = "5692e9ddcaef423f6b1d487005f0fdafc50b6bccbd85c66fc5ce8875c218bb4b"
ONLINE_ARTIFACT_REJECTIONS_VERIFY = "c88ba4baed7333bfa6f39a5df551bae5b08d267a7d8a929a659b09125004b4a8"
ONLINE_PLAYER_UPDATES = (
    ("0042_player_base_stats",
     "a5698a97f953e175fee3030fd7408fff5a7cdb53d15d6bd8bfb5136f203ec78f",
     "5210ecad75bcd7948718ece18d6033cd34770c5091c6a7a24551f95d338f0533"),
    ("0043_news_acknowledgement",
     "fb6243dd098b4f017fbda8d9aeb422f606a3aa7c5a96969c2ed4d369a154ef60",
     "2cca57fdb73c604aecf44d3e75295510eddbbdadbf4b2da50ca74e2328faba6a"),
)
ONLINE_ARTIFACT_PVP = (
    ("0044_artifact_canonical_identity",
     "1d64797c4ad6c448c4a771262fd08e0ee4e79b3db0f84ba3143db9856395afce",
     "d008062231aaab96090ad593fb281bb7876a080948cfe5742b575b0f5697be84"),
    ("0045_pkill_webinfo_at_capture",
     "9ec4164a7f70796409f6e88e483b1e90044eae1ff8ef9c3151397dba9e24e110",
     "0d3f5cf89844a00fdba5e0be9cec79bd6b91bcb79c20bd94157d57f43e0a96d1"),
)
ONLINE_OUTBOX_EXPECTATIONS_ID = "0050_critical_outbox_expectations"
ONLINE_OUTBOX_EXPECTATIONS_APPLY = "fc3590231a567095458ff25bf19635a479eac3f2b63f0eb360900c5279cf423a"
ONLINE_OUTBOX_EXPECTATIONS_VERIFY = "0e46e28c7f4bb57110b03dbe6c338d9a48d9169ea0b595c9971f7620e29fff94"
ONLINE_PWIPE_ROSTER_ID = "0052_pwipe_roster_checkpoint"
ONLINE_PWIPE_ROSTER_APPLY = "497c7d9eb21f5fdad4dca04edf1289a1f61e7f022129dc612d73b5963b1161ef"
ONLINE_PWIPE_ROSTER_VERIFY = "5bc71cbd1a39cd1a036e2d907c9002cc7ff8f082c914d07948201ed4c0f86f8e"
ONLINE_WORLD_QUEST_ID = "0055_world_quest_recovery"
ONLINE_WORLD_QUEST_APPLY = "47767f2f2110f99179be5ae51a04e1250fa2380cdf4e5b6a4d2eb885e46999bb"
ONLINE_WORLD_QUEST_VERIFY = "344a942d5d7122aa55470cc77b11220fa55d0fff73d87e0dc937da70e823713a"
ONLINE_QUEST_REWARD_COUNT_ID = "0058_world_quest_reward_count"
ONLINE_QUEST_REWARD_COUNT_APPLY = "d2ec137c50a0e5e4c91af6090c2e07c92959de4c192974c92088d716b040ccef"
ONLINE_QUEST_REWARD_COUNT_VERIFY = "dc73918bc2426edbc0a607b4577eb6e86b9cec72b43f9d4c5346424013651316"
ONLINE_DIVINE_BOON = (
    ("0048_divine_boon_state",
     "7c84955a35a6f34e4618773b2f08c2470219a54a982b0bf3e5a161ece78d0a68",
     "beb92063f46b04089b21520f242334d15dd127d35ef381030d40a2da17822234"),
    ("0049_divine_boon_delivery",
     "e4e0268f5f7ab27b6872f87d44453c862116829b80fdc247191c968a207a41b3",
     "d9ace2841a6cc5b9fb2ef28a8a9fa46467cf99f63be71fdfa96bb4ff08bc7f15"),
)
ONLINE_DIVINE_TRADE = (
    ("0050_divine_trade_state",
     "3657f30c78faea6b728e456220c62737aceea2e44968d0e1b88d27e57674861c",
     "6e580109ffc73d3e1e82493c1b6b9b4df5dad38fbb9a244de1c7b2e1f53b9508"),
    ("0051_divine_effect_delivery",
     "60c23ec1a9a172ad04fda08dc041bc0d90192e69054008b06d282b00b86a32b7",
     "3f37071ddb6706e39a4736daa0bcd3d156acbb192e08acbf760985ef706b6c2c"),
)
ONLINE_CHEST_FRAG = (
    ("0056_private_chest_receipts",
     "c45fd75d0332eb756e067746bf8430ed251ea9261ef83abb0cdc9a9e50d9144c",
     "4c6f51ac4ab2e8dc7ee96028d11cf877bc05689d92a4c85303c3536394916d3d"),
    ("0057_shared_frag_cap",
     "c462a873548d8c24987ac00964a88445fc6f0590eaabfbb7a2a8b42922818742",
     "6656fbbf70210957aa306640f5ab2b519c10cb9f9dbac5bf5d3337ba5b02fc8d"),
)


class MigrationContractError(Exception):
    pass


def strict_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise MigrationContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def read_regular(path: Path, maximum: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as source:
            payload = source.read(maximum + 1)
    except OSError as error:
        raise MigrationContractError(f"cannot read {label}: {error}") from error
    if len(payload) > maximum:
        raise MigrationContractError(f"{label} exceeds fixed bound")
    return payload


def checksum(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate_production_backup(path: Path, database: str) -> None:
    if not path.is_absolute() or not re.fullmatch(r"[A-Za-z0-9_.-]+", database):
        raise MigrationContractError("production backup path or database name is invalid")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
        metadata = os.fstat(descriptor)
    except OSError as error:
        raise MigrationContractError(f"cannot open production backup: {error}") from error
    try:
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid() or \
                metadata.st_mode & 0o077:
            raise MigrationContractError(
                "production backup must be an owner-only regular file")
        age = time.time() - metadata.st_mtime
        if age < -300 or age > MAX_PRODUCTION_BACKUP_AGE_SECONDS:
            raise MigrationContractError("production backup is not recent")
        markers = {
            f"USE `{database}`;".encode(),
            b"CREATE TABLE `accounts`",
            b"CREATE TABLE `player_data`",
            b"CREATE TABLE `ships`",
        }
        tail = b""
        with os.fdopen(descriptor, "rb") as raw:
            descriptor = -1
            with gzip.GzipFile(fileobj=raw) as source:
                while payload := source.read(1024 * 1024):
                    window = tail + payload
                    markers = {marker for marker in markers if marker not in window}
                    tail = window[-512:]
        if markers:
            raise MigrationContractError(
                "production backup does not identify the configured Duris database")
    except (OSError, EOFError) as error:
        raise MigrationContractError(f"production backup validation failed: {error}") from error
    finally:
        if descriptor >= 0:
            os.close(descriptor)


@dataclass(frozen=True)
class Migration:
    migration_id: str
    sequence: int
    description: str
    apply_path: Path
    apply_checksum: str
    verify_path: Path
    verify_checksum: str
    compatibility: str
    engine_verifiers: tuple[tuple[str, Path], ...] = ()

    def verifier(self, engine: str) -> Path:
        """The verifier to run on `engine`: its own one, or the sealed one."""
        return dict(self.engine_verifiers).get(engine, self.verify_path)


def engine_of(version: str) -> str:
    """The ENGINE_VERSIONS name of a server's SELECT VERSION(), or '' for any other."""
    for engine, pattern in ENGINE_VERSIONS.items():
        if re.fullmatch(pattern, version):
            return engine
    return ""


@dataclass(frozen=True)
class Manifest:
    version: int
    runner_version: int
    baseline_id: str
    required_table_count: int
    required_table_fingerprint: str
    required_tables: tuple[str, ...]
    migrations: tuple[Migration, ...]


@dataclass(frozen=True)
class AppliedMigration:
    migration_id: str
    sequence: int
    description: str
    apply_checksum: str
    verify_checksum: str
    compatibility: str
    runner_version: int


def load_manifest(path: Path = DEFAULT_MANIFEST) -> Manifest:
    try:
        raw = read_regular(path, MAX_MANIFEST_BYTES, "migration manifest")
        value = json.loads(raw, object_pairs_hook=strict_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MigrationContractError(f"migration manifest parse failed: {error}") from error
    if not isinstance(value, dict) or \
            set(value) - {"engine_verifiers"} != MANIFEST_FIELDS:
        raise MigrationContractError("migration manifest fields differ")
    if type(value["manifest_version"]) is not int or value["manifest_version"] != 1 or \
            type(value["runner_version"]) is not int or value["runner_version"] != 1:
        raise MigrationContractError("unsupported manifest or runner version")
    baseline = value["baseline"]
    if not isinstance(baseline, dict) or set(baseline) != BASELINE_FIELDS or \
            not re.fullmatch(r"[a-z0-9][a-z0-9._-]{7,63}", baseline.get("id", "")) or \
            type(baseline.get("required_table_count")) is not int or \
            baseline["required_table_count"] < 1 or \
            not re.fullmatch(r"[0-9a-f]{64}", baseline.get(
                "required_table_fingerprint", "")):
        raise MigrationContractError("baseline contract is invalid")
    required_tables = baseline["required_tables"]
    if not isinstance(required_tables, list) or \
            len(required_tables) != baseline["required_table_count"]:
        raise MigrationContractError("baseline table inventory count differs")
    try:
        required_fingerprint = table_fingerprint(required_tables)
    except MigrationContractError as error:
        raise MigrationContractError("baseline table inventory is invalid") from error
    if required_fingerprint != baseline["required_table_fingerprint"]:
        raise MigrationContractError("baseline table inventory fingerprint differs")
    items = value["migrations"]
    if not isinstance(items, list):
        raise MigrationContractError("migrations must be a list")
    directory = path.resolve().parent
    migrations = []
    seen_ids = set()
    for expected_sequence, item in enumerate(items, 1):
        if not isinstance(item, dict) or set(item) != MIGRATION_FIELDS:
            raise MigrationContractError("migration fields differ")
        migration_id = item["id"]
        if not isinstance(migration_id, str) or \
                not re.fullmatch(r"[0-9]{4}_[a-z0-9][a-z0-9_]{2,54}", migration_id):
            raise MigrationContractError("migration id is invalid")
        if migration_id in seen_ids:
            raise MigrationContractError("duplicate migration id")
        seen_ids.add(migration_id)
        if item["sequence"] != expected_sequence:
            raise MigrationContractError("migration sequence is missing or reordered")
        paths = []
        for field, extension in (("apply", "sql"), ("verify", "sh")):
            relative = item[field]
            if not isinstance(relative, str) or not re.fullmatch(
                    rf"immutable/[0-9]{{4}}_[a-z0-9_]+\.{extension}", relative):
                raise MigrationContractError(f"migration {field} path is invalid")
            candidate = directory / relative
            if candidate.resolve().parent != (directory / "immutable").resolve():
                raise MigrationContractError("migration path escapes immutable directory")
            paths.append(candidate)
        apply_payload = read_regular(paths[0], MAX_MIGRATION_BYTES, "migration apply")
        verify_payload = read_regular(paths[1], MAX_MIGRATION_BYTES, "migration verifier")
        if item["apply_checksum"] != checksum(apply_payload) or \
                item["verify_checksum"] != checksum(verify_payload):
            raise MigrationContractError("migration content checksum mismatch")
        if not isinstance(item["description"], str) or \
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/+()-]{2,254}",
                                 item["description"]) or \
                not isinstance(item["compatibility"], str) or not re.fullmatch(
                    r"[A-Za-z0-9][A-Za-z0-9._+-]{2,63}", item["compatibility"]):
            raise MigrationContractError("migration metadata is invalid")
        migrations.append(Migration(migration_id, expected_sequence, item["description"],
                                    paths[0], item["apply_checksum"], paths[1],
                                    item["verify_checksum"], item["compatibility"]))
    engine_verifiers: dict[str, list[tuple[str, Path]]] = {}
    items = value.get("engine_verifiers", [])
    if not isinstance(items, list):
        raise MigrationContractError("engine verifiers must be a list")
    for item in items:
        if not isinstance(item, dict) or set(item) != ENGINE_VERIFIER_FIELDS:
            raise MigrationContractError("engine verifier fields differ")
        owner = item["migration"]
        relative = item["verify"]
        if owner not in seen_ids or item["engine"] not in ENGINE_VERSIONS or \
                any(engine == item["engine"] for engine, _ in engine_verifiers.get(owner, [])):
            raise MigrationContractError("engine verifier names no migration or engine")
        if not isinstance(relative, str) or not re.fullmatch(
                rf"immutable/{owner}_[a-z0-9_]+\.sh", relative):
            raise MigrationContractError("engine verifier path is invalid")
        candidate = directory / relative
        if candidate.resolve().parent != (directory / "immutable").resolve():
            raise MigrationContractError("migration path escapes immutable directory")
        if item["verify_checksum"] != checksum(
                read_regular(candidate, MAX_MIGRATION_BYTES, "engine verifier")):
            raise MigrationContractError("migration content checksum mismatch")
        engine_verifiers.setdefault(owner, []).append((item["engine"], candidate))
    migrations = [replace(migration, engine_verifiers=tuple(
        engine_verifiers.get(migration.migration_id, []))) for migration in migrations]
    return Manifest(value["manifest_version"], value["runner_version"], baseline["id"],
                    baseline["required_table_count"],
                    baseline["required_table_fingerprint"], tuple(required_tables),
                    tuple(migrations))


def table_fingerprint(table_names: list[str]) -> str:
    if len(set(table_names)) != len(table_names) or any(
            not re.fullmatch(r"[A-Za-z0-9_]+", name) for name in table_names):
        raise MigrationContractError("schema table inventory is invalid")
    return checksum(("\n".join(sorted(table_names)) + "\n").encode())


def history_checksum(rows: list[AppliedMigration]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        for value in (row.migration_id, str(row.sequence), row.description,
                      row.apply_checksum, row.verify_checksum, row.compatibility,
                      str(row.runner_version)):
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(8, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def validate_history_state(rows: list[AppliedMigration], applied_count: int,
                           expected_checksum: str) -> None:
    if type(applied_count) is not int or applied_count != len(rows) or \
            not re.fullmatch(r"[0-9a-f]{64}", expected_checksum) or \
            not hmac.compare_digest(history_checksum(rows), expected_checksum):
        raise MigrationContractError("migration history head/count mismatch")


def validate_applied_prefix(manifest: Manifest,
                            applied: list[AppliedMigration]) -> tuple[Migration, ...]:
    if len(applied) > len(manifest.migrations):
        raise MigrationContractError("applied history extends beyond manifest")
    for index, row in enumerate(applied):
        expected = manifest.migrations[index]
        actual = (row.migration_id, row.sequence, row.description, row.apply_checksum,
                  row.verify_checksum, row.compatibility, row.runner_version)
        wanted = (expected.migration_id, expected.sequence, expected.description,
                  expected.apply_checksum, expected.verify_checksum,
                  expected.compatibility, manifest.runner_version)
        if actual != wanted:
            raise MigrationContractError("applied migration history was edited or reordered")
    return manifest.migrations[len(applied):]


class Executor(Protocol):
    def acquire_lock(self) -> None: ...
    def release_lock(self) -> None: ...
    def require_baseline(self, manifest: Manifest) -> None: ...
    def applied(self) -> list[AppliedMigration]: ...
    def apply(self, migration: Migration) -> None: ...
    def verify(self, migration: Migration) -> None: ...
    def record(self, migration: Migration, runner_version: int) -> None: ...


def run_pending(manifest: Manifest, executor: Executor) -> list[str]:
    executor.acquire_lock()
    completed = []
    try:
        executor.require_baseline(manifest)
        pending = validate_applied_prefix(manifest, executor.applied())
        for migration in pending:
            try:
                executor.apply(migration)
                executor.verify(migration)
                executor.record(migration, manifest.runner_version)
            except MigrationContractError as error:
                raise MigrationContractError(
                    f"migration {migration.migration_id} failed: {error}") from error
            completed.append(migration.migration_id)
        return completed
    finally:
        executor.release_lock()


class MysqlExecutor:
    def __init__(self, manifest: Manifest, confirmed_production_target: str | None = None,
                 production_backup: Path | None = None,
                 online_level_cap_sides: bool = False,
                 online_combat_outcome_allies: bool = False,
                 online_player_updates: bool = False,
                 online_artifact_pvp: bool = False,
                 online_nexus_phase1: bool = False,
                 online_artifact_rejections: bool = False,
                 online_divine_boon: bool = False,
                 online_outbox_expectations: bool = False,
                 online_divine_trade: bool = False,
                 online_pwipe_roster: bool = False,
                 online_world_quest: bool = False,
                 online_chest_frag: bool = False,
                 online_quest_reward_count: bool = False):
        environment = os.environ.get("ENVIRONMENT", "").casefold()
        host = os.environ.get("DB_HOST", "")
        database = os.environ.get("DB_NAME", "")
        socket_path = os.environ.get("DB_SOCKET", "")
        self.production = environment == "production"
        self.online_migration: Migration | None = None
        self.online_player_updates = online_player_updates
        self.online_artifact_pvp = online_artifact_pvp
        self.online_divine_boon = online_divine_boon
        self.online_divine_trade = online_divine_trade
        self.online_chest_frag = online_chest_frag
        self.lock_process = None
        self.lock_errors = None
        self.lock_connection_id = 0
        if self.production:
            expected_target = f"{host}/{database}"
            if confirmed_production_target is None or not hmac.compare_digest(
                    confirmed_production_target, expected_target):
                raise MigrationContractError("production migration target is not confirmed")
            if f",{expected_target}," not in \
                    f",{os.environ.get('DB_ALLOWED_TARGETS', '')},":
                raise MigrationContractError("production migration target is not allow-listed")
            if production_backup is None:
                raise MigrationContractError("production migration requires a validated backup")
            validate_production_backup(production_backup, database)
        else:
            if confirmed_production_target is not None or production_backup is not None:
                raise MigrationContractError(
                    "production migration options require ENVIRONMENT=production")
            if environment not in {"local", "development", "dev", "test"} or \
                    host not in {"127.0.0.1", "localhost", "::1"} or \
                    re.search(r"(^|[_-])prod(uction)?($|[_-])", database, re.I):
                raise MigrationContractError("migration target must be loopback non-production")
        if socket_path and not os.path.isabs(socket_path):
            raise MigrationContractError("DB_SOCKET must be an absolute path")
        if self.production and socket_path:
            raise MigrationContractError("production migration does not allow a database socket")
        for name in ("DB_USER", "DB_PASSWD", "DB_NAME"):
            if not os.environ.get(name):
                raise MigrationContractError(f"missing migration credential: {name}")
        if sum((online_level_cap_sides, online_combat_outcome_allies,
                online_player_updates, online_artifact_pvp, online_nexus_phase1,
                online_artifact_rejections, online_divine_boon, online_outbox_expectations,
                online_divine_trade, online_pwipe_roster, online_world_quest,
                online_chest_frag, online_quest_reward_count)) > 1:
            raise MigrationContractError("select only one reviewed online migration")
        for enabled, count, pair in (
                (online_player_updates, 43, ONLINE_PLAYER_UPDATES),
                (online_artifact_pvp, 45, ONLINE_ARTIFACT_PVP),
                (online_divine_boon, 49, ONLINE_DIVINE_BOON),
                (online_divine_trade, 52, ONLINE_DIVINE_TRADE),
                (online_chest_frag, 58, ONLINE_CHEST_FRAG)):
            if not enabled:
                continue
            reviewed = tuple((step.migration_id, step.apply_checksum, step.verify_checksum)
                             for step in manifest.migrations[-2:])
            if not self.production or len(manifest.migrations) != count or reviewed != pair:
                raise MigrationContractError(
                    f"online migration requires the reviewed production {count - 1:04d}/{count:04d} manifest")
            self.online_migration = manifest.migrations[-1]
            self.online_table = "player_data"
        if (online_level_cap_sides or online_combat_outcome_allies or online_nexus_phase1 or
                online_artifact_rejections or online_outbox_expectations or online_pwipe_roster or
                online_world_quest or online_quest_reward_count):
            if online_level_cap_sides:
                reviewed = (ONLINE_LEVEL_CAP_ID, ONLINE_LEVEL_CAP_APPLY, ONLINE_LEVEL_CAP_VERIFY)
                count, self.online_table = 39, "level_cap"
            elif online_combat_outcome_allies:
                reviewed = (ONLINE_COMBAT_ALLIES_ID, ONLINE_COMBAT_ALLIES_APPLY,
                            ONLINE_COMBAT_ALLIES_VERIFY)
                count, self.online_table = 40, "combat_outcome"
            elif online_nexus_phase1:
                reviewed = (ONLINE_NEXUS_ID, ONLINE_NEXUS_APPLY, ONLINE_NEXUS_VERIFY)
                count, self.online_table = 46, "nexus_stones"
            elif online_outbox_expectations:
                reviewed = (ONLINE_OUTBOX_EXPECTATIONS_ID, ONLINE_OUTBOX_EXPECTATIONS_APPLY,
                            ONLINE_OUTBOX_EXPECTATIONS_VERIFY)
                count, self.online_table = 50, "critical_operation_inbox"
            elif online_world_quest:
                reviewed = (ONLINE_WORLD_QUEST_ID, ONLINE_WORLD_QUEST_APPLY,
                            ONLINE_WORLD_QUEST_VERIFY)
                count, self.online_table = 56, "player_data"
            elif online_quest_reward_count:
                reviewed = (ONLINE_QUEST_REWARD_COUNT_ID, ONLINE_QUEST_REWARD_COUNT_APPLY,
                            ONLINE_QUEST_REWARD_COUNT_VERIFY)
                count, self.online_table = 59, "player_data"
            elif online_pwipe_roster:
                reviewed = (ONLINE_PWIPE_ROSTER_ID, ONLINE_PWIPE_ROSTER_APPLY,
                            ONLINE_PWIPE_ROSTER_VERIFY)
                count, self.online_table = 53, "season_reset_state"
            else:
                reviewed = (ONLINE_ARTIFACT_REJECTIONS_ID, ONLINE_ARTIFACT_REJECTIONS_APPLY,
                            ONLINE_ARTIFACT_REJECTIONS_VERIFY)
                count, self.online_table = 47, "artifact_domain_state"
            head = manifest.migrations[-1] if manifest.migrations else None
            if not self.production or head is None or len(manifest.migrations) != count or \
                    (head.migration_id, head.apply_checksum, head.verify_checksum) != reviewed:
                raise MigrationContractError(
                    f"online migration requires the reviewed production {count:04d} manifest")
            self.online_migration = head
        self.manifest = manifest
        self.socket_path = socket_path
        self.engine: str | None = None
        if socket_path:
            connection = ["--protocol=socket", f"--socket={socket_path}"]
        elif host in {"127.0.0.1", "localhost", "::1"}:
            connection = ["--protocol=tcp", "-h", host, "-P",
                          os.environ.get("DB_PORT", "3306")]
        else:
            certificate = os.environ.get("DB_SSL_CA", "")
            if os.environ.get("DB_TLS") != "TRUE" or not Path(certificate).is_file():
                raise MigrationContractError(
                    "remote production migration requires TLS and a CA file")
            mysql_help = subprocess.run(["mysql", "--help"], capture_output=True,
                                        check=False).stdout
            if b"--ssl-mode" in mysql_help:
                tls = ["--ssl-mode=VERIFY_IDENTITY", f"--ssl-ca={certificate}"]
            elif b"--ssl-verify-server-cert" in mysql_help:
                tls = [f"--ssl-ca={certificate}", "--ssl-verify-server-cert"]
            else:
                raise MigrationContractError(
                    "database client cannot verify the remote server identity")
            connection = ["--protocol=tcp", "-h", host, "-P",
                          os.environ.get("DB_PORT", "3306"), *tls]
        self.command = ["mysql", *connection, "-u", os.environ["DB_USER"],
                        "-N", "-B", database]

    def sql(self, statement: str, input_payload: bytes | None = None) -> str:
        self.require_lock()
        if self.lock_process is not None:
            # Apply and history writes must use the session holding GET_LOCK.
            # KILL/connection loss then stops the SQL itself, not just the next step.
            result = self.locked_sql(input_payload.decode() if input_payload is not None
                                     else statement)
            self.require_lock()
            return result
        environment = dict(os.environ)
        environment["MYSQL_PWD"] = os.environ["DB_PASSWD"]
        result = subprocess.run(self.command + (["-e", statement] if input_payload is None
                                                else []), input=input_payload,
                                capture_output=True, env=environment, check=False)
        self.require_lock()
        if result.returncode:
            detail = result.stderr.decode(errors="replace").strip().splitlines()
            raise MigrationContractError(
                "database migration command failed" +
                (f": {detail[-1]}" if detail else ""))
        return result.stdout.decode().strip()

    def locked_sql(self, payload: str) -> str:
        marker = 'migration_result_' + secrets.token_hex(16)
        write_errors = []

        def write():
            try:
                self.lock_process.stdin.write(payload + f"\n;\nSELECT '{marker}';\n")
                self.lock_process.stdin.flush()
            except OSError as error:
                write_errors.append(error)

        # Drain output while feeding SQL: a migration can exceed the pipe buffer
        # in both directions. The mysql client handles DELIMITER and batch errors.
        writer = threading.Thread(target=write)
        writer.start()
        output = []
        for line in self.lock_process.stdout:
            if line.rstrip('\n') == marker:
                writer.join()
                if not write_errors:
                    return ''.join(output).strip()
                break
            output.append(line)
        writer.join()
        self.lock_process.wait()
        self.lock_errors.seek(0)
        detail = self.lock_errors.read().decode(errors='replace').strip().splitlines()
        raise MigrationContractError(
            'database migration command failed or lock connection was lost' +
            (f': {detail[-1]}' if detail else ''))

    def acquire_lock(self) -> None:
        # The lock's session must outlive apply, verification and history recording.
        environment = dict(os.environ, MYSQL_PWD=os.environ["DB_PASSWD"])
        # Error output must not block the client while stdout carries SQL results.
        self.lock_errors = tempfile.TemporaryFile()
        try:
            self.lock_process = subprocess.Popen(
                self.command + ["--unbuffered", "--skip-reconnect", "--connect-timeout=5"],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.lock_errors,
                text=True, env=environment)
            self.lock_process.stdin.write(
                "SELECT GET_LOCK('duris_immutable_migration',5), CONNECTION_ID();\n")
            self.lock_process.stdin.flush()
            readable, _, _ = select.select([self.lock_process.stdout], [], [], 12)
            result = self.lock_process.stdout.readline().strip() if readable else ""
            if not re.fullmatch(r"1\t[1-9][0-9]*", result):
                raise MigrationContractError("migration lock unavailable")
            self.lock_connection_id = int(result.split("\t")[1])
        except (OSError, MigrationContractError) as error:
            self.release_lock()
            raise MigrationContractError("migration lock unavailable") from error

    def require_lock(self) -> None:
        if self.lock_process is None:
            return  # Standalone inspection/verifier calls do not acquire a lock.
        if self.lock_process.poll() is not None:
            raise MigrationContractError("migration lock connection was lost")
        try:
            # A server-side KILL may leave the client idle/alive. Check the session,
            # not just its process, before and after each database operation.
            self.lock_process.stdin.write(
                "SELECT IS_USED_LOCK('duris_immutable_migration')=CONNECTION_ID();\n")
            self.lock_process.stdin.flush()
            readable, _, _ = select.select([self.lock_process.stdout], [], [], 12)
            if not readable or self.lock_process.stdout.readline().strip() != "1":
                raise MigrationContractError("migration lock connection was lost")
        except OSError as error:
            raise MigrationContractError("migration lock connection was lost") from error

    def release_lock(self) -> None:
        self.lock_connection_id = 0
        if self.lock_process is not None:
            process = self.lock_process
            self.lock_process = None
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
            process.stdin = None
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.communicate()
        if self.lock_errors is not None:
            self.lock_errors.close()
            self.lock_errors = None

    def require_quiescent(self) -> None:
        connections = self.sql(
            "SELECT COUNT(*) FROM information_schema.PROCESSLIST "
            "WHERE DB=DATABASE() AND ID<>CONNECTION_ID();")
        if connections != "0":
            raise MigrationContractError(
                "production migration requires every other database connection to stop")

    def live_tables(self) -> list[str]:
        output = self.sql("SELECT table_name FROM information_schema.tables WHERE "
                          "table_schema=DATABASE() AND table_type='BASE TABLE' ORDER BY table_name;")
        return output.splitlines() if output else []

    def require_baseline(self, manifest: Manifest) -> None:
        row = self.sql("SELECT baseline_id,HEX(schema_fingerprint),manifest_version,"
                       "runner_version FROM mud_schema_baselines ORDER BY adopted_at LIMIT 1;")
        expected = (f"{manifest.baseline_id}\t"
                    f"{manifest.required_table_fingerprint.upper()}\t"
                    f"{manifest.version}\t{manifest.runner_version}")
        if row != expected:
            raise MigrationContractError("verified migration baseline is absent or stale")

    def applied(self) -> list[AppliedMigration]:
        output = self.sql("SELECT migration_id,sequence_number,description,"
                          "LOWER(HEX(apply_checksum)),LOWER(HEX(verify_checksum)),"
                          "compatibility,runner_version FROM mud_schema_history "
                          "ORDER BY sequence_number;")
        rows = []
        for line in output.splitlines() if output else []:
            fields = line.split("\t")
            if len(fields) != 7:
                raise MigrationContractError("migration history row shape is invalid")
            rows.append(AppliedMigration(fields[0], int(fields[1]), fields[2], fields[3],
                                         fields[4], fields[5], int(fields[6])))
        state = self.sql("SELECT applied_count,LOWER(HEX(history_checksum)) FROM "
                         "mud_schema_migration_state WHERE state_id=1;").split("\t")
        if len(state) != 2:
            raise MigrationContractError("migration history state is absent")
        try:
            validate_history_state(rows, int(state[0]), state[1])
        except ValueError as error:
            raise MigrationContractError("migration history state is invalid") from error
        return rows

    def apply(self, migration: Migration) -> None:
        if self.online_migration is not None:
            reviewed = self.online_migration
            if (self.online_player_updates or self.online_artifact_pvp or self.online_divine_boon or
                    self.online_divine_trade or self.online_chest_frag) and \
                    migration.migration_id == self.manifest.migrations[-2].migration_id:
                reviewed = self.manifest.migrations[-2]
            if self.online_artifact_pvp:
                self.online_table = ("artifact_domain_state" if reviewed.sequence == 44
                                     else "pkill_info")
            if (migration.migration_id, migration.apply_checksum, migration.verify_checksum) != \
                    (reviewed.migration_id, reviewed.apply_checksum, reviewed.verify_checksum):
                raise MigrationContractError(
                    f"only reviewed migration {reviewed.migration_id} may run online")
            if engine_of(self.sql("SELECT VERSION();")) != "mariadb-11.8":
                raise MigrationContractError("online migration requires MariaDB 11.8")
            tables = ("artifact_domain_state", "guilds") if self.online_divine_trade else (self.online_table,)
            if self.online_chest_frag:
                tables = (("private_chests", "private_chest_log") if migration.sequence == 57
                          else ("level_cap",))
            for table in tables:
                if self.sql("SELECT ENGINE FROM information_schema.TABLES WHERE "
                            f"TABLE_SCHEMA=DATABASE() AND TABLE_NAME='{table}';") != "InnoDB":
                    raise MigrationContractError(
                        f"online migration requires InnoDB {table}")
            payload = read_regular(migration.apply_path, MAX_MIGRATION_BYTES,
                                   "migration apply")
            if checksum(payload) != reviewed.apply_checksum:
                raise MigrationContractError("online migration apply checksum changed")
            algorithm = b"INSTANT"
            if self.online_chest_frag:
                # Nullable additions preserve the named-column legacy writers.
                # Receipt indexes need INPLACE; LOCK=NONE forbids blocking DDL.
                for table in tables:
                    old = f"ALTER TABLE {table} ".encode()
                    if payload.count(old) != 1:
                        raise MigrationContractError("reviewed online ALTER was not found")
                    payload = payload.replace(old, old.replace(b"ALTER TABLE", b"ALTER ONLINE TABLE"))
                algorithm = b"INPLACE" if migration.sequence == 57 else b"INSTANT"
            if self.online_divine_trade and migration.sequence == 52:
                # Nullable tail columns preserve named-column legacy writers.
                # Require instant, nonblocking DDL for each sealed ALTER.
                for table, count in (("artifact_domain_state", 1), ("guilds", 2)):
                    old = f"'ALTER TABLE {table} ".encode()
                    if payload.count(old) != count:
                        raise MigrationContractError("reviewed online ALTER was not found")
                    payload = payload.replace(old, old.replace(b"ALTER TABLE", b"ALTER ONLINE TABLE"))
            if (self.online_artifact_pvp or
                    reviewed.migration_id in {ONLINE_ARTIFACT_REJECTIONS_ID, ONLINE_PWIPE_ROSTER_ID,
                                             ONLINE_WORLD_QUEST_ID, ONLINE_QUEST_REWARD_COUNT_ID} or
                    (self.online_divine_boon and migration.sequence == 49)):
                # Strengthen only the sealed statements to LOCK=NONE. NOCOPY
                # permits the unique index but refuses a clustered-table rebuild.
                old = f"'ALTER TABLE {self.online_table} ".encode()
                if payload.count(old) != (3 if migration.sequence == 44 else
                                          2 if reviewed.migration_id == ONLINE_WORLD_QUEST_ID else 1):
                    raise MigrationContractError("reviewed online ALTER was not found")
                payload = payload.replace(old, old.replace(b"ALTER TABLE", b"ALTER ONLINE TABLE"))
                if migration.sequence == 44:
                    algorithm = b"NOCOPY"
            if self.online_player_updates and migration.sequence == 42:
                # Widening TINYINT requires COPY. On 11.8, ONLINE requires LOCK=NONE
                # and refuses unsupported shapes instead of blocking live writers.
                # Keep the sealed file and ledger checksum intact; strengthen only
                # this exact checked statement's execution lock requirement.
                old = b"'ALTER TABLE player_data '"
                if payload.count(old) != 1:
                    raise MigrationContractError("reviewed base-stat ALTER was not found")
                payload = payload.replace(old, b"'ALTER ONLINE TABLE player_data '")
                algorithm = b"COPY"
            self.sql("", b"SET SESSION alter_algorithm='" + algorithm + b"';\n"
                     b"SET SESSION lock_wait_timeout=1;\n"
                     b"SET SESSION innodb_lock_wait_timeout=1;\n" + payload)
            return
        if self.production:
            self.require_quiescent()
        self.sql("", read_regular(migration.apply_path, MAX_MIGRATION_BYTES,
                                  "migration apply"))

    def verify(self, migration: Migration) -> None:
        self.require_lock()
        environment = dict(os.environ)
        if self.socket_path:
            # Immutable verifier files are checksum-sealed and carry explicit
            # TCP flags. Route only their mysql executable through a narrow
            # adapter instead of rewriting those historical artifacts.
            real_mysql = shutil.which("mysql")
            if not real_mysql:
                raise MigrationContractError("mysql client is unavailable")
            environment["DURIS_REAL_MYSQL_CLIENT"] = real_mysql
            environment["PATH"] = (str(ROOT / "scripts/mysql_socket_bin") +
                                   os.pathsep + environment.get("PATH", ""))
        if self.engine is None:
            self.engine = engine_of(self.sql("SELECT VERSION();"))
        result = subprocess.run([str(migration.verifier(self.engine))], capture_output=True,
                                env=environment, check=False)
        self.require_lock()
        if result.returncode:
            detail = (result.stderr or result.stdout).decode(errors="replace").strip().splitlines()
            raise MigrationContractError(
                "migration verifier failed" +
                (f": {detail[-1]}" if detail else ""))

    def record(self, migration: Migration, runner_version: int) -> None:
        description_hex = migration.description.encode("utf-8").hex()
        compatibility_hex = migration.compatibility.encode("utf-8").hex()
        existing = self.applied()
        old_checksum = history_checksum(existing)
        new_row = AppliedMigration(migration.migration_id, migration.sequence,
                                   migration.description, migration.apply_checksum,
                                   migration.verify_checksum, migration.compatibility,
                                   runner_version)
        new_checksum = history_checksum(existing + [new_row])
        result = self.sql("START TRANSACTION; INSERT INTO mud_schema_history("
                 "migration_id,sequence_number,description,apply_checksum,verify_checksum,"
                 "compatibility,runner_version) VALUES("+
                 f"'{migration.migration_id}',{migration.sequence},"
                 f"CONVERT(UNHEX('{description_hex}') USING utf8mb4),"
                 f"UNHEX('{migration.apply_checksum}'),UNHEX('{migration.verify_checksum}'),"
                 f"CONVERT(UNHEX('{compatibility_hex}') USING utf8mb4),{runner_version}); "
                 "UPDATE mud_schema_migration_state "
                 f"SET applied_count={migration.sequence},history_checksum=UNHEX('{new_checksum}') "
                 f"WHERE state_id=1 AND applied_count={len(existing)} AND "
                 f"history_checksum=UNHEX('{old_checksum}'); SELECT ROW_COUNT(); COMMIT;")
        if result.splitlines()[-1:] != ["1"]:
            raise MigrationContractError("migration history head changed during record")

    def adopt(self, kind: str) -> None:
        tables = self.live_tables()
        missing = sorted(set(self.manifest.required_tables) - set(tables))
        if missing:
            raise MigrationContractError(
                "live schema is missing required baseline tables: " + ", ".join(missing[:8]))
        if kind not in {"fresh_bootstrap", "verified_legacy_adoption"}:
            raise MigrationContractError("invalid baseline kind")
        self.sql("INSERT INTO mud_schema_baselines(baseline_id,baseline_kind,"
                 "schema_fingerprint,manifest_version,runner_version) VALUES("+
                 f"'{self.manifest.baseline_id}','{kind}',"
                 f"UNHEX('{self.manifest.required_table_fingerprint}'),"
                 f"{self.manifest.version},{self.manifest.runner_version}) "
                 "ON DUPLICATE KEY UPDATE baseline_id=IF(baseline_id=VALUES(baseline_id) "
                 "AND schema_fingerprint=VALUES(schema_fingerprint),baseline_id,NULL);")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--confirm-production-target")
    parser.add_argument("--production-backup", type=Path)
    online = parser.add_mutually_exclusive_group()
    online.add_argument("--online-level-cap-sides", action="store_true",
                        help="apply only reviewed 0039 on MariaDB 11.8 using INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-combat-outcome-allies", action="store_true",
                        help="apply only reviewed 0040 on MariaDB 11.8 using INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-player-updates", action="store_true",
                        help="apply only reviewed 0042/0043 on MariaDB 11.8 using online COPY "
                             "and INSTANT DDL; requires production confirmation and backup")
    online.add_argument("--online-artifact-pvp", action="store_true",
                        help="apply only reviewed 0044/0045 on MariaDB 11.8 using online "
                             "NOCOPY/INSTANT DDL; requires production confirmation and backup")
    online.add_argument("--online-nexus-phase1", action="store_true",
                        help="apply only reviewed 0046 Nexus inserts on MariaDB 11.8 InnoDB; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-artifact-rejections", action="store_true",
                        help="apply only reviewed 0047 on MariaDB 11.8 using online INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-divine-boon", action="store_true",
                        help="apply only reviewed 0048/0049 on MariaDB 11.8 using CREATE and "
                             "online INSTANT DDL; requires production confirmation and backup")
    online.add_argument("--online-outbox-expectations", action="store_true",
                        help="apply only reviewed 0050 on MariaDB 11.8 using INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-divine-trade", action="store_true",
                        help="apply only reviewed Divine trade/delivery steps 51/52 on MariaDB 11.8 "
                             "using CREATE and online INSTANT DDL; requires production confirmation and backup")
    online.add_argument("--online-pwipe-roster", action="store_true",
                        help="apply only reviewed 0052 on MariaDB 11.8 using online INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-chest-frag", action="store_true",
                        help="apply only reviewed 0056/0057 on MariaDB 11.8 with LOCK=NONE; "
                             "requires production confirmation and backup")
    online.add_argument("--online-world-quest", action="store_true",
                        help="apply only reviewed 0055 on MariaDB 11.8 using online INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    online.add_argument("--online-quest-reward-count", action="store_true",
                        help="apply only reviewed 0058 on MariaDB 11.8 using online INSTANT DDL; "
                             "requires production confirmation, backup and compatible live writers")
    parser.add_argument("command", choices=("inspect", "adopt", "run"))
    parser.add_argument("--kind", choices=("fresh_bootstrap", "verified_legacy_adoption"))
    arguments = parser.parse_args()
    try:
        manifest = load_manifest(arguments.manifest)
        if (arguments.online_level_cap_sides or arguments.online_combat_outcome_allies or
                arguments.online_player_updates or arguments.online_artifact_pvp or
                arguments.online_nexus_phase1 or arguments.online_artifact_rejections or
                arguments.online_divine_boon or arguments.online_outbox_expectations or
                arguments.online_divine_trade or arguments.online_pwipe_roster or
                arguments.online_world_quest or arguments.online_chest_frag or
                arguments.online_quest_reward_count) and \
                arguments.command != "run":
            raise MigrationContractError("online migration option requires run")
        if arguments.command == "inspect":
            print(json.dumps({"baseline_id": manifest.baseline_id,
                              "required_table_count": manifest.required_table_count,
                              "required_table_fingerprint":
                                  manifest.required_table_fingerprint,
                              "migration_count": len(manifest.migrations),
                              "manifest_version": manifest.version,
                              "runner_version": manifest.runner_version}, sort_keys=True))
            return 0
        if arguments.command != "run" and (arguments.confirm_production_target is not None or
                                           arguments.production_backup is not None):
            raise MigrationContractError(
                "production migration options are valid only with the run command")
        executor = MysqlExecutor(manifest, arguments.confirm_production_target,
                                 arguments.production_backup, arguments.online_level_cap_sides,
                                 arguments.online_combat_outcome_allies,
                                 arguments.online_player_updates, arguments.online_artifact_pvp,
                                 arguments.online_nexus_phase1, arguments.online_artifact_rejections,
                                 arguments.online_divine_boon, arguments.online_outbox_expectations,
                                 arguments.online_divine_trade, arguments.online_pwipe_roster,
                                 arguments.online_world_quest, arguments.online_chest_frag,
                                 arguments.online_quest_reward_count)
        if arguments.command == "adopt":
            if arguments.kind is None:
                raise MigrationContractError("adopt requires --kind")
            executor.acquire_lock()
            try:
                executor.adopt(arguments.kind)
            finally:
                executor.release_lock()
        else:
            if executor.production and executor.online_migration is None:
                executor.require_quiescent()
            run_pending(manifest, executor)
        return 0
    except MigrationContractError as error:
        print(f"migration runner blocked: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
