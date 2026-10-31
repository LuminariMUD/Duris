#!/usr/bin/env python3
"""Production private-chest purchase on an isolated MariaDB/MySQL instance."""
import os
from pathlib import Path
import subprocess
import tempfile
import uuid
from _paths import ROOT

assert os.environ["TEST_DB_HOST"] == "127.0.0.1", "use with_disposable_mariadb.sh"
name = "private_chest_" + uuid.uuid4().hex[:12]
env = {**os.environ, "MYSQL_PWD": os.environ["TEST_DB_PASSWORD"], "CHEST_TEST_DB": name}
client = ["mysql", "--protocol=tcp", "--skip-ssl", "-h", env["TEST_DB_HOST"], "-P", env["TEST_DB_PORT"], "-u", env["TEST_DB_USER"]]
subprocess.run(client, input="CREATE DATABASE " + name + " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", text=True, env=env, check=True)
try:
    build = ROOT / "bin/tests"
    build.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="chest-purchase-", dir=build) as tmp:
        binary = Path(tmp) / "test"
        subprocess.run(["g++", "-std=c++20", "-g", "-ffunction-sections", "-fdata-sections", "-Wl,--gc-sections", "-Isrc", "-I/usr/include/mysql", "tests/async/private_chest_purchase_mysql.cpp", "-lmysqlclient", "-o", str(binary)], cwd=ROOT, check=True)
        subprocess.run([str(binary)], cwd=ROOT, env=env, check=True, timeout=30)
finally:
    subprocess.run(client, input="DROP DATABASE " + name, text=True, env=env, check=True)
