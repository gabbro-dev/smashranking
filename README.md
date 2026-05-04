# Smash Ranking

Ranking system for Smash Bros. Ultimate in Argentina (and per-region rankings, e.g. Cordoba).
The script pulls tournaments from the [start.gg](https://start.gg) API, computes ELO + Placement
Points per player, normalizes everything into a single rank score, and stores it in a database.

For the deeper / formula-by-formula breakdown, see [`ALGORITHM.md`](./ALGORITHM.md).

---

## Concepts

A few terms are used over and over in this document. Here's what they mean.

- **Set** — a single best-of-N match between two players in a tournament (e.g. a Bo3 in pools or a
  Bo5 in top 8). One set has one winner and one loser. ELO updates per set, not per game.
- **Game** — a single match within a set. The algorithm only uses games to count which characters
  each player picked; only the set's outcome moves ELO.
- **DQ (disqualification)** — a set that didn't really happen because a player no-showed, was
  removed, etc. DQs are listed by set ID in the CSV and are skipped entirely (no ELO change, no
  PP).
- **Bracket / Phase** — start.gg's structure for a tournament: pools, top 8, double-elimination,
  round robin, etc. The algorithm only special-cases one phase ("Resurrection Bracket", a Buenos
  Aires-specific revival pool that gets ignored).
- **Entrant** — a tournament-specific ID that start.gg assigns to a registered player. Two
  different entrants in two different tournaments can be the same person.
- **Player (`globalid`)** — the persistent start.gg user account behind one or more entrants.
  Rankings are keyed by `globalid`.
- **Guest** — an entrant whose `participants[0].user.id` is `null` on start.gg, meaning they
  registered without a linked account. Guests get a temporary in-memory ELO that doesn't survive
  past the tournament; they don't earn Placement Points.
- **ELO** — a skill rating originally invented for chess. Every player has a single number (we
  start at 1500). When two players meet, ELO predicts who's more likely to win based on the gap
  between their ratings. After the set, the winner takes points from the loser; the bigger the
  upset (the lower-rated player winning), the more points change hands. Over many sets, ELO
  converges to a stable estimate of each player's relative skill.
- **K-factor (`K`)** — the maximum ELO swing per set. With `K = 32`, a wildly unexpected win can
  move ELO by up to 32 points; an expected win moves it much less.
- **Placement** — the position a player finished in a tournament (1st, 2nd, 5th, 9th, ...). For
  Smash brackets these are usually reported in standard buckets: 1, 2, 3, 4, 5, 7, 9, 13, 17, 25,
  33, 65...
- **Placement Points (PP)** — points awarded for finishing well in a tournament. Unlike ELO, PP
  is **cumulative**: it sums up across the season instead of moving up and down. ELO measures
  *skill* (relative to opponents), PP measures *results* (relative to the field).
- **Pre-tournament ELO** — a player's ELO captured **before** a tournament's sets are processed.
  Used to estimate the strength of the field for that tournament without circular logic (the
  tournament's own results don't influence the strength weight it gets).
- **Field strength** — how strong, on average, the players in a tournament are. A tournament
  full of high-ELO players is "stronger". The Placement Points formulas multiply by a strength
  factor so that doing well in a strong field is worth more than doing well in a weak one.
- **Bracket size (`nplayers`)** — the number of *present* attendees (entrants who actually played
  at least 1 set). Registered no-shows don't count.
- **Normalization (min-max)** — rescaling ELO and PP into the `[0, 1]` range so they can be
  combined. The lowest ELO in the run becomes `0`, the highest becomes `1`, everyone else lands
  somewhere in between proportional to their distance from min and max. Same for PP.
- **rankingid** — a string that namespaces a ranking in the database, like `arg26` (Argentina
  2026) or `cba26` (Cordoba 2026). All tables that hold ranking-specific data carry this column.
- **Connectivity Index (CI)** — a 0–1 score for how much a player competed across regions vs.
  staying inside their own. Used by the dormant `shrink.py` to deflate the ELO of regionally
  isolated players. Not currently applied.

---

## What it does

For every tournament listed in a CSV file, the algorithm:

1. Fetches all attendees from start.gg and registers them as players.
2. Fetches every set, sorts them by completion time, and updates each player's **ELO** as games happen.
3. Fetches placements and gives **Placement Points (PP)** based on how the player finished, the size
   of the bracket, and the strength of the field.
4. After all tournaments are processed, **normalizes** ELO and PP across all players and combines
   them into a final rank score.

The result is written to MariaDB tables (`rankings`, `attendees`, `sets`, `tournaments`, `players`).

## Running it

```bash
pip install -r requirements.txt
# place a .env file with: token=<your_startgg_token>
python app.py
```

The script asks an option:

| Option              | What it does                                                                                              |
|---------------------|-----------------------------------------------------------------------------------------------------------|
| `1`                 | National (Argentina) ranking from scratch. Wipes `sets`/`attendees` for `arg26`, reads `Tournaments/tournaments2026.csv`. |
| `2` then `1`        | **Update** the current national ranking. Loads existing ELO/PP from DB and processes `Tournaments/Update/arg26.csv`. |
| `2` then `<region>` | **Update** an existing regional ranking. Reads `Tournaments/Update/<region>.csv`.                          |
| `<region>`          | Build a regional ranking from scratch (e.g. `cba26`). Reads `Tournaments/Regions/<region>.csv`.            |

Tunable constants live in [`vars.txt`](./vars.txt) — no need to edit Python to change weights.

---

## How a player's score is computed

Every player ends up with a single number, `rank ∈ [0, 1]`, that we sort the ranking by. It's
built in three stages: ELO, Placement Points, and a final combination step.

### Step 1 — ELO (skill rating)

ELO is a moving estimate of a player's skill. Starting value is **1500**. After every (non-DQ)
set the algorithm runs two updates: one for the winner, one for the loser.

```
expected = 1 / (1 + 10^((opponent_elo - player_elo) / 400))
new_elo  = player_elo + K * (score - expected)     # score = 1 if won, 0 if lost
```

In other words:

- **`expected`** is the predicted probability that this player wins the set, given the gap
  between their ELO and their opponent's. If both players are tied at 1500, `expected = 0.5`.
  If the player is 200 ELO higher, `expected ≈ 0.76`. If they're 400 ELO lower, `expected ≈ 0.09`.
- **`new_elo`** moves the player's ELO toward what actually happened. If the player won
  (`score = 1`) and the model expected them to (`expected ≈ 1`), the gain is tiny — there was
  nothing to learn. If the player won when they were predicted to lose (`expected ≈ 0`), the gain
  is close to the full `K` — that's a big upset and ELO needs to catch up.
- **`K = 32`** caps how far ELO can move on any single set. Higher K means ELO reacts faster but
  is more volatile; lower K means it's slower but more stable.

Sets are processed **chronologically by completion time**, so a player's ELO going into a top-8
match already reflects everything they did in pools.

### Step 2 — Placement Points (results across the season)

Placement Points add up across the whole season. The base table awards points by finish:

| Place | Pts | Place | Pts |
|------:|----:|------:|----:|
|   1st | 100 |  9–12 |  10 |
|   2nd |  70 | 13–16 |   6 |
|   3rd |  50 | 17–20 |   4 |
|   4th |  35 | 21–24 |   3 |
| 5–6th |  25 | 25–32 |   2 |
| 7–8th |  15 | 33–64 |   1 |
|       |     |   65+ | 0.5 |

Those base values are then multiplied by two adjustment factors: a **size weight** and a
**strength weight**. The exact formulas differ between national and regional rankings — see
[How much is a tournament "worth"?](#how-much-is-a-tournament-worth) below.

### Step 3 — Combining ELO and PP into the final rank

ELO and PP measure different things and live on different scales (ELO is roughly 1300–1700;
PP can reach hundreds across a season). Before combining them, both are rescaled to `[0, 1]`
using their min and max in the current run:

```
normalized_ELO = (player_elo - lowest_elo) / (highest_elo - lowest_elo)
normalized_PP  = (player_pp  - lowest_pp)  / (highest_pp  - lowest_pp)
```

Then the final rank is a weighted average:

```
rank  = (eloweight * normalized_ELO) + (placementweight * normalized_PP)
rank *= low_data_penalty(ntourneys)
```

In other words:

- We turn ELO and PP into the **same 0-to-1 scale** so they can be added together fairly. The
  player with the highest ELO of the season gets `1.0` for the ELO part; the lowest gets `0.0`;
  everyone else is proportionally placed in between. Same for PP.
- We then **mix the two**: 60% comes from where you land on the ELO scale, 40% from where you
  land on the PP scale (`eloweight = 0.6`, `placementweight = 0.4`).
- Finally we **down-weight players who barely competed** so a single lucky tournament doesn't
  let them dominate the ranking.

There's also an unused 3rd term, `formpointsweight`, currently set to `0`. It was meant to mix in
a manual "form" signal from `form.csv`; today it does nothing.

### Low-data penalty

The final multiplier punishes players who haven't shown up enough to have reliable data:

| `ntourneys` | multiplier |
|------------:|-----------:|
| 0           | `× 0` (effectively excluded) |
| 1           | `× 0.3` |
| 2           | `× 0.8` |
| 3 or more   | `× 1.0` |

So you need ≥ 3 tournaments in the season to get your "true" score.

---

## What makes a tournament "qualified"

A tournament gets read by the algorithm as long as it's listed in the right CSV. Inside that
tournament the **sets** and **placements** that count are filtered:

- **DQ sets** (set IDs in column 4 of the CSV, pipe-separated) are skipped — no ELO change.
- **Sets with `winnerId == null`** are skipped.
- **`Resurrection Bracket`** phase sets (Buenos Aires specific) are skipped entirely.
- A player must have **played at least 1 set** to count as a "present attendee". Absent
  registrants get no PP and don't count toward `nplayers`.
- Guests (entrants without a linked start.gg user account) are tracked with a temporary local ELO
  but never persisted, and they don't get PP. They do count toward `nplayers` for size scaling.
- For regional rankings, sets where **either side is region-banned** are skipped for ELO updates
  (still counted as "presence").
- For the **national** ranking, only the placements that the bracket size justifies award PP
  (see [Tournament "worth"](#how-much-is-a-tournament-worth)). Smaller brackets cut off lower
  placements entirely.

## How much is a tournament "worth"?

A player's points from a tournament are:

```
points = base_points_by_placement × size_weight × strength_weight
```

- **`base_points_by_placement`** is the table from [Step 2](#step-2--placement-points-results-across-the-season).
- **`size_weight`** scales the tournament down if it had few players. A 32-person bracket is the
  reference (`size_weight = 1`); smaller brackets get a fractional weight.
- **`strength_weight`** scales the tournament up or down based on how strong the field was.
  Beating a stacked top 8 is worth more than beating a soft one.

The exact size and strength formulas differ by ranking type.

### National (`arg26`) — `calculatePointsArg`

```
size_w     = min((nplayers / 32) ^ 4, 1.0)
mean_top   = average pre-tournament ELO of the top-8 finishers
strength_w = clamp(1 + (mean_top - 1500) / 600, 0.90, 1.15)
points     = round(base * size_w * strength_w, 3)
```

What each line is doing:

- **`size_w`** says: divide the bracket size by 32 (our reference), raise that ratio to the
  4th power, and cap at 1. The `^4` makes the penalty *very* aggressive — half-size brackets
  (16 players) only retain `(0.5)^4 = 0.0625` of the points, three-quarter-size brackets
  (24 players) retain `(0.75)^4 ≈ 0.316`. From 32 players onward, no penalty.
- **`mean_top`** is the mean ELO of the top-8 finishers, measured **before** this tournament
  ran. We use the top 8 because they define the ceiling of the bracket — the strength of the
  upper half is what really matters for whether 1st place was hard-earned.
- **`strength_w`** then turns that average into a multiplier centered on 1.0. The line
  `1 + (mean_top - 1500) / 600` reads as: "for every 600 ELO above 1500, add 1.0; for every 600
  below, subtract 1.0". Then we **clamp** the result to `[0.90, 1.15]`, so even a top 8
  averaging 1700 (a stacked national) only gives a +15% bonus, and a top 8 averaging 1300 only
  cuts -10%. The clamp prevents a single very-strong or very-weak weekend from dwarfing the
  whole season.
- **Eligible placements** also depend on bracket size:
  - `< 16` attendees → only places **1–4** get points.
  - `< 24` → only **1, 2, 3, 4, 5–6, 7–8**.
  - `< 32` → only **1, 2, 3, 4, 5–6, 7–8, 9–12**.
  - `≥ 32` → the full table above.

  This is a hard cutoff: in a 14-player bracket, 5th place gets **0** points, regardless of how
  the math would otherwise work out.

### Regional (e.g. `cba26`) — `calculatePointsRegion`

```
size_w     = min((nplayers / 32) ^ 0.8, 1.0)
avg_elo    = average pre-tournament ELO of all present attendees (guests counted at 1500)
strength_w = avg_elo / 1500
points     = base * size_w * strength_w
```

What each line is doing:

- **`size_w`** is the same shape as the national one but with exponent `0.8` instead of `4`.
  That makes it much **gentler** for small brackets: a 16-person tournament keeps `(0.5)^0.8
  ≈ 0.574` of its weight, a 24-person bracket keeps `≈ 0.789`. Regional scenes have smaller
  events, so this is by design.
- **`avg_elo`** is the average pre-tournament ELO of **everyone present**, not just the top 8.
  Guests (no start.gg account) are counted at the default ELO of 1500 so they don't pull the
  average around.
- **`strength_w = avg_elo / 1500`** turns that average into a multiplier centered on 1.0:
  every point of average ELO above 1500 increases the weight, below 1500 decreases it. There's
  **no clamp**, so a particularly strong (or weak) regional can move the multiplier more than
  the national formula would allow.
- **All placements are eligible** regardless of bracket size — no cutoff like the national side
  has.

---

## National vs Cordoba (regional) ranking — differences

|                                | National (`arg26`)                                          | Regional (`cba26`)                                          |
|--------------------------------|-------------------------------------------------------------|-------------------------------------------------------------|
| Tournaments source (fresh)     | `Tournaments/tournaments2026.csv`                           | `Tournaments/Regions/cba26.csv`                             |
| Tournaments source (update)    | `Tournaments/Update/arg26.csv`                              | `Tournaments/Update/cba26.csv`                              |
| Banlist                        | `nationbans` in `vars.txt` (foreign players)                | `regionbans["cba26"]` in `vars.txt` (out-of-region players) |
| What the banlist does          | Pre-seeds known foreigners' ELO; their sets **still affect** Argentinian ELO; they're **excluded from the final printed ranking** | Sets where either side is region-banned are **skipped entirely** for ELO; never appear in ranking |
| Foreign-player pre-ELO seeds   | Peco/Garu = 1600, Flame/Tapia = 1560, Benny Henny/LRBA = 1540, others = 1500 | None                                                        |
| PP formula                     | `calculatePointsArg` (top-8 ELO, harshness 4)               | `calculatePointsRegion` (avg ELO, harshness 0.8)            |
| Placement eligibility gating   | Yes (small brackets cut off low placements)                 | No (full table always)                                      |
| `shadowbans`                   | Yes — hidden from final printed ranking                     | Not applied                                                 |
| Region tracking                | Counts each player's tournaments per region to label their main region | Not used                                                  |
| Wipes on fresh run             | `attendees` and `sets` rows for `rankingid='arg26'`         | `attendees` and `rankings` rows for `rankingid=<region>`    |

Note: a regional fresh run does **not** wipe `sets` for that ranking id — that's by design (sets
are shared across rankings via the `rankingid` column on the `sets` table; you typically don't
re-run a region from scratch unless you want to recreate just the ranking row).

---

## How things are handled between years

The ranking ID is **year-suffixed** (`arg`, `arg26`, `cba`, `cba26`, …) so each season is its own
isolated dataset. When a new year starts:

1. The previous year's final ELOs are **carried over with regression toward the mean**.
   Concretely, `shrink_elo.sql` copies rows from `rankingid='arg'` into `rankingid='arg26'` with:

   ```sql
   new_elo = ROUND(1500 + (old_elo - 1500) * 0.3)
   ```

   In other words: keep the player's *deviation* from 1500, but only **30%** of it. A 1700
   becomes `1500 + 200 * 0.3 = 1560`. A 1400 becomes `1500 + (-100) * 0.3 = 1470`. The closer
   you were to average, the less you change; the further you were, the more you regress. The
   intent is to start everyone closer to even on day one of the new season while still
   acknowledging who was good last year. PP, wins, losses, characters and placement are reset.

2. Going forward, **option `2`** (update) is used week-by-week: it loads the seeded ELO from the
   DB and processes the next batch of tournaments listed in `Tournaments/Update/<rankingid>.csv`.

3. The legacy snapshot of last year's seeded ELOs is also kept as a flat file in `preelo-2025.txt`
   (one `playerid | elo` per line). It's purely a backup / reference.

4. `shrink.py` implements an alternative, **per-player** ELO shrink based on a "Connectivity Index"
   (how much each player competed across regions). Currently **not called** from `app.py` (the call
   is commented out). It could be used at year-end to deflate ELO of regionally-isolated players
   before the SQL carry-over.

5. Foreign-player seeds (1600/1560/1540) are only applied during a from-scratch run for **brand new
   players** that the DB hasn't seen yet.

---

## Penalties — quick reference

| Where applied              | Penalty                                                                                       |
|----------------------------|-----------------------------------------------------------------------------------------------|
| Small bracket (national)   | `size_w = min((n/32)^4, 1)` — very harsh                                                      |
| Small bracket (region)     | `size_w = min((n/32)^0.8, 1)` — soft                                                          |
| Small bracket (national)   | Lower placements **excluded** entirely (placements 5+ for <16, 9+ for <24, 13+ for <32)       |
| Weak field (national)      | `strength_w` clamped down to 0.90 if top-8 mean ELO is well below 1500                        |
| Strong field (national)    | `strength_w` clamped up to 1.15 if top-8 mean ELO is well above 1500                          |
| Field strength (region)    | `strength_w = avg_elo / 1500` (no clamp)                                                      |
| Few tournaments played     | `× 0` if 0 played, `× 0.3` if 1, `× 0.8` if 2, `× 1.0` from 3 onwards                          |
| DQ                         | Set ignored — no ELO update                                                                   |
| Buenos Aires resurrection  | Whole phase ignored                                                                           |
| Region-banned player       | Sets involving them are skipped for ELO                                                       |
| Yearly carry-over          | ELO compressed: `new_elo = 1500 + (old_elo - 1500) * 0.3`                                     |

---

## Repository layout

```
app.py                  Main orchestrator. Loads tournaments, calls the API, processes everything,
                        normalizes scores, writes to DB.
elo.py                  ELO update over a sorted list of sets (handles guests, region bans, DQs).
placement.py            Placement Points logic. Two formulas: calculatePointsArg vs calculatePointsRegion.
normalize.py            Min-max normalization of ELO and PP, applies eloweight/placementweight and
                        the low-data multiplier. Splits "Sponsor | Tag" into separate fields.
player.py               Player class. Holds ELO, PP, characters used, regions attended, CI, etc.
shrink.py               (Currently disabled.) Connectivity-Index ELO shrink: contracts the ELO of
                        players who don't play outside their own region.
importvars.py           Tiny loader for vars.txt.
vars.txt                All tunable knobs: K, default ELO, harshness, basesize, weights, banlists,
                        regionbans, low-data multipliers.
requirements.txt        mariadb, requests, python-dotenv.
db.py                   Not committed. Provides `executeQuery` against MariaDB.
                        See ALGORITHM.md for the expected schema.
.env                    Not committed. Holds `token=<startgg api token>`.
Tournaments/
  tournaments2024.csv         Historical: 2024 national tournaments
  tournaments2025.csv         Historical: 2025 national tournaments
  tournaments2026.csv         Current: 2026 national tournaments (used by option 1)
  tournaments.csv             Legacy combined list
  Regions/<region>.csv        Tournaments for a from-scratch regional run
  Update/<rankingid>.csv      New tournaments to append in an "update" run
```

### Stray scripts and files

- **`temp.py`** — One-off helper. Reads `preelo-2025.txt` (`playerid | elo` per line) and prints a
  PHP `$elo` array. Useful when porting the carry-over ELOs to the front-end (which is in PHP).
- **`shrink_elo.sql`** — Year-end carry-over. Copies the previous year's `rankings` rows into the
  new `rankingid` with the `1500 + (elo - 1500) * 0.3` shrink. Run this once when starting a new
  season, before option `2 → 1` updates start adding new tournaments.
- **`preelo-2025.txt`** — Snapshot of every player's ELO at the start of 2025 (after carry-over).
  Read by `temp.py`. Kept around as a backup.
- **`form.csv`** — Pipe-separated `id, alias, form_points` list, intended for a future "form"
  signal. Currently unused: `formpointsweight = 0` and the loader is commented out in `normalize.py`.
  Listed in `.gitignore` so it's local-only.
- **`shrink.py`** — Connectivity-Index ELO shrink. Disabled in `app.py` (call is wrapped in a
  triple-quoted block). Documented in detail in `ALGORITHM.md`.
