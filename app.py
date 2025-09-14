import requests, os, csv, time, json, ast
from datetime import datetime
from dotenv import load_dotenv
#
from elo import updateElo
from placement import updatePlacement
from normalize import normalize
from db import executeQuery
from player import Player

### Vars

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
    "cba": [2045211, 3062615, 2110319, 863905, 3061033, 2788991, 3083847, 1975365, 3065743, 1039246, 2883101, 2618737],
    "jujuy": [],
    "santafe": [],
    "bsas": [],
    "salta": []
}

### Menu: Start from scratch or from database
print("Made by Floripundo, Neiel was not here neither was Wadi. Choose an option:")
option = input("1 - Arg Ranking | 2 - Update Ranking (add tourneys) | Or Write the region you want to run the algorithm for: ")
option2 = None

if option == "1":
    # Start from scratch
    executeQuery("""delete from attendees where rankingid = 'arg'""")
    executeQuery("""delete from rankings where rankingid = 'arg'""")
    tournamentCSV = "tournaments2024"
elif option == "2":
    # Ask ranking to update
    option2 = input("1 - Update Arg Ranking | Or write the region you want to update the ranking for: ")
    if option2 == "1":
        # Update Arg Ranking
        data = executeQuery("""select p.name, p.sponsor, r.playerid, r.elo, r.pp, r.wins, r.losses, r.characters, r.ntourneys from rankings r join players p on p.id = r.playerid where rankingid = 'arg'""")
        for i in data:
            Player(i[2], i[0], float(i[3]), float(i[4]), i[1], i[8], i[5], i[6], ast.literal_eval(i[7]))

        tournamentCSV = "Update/arg"
    else:
        # Update region ranking
        data = executeQuery("""select p.name, p.sponsor, r.playerid, r.elo, r.pp, r.wins, r.losses, r.characters, r.ntourneys from rankings r join players p on p.id = r.playerid where rankingid = ? order by rank desc""", (option2.lower(),))
        count = 0 # For calculating variation in ranking
        lastranking = {}
        for i in data:
            count += 1
            Player(i[2], i[0], float(i[3]), float(i[4]), i[1], i[8], i[5], i[6], ast.literal_eval(i[7]))
            print(i[2], i[0], float(i[3]), float(i[4]), i[1], i[8], i[5], i[6])
            lastranking[i[2]] = count

        tournamentCSV = "Update/" + option2.lower()
        bannedregionplayers = bannedregionplayersdict[option2.lower()]

else:
    executeQuery("""delete from attendees where rankingid = ?""", (option.lower(),))
    executeQuery("""delete from rankings where rankingid = ?""", (option.lower(),))
    tournamentCSV = "Regions/" + option.lower()
    bannedregionplayers = bannedregionplayersdict[option.lower()]


### Params

# ELO
defaultelo = 1500 # Everyone starts at this ELO
k = 8 # High -> More data | Low -> Less data

### Functions
# maxi
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
    # Reset entrants
    Player.resetEntrants()

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

        if globalid not in Player.players:
            # Manual pre-ELO for non Argentinians players
            if globalid in bannedplayers:
                # Peco, Garu - 1600 ELO
                if globalid == 135383 or globalid == 1451270:
                    Player(globalid, i["name"], 1600, 0)
                    executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
                # Flame, Gonzalo Tapia - 1560 ELO
                elif globalid == 780143 or globalid == 298485:
                    Player(globalid, i["name"], 1560, 0)
                    executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
                # Benny Henny, LRBA->START - 1540 ELO
                elif globalid == 433945 or globalid == 635540:
                    Player(globalid, i["name"], 1540, 0)
                    executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
                else:
                    Player(globalid, i["name"], defaultelo, 0)
                    executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
            else:
                Player(globalid, i["name"], defaultelo, 0)
                executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
        else:
            Player.getPlayer(globalid).name = i["name"]

        # Update tourney player list
        entrantid = i["id"]

        if entrantid not in Player.entrants:
            Player.entrants[entrantid] = [Player.getPlayer(globalid), 0] # 0 is to count games played to determine present or nonpresent attendee

# Get character usage per player
def mapCharacters(data):
    for i in data:
        try:
            for j in i["games"]:
                for k in j["selections"]:
                    if k["selectionType"] != "CHARACTER":
                        continue
                    if characters[k["selectionValue"]] not in Player.entrants[k["entrant"]["id"]][0].characters:
                        Player.entrants[k["entrant"]["id"]][0].characters[characters[k["selectionValue"]]] = 1
                        #players[entrants[k["entrant"]["id"]][0]][6][characters[k["selectionValue"]]] = 1
                    else:
                        Player.entrants[k["entrant"]["id"]][0].characters[characters[k["selectionValue"]]] += 1
                        #players[entrants[k["entrant"]["id"]][0]][6][characters[k["selectionValue"]]] += 1
        except: # Games not reported
            continue

### Querys for Start.gg API's

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

# CSV structure: link, tournament name, format, DQ sets ID's, Region, Date
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
    startgg = "https://start.gg/" + tourney[0]
    executeQuery("""insert ignore into tournaments (name, date, region, startgg, format, attendees) values (?, ?, ?, ?, ?, ?)""", (tourney[1], date, tourney[4], startgg, tourney[2], 0))

    # Get all tournament attendees and update global list
    playersdata = fetchData(queryAttendees, variables, headers, ["event", "entrants"])
    mapPlayers(playersdata)

    # Get sets and update ELO
    setsdata = fetchData(querySets, variables, headers, ["event", "sets"])
    mapCharacters(setsdata)
    # Save ELO before tournament for avg elo in updatePlacement()
    lastelo = {}
    for globalid, player in Player.players.items():
        lastelo[globalid] = player.elo

    # Set up DQ list
    dqlist = tourney[3].split("|")
    guests = updateElo(setsdata, k, dqlist, bannedregionplayers) # This function also counts the games for each player to help for next step

    # Get placements and update Placement points
    placementdata = fetchData(queryPlacements, variables, headers, ["event", "entrants"])
    tournamentid = executeQuery("""select id from tournaments where name = ?""", (tourney[1],))[0][0]
    updatePlacement(placementdata, tournamentid, guests, lastelo, option, option2) # This function also updates the tournaments attendees for the database and their ELO / PP change per player

    processCount += 1

# All params and scores calculated. Normalize data

sortedelo = sorted(Player.players.items(), key=lambda x: x[1].elo, reverse=True)

highestelo = sortedelo[0][1].elo
lowestelo = sortedelo[-1][1].elo

sortedplacement = sorted(Player.players.items(), key=lambda x: x[1].pp, reverse=True)

highestplacement = sortedplacement[0][1].pp
lowestplacement = sortedplacement[-1][1].pp

# globalid: [name, sponsor, rank, elo, placementpoints, [wins, losses], {characters}] <-- ELO and PP not normalized
ranking = normalize(highestelo, lowestelo, highestplacement, lowestplacement) 

count = 0
# Argentina Ranking
if option == "1":
    print("FINAL RANK ARGENTINA 2024")
    for playerid, (player, rank) in ranking:
        if player.globalid in bannedplayers:
            print(f"❌ BANNED PLAYER: {player.name} | {player.globalid}")
            continue

        count += 1
        print(f"{count} - {player.name}: {rank} | {player.globalid}")     
        # Save ranking into DB
        executeQuery("""
            insert into rankings (rankingid, playerid, rank, elo, pp, wins, losses, characters, ntourneys)
            values ('arg', ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player.globalid,
            rank,
            player.elo,
            player.pp,
            player.wins,
            player.losses,
            json.dumps(player.characters),
            player.ntourneys
        ))

        executeQuery("""
            update players set name = ?, sponsor = ? where id = ?
        """, (
            player.name,
            player.sponsor,
            player.globalid
        ))

        executeQuery("""
            update rankingdata set tournamentcount = ? where id = 'arg
        """, (
            tournamentCount,
        ))
# Region Ranking
else:
    if option != "2":
        rankingid = option
    else:
        rankingid = option2
    print(f"FINAL RANK {option.upper()}")
    newranking = {}
    for playerid, (player, rank) in ranking:
        if player.globalid in bannedregionplayers:
            continue
        count += 1
        print(f"{count} - {player.name}: {rank} | ELO: {player.elo} - PP: {player.pp}")
        print(player.name, player.characters)   
        newranking[player.globalid] = count
        executeQuery("""
                  replace into rankings (rankingid, playerid, rank, elo, pp, wins, losses, characters, ntourneys)
                  values (?, ?, ?, ?, ?, ?, ?, ?, ?)
              """, (
                  rankingid,
                  player.globalid,
                  rank,
                  player.elo,
                  player.pp,
                  player.wins,
                  player.losses,
                  json.dumps(player.characters),
                  player.ntourneys
              ))

        executeQuery("""
            update players set name = ?, sponsor = ? where id = ?
        """, (
            player.name,
            player.sponsor,
            player.globalid
        ))

        lastTournamentCount = executeQuery("""select tournamentcount from rankingdata where id = ?""", (rankingid,))[0][0]
        newTournamentCount = lastTournamentCount + tournamentCount
        executeQuery("""update rankingdata set tournamentcount = ? where id = ?""", (newTournamentCount, rankingid))
# Calculate variations
if option == "2":
    for globalid, newTop in newranking.items():
        lastTop = lastranking.get(globalid, None)
        if lastTop != None:
            variation = lastTop - newTop
            print(Player.getPlayer(globalid).name, variation)
        else:
            variation = 0
        executeQuery("""update rankings set variation = ? where playerid = ? and rankingid = ?""", (variation, globalid, option2))
