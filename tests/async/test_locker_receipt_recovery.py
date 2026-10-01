"""Real process exits at receipt/payment boundaries.

The payment is the in-memory charge the live service makes; the harness saves the
purse after the completion, as the player's next save would.
"""
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ['src/item/locker_receipt.c', 'src/flatfile/flatfile_store.c',
           'src/economy/currency_command.c', 'src/persistence/critical_command.c']


def run(temp):
    directory = temp / 'harness'
    directory.mkdir()
    source = directory / 'harness.cpp'
    service = re.sub(r'^#include.*\n', '', (ROOT / 'src/item/locker_identify.c').read_text(), flags=re.M)
    service = service.replace('locker_receipt_write(directory, value)', 'test_receipt_write(directory, value)')
    source.write_text((ROOT / 'tests/async/locker_receipt_harness.cpp').read_text().replace('// SERVICE_BODY', service))
    binary = directory / 'harness'
    subprocess.run(['g++', '-std=c++20', '-Wall', '-Wextra', '-Werror', '-Isrc', '-D__NO_MYSQL__',
                    '-Isrc/no_mysql', str(source), *SOURCES, '-lcrypto', '-pthread', '-o', str(binary)],
                   cwd=ROOT, check=True)
    for purse in ('wallet', 'bank'):
        subprocess.run([str(binary), str(directory / ('normal-'+purse)), 'normal', purse], check=True, timeout=30)
        for crash, exit_code in [('before-payment', 77), ('after-payment', 78), ('after-receipt', 79)]:
            for prefix in ('', 'saturated-'):
                state = str(directory / (prefix+crash+'-'+purse))
                result = subprocess.run([str(binary), state, crash, purse], timeout=30)
                assert result.returncode == exit_code, (crash, result.returncode)
                recovery = 'replay' if crash == 'after-receipt' else 'recover'
                subprocess.run([str(binary), state, prefix+recovery, purse], check=True, timeout=30)
                subprocess.run([str(binary), state, prefix+'delivered', purse], check=True, timeout=30)


# Receipts require native private-directory permissions; a Windows-backed checkout can
# ignore chmod(0700). Use the host's disposable temporary filesystem.
with tempfile.TemporaryDirectory(prefix='locker-recovery-') as temporary:
    run(Path(temporary))
