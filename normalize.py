from player import Player

### Functions to normalize the scores

# Vars

eloweight = 0.6
placementweight = 0.4
ranking = {} # globalid: [name, sponsor, rank, elo, placementpoints, [wins, losses], {characters}, ntourneys] <-- ELO and PP not normalized

tourneycount = {
    0: 0,
    1: 0.1,
    2: 0.5,
    3: 0.75
}

def normalize(highestelo, lowestelo, highestplacement, lowestplacement):
    global ranking
    # Normalize, calculate ranking score and store it in ranking
    for globalid, player in Player.players.items():
        # Normalize ELO
        elo = (player.elo - lowestelo) / (highestelo - lowestelo)
        #print(f"Normalized elo: {data[1]} -> {elo}")
        # Normalize placement points
        placement = (player.pp - lowestplacement) / (highestplacement - lowestplacement)
        #print(f"Normalized placement: {data[2]} -> {placement}")
        rank = eloweight * elo + placementweight * placement
        # Lower final ranking if low tournament count to balance low data
        #print(f"Rank before multiplier for {players[playerid][0]}: {rank}")
        rank *= tourneycount.get(player.ntourneys, 1)
        #print(f"Rank after multiplier for {players[playerid][0]}: {rank}")
        #print(f"{data[0]} multiplier was {tourneycount.get(data[4], 1)}")
        # Separate Sponsor from name
        playertag = player.name.split("|")
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
        player.name = name
        player.sponsor = sponsor

        ranking[globalid] = [player, rank]

    ranking = sorted(ranking.items(), key=lambda x: x[1][1], reverse=True)
    return ranking
