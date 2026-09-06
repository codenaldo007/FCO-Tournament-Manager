import aiosqlite
from typing import Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

DB_PATH = "tournament.db"

async def init_db():
    """Create tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS tournament_config (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                player_count INTEGER NOT NULL,
                round_duration_minutes INTEGER NOT NULL,
                announce_channel_id TEXT,
                announce_role_id TEXT,
                alert_minutes_before_end INTEGER DEFAULT 5,
                current_round INTEGER DEFAULT 0,
                status TEXT DEFAULT 'idle'
            );

            CREATE TABLE IF NOT EXISTS staff (
                user_id TEXT PRIMARY KEY,
                added_by TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS players (
                user_id TEXT PRIMARY KEY,
                discord_name TEXT,
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS matchups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                round_number INTEGER NOT NULL,
                player1_id TEXT NOT NULL,
                player2_id TEXT,
                winner_id TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (player1_id) REFERENCES players(user_id),
                FOREIGN KEY (player2_id) REFERENCES players(user_id),
                FOREIGN KEY (winner_id) REFERENCES players(user_id)
            );

            CREATE TABLE IF NOT EXISTS backups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                created_by TEXT
            );
        """)
        await db.commit()

# ----------------- Helper functions for tournament_config -----------------
async def get_tournament_config() -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM tournament_config WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            cols = [desc[0] for desc in cursor.description]
            return dict(zip(cols, row))
        return None

async def set_tournament_config(config: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO tournament_config 
            (id, player_count, round_duration_minutes, announce_channel_id, 
             announce_role_id, alert_minutes_before_end, current_round, status)
            VALUES (1, :player_count, :round_duration_minutes, :announce_channel_id,
                    :announce_role_id, :alert_minutes_before_end, :current_round, :status)
        """, config)
        await db.commit()

# ----------------- Staff management -----------------
async def add_staff(user_id: str, added_by: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO staff (user_id, added_by) VALUES (?, ?)", (user_id, added_by))
        await db.commit()

async def remove_staff(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM staff WHERE user_id = ?", (user_id,))
        await db.commit()

async def is_staff(user_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT 1 FROM staff WHERE user_id = ?", (user_id,))
        return await cursor.fetchone() is not None

# ----------------- Player management -----------------
async def add_player(user_id: str, discord_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR IGNORE INTO players (user_id, discord_name, is_active)
            VALUES (?, ?, 1)
        """, (user_id, discord_name))
        await db.commit()

async def remove_player(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM players WHERE user_id = ?", (user_id,))
        await db.commit()

async def get_active_players() -> List[Tuple[str, str]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, discord_name FROM players WHERE is_active = 1")
        return await cursor.fetchall()

async def get_all_players() -> List[Tuple[str, str, int]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id, discord_name, is_active FROM players")
        return await cursor.fetchall()

async def set_player_inactive(user_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE players SET is_active = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

# ----------------- Matchup management -----------------
async def create_matchups(round_number: int, pairs: List[Tuple[str, Optional[str]]]) -> List[int]:
    """Insert matchups and return IDs."""
    ids = []
    async with aiosqlite.connect(DB_PATH) as db:
        for p1, p2 in pairs:
            cursor = await db.execute("""
                INSERT INTO matchups (round_number, player1_id, player2_id, status)
                VALUES (?, ?, ?, 'pending')
            """, (round_number, p1, p2))
            ids.append(cursor.lastrowid)
        await db.commit()
    return ids

async def get_matchups_for_round(round_number: int) -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            SELECT * FROM matchups WHERE round_number = ?
            ORDER BY id
        """, (round_number,))
        rows = await cursor.fetchall()
        if rows:
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in rows]
        return []

async def update_matchup_winner(matchup_id: int, winner_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE matchups SET winner_id = ?, status = 'completed'
            WHERE id = ?
        """, (winner_id, matchup_id))
        await db.commit()

async def get_all_matchups() -> List[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT * FROM matchups ORDER BY round_number, id")
        rows = await cursor.fetchall()
        if rows:
            cols = [desc[0] for desc in cursor.description]
            return [dict(zip(cols, row)) for row in rows]
        return []

# ----------------- Backup/restore -----------------
async def get_backup_file_path() -> str:
    import time
    return f"backup_{int(time.time())}.db"

async def copy_db_file(destination: str):
    import shutil
    shutil.copy2(DB_PATH, destination)

async def restore_db_file(source: str):
    import shutil
    shutil.copy2(source, DB_PATH)
