from discord.ext import commands
import discord
from discord import app_commands, Interaction


class Stats_manager(commands.Cog):

    def __init__(self, bot) -> None:
        self.bot = bot

    async def update_stats(self):
        print("Running update on player stats")
        # Need all players that was in game.. their ID and Messplayer_stats
        players = await self.bot.db.get_active_players()
        for player_id, message_id, thread_id, player_nickname, discord_id in players:
            if discord_id is None:
                continue
            if message_id is None:
                # Create a Forum post:
                await self.create_post(
                    player_id=player_id, player_nickname=player_nickname
                )
            else:
                # Update exisitng Forum Post:
                await self.update_post(
                    player_id=player_id,
                    message_id=message_id,
                    thread_id=thread_id,
                    player_nickname=player_nickname,
                )

    async def create_post(self, player_id, player_nickname):
        # Get channel ID Figure out something better to get the guild ID
        channel_data = await self.bot.db.find_channel_data(
            guild=1378393725256077322, type="Stats"
        )
        channel_id = channel_data[0]["channel"]
        channel = self.bot.get_channel(channel_id)
        # Get Player Name to set title of the Thread
        post = await channel.create_thread(
            name=f"{player_nickname}'s stats",
            content="Games played: 0\nRoles: None yet.",
        )
        # Get the channel and Post ID
        thread_id = post.thread.id
        message_id = post.message.id
        # Save it to the database
        await self.bot.db.save_player_thread(player_id, thread_id, message_id)

        # Send it to be updated in Discord
        await self.update_post(
            player_id=player_id, message_id=message_id, thread_id=thread_id
        )

    async def update_post(self, player_id, message_id, thread_id, player_nickname):
        try:
            thread = self.bot.get_channel(thread_id)
            print(f"Thread: {thread}")
            msg = await thread.fetch_message(message_id)
            print(f"Message: {msg}")
        except Exception as arg:
            print(arg)
            await self.create_post(player_id=player_id, player_name=player_nickname)
        # Use player_id to get all relevant data yes
        games_played = await self.bot.db.games_played(player_id)
        print(games_played)
        squads_played = await self.bot.db.squads_played(player_id)
        print(squads_played)
        roles_played = await self.bot.db.roles_played(player_id)
        print(roles_played)
        sides_played = await self.bot.db.sides_played(player_id)
        print(sides_played)

        squad_text = "\n".join(f"{t} – {c}" for t, c in squads_played) or "None"
        role_text = "\n".join(f"{r} – {c}" for r, c in roles_played) or "None"
        side_text = "\n".join(f"{s} – {c}" for s, c in sides_played) or "None"

        embed = discord.Embed(
            title=f"Player Stats", description=f"Games played: **{games_played}**"
        )
        embed.add_field(name="Squad Types", value=squad_text, inline=False)
        embed.add_field(name="Roles", value=role_text, inline=False)
        embed.add_field(name="Sides", value=side_text, inline=False)

        await msg.edit(content=None, embed=embed)


async def setup(bot):
    await bot.add_cog(Stats_manager(bot))
