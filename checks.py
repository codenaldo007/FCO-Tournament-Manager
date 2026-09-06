import discord
from discord.ext import commands
import config
from database import is_staff

def is_owner():
    async def predicate(ctx):
        return ctx.author.id == config.OWNER_ID
    return commands.check(predicate)

def is_owner_or_staff():
    async def predicate(ctx):
        if ctx.author.id == config.OWNER_ID:
            return True
        return await is_staff(str(ctx.author.id))
    return commands.check(predicate)
