#!/usr/bin/env python3
"""The PSP journey CLI retains JSON in new and existing output directories."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

import run_psp_regen_journey as journey


with tempfile.TemporaryDirectory(prefix="psp-journey-output-") as directory:
    output = Path(directory) / "analysis/issue57-plan/journey.json"
    assert not output.parent.exists()
    binary = Path("bin/server/dms_issue57_flatfile")
    for callbacks in (569, 570):
        result = {"callback_count": callbacks, "duplicate_psp_callbacks": 0}
        stdout = io.StringIO()
        with patch("sys.argv", ["run_psp_regen_journey.py", "--binary", str(binary),
                                "--output", str(output)]), \
                patch.object(journey, "run", return_value=result) as run, \
                redirect_stdout(stdout):
            journey.main()
        run.assert_called_once_with(binary.resolve())
        assert json.loads(output.read_text()) == result
        assert json.loads(stdout.getvalue()) == result

print("PSP journey CLI creates output parents and replaces existing JSON")
