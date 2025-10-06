import discord
from discord.ext import commands
from discord import app_commands, Interaction
from datetime import datetime, timedelta


class Admin_Commands(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot

    # =============== DB HELPERS ==================
    async def get_all_squads(self):
        return await self.bot.db.get_all_squads()

    async def switch_squad_side(self, squad_id: int):
        return await self.bot.db.switch_squad_side(squad_id)

    async def remove_squad(self, squad_id: int):
        return await self.bot.db.remove_squad(squad_id)

    async def get_current_game(self):
        return await self.bot.db.get_current_game()

    async def update_game(self, title: str, time_unix: int, description: str):
        return await self.bot.db.update_game_data(title, time_unix, description)

    async def finish_current_game(self):
        print("Finnis game")
        squad_cog = self.bot.get_cog("Stats_manager")
        if squad_cog is not None:
            await squad_cog.update_stats()

    async def create_next_game(self, time: str):
        return await self.bot.db.create_next_game(time)

    async def update_squad_composition(self, guild_id):
        squad_cog = self.bot.get_cog("Squad_composition")
        print("squad update")
        if squad_cog is not None:
            await squad_cog.update_squad_composition(guild_id)

    # =============== ACTION MENU ==================
    class AdminActionView(discord.ui.View):
        def __init__(self, cog, user: discord.User):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        @discord.ui.select(
            placeholder="Choose an action...",
            options=[
                discord.SelectOption(label="Edit Squad", value="edit_squad"),
                discord.SelectOption(label="Edit Game", value="edit_game"),
                discord.SelectOption(label="Next Game", value="next_game"),
            ],
        )
        async def select_action(
            self, interaction: Interaction, select: discord.ui.Select
        ):
            action = select.values[0]

            if action == "edit_squad":
                squads = await self.cog.get_all_squads()
                if not squads:
                    await interaction.response.edit_message(
                        content="No squads found.", view=None
                    )
                    return
                await interaction.response.edit_message(
                    content="Select a squad to edit:",
                    view=self.cog.SquadSelectView(self.cog, interaction.user, squads),
                )

            elif action == "edit_game":
                current_game = await self.cog.get_current_game()
                if not current_game:
                    await interaction.response.edit_message(
                        content="No active game found.", view=None
                    )
                    return

                # Launch modal with prefilled current game data
                await interaction.response.send_modal(
                    self.cog.EditGameModal(self.cog, current_game)
                )

            elif action == "next_game":
                await interaction.response.edit_message(
                    content="Confirm creating next game?",
                    view=self.cog.ConfirmNextGameView(self.cog, interaction.user),
                )

    # =============== EDIT SQUAD ==================
    class SquadSelectView(discord.ui.View):
        def __init__(self, cog, user, squads):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user
            options = [
                discord.SelectOption(
                    label=f"{s['name']}",
                    description=f"Side: {s.get('side', 'Unknown')}",
                    value=str(s["id"]),
                )
                for s in squads
            ]
            self.add_item(Admin_Commands.SquadDropdown(self, options))

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

    class SquadDropdown(discord.ui.Select):
        def __init__(self, outer, options):
            super().__init__(placeholder="Select a squad...", options=options)
            self.outer = outer

        async def callback(self, interaction: Interaction):
            squad_id = int(self.values[0])
            await interaction.response.edit_message(
                content=f"Selected squad ID: {squad_id}",
                view=Admin_Commands.SquadActionView(self.outer.cog, squad_id),
            )

    class SquadActionView(discord.ui.View):
        def __init__(self, cog, squad_id: int):
            super().__init__(timeout=120)
            self.cog = cog
            self.squad_id = squad_id

        @discord.ui.button(label="Switch Side", style=discord.ButtonStyle.primary)
        async def switch_side(
            self, interaction: Interaction, button: discord.ui.Button
        ):
            result = await self.cog.switch_squad_side(self.squad_id)
            guild_id = interaction.guild.id
            await self.cog.update_squad_composition(guild_id)
            await interaction.response.edit_message(content=result, view=None)

        @discord.ui.button(label="Remove Squad", style=discord.ButtonStyle.danger)
        async def remove_squad(
            self, interaction: Interaction, button: discord.ui.Button
        ):
            result = await self.cog.remove_squad(self.squad_id)
            guild_id = interaction.guild.id
            await self.cog.update_squad_composition(guild_id)
            await interaction.response.edit_message(content=result, view=None)

    # =============== EDIT GAME MODAL ==================
    class EditGameModal(discord.ui.Modal, title="Edit Current Game"):
        def __init__(self, cog, current_game):
            super().__init__()
            self.cog = cog
            self.current_game = current_game

            # Pre-fill inputs from current DB values
            self.title_input = discord.ui.TextInput(
                label="Game Title",
                default=current_game.get("title", ""),
                required=False,
            )

            self.time_input = discord.ui.TextInput(
                label="Game Time (Unix Timestamp)",
                default=str(current_game.get("time", "")),
                required=False,
                placeholder="Example: 1728841200",
            )

            self.desc_input = discord.ui.TextInput(
                label="Description",
                default=current_game.get("description", ""),
                style=discord.TextStyle.paragraph,
                required=False,
            )

            self.add_item(self.title_input)
            self.add_item(self.time_input)
            self.add_item(self.desc_input)

        async def on_submit(self, interaction: Interaction):
            # Retrieve old values for fallback
            old_title = self.current_game.get("title", "")
            old_time = self.current_game.get("time", "")
            old_desc = self.current_game.get("description", "")

            # Merge old data with new edits
            new_title = self.title_input.value.strip() or old_title
            new_desc = self.desc_input.value.strip() or old_desc

            # Validate timestamp (if changed)
            if self.time_input.value.strip():
                try:
                    new_time = int(self.time_input.value.strip())
                except ValueError:
                    await interaction.response.send_message(
                        "❌ Invalid timestamp. Please use a valid Unix time (integer).",
                        ephemeral=True,
                    )
                    return
            else:
                new_time = old_time

            # Update DB
            result = await self.cog.update_game(
                title=new_title,
                time_unix=new_time,
                description=new_desc,
            )

            guild_id = interaction.guild.id
            await self.cog.update_squad_composition(guild_id)
            await interaction.response.edit_message(
                content=(
                    f"✅ Game updated:\n"
                    f"**Title:** {new_title}\n"
                    f"**Time:** <t:{new_time}:F>\n"
                    f"**Description:** {new_desc or '*No description*'}"
                ),
                view=None,
            )

    # =============== NEXT GAME CONFIRMATION ==================
    class ConfirmNextGameView(discord.ui.View):
        def __init__(self, cog, user):
            super().__init__(timeout=60)
            self.cog = cog
            self.user = user

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
        async def confirm(self, interaction: Interaction, button: discord.ui.Button):
            current = await self.cog.get_current_game()
            if not current:
                await interaction.response.edit_message(
                    content="No current game found.", view=None
                )
                return

            # Current["time"] is stored as an integer Unix timestamp
            try:
                current_time = int(current["time"])
            except (ValueError, TypeError):
                await interaction.response.edit_message(
                    content="❌ Invalid time format in DB.", view=None
                )
                return

            # Add +1 week (604800 seconds)
            next_time_unix = current_time + 604800
            guild_id = interaction.guild.id
            # Mark current game finished and create the next one
            await self.cog.finish_current_game()
            result = await self.cog.create_next_game(next_time_unix)
            await self.cog.update_squad_composition(guild_id)

            await interaction.response.edit_message(
                content=f"✅ {result}\nNew game scheduled for <t:{next_time_unix}:F>",
                view=None,
            )

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)
        async def cancel(self, interaction: Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="❌ Cancelled.", view=None)

    # =============== COMMANDS ===============
    @app_commands.command(
        name="admin", description="Admin control panel for managing games and squads"
    )
    async def admin(self, interaction: Interaction):
        view = self.AdminActionView(self, interaction.user)
        await interaction.response.send_message(
            "What do you want to do?",
            view=view,
            ephemeral=True,
        )


async def setup(bot):
    await bot.add_cog(Admin_Commands(bot))
