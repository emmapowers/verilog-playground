# ===== Vivado batch Makefile (project mode) =====
# - Sources settings64.sh automatically
# - Builds bitstream via build.tcl
# - Programs board via program.tcl
# - On failure, tails key logs and opens them in VS Code (if 'code' CLI is available)

# --- Edit these if needed ---
VIVADO_SETTINGS ?= ${HOME}/tools/Xilinx/2025.1/Vivado/settings64.sh
VIVADO ?= vivado

# Batch flags: quiet-ish terminal
VFLAGS  = -mode batch -nolog -nojournal -notrace

# Use bash everywhere for 'source'
# SHELL := $(/usr/bin/env bash)
SHELL := /usr/bin/bash
.SHELLFLAGS := -euo pipefail -c
.ONESHELL:

# Detect project (expects exactly one .xpr in cwd)
XPR    := $(firstword $(wildcard *.xpr))
PROJ   := $(basename $(notdir $(XPR)))
RUNDIR := $(PROJ).runs
PROJECT_TCL := project.tcl

# Common log/report paths
TOPLOG    := vivado.log
SYNLOG    := $(RUNDIR)/synth_1/runme.log
IMPLOG    := $(RUNDIR)/impl_1/runme.log
TIMINGRPT := timing_summary.rpt
UTILRPT   := utilization.rpt

# Helper: run vivado with env loaded
define RUN_VIVADO
	if [ ! -f "$(VIVADO_SETTINGS)" ]; then \
	  echo "ERROR: Vivado settings file not found: $(VIVADO_SETTINGS)"; exit 127; \
	fi; \
	source "$(VIVADO_SETTINGS)"; \
	"$(VIVADO)" $(VFLAGS) -source $(1)
endef

# Helper: after a failure, show + open logs if possible
define ON_FAIL_OPEN_LOGS
	@echo ""; echo "========== BUILD FAILED: showing logs =========="; \
	[ -f "$(TOPLOG)" ]  && { echo ""; echo "--- $(TOPLOG) (last 50 lines) ---"; tail -n 50 "$(TOPLOG)"; } || true; \
	[ -f "$(SYNLOG)" ]  && { echo ""; echo "--- $(SYNLOG) (last 50 lines) ---"; tail -n 50 "$(SYNLOG)"; } || true; \
	[ -f "$(IMPLOG)" ]  && { echo ""; echo "--- $(IMPLOG) (last 50 lines) ---"; tail -n 50 "$(IMPLOG)"; } || true; \
	[ -f "$(TIMINGRPT)" ] && echo ""; [ -f "$(TIMINGRPT)" ] && echo "Timing report: $(TIMINGRPT)"; true; \
	[ -f "$(UTILRPT)" ]   && echo "Utilization report: $(UTILRPT)"; true; \
	if command -v code >/dev/null 2>&1; then \
	  echo ""; echo "Opening logs in VS Code..."; \
	  code -r "$(TOPLOG)" 2>/dev/null || true; \
	  [ -f "$(SYNLOG)" ]  && code -r "$(SYNLOG)" 2>/dev/null || true; \
	  [ -f "$(IMPLOG)" ]  && code -r "$(IMPLOG)" 2>/dev/null || true; \
	  [ -f "$(TIMINGRPT)" ] && code -r "$(TIMINGRPT)" 2>/dev/null || true; \
	  [ -f "$(UTILRPT)" ]   && code -r "$(UTILRPT)" 2>/dev/null || true; \
	else \
	  echo ""; echo "Tip: install the 'code' CLI on this remote to auto-open files."; \
	  echo "Paths you can open manually:"; \
	  echo "  $(TOPLOG)"; \
	  [ -f "$(SYNLOG)" ]  && echo "  $(SYNLOG)"  || true; \
	  [ -f "$(IMPLOG)" ]  && echo "  $(IMPLOG)"  || true; \
	  [ -f "$(TIMINGRPT)" ] && echo "  $(TIMINGRPT)" || true; \
	  [ -f "$(UTILRPT)" ]   && echo "  $(UTILRPT)"   || true; \
	fi
endef

.PHONY: all bit prog clean logs check import-tcl export-tcl

all: bit

check:
	@# Sanity checks to give crisp errors up front
	@if [ -z "$(XPR)" ]; then echo "ERROR: No .xpr found in $(PWD)"; exit 1; fi
	@if [ ! -f "$(VIVADO_SETTINGS)" ]; then echo "ERROR: Missing Vivado settings: $(VIVADO_SETTINGS)"; exit 1; fi

bit: check
	@echo "==> Building bitstream for $(PROJ)"
	if ! ($(call RUN_VIVADO,scripts/build.tcl)); then
	  echo "Build failed."
	  exit 2
	fi
	@echo "==> Build complete."

prog: check
	@echo "==> Programming board"
	if ! ($(call RUN_VIVADO,scripts/program.tcl)); then
	  echo "Programming failed."
	  exit 3
	fi
	@echo "==> Device programmed."

logs:
	@# Convenience target to open logs/reports on demand
	@if command -v code >/dev/null 2>&1; then \
	  [ -f "$(TOPLOG)" ]    && code -r "$(TOPLOG)"    || true; \
	  [ -f "$(SYNLOG)" ]    && code -r "$(SYNLOG)"    || true; \
	  [ -f "$(IMPLOG)" ]    && code -r "$(IMPLOG)"    || true; \
	  [ -f "$(TIMINGRPT)" ] && code -r "$(TIMINGRPT)" || true; \
	  [ -f "$(UTILRPT)" ]   && code -r "$(UTILRPT)"   || true; \
	else \
	  echo "No 'code' CLI; here are the files:"; \
	  ls -1 $(TOPLOG) $(SYNLOG) $(IMPLOG) $(TIMINGRPT) $(UTILRPT) 2>/dev/null || true; \
	fi

import-tcl:
	@if [ ! -f "$(PROJECT_TCL)" ]; then \
		echo "ERROR: $(PROJECT_TCL) not found. Export one first!"; \
		exit 1; \
	fi
	@echo "==> Importing Vivado project from $(PROJECT_TCL)"
	@$(VPROJ) --settings "$(VIVADO_SETTINGS)" import-tcl "$(PROJECT_TCL)" --workdir .
	@echo "==> Vivado project recreated in $(PROJECT_DIR)"

export-tcl:
	@if [ -f "$(XPR)" ]; then \
		echo "Exporting $(PROJECT_TCL)"; \
		scripts/vproj --settings "$(VIVADO_SETTINGS)" --proj $(XPR) export-tcl --out $(PROJECT_TCL) --rel-to . --no-copy-sources; \
	else \
		echo "No project found."; \
	fi

clean:
	@rm -f vivado*.log vivado*.jou
	@rm -rf .Xil
	@# Keep runs/ unless you really want to wipe them:
	@# rm -rf $(RUNDIR)