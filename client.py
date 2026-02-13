import discord
from discord.ext import commands
from database import Database
import os
import create_db


# Setting command Prefix and setting the Intents
class Client(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.db: Database | None = None

    async def on_ready(self):
        # Set Bot acctivity "Playing Squad 44"
        activity = discord.Activity(
            type=discord.ActivityType.watching, name="The frontlines"
        )
        await self.change_presence(activity=activity)
        # Sync all the / commands
        await self.tree.sync()
        # Informing User that the Bot is ready and online
        print("Bot is now ready for use! \n")

    async def load_cogs(self):
        # Loading all the Cogs
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded Cog: {filename[:-3]}")
        else:
            print(f"Unable to load. ({filename[:-3]})")

    async def setup_hook(self):
        # Init database once
        self.db = Database("data.db")
        await self.db.connect()
        # Set up tables if not exist
        await self.create_tables()
        # Load all cogs
        await self.load_cogs()

    async def create_tables(self):
        # Example: basic users table
        await self.db.conn.executescript(create_db.data)

        await self.db.conn.commit()

    async def close(self):
        # close db when bot stops
        if self.db:
            await self.db.close()
        await super().close()
