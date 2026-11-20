#!/bin/bash
# Preserve archived C common-symbol semantics in all consumers of dvodb.h.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
ipp_task_root="$PSCRATCH/legacy-satellite-search/software/ipp"
ipp_task_probe="$ipp_task_root/probe_common_core"
mkdir -p "$ipp_task_probe"
export PSCONFDIR="$ipp_task_root/install" PSVERSION=lssat
source "$PSCONFDIR/psconfig.bash" lssat
# Existing Ohana headers/libraries were successfully regenerated serially.
# Clean only isolated core build products so no fno-common object survives.
for ipp_task_module in psLib psModules psphot; do
  if [[ -f "$ipp_task_root/ipp-20190404/$ipp_task_module/Makefile" ]]; then
    make -C "$ipp_task_root/ipp-20190404/$ipp_task_module" clean > "$ipp_task_probe/clean_$ipp_task_module.log" 2>&1
  fi
done
cat > "$ipp_task_probe/config.site" <<'SITE'
with_mysql=no
enable_debug_build=yes
# The package overwrites CFLAGS; a compiler-driver option preserves its other
# generated flags while applying GCC's documented legacy-C workaround.
CC='gcc -fcommon'
SITE
export CONFIG_SITE="$ipp_task_probe/config.site" LS_SAT_IPP_RECONFIGURE=1
export LS_SAT_IPP_PROBE_NAME=probe_common_core LS_SAT_IPP_FIX_LIBS=0 LS_SAT_IPP_OUTPUT=build_common_core.json
exec bash scripts/v14_ipp_build_probe.sh
