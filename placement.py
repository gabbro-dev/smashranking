import math
#
from db import executeQuery
from player import Player

### Functions for calculating placement

"""
Old function for calculating points (based of average elo of ALL ATTENDEES in a tourney):

def calculatePoints(placement, nplayers, avgelo, basesize=32, harshness=0.8):
    global placementBase
    base = placementBase.get(placement, 0)
    scale = min((nplayers / basesize) ** harshness, 1)
    points = base * scale * (avgelo / 1500)
    return points
"""

# Vars

placementBase = {
  1: 100,
  2: 70,
  3: 50,
  4: 35,
  5: 25,
  7: 15,
  9: 10,
  13: 6,
  17: 4,
  21: 3,
  25: 2,
  33: 1,
  65: 0.5
}
harshness = 4 # Adjusts the penalty for tournaments with attendees count below base size
basesize = 32

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
                    basesize=32, harshness=4):
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
        strength_w = 1 + (mean_top - 1500) / 600.0
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
            #print("❕ Non existent user not valid for nplayers in: updatePlacement()")
            continue
        #print(f"Player: {players[entrants[entrantid][0]][0]} | ELO: {players[entrants[entrantid][0]][1]}")
        nplayers += 1
        presentattendees.append(entrantid)
        #print(f"Elo for {players[entrants[entrantid][0]][0]}: {lastelo[entrants[entrantid][0]]}")
    nplayers += len(guests) # To count for guests

    # Update N players in database for this tournament
    executeQuery("""update tournaments set attendees = ? where id = ?""", (nplayers, tournamentid))
    print("Players in tourney:", nplayers)

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
            elopre = lastelo.get(player.globalid, 1500.0)
        except:
            # Guest
            elopre = 1500.0
        ranked.append((plc, -elopre, entrantid))

    ranked.sort()
    top8entrants = [eid for _, _, eid in ranked[:8]]

    topelos = []
    for eid in top8entrants:
        try:
            gid = Player.entrants[eid][0].globalid
            topelos.append(lastelo.get(gid, 1500.0))
            print(f"Top 8 elo para este torneo: {Player.entrants[eid][0].name} | {lastelo.get(gid, 1500.0)}")
        except:
            topelos.append(1500.0)

    # Update points per player
    for i in placementdata:
        # Check if DQ / user did not participate
        if i["standing"] == None:
            #print("❕ Skipped Placement calculations for non existent user in: updatePlacement()")
            continue

        entrantid = i["id"]
        placement = i["standing"]["placement"]

        # Dont update if didnt participate
        try:
            if entrantid not in presentattendees:
                #print("SKIPPED NON PRESENT ATTENDEE:", players[entrants[entrantid][0]][0])
                continue
            if Player.entrants[entrantid][1] < 1:
                continue
        except:
            # User is guest / doesnt exist
            #print("❕ Skipped Placement calculations for non existent user in: updatePlacement()")
            continue

        # Update points and ntourneys
        points = calculatePoints(placement, nplayers, topelos)
        Player.entrants[entrantid][0].pp += points
        Player.entrants[entrantid][0].ntourneys += 1

        #print(f"{players[entrants[entrantid][0]][0]} | Points: {points} | Placement: {placement}")

        # Additionaly save the attendee ELO / PP variation in the database
        if option == "1":
            rankingid = "arg"
        elif option == "2":
            rankingid = option2.lower()
        else:
            rankingid = option.lower()
        executeQuery("""REPLACE INTO attendees (playerid, tournamentid, points, elo, placement, rankingid) VALUES (?, ?, ?, ?, ?, ?)""", (Player.entrants[entrantid][0].globalid, tournamentid, round(points, 3), Player.entrants[entrantid][0].elo, placement, rankingid))
