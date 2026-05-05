# Smash Ranking — Algorithm reference

Detailed documentation of how the ranking is built. This is the long version of [`README.md`](./README.md).

## Table of contents

1. [Pipeline overview](#1-pipeline-overview)
2. [Inputs and configuration](#2-inputs-and-configuration)
3. [Player model](#3-player-model)
4. [Player & set discovery](#4-player--set-discovery)
5. [ELO update (`elo.py`)](#5-elo-update-elopy)
6. [Set persistence (`mapSets` in `app.py`)](#6-set-persistence-mapsets-in-apppy)
7. [Placement Points (`placement.py`)](#7-placement-points-placementpy)
8. [Normalization and final score (`normalize.py`)](#8-normalization-and-final-score-normalizepy)
9. [Connectivity Index ELO shrink (`shrink.py`)](#9-connectivity-index-elo-shrink-shrinkpy)
10. [Yearly carry-over (`shrink_elo.sql` and friends)](#10-yearly-carry-over-shrink_elosql-and-friends)
11. [National vs regional rankings — full delta](#11-national-vs-regional-rankings--full-delta)
12. [Database schema (inferred)](#12-database-schema-inferred)
13. [Stray scripts and files](#13-stray-scripts-and-files)
14. [Known quirks / TODOs](#14-known-quirks--todos)

---

## 1. Pipeline overview

`app.py` is the orchestrator. The flow is:

```
ask user (mode: arg-fresh | arg-update | region-fresh | region-update)
  └─ load existing players from DB if "update", otherwise wipe
  └─ if regional run: load argelo = {globalid: arg26_elo} from rankings (once)
     └─ for each tournament in the CSV:
        ├─ insert tournament row
        ├─ fetchData(queryAttendees)         → mapPlayers
        ├─ fetchData(queryDetailedSets)      → mapSets         (persists sets to DB)
        ├─ fetchData(querySets)              → mapCharacters   (counts character usage)
        │                                     → updateElo(..., argelo)      (mutates Player.elo)
        ├─ fetchData(queryPlacements)        → updatePlacement(..., bannedregionplayers, argelo)
     └─ normalize across all players
     └─ write rankings rows
     └─ for "update" runs, compute per-player rank variation
```

Every tournament is processed in the order listed in the CSV. Sets are sorted **by completion
timestamp** internally to `updateElo`, so even if tournaments are listed out of order in the CSV,
ELO progression within a single tournament is correct.

A 20-second `time.sleep(20)` runs after every paginated `fetchData` call to stay under start.gg's
rate limit.

---

## 2. Inputs and configuration

### 2.1 `vars.txt`

Loaded by `importvars.importVars(<index>)`. Indices map to lines in the file:

| Index | Var name           | Type    | Current value                                                   | Used by |
|------:|--------------------|---------|-----------------------------------------------------------------|---------|
|     3 | `k`                | float   | `32`                                                            | `elo.py`, `app.calculateElo` |
|     4 | `defaultelo`       | float   | `1500`                                                          | `elo`, `placement`, `app`, `shrink` |
|     6 | `harshness`        | float   | `4`                                                             | `placement.calculatePointsArg` (national) |
|     7 | `basesize`         | float   | `32`                                                            | `placement.calculatePointsArg` |
|     8 | `placementBase`    | dict    | `{1:100, 2:70, 3:50, 4:35, 5:25, 7:15, 9:10, 13:6, 17:4, 21:3, 25:2, 33:1, 65:0.5}` | `placement.py` |
|    10 | `eloweight`        | float   | `0.6`                                                           | `normalize.py` |
|    11 | `placementweight`  | float   | `0.4`                                                           | `normalize.py` |
|    12 | `formpointsweight` | float   | `0` (dead code)                                                 | `normalize.py` |
|    13 | `tourneyCount`     | dict    | `{0:0, 1:0.3, 2:0.8}` (default `1.0`)                            | `normalize.py` |
|    15 | `nationbans`       | int[]   | foreign players                                                 | `app.py` |
|    16 | `shadowbans`       | int[]   | hidden from final printed ranking                               | `app.py` |
|     – | `regionbans`       | dict    | `{<rankingid>: int[]}`, parsed from line 19 onwards              | `app.py`, `elo.py` |

### 2.2 `.env`

Just one variable: `token=<your start.gg API token>` — used as `Authorization: Bearer <token>`.

### 2.3 Tournament CSVs

A flat CSV with no header, six columns:

| # | Field            | Notes                                                                                  |
|--:|------------------|----------------------------------------------------------------------------------------|
| 0 | `eventSlug`      | start.gg event slug, e.g. `tournament/llama-smash-7/event/ultimate-singles`            |
| 1 | `name`           | Display name of the tournament                                                         |
| 2 | `format`         | Free-text label (`Singles`, `Ladder`, `Round Robin`, `Matchmaking`, `Swiss`, …)        |
| 3 | `dq_set_ids`     | Pipe-separated list of set IDs to skip. Often has duplicates — the algorithm tolerates them |
| 4 | `region`         | One of: `Salta`, `Buenos Aires`, `Cordoba`, `Jujuy`, `Santa Fe`, `Mendoza`             |
| 5 | `date`           | `DD/MM/YYYY`                                                                           |

CSV files live in:

- `Tournaments/tournaments2026.csv` — full national season (option `1`).
- `Tournaments/Regions/<region>.csv` — full regional season (`<region>` as the user input).
- `Tournaments/Update/<rankingid>.csv` — incremental list for an "update" run (option `2`).

---

## 3. Player model

`player.Player` keeps two class-level dicts:

- `Player.players: dict[globalid, Player]` — all known players this run.
- `Player.entrants: dict[entrantid, [Player, ngames]]` — entrants for the **current tournament
  only** (reset by `Player.resetEntrants()` at the start of each tournament). The second value is
  a counter of how many sets that entrant played, used later to detect "absent" attendees.

Per-player attributes:

```
globalid       start.gg user.id
name           display name (sponsor stripped after normalize)
sponsor        team prefix from "Sponsor | Tag"; None if no pipe
elo            current ELO
pp             accumulated Placement Points (sum across tournaments)
ntourneys      number of tournaments where the player actually played ≥ 1 set
wins, losses   match record (national: includes guest matches; region: only counted matches)
characters     dict[character_name, count] — character picks across reported games
region         dict[region_name, attended_count] — which region(s) this player plays in
ci             Connectivity Index (0..1) — set by shrink.py if/when called
```

---

## 4. Player & set discovery

### 4.1 `mapPlayers(data, tourneyRegion)` — `app.py`

For each entrant returned by `queryAttendees`:

1. Resolve `globalid = participants[0].user.id`. If `null`, skip.
2. If new to `Player.players`:
   - **National (`option == 1`)**: special-cased pre-ELO seeds for foreign players known to be
     above default skill (Peco/Garu = 1600, Flame/Tapia = 1560, Benny Henny/LRBA = 1540). Anyone
     in `nationbans` not on that list starts at `defaultelo` (1500). Non-banned players also start
     at 1500 and have their region tally bumped (`tourneyRegion`).
   - **Regional / update**: simply create at `defaultelo`.
3. If already known: refresh `name` (people change tags), and only bump `region` for option 1.
4. Register the entrant: `Player.entrants[entrantid] = [player, 0]`. Sets ngames to 0; this gets
   incremented every time the entrant plays a non-DQ set.

### 4.2 `mapCharacters(data)` — `app.py`

For each game with a `selections` array, increments `player.characters[character_name]`. Quiet
about missing data (a wrapping `try/except` swallows tournaments that don't report games).

---

## 5. ELO update (`elo.py`)

`updateElo(data, k, dqlist, bannedregionplayers, argelo=None) → guests`.

```python
expected = 1 / (1 + 10 ** ((opponent - player) / 400))
new_elo  = round(player + k * (score - expected), 3)
```

Steps:

1. Sort `data` by `completedAt`, drop sets without `completedAt` (treated as "not finished").
2. For each set:
   - Skip if its `id` is in `dqlist`.
   - Skip if `phaseGroup.phase.name == "RESURRECTION BRACKET"` (Buenos Aires).
   - Resolve winner / loser entrants.
   - **Guest handling**: if an entrant isn't in `Player.entrants` (no linked start.gg user), it
     gets a temporary in-memory ELO via the `guests` dict, starting at `defaultelo`. Mixed
     guest/normal sets do update the real player's ELO and W/L. Guest-vs-guest sets only update
     the local `guests` dict. Guests are returned so `placement.py` can include them in the
     attendee count.
   - **Cross-region branch** (regional rankings, `argelo` non-empty): when exactly one of the two
     real entrants is in `bannedregionplayers`, the expected outcome is computed in **arg26-space**
     using `argelo.get(globalid, defaultelo)` for both sides, so the ELO gap reflects national
     calibration instead of the visitor's stub-1500 cba26 value. The resulting `delta = round(k *
     (1 - expected_winner_in_arg), 3)` is added to the local winner's ELO (or subtracted from the
     local loser's ELO); only the local player's `wins` / `losses` is incremented. The visitor's
     in-memory ELO is left alone since they're filtered out at write time.
   - **Cross-region branch — legacy fallback** (`argelo` empty): in arg26-update mode the menu
     sets `bannedregionplayers = nationbans` while `argelo` stays empty. To preserve the old
     behavior in that mode, the cross-region branch only counts presence (game counters tick) and
     skips ELO updates entirely. The new arg-space scoring is opt-in: it requires `argelo` to be
     populated, which only happens for regional runs.
   - **Visitor-vs-visitor**: if both real entrants are in `bannedregionplayers`, the set is
     skipped for ELO updates (game counters still tick). Neither side will appear in the printed
     regional ranking, so there's nothing meaningful to update.
   - **Locals-vs-locals**: regular ELO update, increment `wins`/`losses` and the entrant's
     `ngames`.

---

## 6. Set persistence (`mapSets` in `app.py`)

Distinct from `updateElo`. This function writes the set rows into the DB so the front-end can
display match histories. Each set is `REPLACE`d with:

- Round label, computed from `phaseGroup.bracketType` + `fullRoundText`. For `DOUBLE_ELIMINATION`
  it produces `WSF`, `LF`, `GF`, `GFR`, `L.T8` (Losers Round 1 inside a "Top 8" phase), and
  fallbacks to `W. Pools` / `L. Pools` for unknown rounds. For other bracket types, falls back to
  `RR` / `MM` / `LADDER` / `SWISS` / `Pools`.
- Per-game scores (1/0), per-game character picks, per-game stage names.
- A timestamp from `startedAt` / `startAt` / `completedAt` (first non-null).
- Placeholders for `winnerpreelo`, `loserpreelo`, `newwinnerelo`, `newloserelo`, `notablewins`
  (all 0 today — see [Known quirks](#14-known-quirks--todos)).

For tournaments where `i["games"]` is null (some Buenos Aires events report only set scores), it
falls back to `slots[*].standing.stats.score.value`.

---

## 7. Placement Points (`placement.py`)

### 7.1 The base table

```
placementBase = {1:100, 2:70, 3:50, 4:35, 5:25, 7:15, 9:10, 13:6, 17:4, 21:3, 25:2, 33:1, 65:0.5}
```

Read as: a placement of `n` looks up the largest key `≤ n`. So 12th place uses key 9 (= 10 pts),
14th place uses key 13 (= 6 pts), etc. Standard Smash bracket reporting (1, 2, 3, 4, 5, 7, 9, 13,
17, 25, 33, …) means most placements hit a key directly.

### 7.2 `validBaseFor(placement, nplayers, placementBase)` — national only

Filters which placements are eligible for points based on attendance. This is a **hard cutoff**:

| `nplayers` | Eligible placement keys                |
|-----------:|----------------------------------------|
|  `< 16`    | `{1, 2, 3, 4}`                          |
|  `< 24`    | `{1, 2, 3, 4, 5, 7}`                    |
|  `< 32`    | `{1, 2, 3, 4, 5, 7, 9}`                 |
|  `≥ 32`    | all keys                                |

Anything outside the eligible set returns `0` from `validBaseFor`, which short-circuits the
arg-formula to `points = 0`.

### 7.3 `calculatePointsArg(placement, nplayers, topelos, basesize=32, harshness=4)`

```python
base       = validBaseFor(placement, nplayers, placementBase)
size_w     = min((nplayers / basesize) ** harshness, 1.0)
mean_top   = mean(sorted(topelos, reverse=True)[:min(8, len(topelos))])
strength_w = clamp(1 + (mean_top - 1500) / 600, 0.90, 1.15)
points     = round(base * size_w * strength_w, 3)
```

`topelos` is the **pre-tournament** ELO of the entrants that ended up in the top 8 (resolved by
the `ranked = sorted((placement, -elopre, entrantid))` step). Pre-tournament ELO comes from
`lastelo`, which is captured before `updateElo` runs.

Notes:

- `(nplayers/32)^4` is brutal. This is intentional — the weekly-tournaments meta in 2025/26 was
  rewarding small brackets too much under the old formula.
- The strength factor is bounded to `[0.90, 1.15]`, so even a top-8 averaging 1700 only gives a
  +15% bonus, and a top-8 averaging 1300 only knocks 10% off.

### 7.4 `calculatePointsRegion(placement, nplayers, avgelo, basesize=32, harshness=0.8)`

```python
base   = placementBase.get(placement, 0)         # full table, no validBaseFor gating
size_w = min((nplayers / basesize) ** harshness, 1.0)
points = base * size_w * (avgelo / 1500)
```

`avgelo` is the **mean pre-tournament ELO of all present attendees**, with guests counted at
`defaultelo`:

```python
avgelo = (sum_elo_of_present_real_players + 1500 * n_guests) / nplayers
```

This is the legacy formula, kept for regional rankings. It's softer because:

- `harshness = 0.8` instead of `4`.
- Strength uses the **whole field**, not just the top 8, so it averages closer to 1500.
- No placement-eligibility gating.

### 7.5 `updatePlacement(placementdata, tournamentid, guests, lastelo, option, option2, bannedregionplayers=None, argelo=None)`

1. Builds the list of "present attendees" — entrants whose `Player.entrants[id][1] ≥ 1`
   (≥ 1 set played). These are the only ones who get points.
2. `nplayers = len(present_real) + len(guests)`. Persists this on `tournaments.attendees`.
3. Computes `avgelo` (region) and `topelos` (national). Each attendee's contribution to these
   numbers comes from a `strengthElo(globalid)` helper that picks the right rating source:
   - Visitor with an `argelo` entry (regional runs only): their arg26 ELO. This is the cross-
     region fix — strong nationals show up as strong, weak visitors show up as weak.
   - Otherwise: `lastelo.get(globalid, defaultelo)`. This covers locals (their pre-tournament
     regional ELO), visitors with no `arg26` row, and **arg26-update mode** where the menu sets
     `bannedregionplayers = nationbans` but `argelo` stays empty (so foreigners keep contributing
     their seeded ELO to `topelos` exactly like before).
   - Guests: still counted at `defaultelo` for `nplayers` weighting.
4. For each present attendee, computes points via the appropriate formula and:
   - Adds points to `Player.entrants[entrantid][0].pp`.
   - Increments `ntourneys`.
   - `REPLACE INTO attendees (...) VALUES (...)` to record this player's contribution to this
     tournament (PP + post-set ELO + placement + rankingid).

---

## 8. Normalization and final score (`normalize.py`)

After every tournament has been processed:

```python
elo_norm   = (player.elo - lowestelo)        / (highestelo - lowestelo)
pp_norm    = (player.pp  - lowestplacement)  / (highestplacement - lowestplacement)
rank       = eloweight * elo_norm + placementweight * pp_norm
rank      *= tourneycount.get(player.ntourneys, 1)
```

Notes:

- `eloweight = 0.6`, `placementweight = 0.4` (sum to 1).
- The `formpointsweight = 0` block is dead code; `form.csv` is loaded inside a triple-quoted
  string. Don't rely on it.
- The low-data multiplier (`tourneyCount`) is the only "soft exclusion" mechanism. Players with
  `ntourneys == 0` get rank `0`; with 1 tournament `× 0.3`; with 2 `× 0.8`; from 3 onwards
  `× 1.0`.
- The function also splits `"Sponsor | Tag"` into `player.sponsor` and `player.name` (joins
  multiple pipes back into the sponsor part).

The result is sorted by `rank desc` and returned as a list of `(globalid, [player, rank])`.

---

## 9. Connectivity Index ELO shrink (`shrink.py`)

**Currently disabled** — the call in `app.py` is wrapped in a `"""..."""` block. This describes
what it would do.

The CI of a player measures how much they play against other regions:

```python
C0sets = 4   # threshold for CI = 1
C0opps = 4

CIsets = min(1, intersets / C0sets)        # # of sets vs out-of-region opponents
CIopps = min(1, len(interopps) / C0opps)   # # of unique out-of-region opponents
ci     = max(CIsets, CIopps)
```

Then the ELO is shrunk toward the base:

```python
Rsh = 1500 + ci * (R - 1500)
```

So:

- `ci = 1` (well-traveled): ELO unchanged.
- `ci = 0` (only plays own region): ELO collapses to 1500.
- `ci = 0.5`: half the deviation from 1500 is preserved.

`shrinkElo()` queries the `sets` table joined with `players.region` to count inter-region sets and
opponents per player. It's intended to run **once at year-end**, before the next year's
`shrink_elo.sql` carry-over, to deflate inflated regional kings.

---

## 10. Yearly carry-over (`shrink_elo.sql` and friends)

### 10.1 The actual carry-over (`shrink_elo.sql`)

Two queries:

```sql
INSERT INTO rankings (playerid, rankingid, elo, rank, pp, wins, losses, characters, top)
SELECT
    playerid,
    'arg26'                                    AS rankingid,
    ROUND(1500 + (elo - 1500) * 0.3)           AS elo,
    0 AS rank, 0 AS pp, 0 AS wins, 0 AS losses,
    '{}' AS characters, 100 AS top
FROM rankings
WHERE rankingid = 'arg';
```

This seeds `arg26` from `arg`. The `0.3` coefficient is the carry-over weight: a 1700 ELO becomes
`1500 + 200*0.3 = 1560`; a 1400 becomes `1470`. The second query in the file is a read-only
preview of the same transformation.

After this seed runs:

1. `option 2 → 1` ("Update Arg Ranking") loads ELOs from `rankings` (seeded values), then walks
   through `Tournaments/Update/arg26.csv` to add new tournaments to the season.
2. `option 1` (full re-run from scratch) **does not use** the seed — it processes every tournament
   listed in `tournaments2026.csv` starting from `defaultelo = 1500`. It does **not** delete the
   `rankings` rows for `arg26` (that line is commented out), but the final `INSERT` then either
   tries to add new rows or relies on a unique constraint to fail. In practice option 1 is meant
   for a fresh season **before** the seed is written, or paired with a manual cleanup.

### 10.2 `preelo-2025.txt`

A flat snapshot of the seeded `arg25` ELOs (`<playerid> | <elo>` per line). Used as a backup
and as input to `temp.py`.

### 10.3 `temp.py`

One-off PHP exporter:

```python
def load_elo_dict(filepath):  # parses preelo-2025.txt
def dict_to_php_array(d):     # emits   $elo = [ id => elo, ... ];
```

Used to feed the seeded ELOs into the front-end (PHP) when bootstrapping a new season's display.

---

## 11. National vs regional rankings — full delta

| Concern                          | National (`arg26`)                                           | Regional (e.g. `cba26`)                                       |
|----------------------------------|--------------------------------------------------------------|---------------------------------------------------------------|
| Entry CSV (fresh)                | `Tournaments/tournaments2026.csv`                            | `Tournaments/Regions/<region>.csv`                            |
| Entry CSV (update)               | `Tournaments/Update/arg26.csv`                               | `Tournaments/Update/<region>.csv`                             |
| Banlist source                   | `nationbans` (line 16)                                       | `regionbans[<rankingid>]` (line 19+)                          |
| Pre-ELO seeds for foreigners     | Yes (1600/1560/1540/1500)                                    | No                                                            |
| Set-level treatment of bans      | Banned players' sets **affect** Argentinian ELOs              | Cross-region sets are scored in **arg26-space** (delta lands on the local player only). Visitor-vs-visitor still skipped. |
| Banned players in final ranking  | Excluded from print and DB write                              | Excluded from print and DB write                              |
| `shadowbans`                     | Excluded from print and DB write                              | Not used                                                       |
| PP formula                       | `calculatePointsArg`                                         | `calculatePointsRegion`                                        |
| `harshness`                      | `4`                                                          | `0.8`                                                         |
| Strength signal                  | Top-8 pre-ELO mean, clamped 0.90–1.15                         | Average pre-ELO of all attendees (no clamp). Visitors contribute their `arg26` ELO when available, otherwise `lastelo`. |
| Placement eligibility gating     | Yes (`validBaseFor`)                                         | No                                                            |
| `region` tracking on Player      | Updated per tourney                                          | Not touched                                                    |
| Wipe on fresh run                | `attendees`+`sets` for `arg26`; `rankings` is **not** wiped  | `attendees`+`rankings` for the region; `sets` not wiped        |
| Final write                      | `INSERT INTO rankings`                                       | `REPLACE INTO rankings`                                        |
| Update run reads previous data?  | Yes (loads ELO/PP/etc from `rankings`)                       | Yes                                                           |
| Variation column on update       | Computed (`lastranking − newranking`)                        | Computed                                                       |
| `tournamentcount` bookkeeping    | Set absolute on fresh, **incremented** on update             | Same                                                           |

---

## 12. Database schema (inferred)

`db.py` is gitignored, but we can infer the schema from the queries throughout the code:

### `players`

```
id          int   PK         -- start.gg user.id
name        text
sponsor     text
region      text             -- e.g. 'Cordoba'
```

### `tournaments`

```
id          int   PK auto
name        text
date        date
region      text
startgg     text             -- 'https://start.gg/<slug>'
format      text
attendees   int              -- nplayers (counted post-presence)
logo        text             -- 'Media/TournamentLogos/<name>'
```

### `rankings`

```
playerid    int      FK players.id
rankingid   text              -- 'arg26', 'cba', 'cba26', ...
rank        float             -- normalized 0..1 final score
elo         float
pp          float
wins        int
losses      int
characters  json              -- {"<character>": <count>, ...}
ntourneys   int
top         int               -- printed rank position (1, 2, 3, ...)
variation   int               -- last_top - new_top, set by update runs
PRIMARY KEY (playerid, rankingid)
```

### `attendees`

```
playerid     int   FK players.id
tournamentid int   FK tournaments.id
points       float            -- this tournament's PP contribution
elo          float            -- ELO immediately after this tournament
placement    int
rankingid    text
PRIMARY KEY (playerid, tournamentid, rankingid)
```

### `sets`

```
id            bigint  PK      -- start.gg set id
tournamentid  int     FK
p1id, p2id    int     FK players.id (or 0 for guest)
winnerid      int             -- globalid of winner
p1score       json[int|null]  -- per-game scores
p2score       json[int|null]
p1characters  json[str|null]
p2characters  json[str|null]
stages        json[str|null]
winnerpreelo  float           -- always 0 today (TODO)
loserpreelo   float           -- always 0
notablewins   bool            -- always false (TODO)
rankingid     text
round         text            -- 'WSF', 'LF', 'GF', ..., 'W. Pools', etc.
timestamp     datetime UTC
newwinnerelo  float           -- always 0 (TODO)
newloserelo   float           -- always 0
```

### `rankingdata`

```
id                 text  PK    -- 'arg26', etc.
tournamentcount    int          -- total tournaments processed for this ranking
```

`db.executeQuery` accepts `?` placeholders (the MariaDB Python driver style) and returns the
result of `SELECT` as a list of tuples.

---

## 13. Stray scripts and files

| File                  | Purpose                                                                                  | Status         |
|-----------------------|------------------------------------------------------------------------------------------|----------------|
| `temp.py`             | Convert `preelo-2025.txt` to a PHP `$elo = [...]` array for the front-end.                | One-off helper |
| `shrink_elo.sql`      | Year-end carry-over: copy previous year's `rankings` into next, with `0.3` shrink toward 1500. | Run manually   |
| `preelo-2025.txt`     | Flat backup of seeded 2025 ELOs (`<playerid> \| <elo>` per line).                         | Reference data |
| `form.csv`            | `id,alias,form_points`. Intended for a "form" signal in `normalize.py`. Currently unused (loader commented out, weight = 0). Gitignored. | Dead code     |
| `shrink.py`           | Connectivity-Index-based ELO shrink. The call in `app.py` is wrapped in a triple-quoted block. | Dormant       |
| `Tournaments/tournaments.csv` | Legacy combined tournament list, predating the per-year split.                       | Historical    |
| `Tournaments/tournaments2024.csv` | 2024 season (already processed).                                                   | Historical    |
| `Tournaments/tournaments2025.csv` | 2025 season.                                                                       | Historical    |

---

## 14. Known quirks / TODOs

These are documented as-is; some are intentional, some look like rough edges worth flagging.

- **`mapSets` writes `winnerpreelo / loserpreelo / newwinnerelo / newloserelo / notablewins` as 0
  / `false`.** The actual ELO calculation happens inside `updateElo`, which is called *after*
  `mapSets`. The commented-out blocks inside `mapSets` show the intended fix: process ELO during
  set ingestion so the per-set deltas are stored. Today, only the post-tournament ELO is recorded
  (in the `attendees` table).
- **Option 1 doesn't wipe `rankings`** (the line is commented out). The downstream `INSERT INTO
  rankings` would conflict if those rows already exist. In practice option 1 is paired with a
  manual `DELETE FROM rankings WHERE rankingid = 'arg26'` or run on a fresh season before any
  carry-over rows exist.
- **Region update doesn't wipe `sets`** for that ranking. Stale sets from a previous run can
  remain. The `REPLACE` on the set ID prevents duplicates, but truly removed tournaments would
  leave orphaned set rows.
- **Form points (`form.csv`, `formpointsweight`)** are present but disabled. The form CSV is
  gitignored but referenced — keep it around if you want to re-enable form, otherwise feel free
  to delete the dead code.
- **`shrink.py` is dormant.** If you want to apply CI-shrink to ELOs, re-enable the
  `shrinkElo()` call near the bottom of `app.py`.
- **CSV column 2 (`format`)** is informational. The algorithm doesn't currently switch behavior
  based on it (e.g. it doesn't weight Round-Robin tournaments differently from Singles).
  Round-Robin / Swiss / Ladder formats produce many sets per player which can over-inflate ELO.
- **Buenos Aires `Resurrection Bracket`** is the only phase explicitly excluded. If other regions
  introduce similar revival pools, they need to be added to the `phase.upper() == "RESURRECTION
  BRACKET"` skip in both `app.mapSets` and `elo.updateElo`.
- **Foreign-player ELO seeds** (Peco, Garu, Flame, Tapia, Benny Henny, LRBA→Start) are
  hard-coded by `globalid` in `app.mapPlayers`. Add new ones there if needed.
- **`argelo` is a one-shot snapshot**, loaded once at the start of a regional run from
  `rankings WHERE rankingid='arg26'`. It does not refresh as tournaments are processed inside
  the run, and a from-scratch regional replay uses the *current* arg26 ELOs to score sets that
  may have happened months ago. Run order matters: ideally update arg26 before re-running the
  regions, otherwise visitor strength is staler than it could be.
- **Region tally on player** uses a fixed dict of six regions in `Player.__init__`. If a CSV
  introduces a new region label, `Player.__init__` raises a `KeyError` on
  `region[tourneyRegion] += 1`.
