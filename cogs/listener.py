from discord.ext import commands


class listener(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot

    # Checkes whenever someone joins the server:

    @commands.Cog.listener()
    async def on_member_join(self, member):
        print(f"member joined: {member}")


async def setup(bot):
    await bot.add_cog(listener(bot))
