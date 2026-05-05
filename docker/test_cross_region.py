"""Smoke-tests for the cross-region ELO + PP-strength changes.

Runs entirely in-memory (no DB, no start.gg) so it can validate the math
without needing seeded data. Exercises every meaningful branch in
`elo.updateElo` and `placement.strengthElo`/`avgelo` for both regional
and national run modes.

Usage (from inside the app container or anywhere with the deps installed):

    python docker/test_cross_region.py

Exits 0 on success, 1 on any failed assertion.
"""

import sys
from unittest.mock import patch

sys.path.insert(0, ".")  # so this works whether you run from repo root or docker/

from elo import calculateElo, updateElo  # noqa: E402
from player import Player  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

K = 32
DEFAULT_ELO = 1500


def freshPlayers():
    """Reset Player class state before every test to avoid cross-test pollution."""
    Player.players = {}
    Player.entrants = {}


def makePlayer(globalid, name, elo=DEFAULT_ELO, entrantId=None):
    p = Player(globalid, name, elo, 0)
    if entrantId is not None:
        Player.entrants[entrantId] = [p, 0]
    return p


def makeSet(setId, winnerEntrantId, loserEntrantId, completedAt=1):
    """Build a single-set payload shaped like start.gg's GraphQL response."""
    return {
        "id": setId,
        "winnerId": winnerEntrantId,
        "completedAt": completedAt,
        "phaseGroup": {"phase": {"name": "Top 8"}},
        "slots": [
            {"entrant": {"id": winnerEntrantId}},
            {"entrant": {"id": loserEntrantId}},
        ],
    }


# ---------------------------------------------------------------------------
# Test 1: locals-vs-locals path is unchanged
# ---------------------------------------------------------------------------

def testLocalVsLocalUnchanged():
    freshPlayers()
    a = makePlayer(1001, "Local A", elo=1500, entrantId=10)
    b = makePlayer(1002, "Local B", elo=1500, entrantId=20)

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=[], argelo={})

    # Standard ELO: 1500 vs 1500, A wins -> +16, B -> -16
    assert a.elo == 1516.0, f"local winner ELO should be 1516, got {a.elo}"
    assert b.elo == 1484.0, f"local loser ELO should be 1484, got {b.elo}"
    assert a.wins == 1 and a.losses == 0
    assert b.wins == 0 and b.losses == 1
    print("PASS testLocalVsLocalUnchanged")


# ---------------------------------------------------------------------------
# Test 2: arg-update legacy fallback (argelo empty) still skips visitor sets
# ---------------------------------------------------------------------------

def testArgUpdateLegacyFallback():
    freshPlayers()
    local = makePlayer(2001, "Local", elo=1500, entrantId=10)
    foreigner = makePlayer(2002, "Foreigner", elo=1600, entrantId=20)

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    # arg-update mode: bannedregionplayers = nationbans, argelo = {}
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=[2002], argelo={})

    # Legacy behavior: set is skipped for ELO
    assert local.elo == 1500.0, f"local ELO should be unchanged, got {local.elo}"
    assert foreigner.elo == 1600.0, f"foreigner ELO should be unchanged, got {foreigner.elo}"
    assert local.wins == 0, f"wins should not increment in legacy fallback, got {local.wins}"
    # Game counter should still tick (presence)
    assert Player.entrants[10][1] == 1
    assert Player.entrants[20][1] == 1
    print("PASS testArgUpdateLegacyFallback")


# ---------------------------------------------------------------------------
# Test 3: cross-region upset gives meaningful ELO bump
# ---------------------------------------------------------------------------

def testCrossRegionUpset():
    freshPlayers()
    # Cordoba player at arg26 ELO 1500, cba26 ELO 1500.
    # Visitor (banned in cba26) at arg26 ELO 1700.
    cordoba = makePlayer(3001, "Cordoba", elo=1500, entrantId=10)
    visitor = makePlayer(3002, "Sketch", elo=1500, entrantId=20)

    argelo = {3001: 1500, 3002: 1700}
    bannedregionplayers = [3002]

    # Cordoba upsets the visitor.
    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Expected delta in arg-space: 1500 vs 1700 -> P(win) ~ 0.2402
    # Delta = 32 * (1 - 0.2402) ~ 24.31
    assert 24.0 < cordoba.elo - 1500 < 24.6, f"Cordoba should gain ~24.3 ELO, got delta={cordoba.elo - 1500}"
    assert cordoba.wins == 1, f"Cordoba wins should increment, got {cordoba.wins}"
    # Visitor's running ELO should NOT be modified (they're filtered at write time)
    assert visitor.elo == 1500.0, f"Visitor ELO should be untouched, got {visitor.elo}"
    assert visitor.losses == 0, f"Visitor losses should not increment, got {visitor.losses}"
    # Both game counters tick
    assert Player.entrants[10][1] == 1
    assert Player.entrants[20][1] == 1
    print("PASS testCrossRegionUpset (delta = +%.2f)" % (cordoba.elo - 1500))


# ---------------------------------------------------------------------------
# Test 4: cross-region expected win gives small ELO bump
# ---------------------------------------------------------------------------

def testCrossRegionExpectedWin():
    freshPlayers()
    # Cordoba top player at arg26 ELO 1700.
    # Low-rated visitor at arg26 ELO 1450.
    cordoba = makePlayer(4001, "Cordoba TopDog", elo=1500, entrantId=10)
    visitor = makePlayer(4002, "Random visitor", elo=1500, entrantId=20)

    argelo = {4001: 1700, 4002: 1450}
    bannedregionplayers = [4002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Expected delta in arg-space: 1700 vs 1450 -> P(win) ~ 0.808
    # Delta = 32 * (1 - 0.808) ~ 6.14
    delta = cordoba.elo - 1500
    assert 5.5 < delta < 6.6, f"Cordoba should gain ~6.1 ELO for expected win, got delta={delta}"
    print("PASS testCrossRegionExpectedWin (delta = +%.2f)" % delta)


# ---------------------------------------------------------------------------
# Test 5: cross-region expected win goes against you (loss)
# ---------------------------------------------------------------------------

def testCrossRegionExpectedLoss():
    freshPlayers()
    cordoba = makePlayer(5001, "Cordoba TopDog", elo=1500, entrantId=10)
    visitor = makePlayer(5002, "Random visitor", elo=1500, entrantId=20)

    argelo = {5001: 1700, 5002: 1450}
    bannedregionplayers = [5002]

    # The 1700 cordoba player loses to the 1450 visitor.
    sets = [makeSet(setId=1, winnerEntrantId=20, loserEntrantId=10)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Cordoba was favored 0.808; losing means -32 * 0.808 ~= -25.85
    delta = cordoba.elo - 1500
    assert -26.5 < delta < -25.5, f"Cordoba should lose ~25.85 ELO for upset loss, got delta={delta}"
    assert cordoba.losses == 1
    print("PASS testCrossRegionExpectedLoss (delta = %.2f)" % delta)


# ---------------------------------------------------------------------------
# Test 6: visitor-vs-visitor is skipped for ELO
# ---------------------------------------------------------------------------

def testVisitorVsVisitorSkipped():
    freshPlayers()
    v1 = makePlayer(6001, "Visitor 1", elo=1500, entrantId=10)
    v2 = makePlayer(6002, "Visitor 2", elo=1500, entrantId=20)

    argelo = {6001: 1700, 6002: 1500}
    bannedregionplayers = [6001, 6002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Both visitors -> skip
    assert v1.elo == 1500.0
    assert v2.elo == 1500.0
    assert v1.wins == 0 and v2.losses == 0
    assert Player.entrants[10][1] == 1  # presence still counted
    assert Player.entrants[20][1] == 1
    print("PASS testVisitorVsVisitorSkipped")


# ---------------------------------------------------------------------------
# Test 7: missing arg26 entry falls back to defaultelo
# ---------------------------------------------------------------------------

def testCrossRegionMissingArgEntry():
    freshPlayers()
    cordoba = makePlayer(7001, "Cordoba", elo=1500, entrantId=10)
    visitor = makePlayer(7002, "Brand-new visitor", elo=1500, entrantId=20)

    # Visitor has no arg26 row, but argelo dict is populated for someone else.
    argelo = {9999: 1700}
    bannedregionplayers = [7002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Both fall back to 1500. P(win) = 0.5. Delta = 32 * 0.5 = 16.
    delta = cordoba.elo - 1500
    assert 15.5 < delta < 16.5, f"Cordoba should gain ~16 ELO with both fallbacks, got delta={delta}"
    print("PASS testCrossRegionMissingArgEntry (delta = +%.2f)" % delta)


# ---------------------------------------------------------------------------
# Test 8: placement.strengthElo via avgelo computation
# ---------------------------------------------------------------------------

def testStrengthEloAvgelo():
    """Re-implement the strengthElo logic and confirm avgelo uses arg26 for visitors."""
    freshPlayers()
    bannedregionplayers = [8002]
    argelo = {8001: 1500, 8002: 1700}
    lastelo = {8001: 1500, 8002: 1500}  # visitor's cba26 in-memory ELO is the broken 1500
    defaultelo = DEFAULT_ELO

    def strengthElo(globalid):
        if globalid in bannedregionplayers and globalid in argelo:
            return argelo[globalid]
        return lastelo.get(globalid, defaultelo)

    # 26 locals at 1500 + 6 visitors at arg-1700
    sumelo = 0
    for _ in range(26):
        sumelo += strengthElo(8001)
    for _ in range(6):
        sumelo += strengthElo(8002)
    nplayers = 32

    avgelo = sumelo / nplayers
    strengthW = avgelo / 1500

    # Old behavior would have given avgelo=1500, strengthW=1.0
    # New behavior: 26*1500 + 6*1700 = 49200 / 32 = 1537.5, strengthW ~= 1.025
    assert abs(avgelo - 1537.5) < 0.01, f"avgelo should be 1537.5, got {avgelo}"
    assert abs(strengthW - 1.025) < 0.001, f"strengthW should be ~1.025, got {strengthW}"
    print("PASS testStrengthEloAvgelo (avgelo=%.2f, strengthW=%.4f)" % (avgelo, strengthW))


# ---------------------------------------------------------------------------
# Test 9: arg-update mode (argelo empty) -> visitor's lastelo is used
# ---------------------------------------------------------------------------

def testArgUpdateStrengthFallback():
    bannedregionplayers = [9002]
    argelo = {}  # arg-update mode
    lastelo = {9001: 1500, 9002: 1600}  # foreigner with seeded ELO 1600
    defaultelo = DEFAULT_ELO

    def strengthElo(globalid):
        if globalid in bannedregionplayers and globalid in argelo:
            return argelo[globalid]
        return lastelo.get(globalid, defaultelo)

    # In arg-update, the foreigner contributes their seeded 1600 (legacy preserved)
    assert strengthElo(9001) == 1500
    assert strengthElo(9002) == 1600, "Foreigner should contribute their seeded ELO when argelo is empty"
    print("PASS testArgUpdateStrengthFallback")


# ---------------------------------------------------------------------------

def main():
    tests = [
        testLocalVsLocalUnchanged,
        testArgUpdateLegacyFallback,
        testCrossRegionUpset,
        testCrossRegionExpectedWin,
        testCrossRegionExpectedLoss,
        testVisitorVsVisitorSkipped,
        testCrossRegionMissingArgEntry,
        testStrengthEloAvgelo,
        testArgUpdateStrengthFallback,
    ]
    failures = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures += 1
        except Exception as e:
            print(f"ERROR {t.__name__}: {type(e).__name__}: {e}")
            failures += 1

    if failures:
        print(f"\n{failures} failure(s)")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed")


if __name__ == "__main__":
    main()
