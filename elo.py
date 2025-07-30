### Functions for calculating ELO

def calculateElo(player, opponent, score, k):
    expected = 1 / (1 + 10 ** ((opponent - player) / 400))
    newelo = player + k * (score - expected)
    return round(newelo, 3)

def updateElo(data, k, entrants, players, dqlist, bannedregionplayers):
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
            if entrants[winner][0] in bannedregionplayers or entrants[loser][0] in bannedregionplayers:
                #print(f"❕ Skipped ELO calculations for out of region user in: updateElo() | {players[entrants[winner][0]][0]} VS. {players[entrants[loser][0]][0]}")
                # Count games to help next step
                entrants[winner][1] += 1
                entrants[loser][1] += 1
                continue
            
            newWinnerelo = calculateElo(players[entrants[winner][0]][1], players[entrants[loser][0]][1], 1, k)
            newLoserelo = calculateElo(players[entrants[loser][0]][1], players[entrants[winner][0]][1], 0, k)
        except:
            # User is guest / doesnt exist
            #print("❕ Skipped ELO calculations for non existent user in: updateElo()")

            winnerisguest = loserisguest = False

            # Create / Update temporary profiles for guests
            if winner not in entrants:
                guests[winner] = 1500
                winnerisguest = True
            if loser not in entrants:
                guests[loser] = 1500
                loserisguest = True

            # Both guests
            if winnerisguest and loserisguest:
                newWinnerelo = calculateElo(guests[winner], guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], guests[winner], 0, k)

                guests[winner] = newWinnerelo
                guests[loser] = newLoserelo
            # Winner is guest
            elif winnerisguest and loserisguest == False:
                newWinnerelo = calculateElo(guests[winner], players[entrants[loser][0]][1], 1, k)
                newLoserelo = calculateElo(players[entrants[loser][0]][1], guests[winner], 1, k)

                guests[winner] = newWinnerelo
                players[entrants[loser][0]][1] = newLoserelo
                players[entrants[loser][0]][5][1] += 1 # Update loss
            # Loser is guest
            elif winnerisguest == False and loserisguest:
                newWinnerelo = calculateElo(players[entrants[winner][0]][1], guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], players[entrants[winner][0]][1], 1, k)

                guests[loser] = newLoserelo
                players[entrants[winner][0]][1] = newWinnerelo
                players[entrants[winner][0]][5][0] += 1 # Update win

            continue

        # Update new ELO
        players[entrants[winner][0]][1] = newWinnerelo
        players[entrants[loser][0]][1] = newLoserelo

        # Update win / loss
        players[entrants[winner][0]][5][0] += 1
        players[entrants[loser][0]][5][1] += 1

        # Count games to help next step
        entrants[winner][1] += 1
        entrants[loser][1] += 1

    if dqs > 0:
        print(f"⭕ Games skipped due DQ: {dqs}")
    return players, entrants, guests # <--- Guests included to add to n-players