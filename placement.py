import math
#
from db import executeQuery
from player import Player
from importvars import importVars

### Functions for calculating placement

"""
Old function for calculating points (based of average elo of ALL ATTENDEES in a tourney):

def calculatePoints(placement, nplayers, avgelo, basesize=32, harshness=0.8):
    global placementBase
    base = placementBase.get(placement, 0)
    scale = min((nplayers / basesize) ** harshness, 1)
    points = base * scale * (avgelo / importVars(4))
    return points
"""

# Vars

placementBase = importVars(8)
harshness = importVars(6) # Adjusts the penalty for tournaments with attendees count below base size
basesize = importVars(7)

def validBaseFor(placement, nplayers, placementBase):
    if nplayers < 16:
        allowed = {1, 2, 3, 4}
    elif nplayers < 24:
        allowed = {1, 2, 3, 4, 5, 7}
    elif nplayers < 32:
        allowed = {1, 2, 3, 4, 5, 7, 9}
    else:  # 32+
        allowed = set(placementBase.keys())

    return placementBase.get(placement, 0) if placement in allowed else 0

def calculatePoints(placement, nplayers, topelos,
                    basesize=basesize, harshness=harshness):
    global placementBase

    base = validBaseFor(placement, nplayers, placementBase)
    if base == 0:
        return 0.0

    size_w = min((nplayers / basesize) ** harshness, 1.0)

    if not topelos:
        strength_w = 1.0
    else:
        k = min(8, len(topelos))
        mean_top = sum(sorted(topelos, reverse=True)[:k]) / k
        # Normalizar con clamp para evitar runaway
        strength_w = 1 + (mean_top - importVars(4)) / 600.0
        strength_w = max(0.90, min(strength_w, 1.15))

    return round(base * size_w * strength_w, 3)

def updatePlacement(placementdata, tournamentid, guests, lastelo, option, option2):
    # Initial count for number of present attendes and average elo
    nplayers = 0
    # List of present attendees to not reward abscent ones
    presentattendees = []
    for i in placementdata:
        entrantid = i["id"]
        try:
            if Player.entrants[entrantid][1] < 1:
                continue
        except:
            # User is guest / doesnt exist
            continue
        nplayers += 1
        presentattendees.append(entrantid)
    nplayers += len(guests) # To count for guests

    # Update N players in database for this tournament
    executeQuery("""update tournaments set attendees = ? where id = ?""", (nplayers, tournamentid))

    # ChatGPT new avgelo
    placements = {}
    for i in placementdata:
        if i.get("standing") is None:
            continue
        placements[i["id"]] = i["standing"]["placement"]

    # Lista ordenable: (placement asc, -elopre desc, entrantid)
    ranked = []
    for entrantid, plc in placements.items():
        try:
            player = Player.entrants[entrantid][0]
            elopre = lastelo.get(player.globalid, importVars(4))
        except:
            # Guest
            elopre = importVars(4)
        ranked.append((plc, -elopre, entrantid))

    ranked.sort()
    top8entrants = [eid for _, _, eid in ranked[:8]]

    topelos = []
    for eid in top8entrants:
        try:
            gid = Player.entrants[eid][0].globalid
            topelos.append(lastelo.get(gid, importVars(4)))
        except:
            topelos.append(importVars(4))

    # Update points per player
    for i in placementdata:
        # Check if DQ / user did not participate
        if i["standing"] == None:
            continue

        entrantid = i["id"]
        placement = i["standing"]["placement"]

        # Dont update if didnt participate
        try:
            if entrantid not in presentattendees:
                continue
            if Player.entrants[entrantid][1] < 1:
                continue
        except:
            # User is guest / doesnt exist
            continue

        # Update points and ntourneys
        points = calculatePoints(placement, nplayers, topelos)
        Player.entrants[entrantid][0].pp += points
        Player.entrants[entrantid][0].ntourneys += 1

        # Additionaly save the attendee ELO / PP variation in the database
        if option == "1":
            rankingid = "arg"
        elif option == "2":
            rankingid = option2.lower()
        else:
            rankingid = option.lower()
        executeQuery("""REPLACE INTO attendees (playerid, tournamentid, points, elo, placement, rankingid) VALUES (?, ?, ?, ?, ?, ?)""", (Player.entrants[entrantid][0].globalid, tournamentid, round(points, 3), Player.entrants[entrantid][0].elo, placement, rankingid))
