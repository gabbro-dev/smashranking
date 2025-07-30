### Functions to normalize the scores

# Vars

eloweight = 0.6
placementweight = 0.4
ranking = {} # globalid: [name, sponsor, rank, elo, placementpoints, [wins, losses], {characters}] <-- ELO and PP not normalized

tourneycount = {
    0: 0,
    1: 0.1,
    2: 0.5,
    3: 0.75
}

def normalize(players, highestelo, lowestelo, highestplacement, lowestplacement):
    global ranking
    # Normalize, calculate ranking score and store it in ranking
    for playerid, data in players.items():
        # Normalize ELO
        elo = (data[1] - lowestelo) / (highestelo - lowestelo)
        #print(f"Normalized elo: {data[1]} -> {elo}")
        # Normalize placement points
        placement = (data[2] - lowestplacement) / (highestplacement - lowestplacement)
        #print(f"Normalized placement: {data[2]} -> {placement}")
        rank = eloweight * elo + placementweight * placement
        # Lower final ranking if low tournament count to balance low data
        #print(f"Rank before multiplier for {players[playerid][0]}: {rank}")
        rank *= tourneycount.get(data[4], 1)
        #print(f"Rank after multiplier for {players[playerid][0]}: {rank}")
        #print(f"{data[0]} multiplier was {tourneycount.get(data[4], 1)}")
        # Separate Sponsor from name
        playertag = data[0].split("|")
        if len(playertag) == 1:
            sponsor = None
            name = playertag[0].strip()
        else:
            sponsor = ""
            for i in range(len(playertag) - 1):
                sponsor += (playertag[i] + "|")
            sponsor = sponsor[:-1].strip()
            name = playertag[-1].strip()

        #print(f"DEBUG: Player: {data[0]} | Sponsor: {sponsor} - Name: {name}")

        ranking[playerid] = [name, sponsor, rank, data[1], data[2], [data[5][0], data[5][1]], data[6]]

    ranking = sorted(ranking.items(), key=lambda x: x[1][2], reverse=True)
    return ranking
