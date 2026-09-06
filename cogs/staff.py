import discord
from discord.ext import commands
import asyncio
import random
import config
import database
import checks
import utils

class Staff(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='add_player')
    @checks.is_owner_or_staff()
    async def add_player(self, ctx, user_id: str):
        """Add a player by Discord ID."""
        user_id = utils.parse_user_id(user_id)
        if not user_id:
            await ctx.send("Invalid user ID.")
            return
        try:
            user = await self.bot.fetch_user(user_id)
            name = user.display_name
        except:
            name = str(user_id)
        await database.add_player(str(user_id), name)
        await ctx.send(f"Player <@{user_id}> added.")

    @commands.command(name='remove_player')
    @checks.is_owner_or_staff()
    async def remove_player(self, ctx, user_id: str):
        """Remove a player (before tournament starts)."""
        user_id = utils.parse_user_id(user_id)
        if not user_id:
            await ctx.send("Invalid user ID.")
            return
        await database.remove_player(str(user_id))
        await ctx.send(f"Player <@{user_id}> removed.")

    @commands.command(name='init_tournament')
    @checks.is_owner_or_staff()
    async def init_tournament(self, ctx, player_count: int, duration_minutes: int,
                              announce_channel: discord.TextChannel,
                              announce_role: discord.Role,
                              alert_minutes: int = config.DEFAULT_ALERT_MINUTES):
        """Initialize tournament settings.
        Usage: !init_tournament <player_count> <duration_minutes> <announce_channel> <announce_role> [alert_minutes]
        """
        if player_count < 2:
            await ctx.send("Player count must be at least 2.")
            return
        config_data = {
            "player_count": player_count,
            "round_duration_minutes": duration_minutes,
            "announce_channel_id": str(announce_channel.id),
            "announce_role_id": str(announce_role.id),    # NEW
            "alert_minutes_before_end": alert_minutes,
            "current_round": 0,
            "status": "registration"
        }
        await database.set_tournament_config(config_data)
        await ctx.send(f"Tournament initialized: {player_count} players, {duration_minutes} min rounds, "
                       f"announcements in {announce_channel.mention} mentioning {announce_role.mention}, "
                       f"alert {alert_minutes} min before end.")

    @commands.command(name='start_registration')
    @checks.is_owner_or_staff()
    async def start_registration(self, ctx):
        """Set tournament status to registration."""
        config = await database.get_tournament_config()
        if not config:
            await ctx.send("Tournament not initialized. Use !init_tournament first.")
            return
        config['status'] = 'registration'
        await database.set_tournament_config(config)
        await ctx.send("Registration is now open.")

    @commands.command(name='close_registration')
    @checks.is_owner_or_staff()
    async def close_registration(self, ctx):
        """Close registration and prepare for matchups."""
        config = await database.get_tournament_config()
        if not config:
            await ctx.send("Tournament not initialized.")
            return
        config['status'] = 'closed'
        await database.set_tournament_config(config)
        await ctx.send("Registration closed. You can now generate matchups.")

    @commands.command(name='make_matchups')
    @checks.is_owner_or_staff()
    async def make_matchups(self, ctx):
        """Randomly pair active players for the next round."""
        config = await database.get_tournament_config()
        if not config:
            await ctx.send("Tournament not initialized.")
            return
        if config['status'] not in ['closed', 'active']:
            await ctx.send("Registration must be closed or tournament active to generate matchups.")
            return

        players = await database.get_active_players()
        if len(players) < 2:
            await ctx.send("Not enough active players to create matchups.")
            return

        random.shuffle(players)
        pairs = []
        bye_player = None
        if len(players) % 2 == 1:
            bye_player = players.pop()
            pairs.append((bye_player[0], None))
        for i in range(0, len(players), 2):
            pairs.append((players[i][0], players[i+1][0]))

        next_round = config['current_round'] + 1
        matchup_ids = await database.create_matchups(next_round, pairs)

        if bye_player:
            async with aiosqlite.connect(database.DB_PATH) as db:
                cursor = await db.execute("SELECT id FROM matchups WHERE player2_id IS NULL AND round_number = ?", (next_round,))
                row = await cursor.fetchone()
                if row:
                    await database.update_matchup_winner(row[0], bye_player[0])

        config['current_round'] = next_round
        config['status'] = 'active'
        await database.set_tournament_config(config)

        await ctx.send(f"Matchups for round {next_round} have been generated. Use !list_matchups to view.")

    @commands.command(name='start_round')
    @checks.is_owner_or_staff()
    async def start_round(self, ctx):
        """Announce the current round and start the timer."""
        config = await database.get_tournament_config()
        if not config or config['status'] != 'active':
            await ctx.send("No active round to start.")
            return
        round_num = config['current_round']
        duration = config['round_duration_minutes']
        alert_minutes = config['alert_minutes_before_end']
        announce_channel_id = int(config['announce_channel_id'])
        announce_role_id = config.get('announce_role_id')   # NEW

        channel = self.bot.get_channel(announce_channel_id)
        if not channel:
            await ctx.send("Announcement channel not found.")
            return

        role_mention = f"<@&{announce_role_id}>" if announce_role_id else ""
        if role_mention:
            role_mention += " "   # trailing space before message

        matchups = await database.get_matchups_for_round(round_num)
        if not matchups:
            await ctx.send("No matchups found for current round. Generate them first.")
            return

        lines = []
        for m in matchups:
            p1 = f"<@{m['player1_id']}>"
            p2 = f"<@{m['player2_id']}>" if m['player2_id'] else "BYE"
            if m['status'] == 'completed':
                winner = f"<@{m['winner_id']}>" if m['winner_id'] else "?"
                lines.append(f"**Match {m['id']}:** {p1} vs {p2} → Winner: {winner}")
            else:
                lines.append(f"**Match {m['id']}:** {p1} vs {p2}")

        embed = discord.Embed(title=f"Round {round_num} Matchups", description="\n".join(lines), color=discord.Color.blue())
        embed.add_field(name="Duration", value=f"{duration} minutes", inline=False)
        await channel.send(f"{role_mention}Round {round_num} has begun!", embed=embed)

        # Start timer task
        await self.start_round_timer(round_num, duration, alert_minutes, channel, role_mention)

        await ctx.send(f"Round {round_num} started. Announcements will be sent to {channel.mention}.")

    async def start_round_timer(self, round_num: int, duration_minutes: int, alert_minutes: int,
                                channel: discord.TextChannel, role_mention: str = ""):
        """Background task to handle round timer and alerts."""
        total_seconds = duration_minutes * 60
        alert_seconds = alert_minutes * 60

        if alert_seconds > 0 and total_seconds > alert_seconds:
            await asyncio.sleep(total_seconds - alert_seconds)
            await channel.send(f"{role_mention}⚠️ **Round {round_num} ends in {alert_minutes} minutes!**")
            await asyncio.sleep(alert_seconds)
        else:
            await asyncio.sleep(total_seconds)

        await channel.send(f"{role_mention}⏰ **Round {round_num} time is up!** Please report any remaining results and generate next matchups.")

    @commands.command(name='finish_round')
    @checks.is_owner_or_staff()
    async def finish_round(self, ctx):
        """Manually finish the current round."""
        config = await database.get_tournament_config()
        if not config or config['status'] != 'active':
            await ctx.send("No active round to finish.")
            return
        await ctx.send("Round marked as finished. Use !make_matchups to generate next round.")

    @commands.command(name='report_result')
    @checks.is_owner_or_staff()
    async def report_result(self, ctx, matchup_id: int, winner_id: str):
        """Report the winner of a matchup."""
        winner_id = utils.parse_user_id(winner_id)
        if not winner_id:
            await ctx.send("Invalid winner ID.")
            return
        async with aiosqlite.connect(database.DB_PATH) as db:
            cursor = await db.execute("SELECT * FROM matchups WHERE id = ?", (matchup_id,))
            row = await cursor.fetchone()
            if not row:
                await ctx.send("Matchup not found.")
                return
            cols = [desc[0] for desc in cursor.description]
            matchup = dict(zip(cols, row))

        if matchup['status'] == 'completed':
            await ctx.send("This matchup is already completed.")
            return

        if winner_id not in (matchup['player1_id'], matchup['player2_id']):
            await ctx.send("Winner is not part of this matchup.")
            return

        await database.update_matchup_winner(matchup_id, str(winner_id))
        loser_id = matchup['player1_id'] if matchup['player1_id'] != str(winner_id) else matchup['player2_id']
        if loser_id:
            await database.set_player_inactive(loser_id)
        await ctx.send(f"Match {matchup_id} result recorded: <@{winner_id}> wins!")

    @commands.command(name='backup')
    @checks.is_owner_or_staff()
    async def backup(self, ctx):
        """Create a backup of the tournament database."""
        await utils.create_backup(ctx)

    @commands.command(name='status')
    @checks.is_owner_or_staff()
    async def status(self, ctx):
        """Show current tournament status."""
        config = await database.get_tournament_config()
        if not config:
            await ctx.send("No tournament initialized.")
            return
        players = await database.get_all_players()
        active_count = sum(1 for p in players if p[2] == 1)
        embed = discord.Embed(title="Tournament Status", color=discord.Color.green())
        embed.add_field(name="Status", value=config['status'], inline=True)
        embed.add_field(name="Current Round", value=config['current_round'], inline=True)
        embed.add_field(name="Players", value=f"{active_count}/{len(players)} active", inline=True)
        embed.add_field(name="Round Duration", value=f"{config['round_duration_minutes']} min", inline=True)
        embed.add_field(name="Announce Channel", value=f"<#{config['announce_channel_id']}>", inline=True)
        if config.get('announce_role_id'):
            embed.add_field(name="Announce Role", value=f"<@&{config['announce_role_id']}>", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name='list_players')
    @checks.is_owner_or_staff()
    async def list_players(self, ctx):
        """List all registered players."""
        players = await database.get_all_players()
        if not players:
            await ctx.send("No players registered.")
            return
        lines = []
        for user_id, name, is_active in players:
            status = "Active" if is_active else "Eliminated"
            lines.append(f"<@{user_id}> ({name}) - {status}")
        await ctx.send("\n".join(lines))

    @commands.command(name='list_matchups')
    @checks.is_owner_or_staff()
    async def list_matchups(self, ctx, round_number: int = None):
        """List matchups for a round. Defaults to current round."""
        config = await database.get_tournament_config()
        if round_number is None:
            round_number = config['current_round'] if config else 0
        matchups = await database.get_matchups_for_round(round_number)
        if not matchups:
            await ctx.send(f"No matchups found for round {round_number}.")
            return
        lines = []
        for m in matchups:
            p1 = f"<@{m['player1_id']}>"
            p2 = f"<@{m['player2_id']}>" if m['player2_id'] else "BYE"
            if m['status'] == 'completed':
                winner = f"<@{m['winner_id']}>" if m['winner_id'] else "?"
                lines.append(f"Match {m['id']}: {p1} vs {p2} → Winner: {winner}")
            else:
                lines.append(f"Match {m['id']}: {p1} vs {p2} [Pending]")
        await ctx.send("\n".join(lines))

async def setup(bot):
    await bot.add_cog(Staff(bot))
