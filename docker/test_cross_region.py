"""Smoke-tests for the cross-region ELO + PP-strength changes.

In-memory only (no DB, no start.gg). Run with:
    python docker/test_cross_region.py
"""

import sys

sys.path.insert(0, ".")  # works from repo root and from docker/

from elo import updateElo  # noqa: E402
from player import Player  # noqa: E402


# Fixtures

K = 32
DEFAULT_ELO = 1500


def freshPlayers():
    Player.players = {}
    Player.entrants = {}


def makePlayer(globalid, name, elo=DEFAULT_ELO, entrantId=None):
    p = Player(globalid, name, elo, 0)
    if entrantId is not None:
        Player.entrants[entrantId] = [p, 0]
    return p


def makeSet(setId, winnerEntrantId, loserEntrantId, completedAt=1):
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


# Test 1: locals-vs-locals path is unchanged

def testLocalVsLocalUnchanged():
    freshPlayers()
    a = makePlayer(1001, "Local A", elo=1500, entrantId=10)
    b = makePlayer(1002, "Local B", elo=1500, entrantId=20)

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=[], argelo={})

    # 1500 vs 1500, A wins: +16 / -16
    assert a.elo == 1516.0, f"local winner ELO should be 1516, got {a.elo}"
    assert b.elo == 1484.0, f"local loser ELO should be 1484, got {b.elo}"
    assert a.wins == 1 and a.losses == 0
    assert b.wins == 0 and b.losses == 1
    print("PASS testLocalVsLocalUnchanged")


# Test 2: arg-update legacy fallback (argelo empty) still skips visitor sets

def testArgUpdateLegacyFallback():
    freshPlayers()
    local = makePlayer(2001, "Local", elo=1500, entrantId=10)
    foreigner = makePlayer(2002, "Foreigner", elo=1600, entrantId=20)

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    # arg-update mode: bannedregionplayers=nationbans, argelo={}
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=[2002], argelo={})

    assert local.elo == 1500.0, f"local ELO should be unchanged, got {local.elo}"
    assert foreigner.elo == 1600.0, f"foreigner ELO should be unchanged, got {foreigner.elo}"
    assert local.wins == 0, f"wins should not increment in legacy fallback, got {local.wins}"
    # Presence still ticks
    assert Player.entrants[10][1] == 1
    assert Player.entrants[20][1] == 1
    print("PASS testArgUpdateLegacyFallback")


# Test 3: cross-region upset gives meaningful ELO bump

def testCrossRegionUpset():
    freshPlayers()
    # Cordoba arg=1500 vs visitor arg=1700; Cordoba upsets.
    cordoba = makePlayer(3001, "Cordoba", elo=1500, entrantId=10)
    visitor = makePlayer(3002, "Sketch", elo=1500, entrantId=20)

    argelo = {3001: 1500, 3002: 1700}
    bannedregionplayers = [3002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # 1500 vs 1700 -> P(win) ~ 0.2402, delta = 32 * 0.7598 ~ 24.31
    assert 24.0 < cordoba.elo - 1500 < 24.6, f"Cordoba should gain ~24.3 ELO, got delta={cordoba.elo - 1500}"
    assert cordoba.wins == 1, f"Cordoba wins should increment, got {cordoba.wins}"
    # Visitor's cba26 ELO must not be touched
    assert visitor.elo == 1500.0, f"Visitor ELO should be untouched, got {visitor.elo}"
    assert visitor.losses == 0, f"Visitor losses should not increment, got {visitor.losses}"
    assert Player.entrants[10][1] == 1
    assert Player.entrants[20][1] == 1
    print("PASS testCrossRegionUpset (delta = +%.2f)" % (cordoba.elo - 1500))


# Test 4: cross-region expected win gives small ELO bump

def testCrossRegionExpectedWin():
    freshPlayers()
    # Cordoba arg=1700 vs visitor arg=1450; Cordoba wins.
    cordoba = makePlayer(4001, "Cordoba TopDog", elo=1500, entrantId=10)
    visitor = makePlayer(4002, "Random visitor", elo=1500, entrantId=20)

    argelo = {4001: 1700, 4002: 1450}
    bannedregionplayers = [4002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # 1700 vs 1450 -> P(win) ~ 0.808, delta = 32 * 0.192 ~ 6.14
    delta = cordoba.elo - 1500
    assert 5.5 < delta < 6.6, f"Cordoba should gain ~6.1 ELO for expected win, got delta={delta}"
    print("PASS testCrossRegionExpectedWin (delta = +%.2f)" % delta)


# Test 5: cross-region expected win goes against you (loss)

def testCrossRegionExpectedLoss():
    freshPlayers()
    cordoba = makePlayer(5001, "Cordoba TopDog", elo=1500, entrantId=10)
    visitor = makePlayer(5002, "Random visitor", elo=1500, entrantId=20)

    argelo = {5001: 1700, 5002: 1450}
    bannedregionplayers = [5002]

    # 1700 cordoba loses to 1450 visitor -> -32 * 0.808 ~= -25.85
    sets = [makeSet(setId=1, winnerEntrantId=20, loserEntrantId=10)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    delta = cordoba.elo - 1500
    assert -26.5 < delta < -25.5, f"Cordoba should lose ~25.85 ELO for upset loss, got delta={delta}"
    assert cordoba.losses == 1
    print("PASS testCrossRegionExpectedLoss (delta = %.2f)" % delta)


# Test 6: visitor-vs-visitor is skipped for ELO

def testVisitorVsVisitorSkipped():
    freshPlayers()
    v1 = makePlayer(6001, "Visitor 1", elo=1500, entrantId=10)
    v2 = makePlayer(6002, "Visitor 2", elo=1500, entrantId=20)

    argelo = {6001: 1700, 6002: 1500}
    bannedregionplayers = [6001, 6002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    assert v1.elo == 1500.0
    assert v2.elo == 1500.0
    assert v1.wins == 0 and v2.losses == 0
    # Presence still counted
    assert Player.entrants[10][1] == 1
    assert Player.entrants[20][1] == 1
    print("PASS testVisitorVsVisitorSkipped")


# Test 7: missing arg26 entry falls back to defaultelo

def testCrossRegionMissingArgEntry():
    freshPlayers()
    cordoba = makePlayer(7001, "Cordoba", elo=1500, entrantId=10)
    visitor = makePlayer(7002, "Brand-new visitor", elo=1500, entrantId=20)

    # Visitor has no arg26 row.
    argelo = {9999: 1700}
    bannedregionplayers = [7002]

    sets = [makeSet(setId=1, winnerEntrantId=10, loserEntrantId=20)]
    updateElo(sets, k=K, dqlist=[], bannedregionplayers=bannedregionplayers, argelo=argelo)

    # Both fall back to 1500 -> delta = 16
    delta = cordoba.elo - 1500
    assert 15.5 < delta < 16.5, f"Cordoba should gain ~16 ELO with both fallbacks, got delta={delta}"
    print("PASS testCrossRegionMissingArgEntry (delta = +%.2f)" % delta)


# Test 8: placement.strengthElo via avgelo computation

def testStrengthEloAvgelo():
    """Re-implement strengthElo and confirm avgelo uses arg26 for visitors."""
    freshPlayers()
    bannedregionplayers = [8002]
    argelo = {8001: 1500, 8002: 1700}
    # Visitor's cba26 in-memory ELO is the broken 1500
    lastelo = {8001: 1500, 8002: 1500}
    defaultelo = DEFAULT_ELO

    def strengthElo(globalid):
        if globalid in bannedregionplayers and globalid in argelo:
            return argelo[globalid]
        return lastelo.get(globalid, defaultelo)

    # 26 locals @ 1500 + 6 visitors @ arg-1700
    sumelo = 0
    for _ in range(26):
        sumelo += strengthElo(8001)
    for _ in range(6):
        sumelo += strengthElo(8002)
    nplayers = 32

    avgelo = sumelo / nplayers
    strengthW = avgelo / 1500

    # Old: avgelo=1500, strengthW=1.0. New: 49200/32 = 1537.5, ~1.025.
    assert abs(avgelo - 1537.5) < 0.01, f"avgelo should be 1537.5, got {avgelo}"
    assert abs(strengthW - 1.025) < 0.001, f"strengthW should be ~1.025, got {strengthW}"
    print("PASS testStrengthEloAvgelo (avgelo=%.2f, strengthW=%.4f)" % (avgelo, strengthW))


# Test 9: arg-update mode (argelo empty) -> visitor's lastelo is used

def testArgUpdateStrengthFallback():
    bannedregionplayers = [9002]
    argelo = {}
    # Foreigner with seeded ELO 1600
    lastelo = {9001: 1500, 9002: 1600}
    defaultelo = DEFAULT_ELO

    def strengthElo(globalid):
        if globalid in bannedregionplayers and globalid in argelo:
            return argelo[globalid]
        return lastelo.get(globalid, defaultelo)

    assert strengthElo(9001) == 1500
    assert strengthElo(9002) == 1600, "Foreigner should contribute seeded ELO when argelo is empty"
    print("PASS testArgUpdateStrengthFallback")

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
