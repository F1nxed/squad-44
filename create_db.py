data = """
-- Games (store as INTEGER unix time or TEXT ISO; keeping your insert as unix time)
CREATE TABLE IF NOT EXISTS games (
    game_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date   INTEGER NOT NULL,        -- was DATE; using INTEGER to match your insert 1758646800
    title       TEXT,
    description TEXT
);
INSERT OR IGNORE INTO games (game_id, game_date, title, description)
VALUES (1, 1758646800, 'Best Game Ever', 'Much testing');

-- Sides
CREATE TABLE IF NOT EXISTS sides (
    side_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    side_name   TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO sides VALUES (1, 'Allies');
INSERT OR IGNORE INTO sides VALUES (2, 'Axis');

-- Squad types
CREATE TABLE IF NOT EXISTS squad_types (
    type_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    type_name   TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO squad_types VALUES (1, 'Commander');
INSERT OR IGNORE INTO squad_types VALUES (2, 'Infantry');
INSERT OR IGNORE INTO squad_types VALUES (3, 'Logistic');
INSERT OR IGNORE INTO squad_types VALUES (4, 'Armor');

-- Roles
CREATE TABLE IF NOT EXISTS roles (
    role_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    role_name   TEXT NOT NULL UNIQUE
);
INSERT OR IGNORE INTO roles VALUES (1, 'Commander');
INSERT OR IGNORE INTO roles VALUES (2, 'NCO');
INSERT OR IGNORE INTO roles VALUES (3, 'Tank Commander');
INSERT OR IGNORE INTO roles VALUES (4, 'Radio Man');
INSERT OR IGNORE INTO roles VALUES (5, 'Rifle Man');
INSERT OR IGNORE INTO roles VALUES (6, 'Medic');
INSERT OR IGNORE INTO roles VALUES (7, 'Machine Gunner');
INSERT OR IGNORE INTO roles VALUES (8, 'Sniper');
INSERT OR IGNORE INTO roles VALUES (9, 'Light Anti-Tank');
INSERT OR IGNORE INTO roles VALUES (10, 'Sapper');
INSERT OR IGNORE INTO roles VALUES (11, 'Grenadier');
INSERT OR IGNORE INTO roles VALUES (12, 'Mortarman');
INSERT OR IGNORE INTO roles VALUES (13, 'Combat Engineer AP');
INSERT OR IGNORE INTO roles VALUES (14, 'Combat Engineer AT');
INSERT OR IGNORE INTO roles VALUES (15, 'Combat Engineer HE');
INSERT OR IGNORE INTO roles VALUES (16, 'Tanker');

-- Players  (removed trailing comma; you can add player_stats if you need it)
CREATE TABLE IF NOT EXISTS players (
    player_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name     TEXT,
    discord_id      INTEGER,
    player_nickname TEXT
    -- , player_stats INTEGER DEFAULT 0   -- uncomment if you want this column
);

-- Squads (added missing commas between FK clauses)
CREATE TABLE IF NOT EXISTS squads (
    squad_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER NOT NULL,
    game_id     INTEGER NOT NULL,
    side_id     INTEGER NOT NULL,
    type_id     INTEGER NOT NULL,
    squad_name  TEXT,
    FOREIGN KEY (owner_id) REFERENCES players(player_id),
    FOREIGN KEY (game_id)  REFERENCES games(game_id),
    FOREIGN KEY (side_id)  REFERENCES sides(side_id),
    FOREIGN KEY (type_id)  REFERENCES squad_types(type_id)
);

-- Squad assignments
CREATE TABLE IF NOT EXISTS squad_assignments (
    assignment_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    squad_id        INTEGER NOT NULL,
    player_id       INTEGER NOT NULL,
    role_id         INTEGER NOT NULL,
    FOREIGN KEY (squad_id)  REFERENCES squads(squad_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id),
    FOREIGN KEY (role_id)   REFERENCES roles(role_id)
);

-- Schedules
CREATE TABLE IF NOT EXISTS schedules (
    id       INTEGER PRIMARY KEY,
    time_str TEXT
);
INSERT OR IGNORE INTO schedules VALUES (1, '19:10');

-- Channel manager
CREATE TABLE IF NOT EXISTS channel_manager (
    guild     INTEGER NOT NULL,
    type      TEXT NOT NULL,
    channel   INTEGER NOT NULL,
    category  INTEGER NOT NULL,
    message   INTEGER NOT NULL,
    PRIMARY KEY (guild, type)
);

-- Forum posts (add thread_id so you can find the forum post; keep message_id for the editable first message)
CREATE TABLE IF NOT EXISTS forum_posts (
    player_id  INTEGER PRIMARY KEY,
    thread_id  INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);
            """
