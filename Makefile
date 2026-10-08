SHELL := /bin/sh

.DEFAULT_GOAL := build

PYTHON ?= python3
TEST_JOBS ?= 0
TEST_MATCH ?=
PACKAGE_DIR := bin/packages
BUILD_DEPS_PACKAGE := $(PACKAGE_DIR)/duris-build-deps_1.0_all.deb

AREA_GENERATORS := \
	bin/areas/tools/make_mob \
	bin/areas/tools/make_obj \
	bin/areas/tools/make_qst \
	bin/areas/tools/make_shp \
	bin/areas/tools/make_trg \
	bin/areas/tools/make_wld \
	bin/areas/tools/make_zon
AREA_WORLD_OUTPUTS := \
	areas/world.mob \
	areas/world.obj \
	areas/world.qst \
	areas/world.shp \
	areas/world.trg \
	areas/world.wld \
	areas/world.zon
AREA_WORLD_SCRATCH_OUTPUTS := \
	areas/tworld.mob \
	areas/tworld.obj \
	areas/tworld.qst \
	areas/tworld.shp \
	areas/tworld.trg \
	areas/tworld.wld \
	areas/tworld.zon \
	areas/mini.mob \
	areas/mini.obj \
	areas/mini.wld \
	areas/mini.zon
AREA_LOOKUP_OUTPUTS := \
	lib/misc/lookup.mob \
	lib/misc/lookup.obj \
	lib/misc/lookup.wld \
	lib/misc/lookup.zon \
	lib/misc/lookup_with_limits.zon
AREA_WORLD_DIRECT_INPUTS := \
	areas/AREA \
	areas/RANDOM_AREA \
	areas/lookup.awk \
	areas/lookup.rawk \
	areas/lookup_with_limits.awk \
	areas/m_slow \
	areas/make_all \
	areas/make_lookup \
	areas/moveall \
	$(AREA_GENERATORS)

.PHONY: \
	help all build build-server build-production build-editor build-area-tools world \
	build-deps-package test test-all test-python test-native test-list test-db \
	security-sbom security-check clean clean-all

help:
	@printf '%s\n' \
		'Duris developer targets:' \
		'  make                 Build the server, area editor, and area tools' \
		'  make test            Run deterministic local regression tests' \
		'  make test-all        Build everything (the production profile too), generate world data, and test' \
		'  make test-list       List tests discovered by the regression runner' \
		'  make test-db         Run isolated Docker database tests and MariaDB journeys' \
		'  make build-deps-package  Build the Debian metapackage under bin/packages' \
		'  make security-sbom    Generate dependency inventory and SPDX under bin/security' \
		'  make security-check   Generate the SBOM and run local security contracts' \
		'  make clean           Remove compiled build artifacts' \
		'  make clean-all       Remove all reproducible developer artifacts' \
		'' \
		'Test controls:' \
		'  TEST_JOBS=N          Worker count; 0 selects a bounded automatic value' \
		'  TEST_MATCH=TEXT      Run Python tests whose filename contains TEXT'

all: build

build: build-server build-editor build-area-tools

build-server:
	+$(MAKE) -C src

# The production profile compiles at -O2, where the warning profile reports what
# the development build's -Og does not see. Its objects have their own directory,
# and its binary stays out of bin/server/dms_new, which the tests run.
build-production:
	+$(MAKE) -C src BUILD_PROFILE=production \
		SERVER_BIN_DIR=$(CURDIR)/bin/server/production \
		DMS_BINARY=$(CURDIR)/bin/server/production/dms_new

build-editor:
	+$(MAKE) -C areas/de/src

build-area-tools:
	+$(MAKE) -C areas/src

build-deps-package:
	@mkdir -p $(PACKAGE_DIR)
	cd $(PACKAGE_DIR) && equivs-build ../../packaging/duris-build-deps.equivs
	@test -s $(BUILD_DEPS_PACKAGE)

security-sbom:
	$(PYTHON) scripts/generate_security_sbom.py

security-check: security-sbom
	$(PYTHON) scripts/security_source_check.py
	$(PYTHON) tests/async/test_security_dependency_baseline.py

world: build-area-tools
	@set -eu; \
	stamp=areas/.world.stamp; \
	refresh=0; \
	for output in $(AREA_WORLD_OUTPUTS); do \
		if [ ! -s "$$output" ]; then refresh=1; break; fi; \
	done; \
	if [ "$$refresh" -eq 0 ] && [ ! -f "$$stamp" ]; then refresh=1; fi; \
	if [ "$$refresh" -eq 0 ]; then \
		for input in $(AREA_WORLD_DIRECT_INPUTS); do \
			if [ "$$input" -nt "$$stamp" ]; then refresh=1; break; fi; \
		done; \
	fi; \
	if [ "$$refresh" -eq 0 ]; then \
		newer=$$(find areas/mob areas/obj areas/qst areas/shp areas/trg areas/wld areas/zon areas/src \
			-type f ! -name '*.o' -newer "$$stamp" -print -quit); \
		if [ -n "$$newer" ]; then refresh=1; fi; \
	fi; \
	if [ "$$refresh" -eq 1 ]; then \
		log=$$(mktemp -t duris-area-build.XXXXXX); \
		trap 'rm -f "$$log"' EXIT HUP INT TERM; \
		echo 'Generating combined world data...'; \
		if ! (cd areas && ./m_slow) >"$$log" 2>&1; then \
			cat "$$log"; \
			exit 1; \
		fi; \
		for output in $(AREA_WORLD_OUTPUTS); do \
			if [ ! -s "$$output" ]; then \
				echo "error: area generation did not produce $$output" >&2; \
				exit 1; \
			fi; \
		done; \
		touch "$$stamp"; \
		echo 'Combined world data is ready.'; \
	else \
		echo 'Combined world data is up to date.'; \
	fi

test-python: world
	$(PYTHON) tests/run_regression_tests.py --jobs "$(TEST_JOBS)" $(if $(strip $(TEST_MATCH)),--match "$(TEST_MATCH)",)

test-native:
	tests/async/run_signal_handlers.sh

test: test-python test-native

# Keep compilation ahead of the test phase even when the caller enables
# parallel make. The recursive make inherits the jobserver and test controls.
test-all: build build-production
	+$(MAKE) test

test-list:
	$(PYTHON) tests/run_regression_tests.py --list $(if $(strip $(TEST_MATCH)),--match "$(TEST_MATCH)",)

# Every test here creates and destroys its own MySQL or MariaDB container, and
# they run side by side. They are kept out of test-all because Docker is
# intentionally not a core build dependency. The journeys run the built server.
test-db: build-server world
	@command -v docker >/dev/null 2>&1 || { \
		echo 'error: make test-db requires Docker' >&2; \
		exit 127; \
	}
	@docker info >/dev/null 2>&1 || { \
		echo 'error: the Docker daemon is not available' >&2; \
		exit 1; \
	}
	tests/run_db_tests.sh

clean:
	+$(MAKE) -C src clean
	+$(MAKE) -C areas/de/src clean
	+$(MAKE) -C areas/src clean
	+$(MAKE) -C migrations/tools clean
	rm -rf bin/tests

# Preserve repository configuration and runtime data. Everything below bin/
# is generated; the remaining paths are reproducible build, world, or tooling
# outputs rather than source inputs.
clean-all: clean
	find bin -mindepth 1 ! -path bin/.gitignore -delete
	rm -f $(AREA_WORLD_OUTPUTS) $(AREA_WORLD_SCRATCH_OUTPUTS) areas/.world.stamp
	rm -f $(AREA_LOOKUP_OUTPUTS)
	rm -rf build
	find . -path './.git' -prune -o -type d \
		\( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache \
		-o -name .ruff_cache -o -name htmlcov \) \
		-prune -exec rm -rf {} +
	find . -path './.git' -prune -o -type f \
		\( -name '*.gcda' -o -name '*.gcno' -o -name '*.profraw' \
		-o -name .coverage -o -name '.coverage.*' -o -name coverage.xml \
		-o -name gmon.out -o -name cscope.out \) \
		-exec rm -f {} +


.PHONY: build-restore-tools test-backup-recovery
build-restore-tools:
	python3 scripts/build_restore_qualifier.py
	+$(MAKE) -C src PERSISTENCE_BACKEND=flatfile DMS_BINARY=$(abspath bin/server/dms_restore_flatfile)

test-backup-recovery: build-server build-restore-tools
	python3 tests/async/test_persistence_backup.py
	python3 tests/async/test_backup_pfiles.py
	python3 tests/async/test_flatfile_backup_manifest.py
	python3 tests/async/test_flatfile_launcher.py
	DURIS_RUN_BACKUP_INTEGRATION=1 python3 tests/async/test_persistence_backup_integration.py
