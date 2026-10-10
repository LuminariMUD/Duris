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
# from the user's git config.
PLAIN=(--no-color --no-ext-diff --src-prefix=a/ --dst-prefix=b/ -U0)
if [[ "$MODE" == "staged" ]]; then
	diff=$(git diff --cached "${PLAIN[@]}" -- src)
elif [[ "$MODE" == "worktree" ]]; then
	diff=$(git diff "${PLAIN[@]}" "$REV" -- src)
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
		"$TIDY" -p "$OUT" --quiet 2>/dev/null >"$OUT/raw.log" || status=$?
	# clang-tidy exits 1 on a finding (xargs: 123); above that it did not run or it died.
	if (( status > 123 )); then
		echo "tidy: $TIDY did not run (xargs exit $status)." >&2
		exit 1
	fi
	# A header's finding comes once per file that includes it: count it once.
	grep -E ': (warning|error): ' "$OUT/raw.log" | sed -E "s#^(\./|$PWD/src/)#src/#" |
		sort -u >"$OUT/all.log" || true
	findings=$(wc -l <"$OUT/all.log")
	echo "tidy: ${#FILES[@]} files, $findings findings; by check:"
	grep -o '\[[a-z0-9.,-]*\]$' "$OUT/all.log" | sed 's/,-warnings-as-errors//' | sort | uniq -c |
		sort -rn || true
	echo "Findings: $OUT/all.log (the compiler output around them: $OUT/raw.log)"
	(( findings == 0 ))
	exit
fi

DATABASE="$PWD/$OUT"
if ! out=$(cd "$TREE" && printf '%s\n' "$diff" | "$TIDY_DIFF" -p1 -path "$DATABASE" \
	-clang-tidy-binary "$TIDY" -j "$(nproc)" -quiet 2>&1); then
	printf '%s\n' "$out"
	echo
	echo "tidy: findings on changed lines (fix them, or explain a NOLINT beside the line)."
	exit 1
fi
echo "tidy: changed lines are clean."
