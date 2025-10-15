from collections import defaultdict
#
from player import Player
from db import executeQuery

C0sets = 4 # Amount of inter-region sets for CI = 1
C0opps = 4 # Amount of unique inter-region opponents for CI = 1
elobase = 1500

### Functions

def countIntersets(data):
    intersets = defaultdict(int)
    interopps = defaultdict(set)

    for setid, p1id, p2id, region1, region2 in data:
        if not region1 or not region2:
            continue # null regions
        elif region1 == region2:
            continue # same region

        intersets[p1id] += 1
        intersets[p2id] += 1
        interopps[p1id].add(p2id)
        interopps[p2id].add(p1id)

    return intersets, interopps

# Calculate Conectivity Index / how much a player competes outside it's region
def calculateCI(intersets, interopps, C0sets = C0sets, C0opps = C0opps):
    CI = {}
    # Assign CI to all players
    for globalid, player in Player.players.items():
        s = intersets.get(globalid, 0)
        o = len(interopps.get(globalid, set()))
        
        CIsets = min(1.0, s / float(C0sets)) if C0sets > 0 else 1.0
        CIopps = min(1.0, o / float(C0opps)) if C0opps > 0 else 1.0
        ci = max(CIsets, CIopps)

        player.ci = ci
        CI[globalid] = ci
    return CI

# Apply ELO Shrink to player
def applyShrink(elobase=elobase):
    out = {}
    for globalid, player in Player.players.items():
        R = float(player.elo)
        ci = float(getattr(player, "ci", 0.0))
        Rsh = elobase + ci * (R - elobase)
        player.elo = Rsh
        out[globalid] = Rsh
    return out

def shrinkElo(debug=True):
    sets = executeQuery("""
        SELECT s.id, s.p1id, s.p2id, p1.region, p2.region
            FROM sets AS s
            JOIN players AS p1 ON p1.id = s.p1id
            JOIN players AS p2 ON p2.id = s.p2id
    """) or []

    intersets, interopps = countIntersets(sets)
    CI = calculateCI(intersets, interopps)
    eloshrunk = applyShrink()

    # GPT
    if debug:
        total_players = len(Player.players)
        with_ev = sum(1 for p in Player.players.values() if getattr(p, "ci", 0.0) > 0)
    return CI, eloshrunk
