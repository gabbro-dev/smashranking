import csv
#
from player import Player
from importvars import importVars

### Functions to normalize the scores

# Vars

eloweight = importVars(10)
placementweight = importVars(11)
formpointsweight = importVars(12)
ranking = {} # globalid: [name, sponsor, rank, elo, placementpoints, [wins, losses], {characters}, ntourneys] <-- ELO and PP not normalized

tourneycount = importVars(13)

def normalize(highestelo, lowestelo, highestplacement, lowestplacement):
    global ranking
    # Import form
    """
    formcsv = open("form.csv", mode="r", newline="", encoding="utf-8")
    formplayers = csv.reader(formcsv)
    formtop50 = {}
    for i in formplayers:
        formtop50[i[0]] = int(i[2]) # ID -> Form points
    highestformpoints = max(formtop50.values())
    lowestformpoints = min(formtop50.values())
    """
    # Normalize, calculate ranking score and store it in ranking
    for globalid, player in Player.players.items():
        # Normalize ELO
        elo = (player.elo - lowestelo) / (highestelo - lowestelo)
        # Normalize placement points
        placement = (player.pp - lowestplacement) / (highestplacement - lowestplacement)
        # Normalize form points
        """
        if player.id in formtop50:
            formpoints = (formtop50[player.id] - lowestformpoints) / (highestformpoints - lowestformpoints)
        else:
            formpoints = 0.5
        """
        # Get final score
        rank = eloweight * elo + placementweight * placement
        # Lower final ranking if low tournament count to balance low data
        rank *= tourneycount.get(player.ntourneys, 1)
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

        player.name = name
        player.sponsor = sponsor

        ranking[globalid] = [player, rank]

    ranking = sorted(ranking.items(), key=lambda x: x[1][1], reverse=True)
    return ranking
