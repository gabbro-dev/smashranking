### Players class

class Player:
    players = {} # globalid -> player instance
    entrants = {} # entrantid -> [playerinstance, ngames]

    def __init__(self, globalid, name, elo, pp, sponsor = None, ntourneys = 0, wins = 0, losses = 0, characters=None, region=None, ci=0):
        self.globalid = globalid
        self.name = name
        self.elo = elo
        self.pp = pp
        self.sponsor = sponsor
        self.ntourneys = ntourneys
        self.wins = wins
        self.losses = losses
        self.characters = characters if characters is not None else {}
        self.region = region if region is not None else {'Salta': 0, 'Buenos Aires': 0, 'Cordoba': 0, 'Jujuy': 0, 'Santa Fe': 0, 'Mendoza': 0}
        self.ci = ci

        Player.players[globalid] = self

    @classmethod
    def getPlayer(cls, globalid):
        return cls.players.get(globalid, None)

    @classmethod
    def resetEntrants(cls):
        cls.entrants = {}