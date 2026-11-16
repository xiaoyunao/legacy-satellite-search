#!/bin/bash
set -euo pipefail
data="${LS_SAT_DATA:-$PSCRATCH/legacy-satellite-search}"
mkdir -p "$data/resources"
cd "$data/resources"
base=https://raw.githubusercontent.com/delve-survey/delve_mw_census/1a02f50d25cac74c02ddba8401a5af20aa2db4fe/data
fetch() {
    local url=$1 target=$2 hash=$3
    if [[ -f "$target" ]] && echo "$hash  $target" | sha256sum -c - >/dev/null; then
        return
    fi
    curl -fLsS --retry 2 "$url" -o "$target.tmp"
    echo "$hash  $target.tmp" | sha256sum -c -
    mv "$target.tmp" "$target"
}
fetch "$base/read_config.yaml" read_config.yaml c751b3c0524246854e232582589bbe0f4daccf26eff16db899f35b471a8a761a
fetch "$base/delve_census_official_map_v0.fits.gz" census.fits.gz 74a9fcbbf429e5506b15d45bb24a79ec87814b3b5330cdccb2b7ae52b5c64365
fetch https://github.com/DarkEnergySurvey/ugali/releases/download/v1.9.0/ugali-isochrones-tiny.tar.gz ugali-isochrones-tiny.tar.gz 8d20c8efeb44822ca7e0513269db34a32cfb92596a857b03b36a39bcf9e2549b
tar -xzf ugali-isochrones-tiny.tar.gz isochrones/des/bressan2012/iso_a12.0_z0.00010.dat
