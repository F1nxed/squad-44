import discord
from discord.ext import commands
from discord import app_commands, Interaction
from typing import Literal, Optional


class Squad_manager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.categories = {
            "Infantry": [
                "Radio Man",
                "Rifle Man",
                "Medic",
                "Machine Gunner",
                "Sniper",
                "Light Anti-Tank",
                "Sapper",
                "Grenadier",
                "Mortarman",
            ],
            "Logistic": [
                "Radio Man",
                "Rifle Man",
                "Medic",
                "Combat Engineer Anti Personel",
                "Combat Engineer Anti Tank",
                "Combat Engineer High Explosive",
            ],
            "Armor": ["Tanker"],
        }

    # =============== DB HELPERS ==================

    async def add_squad_member(
        # Sends to the DB to add a mamaber to the owners squad
        self,
        owner: int,
        squad: str,
        role: str,
        player_id: Optional[int],
        nickname: Optional[str],
        guild_id: Optional[int],
    ):
        result = await self.bot.db.add_squad_member(
            owner=owner,
            squad=squad,
            role=role,
            player=player_id,
            nickname=nickname,
        )
        if guild_id:
            squad_cog = self.bot.get_cog("Squad_composition")
            if squad_cog is not None:
                await squad_cog.update_squad_composition(guild_id)
        return result

    async def edit_squad_member_role(
        self, owner: int, player_id: str, new_role: str, guild_id: Optional[int]
    ):
        # Change the Role of a member of the squad
        result = await self.bot.db.edit_squad_member(
            owner=owner, player_id=player_id, new_role=new_role
        )
        if guild_id:
            squad_cog = self.bot.get_cog("Squad_composition")
            if squad_cog is not None:
                await squad_cog.update_squad_composition(guild_id)
        return result

    async def remove_squad_member(
        self, owner: int, player_id: str, guild_id: Optional[int]
    ):
        # Removes a Member of the owners squad
        result = await self.bot.db.remove_squad_member(owner=owner, player_id=player_id)
        if guild_id:
            squad_cog = self.bot.get_cog("Squad_composition")
            if squad_cog is not None:
                await squad_cog.update_squad_composition(guild_id)
        return result

    async def get_user_squad_type(self, user_id: int):
        # Check what squad type the owner has so he can get the proper options
        return await self.bot.db.get_squad_type(user_id)

    async def get_squad_members(self, user_id: int):
        # Checks what members and Role are enlisted in owners squad
        return await self.bot.db.get_squad_members(user_id)

    # =============== PLAYER ADD VIEWS ==================

    class AddExternalPlayerModal(discord.ui.Modal, title="Add External Player"):
        # Handles a popup to add someone not using @ player for external players
        def __init__(self, cog, category: str, role: str):
            super().__init__()
            self.cog = cog
            self.category = category
            self.role = role

            self.player_name = discord.ui.TextInput(
                label="Player name",
                placeholder="Type player name (not on Discord)...",
                required=True,
                max_length=64,
            )
            self.add_item(self.player_name)

        async def on_submit(self, interaction: Interaction):
            owner_id = interaction.user.id
            answer = await self.cog.add_squad_member(
                owner=owner_id,
                squad=self.category,
                role=self.role,
                player_id=self.player_name.value,
                nickname=self.player_name.value,
                guild_id=interaction.guild.id,
            )
            await interaction.response.edit_message(content=answer, view=None)

    class AddPlayerPickerView(discord.ui.View):
        # Gets a dropdown list of all members in the discord
        # For easy selection of squad members
        def __init__(self, cog, user: discord.User, category: str, role: str):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user
            self.category = category
            self.role = role

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        @discord.ui.select(
            cls=discord.ui.UserSelect,
            placeholder="Pick a Discord user...",
            min_values=1,
            max_values=1,
        )
        async def pick_user(
            self, interaction: Interaction, select: discord.ui.UserSelect
        ):
            member = select.values[0]
            if isinstance(member, discord.User):
                member = interaction.guild.get_member(member.id) or member

            nickname = getattr(member, "Nickname", None) or member.display_name
            answer = await self.cog.add_squad_member(
                owner=self.user.id,
                squad=self.category,
                role=self.role,
                player_id=member.id,
                nickname=nickname,
                guild_id=interaction.guild.id,
            )
            await interaction.response.edit_message(content=answer, view=None)

        # Button for popup of external
        @discord.ui.button(
            label="Add external name", style=discord.ButtonStyle.secondary
        )
        async def add_external(self, interaction: Interaction, _: discord.ui.Button):
            await interaction.response.send_modal(
                self.cog.AddExternalPlayerModal(self.cog, self.category, self.role)
            )

    # =============== ACTION MENU ==================

    class SquadActionView(discord.ui.View):
        def __init__(self, cog, user: discord.User):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        # First options after running the /Suqad
        @discord.ui.select(
            placeholder="Choose an action...",
            options=[
                discord.SelectOption(label="Add Squad Member", value="add"),
                discord.SelectOption(label="Edit Squad Member", value="edit"),
                discord.SelectOption(label="Remove Squad Member", value="remove"),
            ],
        )
        async def select_action(
            self, interaction: Interaction, select: discord.ui.Select
        ):
            action = select.values[0]

            if action == "add":
                category = await self.cog.get_user_squad_type(interaction.user.id)
                roles = self.cog.categories[category]
                await interaction.response.edit_message(
                    content="Choose what role the new player shall have:",
                    view=self.cog.SquadRoleView(
                        self.cog, self.user, action, category, roles
                    ),
                )

            elif action == "edit":
                players = await self.cog.get_squad_members(interaction.user.id)
                await interaction.response.edit_message(
                    content="Choose what player to change role for:",
                    view=self.cog.PlayerSelectView(
                        self.cog, self.user, "edit", players
                    ),
                )

            elif action == "remove":
                players = await self.cog.get_squad_members(interaction.user.id)
                await interaction.response.edit_message(
                    content="Choose what player to remove from your squad:",
                    view=self.cog.PlayerSelectView(
                        self.cog, self.user, "remove", players
                    ),
                )

    class SquadRoleView(discord.ui.View):
        def __init__(
            self,
            cog,
            user: discord.User,
            action: str,
            category: str,
            roles: list[str],
            player_id: Optional[str] = None,  # pass player_id when editing
        ):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user
            self.action = action
            self.category = category
            self.player_id = player_id

            options = [discord.SelectOption(label=r, value=r) for r in roles]
            self.add_item(self.RoleSelect(self, options))

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        class RoleSelect(discord.ui.Select):
            def __init__(self, outer, options):
                super().__init__(placeholder="Choose a role...", options=options)
                self.outer = outer

            async def callback(self, interaction: Interaction):
                role = self.values[0]
                if self.outer.action == "add":
                    await interaction.response.edit_message(
                        content="Select a player to add:",
                        view=self.outer.cog.AddPlayerPickerView(
                            self.outer.cog, interaction.user, self.outer.category, role
                        ),
                    )
                elif self.outer.action == "edit":
                    # Actually perform the role update here
                    result = await self.outer.cog.edit_squad_member_role(
                        owner=interaction.user.id,
                        player_id=self.outer.player_id,
                        new_role=role,
                        guild_id=interaction.guild.id,
                    )
                    await interaction.response.edit_message(content=result, view=None)

    class PlayerSelectView(discord.ui.View):
        def __init__(
            self,
            cog,
            user: discord.User,
            action: str,
            players: list[tuple[str, str, str]],
        ):
            super().__init__(timeout=120)
            self.cog = cog
            self.user = user
            self.action = action
            # players expected: (player_id, nickname, role)
            options = [
                discord.SelectOption(label=f"{nickname} ({role})", value=str(player_id))
                for player_id, nickname, role in players
            ]
            self.add_item(self.PlayerSelect(self, options))

        async def interaction_check(self, interaction: Interaction) -> bool:
            return interaction.user.id == self.user.id

        class PlayerSelect(discord.ui.Select):
            def __init__(self, outer, options):
                super().__init__(placeholder="Choose a player...", options=options)
                self.outer = outer

            async def callback(self, interaction: Interaction):
                player_id = self.values[0]
                action = self.outer.action

                if action == "edit":
                    # Ask which new role
                    category = await self.outer.cog.get_user_squad_type(
                        interaction.user.id
                    )
                    roles = self.outer.cog.categories[category]
                    await interaction.response.edit_message(
                        content="Choose new role for this member:",
                        view=self.outer.cog.SquadRoleView(
                            self.outer.cog,
                            self.outer.user,
                            "edit",
                            category,
                            roles,
                            player_id=player_id,  # <-- pass the player being edited
                        ),
                    )
                elif action == "remove":
                    result = await self.outer.cog.remove_squad_member(
                        self.outer.user.id, player_id, guild_id=interaction.guild.id
                    )
                    await interaction.response.edit_message(content=result, view=None)
                else:
                    await interaction.response.edit_message(
                        content="Unknown action", view=None
                    )

    # ========= COMMANDS =========
    @app_commands.command(name="squad", description="Manage your squad")
    async def squad(self, interaction: Interaction):
        # Check that person has a squad first
        answer = await self.bot.db.check_if_has_squad(interaction.user.id)
        print(answer)
        if answer:
            view = self.SquadActionView(self, interaction.user)
            await interaction.response.send_message(
                "What do you want to do?",
                view=view,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                "You donot have a Squad",
                ephemeral=True,
            )

    @app_commands.command(name="add_squad", description="Add a Squad to the signup")
    async def add_squad(
        self,
        interaction: Interaction,
        squad: Literal["Commander", "Infantry", "Logistic", "Armor"],
        name: str,
    ):

        squad_leader = interaction.user.id
        nickname = interaction.user.name
        print(f"Check if Nickname works: {nickname}")
        answer = await self.bot.db.check_if_has_squad(squad_leader)

        if not answer:
            answer = await self.bot.db.create_squad(
                user=squad_leader, squad=squad, name=name, nickname=nickname
            )
            squad_cog = self.bot.get_cog("Squad_composition")
            guild_id = interaction.guild.id
            if squad_cog is not None:
                await squad_cog.update_squad_composition(guild_id)

            await interaction.response.send_message(answer)
        else:
            await interaction.response.send_message("You already have a squad")

    @app_commands.command(
        name="remove_squad", description="Remove your squad and all members"
    )
    async def remove_squad(self, interaction: Interaction):
        user_id = interaction.user.id
        guild_id = interaction.guild.id

        has_squad = await self.bot.db.check_if_has_squad(user_id)
        if not has_squad:
            await interaction.response.send_message(
                "You don’t currently own a squad.",
                ephemeral=True,
            )
            return

        # Perform deletion in DB
        result = await self.bot.db.remove_squad_and_members(user_id)

        # Update composition view
        squad_cog = self.bot.get_cog("Squad_composition")
        if squad_cog is not None:
            await squad_cog.update_squad_composition(guild_id)

        await interaction.response.send_message(result, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Squad_manager(bot))
