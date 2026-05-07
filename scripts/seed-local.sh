#!/usr/bin/env bash
# scripts/seed-local.sh
#
# Stand up a fresh local MariaDB and load it with the cba26 ranking the way
# prod expects it (Piranha Garden weeklies need a smaller K and have to be
# uploaded on their own; majors keep the default K). The K values are the
# K_WEEKLY / K_MONTHLY constants below.
#
# Steps:
#   1. Wipe DB volume + (re)build containers via docker compose.
#   2. arg26 from scratch (K=K_MONTHLY, full Tournaments/tournaments2026.csv)
#      so visitors have national ELOs that the cba26 run will reference.
#   3. cba26 from scratch with K=K_WEEKLY, using only Piranha Garden weeklies.
#   4. cba26 update with K=K_MONTHLY, adding Dark Winter 2026 alone on top.
#
# Files this script mutates while running:
#   vars.txt
#   Tournaments/Regions/cba26.csv
#   Tournaments/Update/cba26.csv
#
# All three are restored to their pre-script contents on exit, regardless of
# whether the script succeeds, fails, or is interrupted (Ctrl+C).
#
# Usage:
#   ./scripts/seed-local.sh
#
# Requires: Docker + docker compose, a populated `.env` (start.gg token),
# and roughly 8-15 minutes for start.gg API rate-limit cooldowns.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VARS_FILE="vars.txt"
REGIONS_CSV="Tournaments/Regions/cba26.csv"
UPDATE_CSV="Tournaments/Update/cba26.csv"

# K-factor per tournament tier. Weeklies (Piranha Garden) need a smaller K so
# a single hot streak doesn't dominate; monthlies/majors keep the default K.
K_WEEKLY=10.67
K_MONTHLY=32

for f in "$VARS_FILE" "$REGIONS_CSV" "$UPDATE_CSV" docker-compose.yml .env; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: required file '$f' is missing." >&2
    exit 1
  fi
done

BACKUP_DIR="$(mktemp -d -t smashranking-seed-XXXXXX)"
cp "$VARS_FILE"   "$BACKUP_DIR/vars.txt"
cp "$REGIONS_CSV" "$BACKUP_DIR/regions-cba26.csv"
cp "$UPDATE_CSV"  "$BACKUP_DIR/update-cba26.csv"

cleanup() {
  local rc=$?
  echo
  echo "==> Restoring vars.txt and cba26 CSVs to pre-script state"
  cp "$BACKUP_DIR/vars.txt"          "$VARS_FILE"   2>/dev/null || true
  cp "$BACKUP_DIR/regions-cba26.csv" "$REGIONS_CSV" 2>/dev/null || true
  cp "$BACKUP_DIR/update-cba26.csv"  "$UPDATE_CSV"  2>/dev/null || true
  rm -rf "$BACKUP_DIR"
  if (( rc != 0 )); then
    echo "FAILED (exit $rc)" >&2
  fi
  exit "$rc"
}
trap cleanup EXIT

set_k() {
  local k="$1"
  sed -i.bak "s/^k=.*/k=${k}/" "$VARS_FILE"
  rm -f "${VARS_FILE}.bak"
  echo "    vars.txt: k=$(grep '^k=' "$VARS_FILE" | cut -d= -f2)"
}

run_app() {
  local desc="$1"; shift
  echo "    $desc"
  printf '%s\n' "$@" | docker compose exec -T app python -u app.py
}

# 1. Reset stack
echo "==> [1/4] Wiping volume + (re)building containers"
docker compose down -v
docker compose up -d --build
echo

# 2. arg26
echo "==> [2/4] arg26 from scratch (K=${K_MONTHLY}) — pulls all 2026 nationals from start.gg"
set_k "$K_MONTHLY"
run_app "Running arg26..." "1"
echo

# 3. cba26 weeklies
echo "==> [3/4] cba26 weeklies from scratch (K=${K_WEEKLY}) — Piranha Garden only"
set_k "$K_WEEKLY"
grep -E 'piranha-garden' "$BACKUP_DIR/regions-cba26.csv" > "$REGIONS_CSV" || {
  echo "ERROR: no Piranha Garden rows found in $REGIONS_CSV (backup)" >&2
  exit 1
}
echo "    Tournaments/Regions/cba26.csv weeklies: $(wc -l < "$REGIONS_CSV")"
run_app "Running cba26 weeklies..." "cba26"
echo

# 4. cba26 update with Dark Winter
echo "==> [4/4] cba26 update (K=${K_MONTHLY}) — Dark Winter 2026 only"
set_k "$K_MONTHLY"
grep -E 'dark-winter' "$BACKUP_DIR/regions-cba26.csv" > "$UPDATE_CSV" || {
  echo "ERROR: no Dark Winter row found in $REGIONS_CSV (backup)" >&2
  exit 1
}
echo "    Tournaments/Update/cba26.csv majors: $(wc -l < "$UPDATE_CSV")"
run_app "Running cba26 update..." "2" "cba26"
echo

# Verification
echo "==> Done. Top 10 cba26 ranking:"
docker compose exec -T mariadb mariadb \
  -usmash_app -pb1f2d41cfaa8f1220ad8b453 -D smashranking --batch -e "
    SELECT r.top, p.name, ROUND(r.elo,2) AS elo, ROUND(r.pp,2) AS pp,
           ROUND(r.\`rank\`,4) AS rank_score, r.ntourneys
    FROM rankings r JOIN players p ON p.id = r.playerid
    WHERE r.rankingid='cba26'
    ORDER BY r.top ASC
    LIMIT 10;
  " 2>&1 | grep -v 'Using a password'

echo
echo "==> Tournament + sets count:"
docker compose exec -T mariadb mariadb \
  -usmash_app -pb1f2d41cfaa8f1220ad8b453 -D smashranking --batch -e "
    SELECT rankingid, COUNT(*) AS rankings FROM rankings GROUP BY rankingid;
    SELECT rankingid, COUNT(*) AS sets     FROM sets     GROUP BY rankingid;
    SELECT COUNT(*) AS tournaments_loaded FROM tournaments;
  " 2>&1 | grep -v 'Using a password'
