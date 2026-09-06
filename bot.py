import discord
from discord.ext import commands
import asyncio
import logging
import config
import database

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True  # Required for reading message content (commands)
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    await database.init_db()
    # Load cogs
    await bot.load_extension('cogs.owner')
    await bot.load_extension('cogs.staff')
    await bot.load_extension('cogs.public')
    print('Cogs loaded.')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You do not have permission to use this command.")
        return
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"Missing required argument: {error.param.name}")
        return
    if isinstance(error, commands.BadArgument):
        await ctx.send(f"Invalid argument: {error}")
        return
    # Log other errors
    logging.error(f"Command error in {ctx.command}: {error}")
    await ctx.send("An error occurred while processing the command.")

if __name__ == "__main__":
    if not config.TOKEN:
        raise ValueError("DISCORD_BOT_TOKEN environment variable not set.")
    bot.run(config.TOKEN)
