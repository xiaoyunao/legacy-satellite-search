#!/bin/bash
# Bounded, isolated psphot build probe; never edits shell startup files.
set -eo pipefail
if [[ -z "${SLURM_JOB_ID:-}" ]]; then exit 2; fi
workspace=$PWD
ipp_task_root="$PSCRATCH/legacy-satellite-search/software/ipp"
ipp_task_probe="$ipp_task_root/${LS_SAT_IPP_PROBE_NAME:-probe}"
export PSCONFDIR="$ipp_task_root/install" PSVERSION=lssat
export MAKEFLAGS="-j${SLURM_CPUS_PER_TASK:-4}"
mkdir -p "$ipp_task_probe" results/v14/ps1_ipp
"$workspace/.venv/bin/python" - "$ipp_task_root" <<'PY'
import hashlib,tarfile,sys,json
from pathlib import Path
root=Path(sys.argv[1]); archive=root/'ipp-20190404.tgz'
if hashlib.md5(archive.read_bytes()).hexdigest()!='16021a46323a79c04432bb839e353f34': raise ValueError('Official IPP archive checksum differs')
target=root/'ipp-20190404'
if not target.exists():
 with tarfile.open(archive) as tar: tar.extractall(root,filter='data')
PY
cd "$ipp_task_root/ipp-20190404/psconfig"
export PATH="$PWD:$PATH"
perl ./psbuild -bootstrap "$PSCONFDIR" > "$ipp_task_probe/bootstrap.log" 2>&1
source "$PSCONFDIR/psconfig.bash" lssat
# Check the archived dependency recipe without installing all database/Perl tools.
set +e
perl ./pschecklibs ipp-3.3 > "$ipp_task_probe/libraries.log" 2>&1
ipp_library_status=$?
set -e
printf '%s\n' "$ipp_library_status" > "$ipp_task_probe/library_check_status.txt"
ipp_result=not_built
ipp_dependencies_ok=true
if [[ "${LS_SAT_IPP_FIX_LIBS:-0}" == 1 ]]; then
  for ipp_library in libcfitsio libfftw3f; do
    set +e
    perl ./pschecklibs -build -only "$ipp_library" ipp-3.3 > "$ipp_task_probe/build_${ipp_library}.log" 2>&1
    ipp_status=$?
    set -e
    printf '%s\n' "$ipp_status" > "$ipp_task_probe/status_${ipp_library}.txt"
    if [[ "$ipp_status" != 0 ]]; then ipp_result="failed_dependency_${ipp_library}"; ipp_dependencies_ok=false; break; fi
  done
fi
ipp_build_options=()
if [[ "${LS_SAT_IPP_RECONFIGURE:-0}" == 1 ]]; then ipp_build_options=(-rebuild); fi
if "$ipp_dependencies_ok"; then
for ipp_module in psLib psModules psphot; do
  set +e
  perl ./psbuild -dev -no-as-needed "${ipp_build_options[@]}" -only "$ipp_module" ipp-3.3 > "$ipp_task_probe/build_${ipp_module}.log" 2>&1
  ipp_status=$?
  set -e
  printf '%s\n' "$ipp_status" > "$ipp_task_probe/status_${ipp_module}.txt"
  if [[ "$ipp_status" != 0 ]]; then ipp_result="failed_${ipp_module}"; break; fi
  ipp_result="built_${ipp_module}"
done
fi
cd "$workspace"
.venv/bin/python - "$ipp_task_root" "$ipp_result" "$ipp_task_probe" "${LS_SAT_IPP_OUTPUT:-build_probe.json}" <<'PY'
import os,json,sys,hashlib
from pathlib import Path
root=Path(sys.argv[1]); paths=sorted(Path(sys.argv[3]).glob('*'))
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths if p.is_file()}
result=dict(job=os.environ['SLURM_JOB_ID'],result=sys.argv[2],artifacts=files,
  probe_script_sha256=hashlib.sha256(Path('scripts/v14_ipp_build_probe.sh').read_bytes()).hexdigest(),
  bundled_c_dependency_fix=os.environ.get('LS_SAT_IPP_FIX_LIBS')=='1',
  archive_sha256=hashlib.sha256((root/'ipp-20190404.tgz').read_bytes()).hexdigest(),
  source='https://ipp.ifa.hawaii.edu/ipp-20190404.tgz',
  isolated_prefix_relative='software/ipp/install',shell_startup_files_modified=False,
  physical_PS1_response_validated=False,
  scope='Bounded core build only. No external database/Perl suite installation, no image processing or PS1 catalogue equivalence claim. A successful build still needs blank-image PSF/photometry/selection validation before injection response can represent PS1 DR2.')
(Path('results/v14/ps1_ipp')/sys.argv[4]).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
PY
