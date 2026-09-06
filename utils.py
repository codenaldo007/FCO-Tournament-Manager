import discord
import aiosqlite
import os
import asyncio
from datetime import datetime, timedelta
import config
import database

async def create_backup(ctx: discord.ext.commands.Context):
    """Create a backup of the database and send it to the context channel."""
    backup_path = await database.get_backup_file_path()
    await database.copy_db_file(backup_path)

    # Send file
    file = discord.File(backup_path)
    await ctx.send("Backup created:", file=file)

    # Log backup in database
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute("INSERT INTO backups (file_path, created_by) VALUES (?, ?)",
                         (backup_path, str(ctx.author.id)))
        await db.commit()

    # Clean up local backup file after sending (optional)
    os.remove(backup_path)

async def restore_backup(ctx: discord.ext.commands.Context, attachment: discord.Attachment):
    """Restore database from an uploaded .db file."""
    if not attachment.filename.endswith('.db'):
        await ctx.send("Invalid file type. Please upload a .db file.")
        return

    # Safety backup of current DB
    safety_path = "pre_restore_backup.db"
    await database.copy_db_file(safety_path)

    # Download attachment to temp file
    temp_path = "restore_temp.db"
    await attachment.save(temp_path)

    # Verify it's a valid SQLite database
    try:
        async with aiosqlite.connect(temp_path) as db:
            await db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    except Exception as e:
        await ctx.send(f"Invalid database file: {e}")
        os.remove(temp_path)
        return

    # Replace current DB
    await database.restore_db_file(temp_path)
    os.remove(temp_path)

    await ctx.send("Database restored successfully. The bot will now reload data.")
    # Optionally: reload caches or restart bot (here we just indicate success)

def parse_user_id(user_input: str) -> Optional[int]:
    """Extract user ID from mention or raw ID."""
    if user_input.isdigit():
        return int(user_input)
    # Try to extract from mention like <@123456789>
    if user_input.startswith('<@') and user_input.endswith('>'):
        id_str = user_input[2:-1]
        if id_str.startswith('!'):
            id_str = id_str[1:]
        if id_str.isdigit():
            return int(id_str)
    return None
