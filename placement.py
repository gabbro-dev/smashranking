import math
#
from db import executeQuery

### Functions for calculating placement

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
harshness = 0.8 # Adjusts the penalty for tournaments with attendees count below base size
basesize = 32

"""
GPT formula

def calculatePoints(placement, nplayers, avgelo, basesize=32, harshness=harshness):
    global placementBase
    base = placementBase.get(placement, 0)
    scale = min((nplayers / basesize) ** harshness, 1)
    points = base * scale * (avgelo / 1500)
    return points

OLD formula

def calculatePoints(placement, nplayers, avgelo):
    global placementBase
    points = placementBase.get(placement, 0) * math.log2(nplayers) * (avgelo / 1500)
    return points
"""

def calculatePoints(placement, nplayers, avgelo, basesize=basesize, harshness=harshness):
    global placementBase
    base = placementBase.get(placement, 0)
    scale = min((nplayers / basesize) ** harshness, 1)
    points = base * scale * (avgelo / 1500)
    return points

def updatePlacement(placementdata, entrants, players, tournamentid, guests, lastelo):
    # Initial count for number of present attendes and average elo
    nplayers = sumelo = 0
    # List of present attendees to not reward abscent ones
    presentattendees = []
    for i in placementdata:
        entrantid = i["id"]
        try:
            if entrants[entrantid][1] < 1:
                continue
        except:
            # User is guest / doesnt exist
            #print("❕ Non existent user not valid for nplayers in: updatePlacement()")
            continue
        #print(f"Player: {players[entrants[entrantid][0]][0]} | ELO: {players[entrants[entrantid][0]][1]}")
        nplayers += 1
        presentattendees.append(entrantid)
        sumelo += lastelo[entrants[entrantid][0]]
        #print(f"Elo for {players[entrants[entrantid][0]][0]}: {lastelo[entrants[entrantid][0]]}")
    nplayers += len(guests) # To count for guests

    # Update N players in database for this tournament
    executeQuery("""update tournaments set attendees = ? where id = ?""", (nplayers, tournamentid))
    avgelo = sumelo / nplayers
    print("Average elo for this tourney:", avgelo)
    print("Players in tourney:", nplayers)
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
            if entrants[entrantid][1] < 1:
                continue
        except:
            # User is guest / doesnt exist
            #print("❕ Skipped Placement calculations for non existent user in: updatePlacement()")
            continue

        # Update points and ntourneys
        points = calculatePoints(placement, nplayers, avgelo)
        players[entrants[entrantid][0]][2] += points
        players[entrants[entrantid][0]][4] += 1
        #print(f"{players[entrants[entrantid][0]][0]} | Points: {points} | Placement: {placement}")

        # Additionaly save the attendee ELO / PP variation in the database
        executeQuery("""REPLACE INTO attendees (playerid, tournamentid, points, elo, placement) VALUES (?, ?, ?, ?, ?)""", (entrants[entrantid][0], tournamentid, round(points, 3), players[entrants[entrantid][0]][1], placement))

    return players
