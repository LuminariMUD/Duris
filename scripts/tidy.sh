#!/usr/bin/env bash
#
# Run clang-tidy, with the repository's .clang-tidy, over the C/C++ lines you changed.
#
#   ./scripts/tidy.sh                    # changed lines, staged and unstaged, against HEAD
#   ./scripts/tidy.sh --staged           # staged lines (the pre-commit hook)
#   ./scripts/tidy.sh --rev origin/master
#   ./scripts/tidy.sh --all [PATH...]    # every line of src/ (or of the paths)
#
# It only reports: exit 1 when a finding falls on a checked line. The .c files are C++20
# and there is no compile database, so one is written to bin/tidy/ from src/Makefile's
# flags (the MariaDB build; code under __NO_MYSQL__ alone is not analysed). See
# docs/guides/formatting.md.
set -euo pipefail
cd "$(dirname "$0")/.." || exit 1

MODE="worktree"
REV="HEAD"
PATHS=()
while [[ $# -gt 0 ]]; do
	case "$1" in
	--staged | --cached) MODE="staged" ;;
	--rev=*) REV="${1#*=}" ;;
	--rev) REV="${2:?--rev needs a commit-ish}"; shift ;;
	--all) MODE="all" ;;
	-h | --help) sed -n '3,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
	-*) echo "Unknown option: $1" >&2; exit 2 ;;
	*) PATHS+=("$1") ;;
	esac
	shift
done

TIDY="${CLANG_TIDY:-$(command -v clang-tidy || true)}"
TIDY_DIFF="$(command -v clang-tidy-diff || true)"
if [[ -z "$TIDY" || -z "$TIDY_DIFF" ]]; then
	echo "tidy: clang-tidy and clang-tidy-diff are needed (apt-get install clang-tidy)." >&2
	exit 1
fi

# clang-tidy-diff reads plain "+++ b/<path>" headers: no color, prefixes or diff drivers
# from the user's git config. Only sources and headers are analysed: the Makefile and the
# .inc and .def fragments are not translation units.
PLAIN=(--no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ -U0)
SOURCES=('src/*.c' 'src/*.cpp' 'src/*.h')
if [[ "$MODE" == "staged" ]]; then
	diff=$(git diff --cached "${PLAIN[@]}" -- "${SOURCES[@]}")
elif [[ "$MODE" == "worktree" ]]; then
	diff=$(git diff "${PLAIN[@]}" "$REV" -- "${SOURCES[@]}")
fi
if [[ "$MODE" != "all" && -z "$diff" ]]; then
	echo "tidy: no changed C/C++ lines under src/."
	exit 0
fi

# The compile database: every C/C++ source under src/, with the build's -D/-I/-std flags.
# A staged check reads what the commit will hold, src/ (its Makefile's flags too) and
# .clang-tidy as staged, written to bin/tidy/staged/: the working tree's unstaged edits may
# differ from it.
OUT=bin/tidy
mkdir -p "$OUT"
TREE=.
if [[ "$MODE" == "staged" ]]; then
	TREE="$OUT/staged"
	rm -rf "$TREE"
	git ls-files -z src .clang-tidy | git checkout-index -z --stdin --prefix="$TREE/"
fi
FLAGS="$(make -s --no-print-directory -C "$TREE/src" '--eval=.PHONY: tidy-flags' \
	'--eval=tidy-flags:;@echo $(CFLAGS) $(INCLUDES)' tidy-flags)"
git ls-files 'src/*.c' 'src/*.cpp' | python3 -c '
import json, os, shlex, sys
root = os.path.abspath(sys.argv[2])
flags = [f for f in shlex.split(sys.argv[1])
         if f.startswith(("-D", "-I", "-std=")) and not f.startswith("-D_FORTIFY_SOURCE")]
command = ["clang++", "-x", "c++"] + flags
json.dump([{"directory": os.path.join(root, "src"), "file": os.path.join(root, path.strip()),
            "arguments": command + ["-c", os.path.join(root, path.strip())]}
           for path in sys.stdin if path.strip()], sys.stdout, indent=0)
' "$FLAGS" "$TREE" >"$OUT/compile_commands.json"

if [[ "$MODE" == "all" ]]; then
	(( ${#PATHS[@]} )) || PATHS=(src)
	mapfile -t FILES < <(git ls-files "${PATHS[@]}" | grep -E '\.(c|cpp)$')
	status=0
	printf '%s\0' "${FILES[@]}" | xargs -0 -P "${TIDY_JOBS:-$(nproc)}" -n 1 \
		"$TIDY" -p "$OUT" --quiet 2>"$OUT/stderr.log" >"$OUT/raw.log" || status=$?
	# A header's finding comes once per file that includes it: count it once.
	grep -E ': (warning|error): ' "$OUT/raw.log" | sed -E "s#^(\./|$PWD/src/)#src/#" |
		sort -u >"$OUT/all.log" || true
	findings=$(wc -l <"$OUT/all.log")
	# clang-tidy fails only after reporting a finding (xargs: 123). A failure with none, or
	# a status above 123 (not found, not runnable, killed), means it did not analyse.
	if (( status > 123 || (status != 0 && findings == 0) )); then
		echo "tidy: $TIDY did not run (xargs exit $status):" >&2
		tail -n 5 "$OUT/stderr.log" >&2
		exit 1
	fi
	echo "tidy: ${#FILES[@]} files, $findings findings; by check:"
	grep -o '\[[a-z0-9.,-]*\]$' "$OUT/all.log" | sed 's/,-warnings-as-errors//' | sort | uniq -c |
		sort -rn || true
	echo "Findings: $OUT/all.log (the compiler output around them: $OUT/raw.log)"
	(( findings == 0 ))
	exit
fi

DATABASE="$PWD/$OUT"
printf '%s\n' "$diff" >"$OUT/changed.diff"
status=0
# A source's changed lines: clang-tidy-diff runs clang-tidy on the file, filtered to them.
out=$(cd "$TREE" && "$TIDY_DIFF" -p1 -regex '.*\.(c|cpp)' -path "$DATABASE" \
	-clang-tidy-binary "$TIDY" -j "$(nproc)" -quiet <"$DATABASE/changed.diff" 2>&1) || status=1
# A header's: clang-tidy cannot compile a header that is not self-contained, so they are
# checked through the nearest source that includes it, directly or through other headers.
out+=$(cd "$TREE" && python3 - "$TIDY" "$DATABASE" 2>&1 <<'PYTHON'
import json, os, re, subprocess, sys
tidy, database = sys.argv[1:]
ranges, name = {}, None
for row in open(os.path.join(database, "changed.diff")):
    if row.startswith("+++ "):
        name = row[6:].strip() if row.startswith("+++ b/") else None
    elif name and name.endswith(".h"):
        hunk = re.match(r"@@ [^+]*\+(\d+)(?:,(\d+))? @@", row)
        if hunk and int(hunk[2] or 1):
            first = int(hunk[1])
            ranges.setdefault(name, []).append([first, first + int(hunk[2] or 1) - 1])
# Who includes what, from the quoted includes, which name a file from src/ or beside the
# includer: a header included only through another header is found through it.
included_by = {}
for directory, _, files in os.walk("src"):
    for file in files:
        if not file.endswith((".c", ".cpp", ".h")):
            continue
        including = os.path.join(directory, file)
        for path in re.findall(r'^[ \t]*#[ \t]*include[ \t]*"([^"]+)"',
                               open(including, errors="replace").read(), re.M):
            for candidate in (os.path.join("src", path), os.path.join(directory, path)):
                if os.path.isfile(candidate):
                    included_by.setdefault(os.path.normpath(candidate), set()).add(including)
                    break
failed = False
for header, lines in ranges.items():
    source, seen, frontier = None, {header}, [header]
    while frontier and source is None:
        frontier = sorted({including for file in frontier for including in
                           included_by.get(file, ()) if including not in seen})
        seen.update(frontier)
        source = next((file for file in frontier if not file.endswith(".h")), None)
    if source is None:
        print(f"tidy: no source includes {header}; its changed lines are not checked.")
        continue
    result = subprocess.run([tidy, "-p", database, "--quiet", "-header-filter=" + re.escape(header),
                             "-line-filter=" + json.dumps([{"name": header, "lines": lines}]),
                             source], capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr)
        failed = True
sys.exit(1 if failed else 0)
PYTHON
) || status=1
if (( status )); then
	printf '%s\n' "$out"
	echo
	echo "tidy: findings on changed lines (fix them, or explain a NOLINT beside the line)."
	exit 1
fi
echo "tidy: changed lines are clean."
