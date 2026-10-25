#!/usr/bin/env python3
"""Keep Kjelgar's compiled harp recipe aligned with the authored ingredients."""

from collections import Counter
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[2]


def main():
    # Resolve the named items from their source definitions so an unattainable
    # ingredient VNUM cannot silently replace the advertised moonstone crystal.
    crystal = re.search(
        r"^#(\d+)\nmoonstone crystal salvaged~$",
        (ROOT / "areas/obj/tradeskills.obj").read_text(), re.MULTILINE,
    )
    token = re.search(
        r"^#(\d+)\ngnomish shopkeepers token _noquest_~$",
        (ROOT / "areas/obj/wh.obj").read_text(), re.MULTILINE,
    )
    harp = re.search(
        r"^#(\d+)\ncrystal harp vokstron _noquest_~$",
        (ROOT / "areas/obj/vehicles.obj").read_text(), re.MULTILINE,
    )
    assert crystal and token and harp, "Kjelgar's ingredient/reward definitions are missing"

    (ROOT / "bin/tests").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kjelgar-quest-", dir=ROOT / "bin/tests") as temporary:
        workspace = Path(temporary)
        binary = workspace / "make_qst"
        subprocess.run(
            ["gcc", str(ROOT / "areas/src/qst/make_qst.c"), "-o", str(binary)],
            check=True,
        )
        (workspace / "AREA").write_text("vehicles\n")
        (workspace / "qst").symlink_to(ROOT / "areas/qst", target_is_directory=True)
        subprocess.run([str(binary)], cwd=workspace, check=True, capture_output=True)
        compiled = (workspace / "tworld.qst").read_text()
        assert compiled == (ROOT / "areas/qst/vehicles.qst").read_text()

    captain = re.search(r"^#47124\n(.*?)^S$", compiled, re.MULTILINE | re.DOTALL)
    assert captain, "Kjelgar's quest is missing from the compiled area"
    recipes = [part.split("~\n", 1)[1] for part in captain[1].split("QA\n")[1:]]
    harp_recipes = [recipe for recipe in recipes if f"R I {harp[1]}\n" in recipe]
    assert len(harp_recipes) == 1, "Kjelgar must have one crystal harp recipe"
    recipe = harp_recipes[0]
    ingredients = Counter(re.findall(r"^G I (\d+)$", recipe, re.MULTILINE))
    assert ingredients == Counter({crystal[1]: 5, token[1]: 2}), (
        "The harp must require five moonstone crystals and two shopkeeper tokens", ingredients
    )
    assert re.findall(r"^G C (\d+)$", recipe, re.MULTILINE) == ["100000"], (
        "The harp must still cost 100 platinum"
    )
    assert re.findall(r"^R I (\d+)$", recipe, re.MULTILINE) == [harp[1]]
    print("Kjelgar crystal harp recipe and area compilation: OK")


if __name__ == "__main__":
    main()
