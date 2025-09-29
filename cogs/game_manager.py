from discord.ext import commands
from discord import app_commands, Interaction


class Game_manager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(name="add_game", description="Add a game to signups")
    async def add_game(
        self, interaction: Interaction, date: str, title: str, description: str
    ):
        # Remove Discord timestamp
        if str(date):
            unix_time = int(date.split(":")[1])
        # Make sure that the timestamp is an Interger
        # Need to add the call for the stats_manager before adding
        # This will trigger the making of player service records..
        # would be good idea to make sure that peeople have the correct
        # members signed up
        if int(unix_time):
            print(unix_time)
            answer = await self.bot.db.add_game(unix_time, title, description)
        if answer:
            squad_cog = self.bot.get_cog("Squad_composition")
            guild_id = interaction.guild.id
            if squad_cog is not None:
                await squad_cog.update_squad_composition(guild_id)
            await interaction.response.send_message("Game date updated")
        else:
            await interaction.response.send_message("Failed to update gamedate")


async def setup(bot):
    await bot.add_cog(Game_manager(bot))
