import discord
from discord.ext import commands
import database

class Public(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='tournament_status')
    async def tournament_status(self, ctx):
        """Show basic tournament info for everyone."""
        config = await database.get_tournament_config()
        if not config:
            await ctx.send("No tournament is currently set up.")
            return
        players = await database.get_all_players()
        active_count = sum(1 for p in players if p[2] == 1)
        embed = discord.Embed(title="Tournament Status", color=discord.Color.blue())
        embed.add_field(name="Status", value=config['status'], inline=True)
        embed.add_field(name="Current Round", value=config['current_round'], inline=True)
        embed.add_field(name="Active Players", value=f"{active_count}/{len(players)}", inline=True)
        if config['current_round'] > 0:
            matchups = await database.get_matchups_for_round(config['current_round'])
            if matchups:
                lines = []
                for m in matchups:
                    p1 = f"<@{m['player1_id']}>"
                    p2 = f"<@{m['player2_id']}>" if m['player2_id'] else "BYE"
                    if m['status'] == 'completed':
                        winner = f"<@{m['winner_id']}>" if m['winner_id'] else "?"
                        lines.append(f"Match {m['id']}: {p1} vs {p2} → Winner: {winner}")
                    else:
                        lines.append(f"Match {m['id']}: {p1} vs {p2}")
                embed.add_field(name="Current Matchups", value="\n".join(lines), inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Public(bot))
