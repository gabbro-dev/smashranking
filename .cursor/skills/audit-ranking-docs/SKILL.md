---
name: audit-ranking-docs
description: Audit README.md and ALGORITHM.md against the ranking algorithm code and config to find drift. Use when the user asks to verify, compare, or check the docs against reality, after manual edits to README/ALGORITHM, after changes to vars.txt or any algorithm Python file, or before publishing/committing doc changes.
disable-model-invocation: true
---

# Audit Ranking Docs

Compares `README.md` and `ALGORITHM.md` against the actual ranking algorithm code and config
(`vars.txt`, `app.py`, `elo.py`, `placement.py`, `normalize.py`, `player.py`, `shrink.py`,
`importvars.py`, `shrink_elo.sql`). Reports every claim that no longer matches reality.

## When to run

- The user asks to "audit", "verify", "compare", "diff", or "check" the README / docs / algorithm
  documentation.
- After manual edits to `README.md` or `ALGORITHM.md`.
- After changes to `vars.txt` or any of the algorithm Python files listed above.
- Before committing or publishing doc changes.

## Output format

Always end with a summary block in this exact shape so the user can scan it quickly:

```
DRIFT REPORT
============
[OK]    <claim>          (file:line ref)
[FIX]   <claim>          (file:line ref)  — actual: <X>  / docs say: <Y>
[NOTE]  <observation>    (file:line ref)

Summary: <N> OK, <M> FIX, <K> NOTE
```

- `OK` — docs match reality.
- `FIX` — docs are wrong; quote both the docs value and the code value.
- `NOTE` — something worth flagging (dormant code, undocumented quirk, ambiguous wording) that
  isn't strictly wrong.

After the report, if there are `FIX` items, list the **exact** README/ALGORITHM lines that need
to change. Do **not** edit files unless the user explicitly asks for it — this skill is read-only
by default.

## Audit checklist

Walk through each of these. For every item, locate the claim in the docs (grep for a distinctive
phrase) and compare against the source.

### A. `vars.txt` constants

| Var               | Docs locations to check                                                   |
|-------------------|---------------------------------------------------------------------------|
| `k`               | README "Step 1 — ELO" bullet, README "Concepts → K-factor", ALGORITHM §2.1 |
| `defaultelo`      | README "Step 1 — ELO" bullet, ALGORITHM §2.1, §10                          |
| `harshness`       | README national PP block (`^4`), Penalties table, ALGORITHM §2.1, §7.3     |
| `basesize`        | README PP blocks (the `/32`), ALGORITHM §2.1, §7.3 / §7.4                  |
| `placementBase`   | README placement-points table, ALGORITHM §7.1                              |
| `eloweight`       | README "Step 3" bullets, ALGORITHM §8                                      |
| `placementweight` | README "Step 3" bullets, ALGORITHM §8                                      |
| `formpointsweight`| README "Step 3" bullets, ALGORITHM §8 (mark as dead code)                  |
| `tourneyCount`    | README low-data table, ALGORITHM §8                                        |
| `nationbans`      | README national-vs-region table, ALGORITHM §11                             |
| `shadowbans`      | README national-vs-region row, ALGORITHM §11                               |
| `regionbans`      | README national-vs-region row, ALGORITHM §11                               |

For each constant, report `[FIX]` if the value in `vars.txt` doesn't match the value in the docs.
For dicts/arrays, check both the keys and the values (the placement-points table maps directly
to `placementBase`).

### B. Formulas

Verify every formula appears identically in code and docs. Check:

1. **ELO update** (`elo.py:calculateElo`)
   - `expected = 1 / (1 + 10 ** ((opponent - player) / 400))`
   - `new_elo = player + k * (score - expected)` (rounded to 3 decimals)
   - README "Step 1 — ELO" + ALGORITHM §5.

2. **National PP** (`placement.py:calculatePointsArg`)
   - `size_w = min((nplayers / basesize) ** harshness, 1.0)`
   - `mean_top` over top-`min(8, len(topelos))` pre-tournament ELOs.
   - `strength_w = clamp(1 + (mean_top - 1500) / 600, 0.90, 1.15)` — confirm bounds and divisor.
   - `points = round(base * size_w * strength_w, 3)`.
   - README "How much is a tournament 'worth'?" + ALGORITHM §7.3.

3. **Region PP** (`placement.py:calculatePointsRegion`)
   - `size_w = min((nplayers / basesize) ** harshness, 1.0)` with default `harshness=0.8`.
   - `strength_w = avgelo / defaultelo` (currently `1500`).
   - `avgelo = (sum_present + 1500 * n_guests) / nplayers`.
   - README region PP block + ALGORITHM §7.4.

4. **Placement eligibility** (`placement.py:validBaseFor`)
   - `< 16` → `{1,2,3,4}`; `< 24` → `{1,2,3,4,5,7}`; `< 32` → `{1,2,3,4,5,7,9}`; `≥ 32` → all.
   - README national PP eligibility bullets + ALGORITHM §7.2.

5. **Final rank combination** (`normalize.py:normalize`)
   - `elo_norm = (elo - lowestelo) / (highestelo - lowestelo)`.
   - `pp_norm = (pp - lowestplacement) / (highestplacement - lowestplacement)`.
   - `rank = eloweight * elo_norm + placementweight * pp_norm`.
   - `rank *= tourneycount.get(ntourneys, 1)`.
   - README "Step 3" + ALGORITHM §8.

6. **CI shrink** (`shrink.py`)
   - `Rsh = 1500 + ci * (R - 1500)`; `ci = max(CIsets, CIopps)`; `C0sets=4`, `C0opps=4`.
   - ALGORITHM §9. README year-handling section should say it's **not currently called** in
     `app.py` (the call is wrapped in a triple-quoted block) — verify this still holds.

7. **Yearly carry-over** (`shrink_elo.sql`)
   - `new_elo = ROUND(1500 + (old_elo - 1500) * 0.3)` — verify the `0.3` coefficient.
   - Source `rankingid` and target `rankingid` in the SQL match what the docs claim.
   - README "How things are handled between years" + ALGORITHM §10.

### C. Behavioral claims

These come from `app.py` and `elo.py`. Each one is something README/ALGORITHM asserts:

- Sets are processed **chronologically by `completedAt`** (sorted in `elo.updateElo`); sets
  without `completedAt` are dropped.
- DQ set IDs come from CSV column 4, pipe-separated; checked in both `app.mapSets` and
  `elo.updateElo`.
- `Resurrection Bracket` phase is skipped in both `app.mapSets` and `elo.updateElo`.
- Sets with `winnerId == None` are skipped in `app.mapSets`.
- Guest entrants get a temporary in-memory ELO seeded at `defaultelo`; not persisted; do **not**
  earn PP; **do** count toward `nplayers`.
- Region-banned players' sets are skipped for ELO updates but still increment the entrant's game
  counter (so the players count as "present").
- Foreign-player pre-ELO seeds in `app.mapPlayers`:
  - Peco/Garu (135383, 1451270) → 1600
  - Flame/Tapia (780143, 298485) → 1560
  - Benny Henny / LRBA→Start (433945, 635540) → 1540
  - Other `nationbans` → `defaultelo`
- "Present attendee" = `Player.entrants[entrantid][1] >= 1` in `placement.updatePlacement`.

### D. Menu options and CSV paths

From `app.py` "Menu" block:

- Option `1` → wipes `attendees`+`sets` for `arg26` (rankings deletion is **commented**); reads
  `Tournaments/tournaments2026.csv`. Year may be different by the time you run this — verify the
  current value of `tournamentCSV` and the corresponding `delete from … where rankingid = '…'`.
- Option `2 → 1` → loads existing data; reads `Tournaments/Update/arg26.csv`.
- Option `2 → <region>` → loads existing data; reads `Tournaments/Update/<region>.csv`.
- Other input → wipes `attendees`+`rankings` for that region; reads `Tournaments/Regions/<region>.csv`.

The README "Running it" table and the national-vs-region table both depend on these. If the year
suffix has rolled over (e.g. from `arg26` to `arg27`), flag it everywhere it appears.

### E. Stray scripts / files

For each file the docs list as "stray", confirm it still exists and the description is accurate:

- `temp.py` — reads `preelo-2025.txt`, prints PHP `$elo = [...]`.
- `shrink_elo.sql` — year-end carry-over; coefficient `0.3`.
- `preelo-2025.txt` — flat `id | elo` snapshot.
- `form.csv` — pipe/CSV-separated; loader still commented out in `normalize.py`?
  `formpointsweight` still 0?
- `shrink.py` — call still wrapped in `"""…"""` in `app.py`?

If new files appear in the repo root, in `Tournaments/`, or any new SQL/data file, flag as
`[NOTE]` so they get documented.

### F. Database schema (ALGORITHM §12)

Read all the queries in `app.py`, `placement.py`, and `shrink.py`. Confirm:

- Tables referenced: `players`, `tournaments`, `rankings`, `attendees`, `sets`, `rankingdata`.
- Columns referenced in INSERT/UPDATE/SELECT match what ALGORITHM §12 lists.
- Any new column or table that isn't in §12 → `[FIX]` (add it).

## Workflow

```
Audit progress:
- [ ] A. Constants in vars.txt
- [ ] B. Formulas (ELO, PP arg, PP region, eligibility, normalize, CI, carry-over)
- [ ] C. Behavioral claims (chronology, DQ, guests, bans, seeds)
- [ ] D. Menu options & CSV paths
- [ ] E. Stray scripts and dormant-code claims
- [ ] F. Database schema
- [ ] Write DRIFT REPORT
- [ ] List exact lines to fix in README.md / ALGORITHM.md (no edits unless asked)
```

When the user asks you to fix the drift, follow the rule
`.cursor/rules/keep-docs-in-sync.mdc` so the same change lands in both docs.
