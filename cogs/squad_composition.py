import discord
from discord.ext import commands
from discord import app_commands, Interaction
from typing import Literal


class Squad_composition(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot

    @app_commands.command(
        name="select_channel",
        description="Select what Channel squad composition will be shown",
    )
    async def select_channel(
        self,
        interaction: discord.Interaction,
        type: Literal["Composition", "History", "Stats"],
        channel: discord.abc.GuildChannel,
    ):
        message_id = 0
        # User selects channel from dropdown
        if type == "Composition":
            message = await channel.send("Hello 👋")
            message_id = message.id
        channel_id = channel.id
        guild_id = channel.guild.id
        category_id = channel.category_id
        # Save the data of channel
        await self.bot.db.save_channel_data(
            guild_id=guild_id,
            category_id=category_id,
            channel_id=channel_id,
            message_id=message_id,
            type=type,
        )

        await interaction.response.send_message(
            f"✅ {type} channel set to {channel.mention}", ephemeral=True
        )

    async def update_squad_composition(self, guild):
        # Get the update channel:
        channel_data = await self.bot.db.find_channel_data(
            guild=guild, type="Composition"
        )
        game_data = await self.bot.db.get_game_data()
        print(f"This is game data: {game_data}")
        channel_id = channel_data[0]["channel"]
        message_id = channel_data[0]["message"]
        # Get channel
        channel = self.bot.get_channel(channel_id).get_partial_message(message_id)

        # Get Current squad data
        squad_data = await self.bot.db.get_squad_data(guild)

        game_title = f"{game_data["game_id"]}: {game_data["title"]} At <t:{game_data["game_date"]}:f>"
        # Create spuad composition embed
        embed = discord.Embed(
            title=game_title,
            description=game_data["description"],
            color=discord.Color.blurple(),
        )

        # Define the display order you want
        SQUAD_TYPE_ORDER = ["Commander", "Infantry", "Logistic", "Armor"]

        for side in ["Axis", "Alies"]:  # <-- watch spelling matches DB
            if side not in squad_data:
                embed.add_field(name=side.upper(), value="*No squads yet*", inline=True)
                continue

            side_text = ""

            # iterate squad types in fixed order
            for squad_type in SQUAD_TYPE_ORDER:
                if squad_type not in squad_data[side]:
                    continue

                squads = squad_data[side][squad_type]
                side_text += f"**{squad_type.upper()}**\n"

                for squad_name, players in squads.items():
                    side_text += f"*{squad_name}*\n"
                    for player, role in players.items():
                        side_text += f"• {player}\n"
                    side_text += "\n"

            # fallback if side_text stayed empty
            if not side_text.strip():
                side_text = "*No squads yet*"

            embed.add_field(name=side.upper(), value=side_text, inline=True)

        # Spacer so both columns stretch evenly
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        await channel.edit(content=None, embeds=[embed])


async def setup(bot):
    await bot.add_cog(Squad_composition(bot))
