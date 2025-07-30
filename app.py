import requests, os, csv, time, json
from datetime import datetime
from dotenv import load_dotenv
#
from elo import updateElo
from placement import updatePlacement
from normalize import normalize
from db import executeQuery

### Vars

entrants = {} # entrantid : [globalid, elo] - Per tourney
players = {} # globalid: [name, elo, top, survey, ntourneys, [wins, loss], {character: n usages}] - Global
bannedplayers = [341901, 1227278, 135383, 635540, 1451270, 298485, 433945, 2709007, 2522784, 437848, 780143, 2501934, 510667, 1683659] # Not Argentinians
bannedregionplayers = [] # For region rankings
characters = {
    1271: "Bayonetta",
    1272: "Bowser Jr.",
    1273: "Bowser",
    1274: "Captain Falcon",
    1275: "Cloud",
    1276: "Corrin",
    1277: "Daisy",
    1278: "Dark Pit",
    1279: "Diddy Kong",
    1280: "Donkey Kong",
    1282: "Dr. Mario",
    1283: "Duck Hunt",
    1285: "Falco",
    1286: "Fox",
    1287: "Ganondorf",
    1289: "Greninja",
    1290: "Ice Climbers",
    1291: "Ike",
    1292: "Inkling",
    1293: "Jigglypuff",
    1294: "King Dedede",
    1295: "Kirby",
    1296: "Link",
    1297: "Little Mac",
    1298: "Lucario",
    1299: "Lucas",
    1300: "Lucina",
    1301: "Luigi",
    1302: "Mario",
    1304: "Marth",
    1305: "Mega Man",
    1307: "Meta Knight",
    1310: "Mewtwo",
    1311: "Mii Brawler",
    1313: "Ness",
    1314: "Olimar",
    1315: "Pac-Man",
    1316: "Palutena",
    1317: "Peach",
    1318: "Pichu",
    1319: "Pikachu",
    1320: "Pit",
    1321: "Pokemon Trainer",
    1322: "Ridley",
    1323: "R.O.B.",
    1324: "Robin",
    1325: "Rosalina",
    1326: "Roy",
    1327: "Ryu",
    1328: "Samus",
    1329: "Sheik",
    1330: "Shulk",
    1331: "Snake",
    1332: "Sonic",
    1333: "Toon Link",
    1334: "Villager",
    1335: "Wario",
    1336: "Wii Fit Trainer",
    1337: "Wolf",
    1338: "Yoshi",
    1339: "Young Link",
    1340: "Zelda",
    1341: "Zero Suit Samus",
    1405: "Mr. Game & Watch",
    1406: "Incineroar",
    1407: "King K. Rool",
    1408: "Dark Samus",
    1409: "Chrom",
    1410: "Ken",
    1411: "Simon Belmont",
    1412: "Richter",
    1413: "Isabelle",
    1414: "Mii Swordfighter",
    1415: "Mii Gunner",
    1441: "Piranha Plant",
    1453: "Joker",
    1526: "Hero",
    1530: "Banjo-Kazooie",
    1532: "Terry",
    1539: "Byleth",
    1746: "Random Character",
    1747: "Min Min",
    1766: "Steve",
    1777: "Sephiroth",
    1795: "Pyra & Mythra",
    1846: "Kazuya",
    1897: "Sora"
}

bannedregionplayersdict = {
    "cordoba": [2045211, 3062615, 2110319, 863905, 3061033, 2788991, 3083847, 1975365, 3065743, 1039246]
}

### Menu: Start from scratch or from database
print("Made by Floripundo - Smash Bros Cordoba TO. Choose an option:")
option = input("1 - Start from Scratch | 2 - Add tournaments | Or Write the region you want to run the algorithm for: ")

if option == "1":
    # Start from scratch
    executeQuery("""delete from attendees""")
    executeQuery("""delete from tournaments""")
    executeQuery("""delete from players""")
    tournamentCSV = "tournaments2024"
elif option == "2":
    # Add tournaments
    tournamentCSV = "addtournaments"
    allplayers = executeQuery("""select * from players""")
    for i in allplayers:
        # Load current ranking in players dict
        players[i[0]] = [(i[1] + "|" + i[0]), i[4], i[5], None] # MISSING N TOURNEYS
else:
    executeQuery("""delete from attendees""")
    executeQuery("""delete from tournaments""")
    executeQuery("""delete from players""")
    tournamentCSV = "Regions/" + option.lower()
    bannedregionplayers = bannedregionplayersdict[option.lower()]


### Params

# ELO
defaultelo = 1500 # Everyone starts at this ELO
k = 8 # High -> More data | Low -> Less data

### Functions

# Calls to Start.gg API
def fetchData(query, variables, headers, path):
    alldata = []
    page = 1

    while True:
        # Get data until it is empty
        variables["page"] = page
        response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()

        # Iterates each string in path list
        nodes = data["data"]
        for i in path:
            nodes = nodes.get(i, {})

        # Checks if there is more data
        pageNodes = nodes.get("nodes", [])
        if len(pageNodes) < 1:
            break

        # Add all data to the list
        alldata.extend(pageNodes)
        page += 1

    # Cooldown to not exceed API rate limit
    time.sleep(3)

    return alldata
        
# First step for the algorithm. Update players and map them to their globalID
def mapPlayers(data):
    global players, entrants
    # Reset entrants
    entrants = {}

    for i in data:
        # Update global player list
        try:
            globalid = i["participants"][0]["user"]["id"]
        except:
            if i["participants"][0]["user"] == None:
                #print(f"❕ Skipped player without Start.gg account: {i["name"]}")
                pass
            else:
                #print(f"❗ Error while processing a player: {i}")
                pass

            continue

        if globalid not in players:
            # Manual pre-ELO for non Argentinians players
            if globalid in bannedplayers:
                # Peco, Garu - 1600 ELO
                if globalid == 135383 or globalid == 1451270:
                    players[globalid] = [i["name"], 1600, 0, None, 0, [0, 0], {}]
                    executeQuery("""insert into players (id, name) values (?, ?)""", (globalid, i["name"])) # Preventing tracebacks with other insertions mid-algorithm
                # Flame, Gonzalo Tapia - 1560 ELO
                elif globalid == 780143 or globalid == 298485:
                    players[globalid] = [i["name"], 1560, 0, None, 0, [0, 0], {}]
                    executeQuery("""insert into players (id, name) values (?, ?)""", (globalid, i["name"])) # Preventing tracebacks with other insertions mid-algorithm
                # Benny Henny, LRBA->START - 1540 ELO
                elif globalid == 433945 or globalid == 635540:
                    players[globalid] = [i["name"], 1540, 0, None, 0, [0, 0], {}]
                    executeQuery("""insert into players (id, name) values (?, ?)""", (globalid, i["name"])) # Preventing tracebacks with other insertions mid-algorithm
                else:
                    players[globalid] = [i["name"], defaultelo, 0, None, 0, [0, 0], {}]
                    executeQuery("""insert into players (id, name) values (?, ?)""", (globalid, i["name"])) # Preventing tracebacks with other insertions mid-algorithm
            else:
                players[globalid] = [i["name"], defaultelo, 0, None, 0, [0, 0], {}]
                executeQuery("""insert into players (id, name) values (?, ?)""", (globalid, i["name"])) # Preventing tracebacks with other insertions mid-algorithm
        else:
            players[globalid][0] = i["name"]

        # Update tourney player list
        entrantid = i["id"]

        if entrantid not in entrants:
            entrants[entrantid] = [globalid, 0]

# Get character usage per player
def mapCharacters(data):
    global players, entrants
    for i in data:
        try:
            for j in i["games"]:
                for k in j["selections"]:
                    if k["selectionType"] != "CHARACTER":
                        continue
                    if characters[k["selectionValue"]] not in players[entrants[k["entrant"]["id"]][0]][6]:
                        players[entrants[k["entrant"]["id"]][0]][6][characters[k["selectionValue"]]] = 1
                    else:
                        players[entrants[k["entrant"]["id"]][0]][6][characters[k["selectionValue"]]] += 1
        except: # Games not reported
            continue
# Honestly i won't even explain this function, it just works. I know it's a mess you figure it out

### Querys for Start.gg API's
queryValidPlayer = """
query CheckUser($id: ID!) {
  user(id: $id) {
    id
    player {
      id
      gamerTag
    }
  }
}
"""
queryAttendees = """
query EventEntrants($eventSlug: String!, $page: Int!) {
  event(slug: $eventSlug) {
    entrants(query: { perPage: 50, page: $page }) {
      pageInfo {
        totalPages
      }
      nodes {
        id
        name
        participants {
          user {
            id
          }
        }
      }
    }
  }
}
"""
querySets = """
query EventSets($eventSlug: String!, $page: Int!) {
  event(slug: $eventSlug) {
    sets(page: $page, perPage: 50, sortType: STANDARD) {
      nodes {
        id
        completedAt
        winnerId
        slots {
          entrant {
            id
          }
        }
        games {
          id
          selections {
            selectionType
            selectionValue
            entrant {
              id
            }
          }    
        }
      }
    }
  }
}
"""
queryPlacements = """
query EventPlacements($eventSlug: String!, $page: Int!) {
  event(slug: $eventSlug) {
    name
    id
    entrants(query: { page: $page, perPage: 100 }) {
      pageInfo {
        totalPages
      }
      nodes {
        id
        name
        standing {
          placement
        }
      }
    }
  }
}
"""

### Setup

url = 'https://api.start.gg/gql/alpha'
load_dotenv()
token = os.getenv("token")

# CSV structure: link, tournament name, format, DQ sets ID's 
tournamentFilePath = tournamentCSV # <------------------------------------------------------------------ CSV FILE NAME
fhandle = open(f"Tournaments/{tournamentFilePath}.csv", mode="r", newline="", encoding="utf-8")
tournamentData = csv.reader(fhandle)

# For debugging
with open(f"Tournaments/{tournamentFilePath}.csv", mode="r", newline="", encoding="utf-8") as tournamentFile:
    tournamentCount = len(list(csv.reader(tournamentFile)))

headers = {
    "Authorization": f"Bearer {token}"
}

### Run algorithm!

print(f"🔵 Running Rank System algorithm for {tournamentCount} tournaments")
processCount = 0

for tourney in tournamentData:
    variables = {
        "eventSlug": tourney[0],
        "page": 1
    }

    print(f"✅ Processing tournament: {tourney[1]} | Progress: {(processCount * 100) // tournamentCount}%")
    # Save tournament in database
    date = datetime.strptime(tourney[5], "%d/%m/%Y").date()
    startgg = "www.start.gg/" + tourney[0]
    executeQuery("""insert into tournaments (name, date, region, startgg, format, attendees) values (?, ?, ?, ?, ?, ?)""", (tourney[1], date, tourney[4], startgg, tourney[2], 0))

    # Get all tournament attendees and update global list
    playersdata = fetchData(queryAttendees, variables, headers, ["event", "entrants"])
    mapPlayers(playersdata)

    # Get sets and update ELO
    setsdata = fetchData(querySets, variables, headers, ["event", "sets"])
    mapCharacters(setsdata)
    # Save ELO before tournament for avg elo in updatePlacement()
    lastelo = {}
    for i, j in players.items():
        lastelo[i] = j[1]

    # Set up DQ list
    dqlist = tourney[3].split("|")
    players, entrants, guests = updateElo(setsdata, k, entrants, players, dqlist, bannedregionplayers) # This function also counts the games for each player to help for next step

    # Get placements and update Placement points
    placementdata = fetchData(queryPlacements, variables, headers, ["event", "entrants"])
    tournamentid = executeQuery("""select id from tournaments where name = ?""", (tourney[1],))[0][0]
    players = updatePlacement(placementdata, entrants, players, tournamentid, guests, lastelo) # This function also updates the tournaments attendees for the database and their ELO / PP change per player

    processCount += 1

# All params and scores calculated. Normalize data

sortedelo = sorted(players.items(), key=lambda x: x[1][1], reverse=True)
# Printing
"""
for rank, (id, data) in enumerate(sortedelo, start=1):
    name = data[0]
    elo = data[1]
    print(f"{rank} - {name} | {elo}")
"""

highestelo = sortedelo[0][1][1]
lowestelo = sortedelo[-1][1][1]

sortedplacement = sorted(players.items(), key=lambda x: x[1][2], reverse=True)
# Printing
"""
for rank, (id, data) in enumerate(sortedplacement, start=1):
    name = data[0]
    elo = data[2]
    print(f"{rank} - {name} | {elo}")
"""

highestplacement = sortedplacement[0][1][2]
lowestplacement = sortedplacement[-1][1][2]

# globalid: [name, sponsor, rank, elo, placementpoints] <-- ELO and PP not normalized
ranking = normalize(players, highestelo, lowestelo, highestplacement, lowestplacement) 

count = 0
# Argentina Ranking
if option == "1" or option == "2":
    print("FINAL RANK ARGENTINA 2024")
    for globalid, data in ranking:
        if globalid in bannedplayers:
            print(f"❌ BANNED PLAYER: {data[0]} | {globalid}")
            continue
        count += 1
        print(f"{count} - {data[0]}: {data[2]} | {globalid}")
        # Save ranking into DB
        executeQuery("""update players set name = ?, sponsor = ?, rankpoints = ?, elo = ?, standingpoints = ?, wins = ?, losses = ?, characters = ? where id = ?""", (data[0], data[1], data[2], data[3], data[4], data[5][0], data[5][1], json.dumps(data[6]), globalid))
# Region Ranking
else:
    print(f"FINAL RANK {option.upper()}")
    for globalid, data in ranking:
        if globalid in bannedregionplayers:
            #print(f"❌ BANNED PLAYER: {data[0]} | {globalid}")
            continue
        count += 1
        print(f"{count} - {data[0]}: {data[2]}")
