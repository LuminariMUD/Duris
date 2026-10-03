#!/usr/bin/env bash
# Print the callback names of a server binary for lib/misc/event_names, one
# "address type name" line per function. Local (t) and weak (W) functions are
# listed with the global ones, so a static callback, one in an anonymous
# namespace and a lambda are named in the event diagnostics too. Parameter
# lists are dropped: a lambda in do_look() reads do_look::{lambda#1}::_FUN.
set -euo pipefail

nm --demangle "$1" |
	sed -n -e 's/(anonymous namespace):://g' \
		-e ':parameters' -e 's/([^()]*)//g' -e 't parameters' \
		-e 's/^\([0-9a-f]\{1,\} [TtWw] [^ ]\{1,\}\).*/\1/p'
