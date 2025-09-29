from discord.ext import commands, tasks
from datetime import datetime
import time
import os
import asyncio
from openai import OpenAI


class Task_manager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def cog_unload(self):
        self.task.cancel()

    async def cog_load(self):
        """Runs when cog is fully loaded and bot is ready."""
        if not self.task.is_running():
            self.task.start()

    async def get_scheduled_times(self):
        # Fetch times (HH:MM) from your DB cog
        return await self.bot.db.get_times()

    async def get_ww2_summary(self):
        today = datetime.now().strftime("%B %d")
        year = int(datetime.now().strftime("%Y")) - 86
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Tell me what happened on {today} {year} during World War II. "
                        f"Make it semi-detailed: around 2–3 paragraphs or up to 200 words. "
                        f"Include the key battles, political events, or notable outcomes."
                    ),
                }
            ],
        )
        return response.choices[0].message.content

    @tasks.loop(minutes=1)
    async def task(self):
        now_seconds = int(time.time())
        try:
            times = await self.get_scheduled_times()
            for scheduled in times:
                # Convert scheduled time to today’s timestamp
                target_time = datetime.strptime(scheduled, "%H:%M").replace(
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day,
                )
                target_seconds = int(target_time.timestamp())

                if abs(now_seconds - target_seconds) <= 30:
                    # Need to remove this hardcoded guild ID for future references..
                    # maybe add it to schedules?
                    guild_id = 643457260030394387
                    channel_data = await self.bot.db.find_channel_data(
                        guild=guild_id, type="History"
                    )
                    channel_id = channel_data[0]["channel"]
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        summary = await self.get_ww2_summary()
                        await channel.send(f"📜 On this day in WWII:\n{summary}")
        except Exception as e:
            print(f"[Task error] {e}")


async def setup(client):
    await client.add_cog(Task_manager(client))
