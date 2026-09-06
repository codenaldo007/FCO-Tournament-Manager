import discord
from discord.ext import commands
import config
import database
import checks
import utils

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='add_staff')
    @checks.is_owner()
    async def add_staff(self, ctx, user_id: str):
        """Add a user as tournament staff."""
        user_id = utils.parse_user_id(user_id)
        if not user_id:
            await ctx.send("Invalid user ID.")
            return
        await database.add_staff(str(user_id), str(ctx.author.id))
        await ctx.send(f"<@{user_id}> has been added as staff.")

    @commands.command(name='remove_staff')
    @checks.is_owner()
    async def remove_staff(self, ctx, user_id: str):
        """Remove a staff member."""
        user_id = utils.parse_user_id(user_id)
        if not user_id:
            await ctx.send("Invalid user ID.")
            return
        await database.remove_staff(str(user_id))
        await ctx.send(f"<@{user_id}> has been removed from staff.")

    @commands.command(name='reset_tournament')
    @checks.is_owner()
    async def reset_tournament(self, ctx):
        """Reset all tournament data (dangerous)."""
        # Confirmation
        confirm_msg = await ctx.send("Are you sure? React with ✅ to confirm.")
        await confirm_msg.add_reaction("✅")
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) == "✅" and reaction.message.id == confirm_msg.id
        try:
            await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Reset cancelled.")
            return

        # Perform reset
        async with aiosqlite.connect(database.DB_PATH) as db:
            await db.execute("DELETE FROM tournament_config")
            await db.execute("DELETE FROM players")
            await db.execute("DELETE FROM matchups")
            await db.commit()
        await ctx.send("Tournament data has been reset.")

    @commands.command(name='restore')
    @checks.is_owner()
    async def restore(self, ctx):
        """Restore database from an attached .db file. Usage: !restore (attach file)"""
        if not ctx.message.attachments:
            await ctx.send("Please attach a .db file to the command message.")
            return
        attachment = ctx.message.attachments[0]
        await utils.restore_backup(ctx, attachment)

async def setup(bot):
    await bot.add_cog(Owner(bot))
