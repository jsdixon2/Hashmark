#!/bin/bash
# e23 full pipeline (Actions or local): downloads -> rows -> fit (-> recruiting test if $E23_REC exists). ~2 min, ~500 MB in /tmp.
set -e; cd "$(dirname "$0")/.."
export E23_DL=${E23_DL:-/tmp/b11/dl} E23_NFL=${E23_NFL:-/tmp/b11/nfl}; mkdir -p $E23_DL $E23_NFL /tmp/b11
CF=https://raw.githubusercontent.com/sportsdataverse/cfbfastR-data/main; NV=https://github.com/nflverse/nflverse-data/releases/download
for y in $(seq 2014 2022); do [ -s $E23_DL/ps_$y.csv ] || curl -sSfL -o $E23_DL/ps_$y.csv $CF/player_stats/csv/player_stats_$y.csv; done
for y in $(seq 2010 2023); do [ -s $E23_DL/ro_$y.csv ] || curl -sSfL -o $E23_DL/ro_$y.csv $CF/rosters/csv/cfb_rosters_$y.csv; done
for y in $(seq 2016 2026); do [ -s $E23_NFL/reg_$y.csv ] || curl -sSfL -o $E23_NFL/reg_$y.csv $NV/stats_player/stats_player_reg_$y.csv; done
python3 backtest/e23_data.py && python3 backtest/e23_fit.py > /tmp/e23_fit_out.json
[ -s "${E23_REC:-/tmp/e23_recruit.json}" ] && python3 backtest/e23_fit_rec.py || true
