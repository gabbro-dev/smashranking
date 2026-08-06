-- Schema bootstrap for local Docker MariaDB. Derived from queries in app.py /
-- placement.py / shrink.py and ALGORITHM.md §12. Restore a production dump on
-- top of this for real history.

CREATE TABLE IF NOT EXISTS players (
    id        BIGINT      PRIMARY KEY,
    name      VARCHAR(255) NOT NULL,
    sponsor   VARCHAR(255) NULL,
    region    VARCHAR(64)  NULL
);

CREATE TABLE IF NOT EXISTS tournaments (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    name       VARCHAR(255) NOT NULL,
    date       DATE         NULL,
    region     VARCHAR(64)  NULL,
    startgg    VARCHAR(512) NOT NULL,
    format     VARCHAR(64)  NULL,
    attendees  INT          DEFAULT 0,
    logo       VARCHAR(512) NULL,
    UNIQUE KEY uk_tournament_startgg (startgg)
);

CREATE TABLE IF NOT EXISTS rankings (
    rankingid   VARCHAR(32)   NOT NULL,
    playerid    BIGINT        NOT NULL,
    `rank`      DOUBLE        DEFAULT 0,
    elo         DOUBLE        DEFAULT 1500,
    pp          DOUBLE        DEFAULT 0,
    wins        INT           DEFAULT 0,
    losses      INT           DEFAULT 0,
    characters  TEXT          NULL,
    ntourneys   INT           DEFAULT 0,
    top         INT           DEFAULT 0,
    variation   INT           DEFAULT 0,
    PRIMARY KEY (rankingid, playerid),
    KEY ix_rankings_playerid (playerid)
);

CREATE TABLE IF NOT EXISTS attendees (
    playerid     BIGINT       NOT NULL,
    tournamentid INT          NOT NULL,
    points       DOUBLE       DEFAULT 0,
    elo          DOUBLE       DEFAULT 1500,
    placement    INT          NULL,
    rankingid    VARCHAR(32)  NOT NULL,
    PRIMARY KEY (playerid, tournamentid, rankingid),
    KEY ix_attendees_tournament (tournamentid),
    KEY ix_attendees_ranking (rankingid)
);

CREATE TABLE IF NOT EXISTS sets (
    id            BIGINT       PRIMARY KEY,
    tournamentid  INT          NOT NULL,
    p1id          BIGINT       NULL,
    p2id          BIGINT       NULL,
    winnerid      BIGINT       NULL,
    p1score       TEXT         NULL,
    p2score       TEXT         NULL,
    p1characters  TEXT         NULL,
    p2characters  TEXT         NULL,
    stages        TEXT         NULL,
    winnerpreelo  DOUBLE       DEFAULT 0,
    loserpreelo   DOUBLE       DEFAULT 0,
    notablewins   TINYINT(1)   DEFAULT 0,
    rankingid     VARCHAR(32)  NOT NULL,
    round         VARCHAR(32)  NULL,
    `timestamp`   DATETIME     NULL,
    newwinnerelo  DOUBLE       DEFAULT 0,
    newloserelo   DOUBLE       DEFAULT 0,
    KEY ix_sets_tournament (tournamentid),
    KEY ix_sets_ranking (rankingid),
    KEY ix_sets_p1 (p1id),
    KEY ix_sets_p2 (p2id)
);

CREATE TABLE IF NOT EXISTS rankingdata (
    id              VARCHAR(32) PRIMARY KEY,
    tournamentcount INT         DEFAULT 0
);

-- Pre-create the rankingdata rows the app expects to UPDATE.
INSERT IGNORE INTO rankingdata (id, tournamentcount) VALUES
    ('arg26', 0),
    ('cba26', 0);
