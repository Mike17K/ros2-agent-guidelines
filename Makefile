# Workspace front door (DEVENV-003): every routine action is one `make` target that
# wraps the real tool, so humans, agents and CI run exactly the same commands.
# `make help` lists targets. Project-specific targets go in Makefile.local.
#
# Package arguments: p=<pkg> (n=<pkg> is accepted too), d=<dest dir> for new packages.

SHELL := /bin/bash
.DEFAULT_GOAL := help
WS := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
ENV := source $(WS)/scripts/env.sh &&
P ?= $(p)$(n)
JOBS := $(or $(shell grep -E '^BUILD_JOBS=' $(WS)/project.env 2>/dev/null | cut -d= -f2-),$(shell nproc))
COLCON_BUILD := colcon build --symlink-install --base-paths src --parallel-workers $(JOBS) \
	--cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
PKG_SEL = $(if $(P),--packages-up-to $(P),)
DEST = $(if $(d),--dest $(d),)

.PHONY: help build debug release test check asan tsan coverage nightly contracts rosdeps \
	new-cpp new-py new-interfaces clean shell image devenv-status host-check panes external \
	verify-templates sync

help: ## list targets
	@grep -hE '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | \
	  awk -F':.*## ' '{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## --- build & test -----------------------------------------------------------
build: ## colcon build, RelWithDebInfo            [p=pkg]
	$(ENV) $(COLCON_BUILD) -DCMAKE_BUILD_TYPE=RelWithDebInfo $(PKG_SEL)
debug: ## colcon build, Debug                      [p=pkg]
	$(ENV) $(COLCON_BUILD) -DCMAKE_BUILD_TYPE=Debug $(PKG_SEL)
release: ## colcon build, Release                  [p=pkg]
	$(ENV) $(COLCON_BUILD) -DCMAKE_BUILD_TYPE=Release $(PKG_SEL)
test: ## colcon test + results (no rebuild)        [p=pkg]
	$(ENV) colcon test --base-paths src $(if $(P),--packages-select $(P),) ; colcon test-result --verbose
check: ## Definition of Done gate (tools/check.sh) [p=pkg]
	$(WS)/tools/check.sh $(if $(P),--packages $(P),)
asan: ## gate with AddressSanitizer + UBSan        [p=pkg]
	$(WS)/tools/check.sh --sanitize asan $(if $(P),--packages $(P),)
tsan: ## gate with ThreadSanitizer                 [p=pkg]
	$(WS)/tools/check.sh --sanitize tsan $(if $(P),--packages $(P),)
coverage: ## gate + coverage report and threshold  [p=pkg]
	$(WS)/tools/check.sh --coverage $(if $(P),--packages $(P),)
nightly: ## gate + replay and scenario tests (L4/L5)
	$(WS)/tools/check.sh --nightly $(if $(P),--packages $(P),)
contracts: ## validate node contracts + static graph check
	python3 $(WS)/tools/contracts.py graph
rosdeps: ## install dependencies of every package in src/
	$(ENV) rosdep update --rosdistro $$ROS_DISTRO && \
	  rosdep install --from-paths src --ignore-src -r -y --rosdistro $$ROS_DISTRO

## --- create -------------------------------------------------------------------
new-cpp: ## scaffold a C++ package   n=name [d=src/group]
	@test -n "$(P)" || { echo "usage: make new-cpp n=<name> [d=src/<group>]"; exit 1; }
	$(WS)/tools/new_package.py cpp $(P) $(DEST)
new-py: ## scaffold a Python package n=name [d=src/group]
	@test -n "$(P)" || { echo "usage: make new-py n=<name> [d=src/<group>]"; exit 1; }
	$(WS)/tools/new_package.py py $(P) $(DEST)
new-interfaces: ## scaffold an interfaces package n=name
	@test -n "$(P)" || { echo "usage: make new-interfaces n=<name>_interfaces"; exit 1; }
	$(WS)/tools/new_package.py interfaces $(P) $(DEST)

## --- environment ----------------------------------------------------------------
host-check: ## check host prerequisites for DEVENV
	$(WS)/scripts/setup_host.sh
image: ## build the dev container image
	$(WS)/scripts/container.sh build
shell: ## open a shell in the dev environment (container or native)
	$(WS)/scripts/container.sh shell
devenv-status: ## show dev environment status
	$(WS)/scripts/container.sh status
panes: ## open the launch panes (scripts/launch/panes.list)
	$(WS)/scripts/launch/panes.sh
external: ## fetch pinned non-ROS deps (external/external.list)
	$(WS)/scripts/setup_external.sh
clean: ## remove build/install/log (all variants)
	rm -rf $(WS)/build $(WS)/install $(WS)/log $(WS)/build-* $(WS)/install-* $(WS)/log-*

## --- guidelines -----------------------------------------------------------------
verify-templates: ## prove the golden templates still pass everything
	$(WS)/tools/verify_templates.sh
sync: ## pull managed guideline files from upstream  u=<path>
	@test -n "$(u)" || { echo "usage: make sync u=<path to upstream guidelines>"; exit 1; }
	$(WS)/tools/sync_guidelines.sh $(u)

-include $(WS)/Makefile.local
