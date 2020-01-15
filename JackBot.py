from discord.ext import commands
from httpx import AsyncClient
from glob import glob


bot = commands.Bot(command_prefix='&')
bot.httpx = AsyncClient()

cogs = [
    'ServerMirror',
    'ServerBackup'
]

for cog in cogs:
    bot.load_extension('cogs.{}'.format(cog))

@bot.event
async def on_ready():
    print('Ready.')

@bot.event
async def on_connect():
    print('Connected to Discord.')

@bot.event
async def on_message(msg):
    if msg.author.bot: return
    ctx = await bot.get_context(msg)
    await bot.invoke(ctx)

bot.run('YOUR TOKEN HERE')
