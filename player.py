### Players class

class Player:
    players = {} # globalid -> player instance
    entrants = {} # entrantid -> [playerinstance, ngames]

    def __init__(self, globalid, name, elo, pp, sponsor = None, ntourneys = 0, wins = 0, losses = 0, characters=None):
        self.globalid = globalid
        self.name = name
        self.elo = elo
        self.pp = pp
        self.sponsor = sponsor
        self.ntourneys = ntourneys
        self.wins = wins
        self.losses = losses
        self.characters = characters if characters is not None else {}

        Player.players[globalid] = self

    @classmethod
    def getPlayer(cls, globalid):
        return cls.players.get(globalid, None)

    @classmethod
    def resetEntrants(cls):
        cls.entrants = {}