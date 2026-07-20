from player import Player
from importvars import importVars

### Functions for calculating ELO

def calculateElo(player, opponent, score, k):
    expected = 1 / (1 + 10 ** ((opponent - player) / 400))
    newelo = player + k * (score - expected)
    return round(newelo, 3)

def updateElo(data, k, dqlist, bannedregionplayers):
    # Order data by timestamps. Ignore games that weren't marked as "Completed"
    data = sorted(
        [s for s in data if s.get("completedAt") is not None],
        key=lambda x: x["completedAt"]
    )
    # For debugging
    dqs = 0
    # Temporary profiles for guests
    guests = {} # entrantid: elo

    for bracket in data:
        # Check DQ
        if str(bracket["id"]) in dqlist:
            dqs += 1
            continue
        # Get set info
        winnerid = bracket["winnerId"]
        player1 = bracket["slots"][0]["entrant"]["id"]
        player2 = bracket["slots"][1]["entrant"]["id"]
        # Skip BS AS Resurrection Bracket Sets
        phase = bracket["phaseGroup"]["phase"]["name"]
        if phase.upper() == "RESURRECTION BRACKET":
            continue

        # Determine winner
        if winnerid == player1:
            winner = player1
            loser = player2
        else:
            winner = player2
            loser = player1

        # Calculate ELO
        try:
            # If its region ranking algorithm, skip region banned players
            if Player.entrants[winner][0].globalid in bannedregionplayers or Player.entrants[loser][0].globalid in bannedregionplayers:
                # Count games to determine DQ
                Player.entrants[winner][1] += 1
                Player.entrants[loser][1] += 1
                continue
            
            newWinnerelo = calculateElo(Player.entrants[winner][0].elo, Player.entrants[loser][0].elo, 1, k)
            newLoserelo = calculateElo(Player.entrants[loser][0].elo, Player.entrants[winner][0].elo, 0, k)
        except:
            # User is guest / doesnt exist
            winnerisguest = loserisguest = False

            # Create / Update temporary profiles for guests
            if winner not in Player.entrants:
                guests[winner] = importVars(4)
                winnerisguest = True
            if loser not in Player.entrants:
                guests[loser] = importVars(4)
                loserisguest = True

            # Both guests
            if winnerisguest and loserisguest:
                newWinnerelo = calculateElo(guests[winner], guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], guests[winner], 0, k)

                guests[winner] = newWinnerelo
                guests[loser] = newLoserelo
            # Winner is guest
            elif winnerisguest and loserisguest == False:
                newWinnerelo = calculateElo(guests[winner], Player.entrants[loser][0].elo, 1, k)
                newLoserelo = calculateElo(Player.entrants[loser][0].elo, guests[winner], 0, k)

                guests[winner] = newWinnerelo
                Player.entrants[loser][0].elo = newLoserelo
                Player.entrants[loser][0].losses += 1
            # Loser is guest
            elif winnerisguest == False and loserisguest:
                newWinnerelo = calculateElo(Player.entrants[winner][0].elo, guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], Player.entrants[winner][0].elo, 0, k)

                guests[loser] = newLoserelo
                Player.entrants[winner][0].elo = newWinnerelo
                Player.entrants[winner][0].wins += 1
            continue

        # Update new ELO
        Player.entrants[winner][0].elo = newWinnerelo
        Player.entrants[loser][0].elo = newLoserelo

        # Update win / loss
        Player.entrants[winner][0].wins += 1
        Player.entrants[loser][0].losses += 1

        # Count games to help next step
        Player.entrants[winner][1] += 1
        Player.entrants[loser][1] += 1

    if dqs > 0:
        print(f"⭕ Games skipped due DQ: {dqs}")
    return guests # <--- Guests included to add to n-players