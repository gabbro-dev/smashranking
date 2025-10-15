import requests, os, csv, time, json, ast
from datetime import datetime
from dotenv import load_dotenv
from bisect import bisect_right
#
from elo import updateElo
from placement import updatePlacement
from normalize import normalize
from db import executeQuery
from player import Player
from shrink import shrinkElo

### Function to import vars from TXT file

def importVars(var):
    onevaluevars = [3, 4, 6, 7, 10, 11, 12]
    with open("vars.txt", mode="r", encoding="utf-8", newline="") as varsfile:
        lines = varsfile.readlines()
        # Return desired var
        if var in onevaluevars:
            return float(lines[var].split("=")[1])

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
    "test": [],
    "cba": [2045211, 3062615, 2110319, 863905, 3061033, 2788991, 3083847, 1975365, 3065743, 1039246, 2883101, 2618737, 2448564, 1673007, 1846138, 2762576, 2527284],
    "jujuy": [],
    "santafe": [],
    "bsas": [],
    "salta": []
}

### Menu: Start from scratch or from database
print("Made by Floripundo. Choose an option to run the algorithm for:")
option = input("1 - Argentina Ranking | 2 - Update Current Ranking (add tourneys) | Or Write the region you want to run the algorithm for: ")
option2 = None

if option == "1":
    # Start from scratch
    executeQuery("""delete from attendees where rankingid = 'arg'""")
    executeQuery("""delete from rankings where rankingid = 'arg'""")
    executeQuery("""delete from sets where rankingid = 'arg'""")
    tournamentCSV = "tournaments2025"
elif option == "2":
    # Ask ranking to update
    option2 = input("1 - Update Arg Ranking | Or write the region you want to update the ranking for: ")
    if option2 == "1":
        # Update Arg Ranking
        data = executeQuery("""select p.name, p.sponsor, r.playerid, r.elo, r.pp, r.wins, r.losses, r.characters, r.ntourneys, p.region from rankings r join players p on p.id = r.playerid where rankingid = 'arg' order by rank desc""")
        count = 0 # For calculating variation in ranking
        lastranking = {}
        for i in data:
            count += 1   
            Player(i[2], i[0], float(i[3]), float(i[4]), i[1], i[8], i[5], i[6], ast.literal_eval(i[7]), i[8], i[9])
            lastranking[i[2]] = count

        tournamentCSV = "Update/arg"
    else:
        # Update region ranking
        data = executeQuery("""select p.name, p.sponsor, r.playerid, r.elo, r.pp, r.wins, r.losses, r.characters, r.ntourneys, p.region from rankings r join players p on p.id = r.playerid where rankingid = ? order by rank desc""", (option2.lower(),))
        count = 0 # For calculating variation in ranking
        lastranking = {}
        for i in data:
            count += 1
            Player(i[2], i[0], float(i[3]), float(i[4]), i[1], i[8], i[5], i[6], ast.literal_eval(i[7]), i[8], i[9])
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
k = 32 # High -> More data | Low -> Less data
defaultelo = 1500 # Everyone starts at this ELO

### Functions

# Calculate win chance
def winProb(winnerelo, loserelo) -> float | None:
    if winnerelo is None or loserelo is None:
        return None
    return 1.0 / (1.0 + 10 ** ((loserelo - winnerelo) / 400.0))

# Calculate if ELO in top 20% pool
def eloPercentile(elovalue, elosorted: list[float] | None = None) -> float | None:
    if elovalue is None:
        return None

    if elosorted is None:
        elosorted = sorted(
            p.elo for p in Player.players.values()
            if getattr(p, "elo", None) is not None
        )

    n = len(elosorted)
    if n == 0:
        return None

    idx = bisect_right(elosorted, elovalue)
    return idx / n

# Calls to Start.gg API
def fetchData(query, variables, headers, path):
    alldata = []
    page = 1
    maxRetries = 5

    while True:
        # Get data until it is empty
        variables["page"] = page
        #response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
        #data = response.json()

        for i in range(maxRetries):
            response = requests.post(url, json={"query": query, "variables": variables}, headers=headers)
            if response.status_code != 200:
                time.sleep(5)
            else:
                data = response.json()
                break

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
    time.sleep(5)

    return alldata

# First step for the algorithm. Update players and map them to their globalID / Update their region
def mapPlayers(data, tourneyRegion):
    # Reset entrants
    Player.resetEntrants()

    for i in data:
        # Update global player list
        try:
            globalid = i["participants"][0]["user"]["id"]
        except:
            if i["participants"][0]["user"] == None:
                pass
            else:
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
                Player.getPlayer(globalid).region[tourneyRegion] += 1
                executeQuery("""insert ignore into players (id, name) values (?, ?)""", (globalid, i["name"]))
        else:
            Player.getPlayer(globalid).name = i["name"]
            if option == "1":
                Player.getPlayer(globalid).region[tourneyRegion] += 1

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
                    else:
                        Player.entrants[k["entrant"]["id"]][0].characters[characters[k["selectionValue"]]] += 1
        except: # Games not reported
            continue

# Map sets
def mapSets(data, dqlist, tournamentLink, option, option2):
    for i in data:
        # Skip if DQ
        if str(i["id"]) in dqlist:
            continue
        else:
            # Process set
            setid = i["id"]
            guest = False
            # Get Players Instances
            if i["winnerId"] == None:
                continue
            # Skip BS AS Resurrection Bracket Sets. This is specific to Argentina, you can just remove this if you dont need it.
            phase = i["phaseGroup"]["phase"]["name"]
            if phase.upper() == "RESURRECTION BRACKET":
                continue
            try:
                p1 = Player.entrants[i["slots"][0]["entrant"]["id"]][0]
                p2 = Player.entrants[i["slots"][1]["entrant"]["id"]][0]

                p1elo = p1.elo
                p2elo = p2.elo
                p1globalid = p1.globalid
                p2globalid = p2.globalid
            except:
                # One player is guest
                guest = True

                # Both are guests
                if i["slots"][0]["entrant"]["id"] not in Player.entrants and i["slots"][1]["entrant"]["id"] not in Player.entrants:
                    continue
                # P1 is guest
                elif i["slots"][0]["entrant"]["id"] not in Player.entrants:
                    p1elo = None
                    p1globalid = 0

                    p2 = Player.entrants[i["slots"][1]["entrant"]["id"]][0]
                    p2elo = p2.elo
                    p2globalid = p2.globalid
                # P2 is guest
                elif i["slots"][1]["entrant"]["id"] not in Player.entrants:
                    p2elo = None
                    p2globalid = 0
                
                    p1 = Player.entrants[i["slots"][0]["entrant"]["id"]][0]
                    p1elo = p1.elo
                    p1globalid = p1.globalid

            # Map Entrants ID's
            winnerid = i["winnerId"]
            p1id = i["slots"][0]["entrant"]["id"]
            p2id = i["slots"][1]["entrant"]["id"]
            # Vars
            p1score = []
            p2score = []
            p1characters = []
            p2characters = []
            stages = []
            gameCount = 0
            # Process Each game
            if i["games"] == None:
                continue

            for j in i["games"]:
                gameCount += 1
                # Scores
                if j["winnerId"] == p1id:
                    p1score.append(1)
                    p2score.append(0)
                else:
                    p2score.append(1)
                    p1score.append(0)
                # Stages
                try:
                    stages.append(j["stage"]["name"])
                except: # Stage is None
                    stages.append(None)
                # Characters
                p1char = None
                p2char = None
                for k in j.get("selections", []) or []:
                    if k.get("selectionType") != "CHARACTER":
                        continue
                    entrant = k.get("entrant", {})
                    eid = entrant.get("id")
                    val = k.get("selectionValue")
                    if eid == p1id:
                        p1char = characters[val]
                    elif eid == p2id:
                        p2char = characters[val]
                p1characters.append(p1char)
                p2characters.append(p2char)

            # Determine Notable Win
            if guest == False:
                if p1id == winnerid:
                    winnerelo = p1elo
                    loserelo = p2elo
                    winnerglobalid = p1globalid
                else:
                    winnerelo = p2elo
                    loserelo = p2elo
                    winnerglobalid = p2globalid
                winnerprob = winProb(winnerelo, loserelo)
                elopool = sorted(p.elo for p in Player.players.values() if p.elo is not None)
                loserelopool = eloPercentile(loserelo, elopool)

                notablewin = (winnerprob is not None and loserelopool is not None and winnerprob <= 0.25 and loserelopool >= 0.80)
            else:
                if p1id == winnerid:
                    winnerelo = p1elo
                    loserelo = p2elo
                    winnerglobalid = p1globalid
                else:
                    winnerelo = p2elo
                    loserelo = p2elo
                    winnerglobalid = p2globalid
                notablewin = False

            # Determine rankingid
            if option == "1":
                rankingid = 'arg'
            else:
                if option != "2":
                    rankingid = option
                else:
                    rankingid = option2

            # Insert into DB
            tournamentid = executeQuery("""SELECT id FROM tournaments WHERE startgg = ?""", (tournamentLink,))[0][0]
            
            executeQuery("""REPLACE INTO sets (id, tournamentid, p1id, p2id, winnerid, p1score, p2score, p1characters, p2characters, stages, winnerpreelo, loserpreelo, notablewins, rankingid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (int(setid), tournamentid, p1globalid, p2globalid, winnerglobalid, json.dumps(p1score, ensure_ascii=True), json.dumps(p2score, ensure_ascii=True), json.dumps(p1characters, ensure_ascii=True), json.dumps(p2characters, ensure_ascii=True), json.dumps(stages, ensure_ascii=True), winnerelo, loserelo, notablewin, rankingid))

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
        phaseGroup {
          id
          displayIdentifier
          phase { id name }
        }
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
queryDetailedSets = """
query EventSets($eventSlug: String!, $page: Int!) {
    event(slug: $eventSlug) {
        sets(page: $page, perPage: 25, sortType: STANDARD) {
            nodes {
                id
                winnerId
                phaseGroup {
                    id
                    displayIdentifier
                    phase { id name }
                }
                slots { entrant { id } }
                games {
                winnerId
                selections { selectionType selectionValue entrant { id } }
                stage { name }
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
    logoPath = f"Media/TournamentLogos/{tourney[1]}"
    executeQuery("""insert ignore into tournaments (name, date, region, startgg, format, attendees, logo) values (?, ?, ?, ?, ?, ?, ?)""", (tourney[1], date, tourney[4], startgg, tourney[2], 0, logoPath))

    # Get all tournament attendees and update global list
    playersdata = fetchData(queryAttendees, variables, headers, ["event", "entrants"])
    mapPlayers(playersdata, tourney[4])

    # Set up DQ list
    dqlist = tourney[3].split("|")
    # Get sets and save them
    detailedsetsdata = fetchData(queryDetailedSets, variables, headers, ["event", "sets"])
    mapSets(detailedsetsdata, dqlist, startgg, option, option2)

    # Get sets and update ELO
    setsdata = fetchData(querySets, variables, headers, ["event", "sets"])
    mapCharacters(setsdata)
    # Save ELO before tournament for avg elo in updatePlacement()
    lastelo = {}
    for globalid, player in Player.players.items():
        lastelo[globalid] = player.elo

    guests = updateElo(setsdata, k, dqlist, bannedregionplayers) # This function also counts the games for each player to help for next step

    # Get placements and update Placement points
    placementdata = fetchData(queryPlacements, variables, headers, ["event", "entrants"])
    tournamentid = executeQuery("""select id from tournaments where name = ?""", (tourney[1],))[0][0]
    updatePlacement(placementdata, tournamentid, guests, lastelo, option, option2) # This function also updates the tournaments attendees for the database and their ELO / PP change per player

    processCount += 1
"""
# If National Ranking, Shrink ELO
if option == "1" or option2 == "arg":
    CI, eloshrunk = shrinkElo()
"""

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
    print("FINAL RANK ARGENTINA")
    for playerid, (player, rank) in ranking:
        if player.globalid in bannedplayers:
            continue

        count += 1
        print(f"{count} - {player.name}: {rank} | ELO: {player.elo} - PP: {player.pp}")     
        # Save ranking into DB
        executeQuery("""
            insert into rankings (rankingid, playerid, rank, elo, pp, wins, losses, characters, ntourneys, top)
            values ('arg', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            player.globalid,
            rank,
            player.elo,
            player.pp,
            player.wins,
            player.losses,
            json.dumps(player.characters),
            player.ntourneys,
            count
        ))

        # Calculate region
        region, topcount = max(player.region.items(), key=lambda kv: kv[1])

        executeQuery("""
            update players set name = ?, sponsor = ?, region = ? where id = ?
        """, (
            player.name,
            player.sponsor,
            region,
            player.globalid
        ))

        executeQuery("""
            update rankingdata set tournamentcount = ? where id = 'arg'
        """, (
            tournamentCount,
        ))
# Region Ranking / update ranking
else:
    if option != "2": # if Region
        rankingid = option
    else: # updating
        if option2 == "1": # Updating arg
            rankingid = 'arg'
        else: # Updating Region
            rankingid = option2
    print(f"FINAL RANK {option.upper()}")
    newranking = {}
    for playerid, (player, rank) in ranking:
        if player.globalid in bannedregionplayers:
            continue
        count += 1
        print(f"{count} - {player.name}: {rank} | ELO: {player.elo} - PP: {player.pp}") 
        newranking[player.globalid] = count
        executeQuery("""
                  replace into rankings (rankingid, playerid, rank, elo, pp, wins, losses, characters, ntourneys, top)
                  values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
              """, (
                  rankingid,
                  player.globalid,
                  rank,
                  player.elo,
                  player.pp,
                  player.wins,
                  player.losses,
                  json.dumps(player.characters),
                  player.ntourneys,
                  count
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
        else:
            variation = 0
        executeQuery("""update rankings set variation = ? where playerid = ? and rankingid = ?""", (variation, globalid, rankingid))
