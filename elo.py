from player import Player
from importvars import importVars

### Functions for calculating ELO

def calculateElo(player, opponent, score, k):
    expected = 1 / (1 + 10 ** ((opponent - player) / 400))
    newelo = player + k * (score - expected)
    return round(newelo, 3)

def updateElo(data, k, dqlist, bannedregionplayers, argelo=None):
    # argelo: {globalid: arg26_elo}. Empty for national runs; populated for
    # regional runs to score cross-region sets in arg26-space.
    if argelo is None:
        argelo = {}
    defaultelo = importVars(4)
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

        # Detect guests (entrants without a linked start.gg user / Player instance)
        winnerIsGuest = winner not in Player.entrants
        loserIsGuest = loser not in Player.entrants

        if winnerIsGuest or loserIsGuest:
            # Guest handling: temporary in-memory ELO that doesn't persist
            if winnerIsGuest and winner not in guests:
                guests[winner] = defaultelo
            if loserIsGuest and loser not in guests:
                guests[loser] = defaultelo

            if winnerIsGuest and loserIsGuest:
                newWinnerelo = calculateElo(guests[winner], guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], guests[winner], 0, k)
                guests[winner] = newWinnerelo
                guests[loser] = newLoserelo
            elif winnerIsGuest:
                newWinnerelo = calculateElo(guests[winner], Player.entrants[loser][0].elo, 1, k)
                newLoserelo = calculateElo(Player.entrants[loser][0].elo, guests[winner], 0, k)
                guests[winner] = newWinnerelo
                Player.entrants[loser][0].elo = newLoserelo
                Player.entrants[loser][0].losses += 1
            else:
                newWinnerelo = calculateElo(Player.entrants[winner][0].elo, guests[loser], 1, k)
                newLoserelo = calculateElo(guests[loser], Player.entrants[winner][0].elo, 0, k)
                guests[loser] = newLoserelo
                Player.entrants[winner][0].elo = newWinnerelo
                Player.entrants[winner][0].wins += 1
            continue

        # Both are real entrants. Resolve them and check region-ban status.
        winnerPlayer = Player.entrants[winner][0]
        loserPlayer = Player.entrants[loser][0]
        winnerBanned = winnerPlayer.globalid in bannedregionplayers
        loserBanned = loserPlayer.globalid in bannedregionplayers

        if winnerBanned and loserBanned:
            # Both visitors: nothing to score, just tick presence.
            Player.entrants[winner][1] += 1
            Player.entrants[loser][1] += 1
            continue

        if winnerBanned or loserBanned:
            # Cross-region: score in arg26-space; presence-only when argelo is
            # empty (legacy arg26-update mode).
            if argelo:
                wArg = argelo.get(winnerPlayer.globalid, defaultelo)
                lArg = argelo.get(loserPlayer.globalid, defaultelo)
                expectedW = 1 / (1 + 10 ** ((lArg - wArg) / 400))
                delta = round(k * (1 - expectedW), 3)
                if not winnerBanned:
                    winnerPlayer.elo = round(winnerPlayer.elo + delta, 3)
                    winnerPlayer.wins += 1
                if not loserBanned:
                    loserPlayer.elo = round(loserPlayer.elo - delta, 3)
                    loserPlayer.losses += 1
            Player.entrants[winner][1] += 1
            Player.entrants[loser][1] += 1
            continue

        # Both local
        newWinnerelo = calculateElo(winnerPlayer.elo, loserPlayer.elo, 1, k)
        newLoserelo = calculateElo(loserPlayer.elo, winnerPlayer.elo, 0, k)

        winnerPlayer.elo = newWinnerelo
        loserPlayer.elo = newLoserelo

        winnerPlayer.wins += 1
        loserPlayer.losses += 1

        Player.entrants[winner][1] += 1
        Player.entrants[loser][1] += 1

    if dqs > 0:
        print(f"⭕ Games skipped due DQ: {dqs}")
    return guests # <--- Guests included to add to n-players