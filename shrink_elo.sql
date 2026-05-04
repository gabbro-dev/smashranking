INSERT INTO rankings (
    playerid,
    rankingid,
    elo,
    rank,
    pp,
    wins,
    losses,
    characters,
    top
)
SELECT 
    playerid,
    'arg26' AS rankingid,
    ROUND(1500 + (elo - 1500) * 0.3) AS elo,
    0 AS rank,
    0 AS pp,
    0 AS wins,
    0 AS losses,
    '{}' AS characters,
    100 AS top
FROM rankings
WHERE rankingid = 'arg';

--

SELECT 
    playerid,
    ROUND(1500 + (elo - 1500) * 0.3) AS elo
FROM rankings
WHERE rankingid = 'arg';