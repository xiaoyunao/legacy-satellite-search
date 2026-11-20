#!/bin/bash
# Build only the bundled Ohana libraries required by IPP, not its application suite.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
workspace=$PWD
ipp_task_root="$PSCRATCH/legacy-satellite-search/software/ipp"
ipp_task_probe="$ipp_task_root/probe_ohana_common"
export PSCONFDIR="$ipp_task_root/install" PSVERSION=lssat
export MAKEFLAGS="-j${SLURM_CPUS_PER_TASK:-4}"
mkdir -p "$ipp_task_probe"
source "$PSCONFDIR/psconfig.bash" lssat
cd "$ipp_task_root/ipp-20190404/Ohana"
./configure --prefix="$PSCONFDIR/lssat.lin64" > "$ipp_task_probe/ohana_configure.log" 2>&1
# GCC 14 diagnoses legacy formatting code; preserve all configured macros and
# warning flags while allowing warnings, as in the core's debug-build option.
ipp_ohana_cppflags=$("$workspace/.venv/bin/python" - <<'PY'
from pathlib import Path
import shlex
lines=Path('Makefile.System').read_text().splitlines()
value=next(line.split('=',1)[1] for line in lines if line.startswith('CPPFLAGS ='))
flags=shlex.split(value)
if '-Werror' not in flags: raise ValueError('Expected generated warning policy changed')
print(' '.join(flag for flag in flags if flag!='-Werror'))
PY
)
printf '%s\n' "$ipp_ohana_cppflags" > "$ipp_task_probe/ohana_cppflags.txt"
ipp_ohana_cflags=$("$workspace/.venv/bin/python" - <<'PY'
from pathlib import Path
lines=Path('Makefile.System').read_text().splitlines()
value=next(line.split('=',1)[1].strip() for line in lines if line.split('=',1)[0].strip()=='CFLAGS')
print(value+' -fcommon')
PY
)
printf '%s\n' "$ipp_ohana_cflags" > "$ipp_task_probe/ohana_cflags.txt"
# Restore the documented pre-GCC10 common-symbol convention for archived C.
# Force rebuilding all library objects so old fno-common objects cannot survive.
make -B libs "CPPFLAGS=$ipp_ohana_cppflags" "CFLAGS=$ipp_ohana_cflags" > "$ipp_task_probe/ohana_libraries.log" 2>&1
cd "$workspace"
cat > "$ipp_task_probe/config.site" <<'SITE'
with_mysql=no
enable_debug_build=yes
SITE
export CONFIG_SITE="$ipp_task_probe/config.site" LS_SAT_IPP_RECONFIGURE=1
export LS_SAT_IPP_PROBE_NAME=probe_ohana_common LS_SAT_IPP_FIX_LIBS=0 LS_SAT_IPP_OUTPUT=build_ohana_common.json
exec bash scripts/v14_ipp_build_probe.sh
