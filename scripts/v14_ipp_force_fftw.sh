#!/bin/bash
# Runtime-only vendor FFTW lacks the development interface psLib requires.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
workspace=$PWD
ipp_task_root="$PSCRATCH/legacy-satellite-search/software/ipp"
ipp_task_probe="$ipp_task_root/probe_core_fftw"
export PSCONFDIR="$ipp_task_root/install" PSVERSION=lssat
export MAKEFLAGS="-j${SLURM_CPUS_PER_TASK:-4}"
mkdir -p "$ipp_task_probe"
cd "$ipp_task_root/ipp-20190404/psconfig"
export PATH="$PWD:$PATH"
source "$PSCONFDIR/psconfig.bash" lssat
perl ./pschecklibs -build -force libfftw3f -only libfftw3f ipp-3.3 > "$ipp_task_probe/force_fftw.log" 2>&1
pkg-config --modversion fftw3f > "$ipp_task_probe/fftw_version.txt"
cd "$workspace"
export LS_SAT_IPP_PROBE_NAME=probe_core_fftw LS_SAT_IPP_FIX_LIBS=0 LS_SAT_IPP_OUTPUT=build_core_fftw.json
exec bash scripts/v14_ipp_build_probe.sh
