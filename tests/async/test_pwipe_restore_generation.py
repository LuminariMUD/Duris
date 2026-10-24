"""The restore drill must reject a failed first boot before later boots can mask it."""
from pathlib import Path
import tempfile
import textwrap

source = Path(__file__).with_name("run_pwipe_runtime_journey.py").read_text()
start = source.index('                        boot()\n                        # Each boot rotates')
end = source.index('                        client = journey.reconnect_character', start)
first_boot = compile(textwrap.dedent(source[start:end]), "first_restore_boot", "exec")
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    log = root / "logs/log/sys"
    log.parent.mkdir(parents=True)
    for message, expected in (("restored world recovery generation sequence=42 ok", True),
                              ("normal zone initialization", False),
                              ("restored world recovery generation sequence=43 ok", False)):
        def boot():
            log.write_text(message)
        passed = True
        try:
            exec(first_boot, {"root": root, "world_generation": "42", "boot": boot})
        except AssertionError:
            passed = False
        assert passed == expected, message
assert 'sequence=" + restored_sequence + " "' in source
print("Matched restore requires the captured generation on first boot and checks the second separately")
