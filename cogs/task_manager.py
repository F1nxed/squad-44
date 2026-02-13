from discord.ext import commands, tasks
from datetime import datetime
import time
import os
import asyncio
import json
import aiohttp

from openai import OpenAI


class Task_manager(commands.Cog):
    def __init__(self, bot) -> None:
        self.bot = bot
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Cache so we generate once per day
        self._cached_date_key = None
        self._cached_report = (
            None  # dict with keys: "sitrep", "image", "image_page", "image_title"
        )

        # For "since last report" continuity (even within a day)
        self._last_sitrep_text = None

    def cog_unload(self):
        self.task.cancel()

    async def cog_load(self):
        """Runs when cog is fully loaded and bot is ready."""
        if not self.task.is_running():
            self.task.start()

    async def get_scheduled_times(self):
        # Fetch times (HH:MM) from your DB cog
        target_time = await self.bot.db.get_times()
        # target_time = ["10:15"]
        return target_time

    def _date_key_and_year(self):
        today_str = datetime.now().strftime("%B %d")
        year = int(datetime.now().strftime("%Y")) - 86
        date_key = f"{today_str} {year}"
        return date_key, today_str, year

    async def _openai_generate_sitrep_json(self, today_str: str, year: int) -> dict:
        """
        Generate a structured SITREP + suggested image search query in JSON.
        We call OpenAI in a thread to avoid blocking the event loop.
        """
        date_line = f"{today_str} {year}"
        yesterday_context = self._last_sitrep_text or ""

        system = (
            "You write detailed 'On This Day in WWII' frontline reports. "
            "Focus on front lines, geography, and military activity. "
            "If no confirmed territorial movement is known for the specific date, say so explicitly, "
            "but still describe where the fronts are and what actions occurred. "
            "Avoid repeating phrasing from earlier reports; vary what you emphasize. "
            "Never invent precise numeric kilometer gains unless you are confident; prefer qualitative wording."
        )

        # Ask for strict JSON so we can parse it reliably
        user = (
            f"DATE: {date_line}\n\n"
            "Return STRICT JSON only (no backticks, no extra text) with this schema:\n"
            "{\n"
            '  "sitrep": string,\n'
            '  "image_query": string\n'
            "}\n\n"
            "'On This Day in WWII' report requirements (180–260 words):\n"
            "Use exactly these section headers:\n"
            "1) Active Fronts Today\n"
            "2) Frontline Snapshot\n"
            "3) Movement Since Last Report\n"
            "4) Notable Actions\n"
            "Rules:\n"
            "- Name 6+ specific places total (cities, rivers, regions, lines).\n"
            "- Movement section: if you cannot confirm changes, say 'no confirmed movement reported' but still describe pressure points.\n"
            "- If uncertain about a claim, label it 'reported' or 'likely'.\n"
            "- 'image_query' should be a Wikimedia-Commons-friendly search query for a relevant MAP or operational diagram for this date/theater.\n"
        )

        if yesterday_context:
            user += f"\n\nLAST REPORT (for continuity, compare against it):\n{yesterday_context}\n"

        def _call():
            return self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.3,
            )

        resp = await asyncio.to_thread(_call)
        raw = resp.choices[0].message.content.strip()

        # Parse JSON with a small fallback (sometimes models prepend whitespace/newlines—fine)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Very small rescue: try to extract first {...} block
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(raw[start : end + 1])
            else:
                # Final fallback: treat all as sitrep
                data = {
                    "sitrep": raw,
                    "image_query": f"World War II {year} map front lines",
                }

        # Ensure keys exist
        data.setdefault("sitrep", "")
        data.setdefault("image_query", f"World War II {year} map front lines")
        return data

    async def _wikimedia_commons_image_search(self, query: str) -> dict | None:
        """
        Search Wikimedia Commons for a File: matching query and return an image URL + page.
        Uses the MediaWiki API. Returns None if nothing found.
        """
        api_url = "https://commons.wikimedia.org/w/api.php"
        params = {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": "6",  # File namespace
            "gsrlimit": "1",
            "prop": "imageinfo|info",
            "inprop": "url",
            "iiprop": "url",
            "iiurlwidth": "900",
            "redirects": "1",
            "origin": "*",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, params=params, timeout=12) as r:
                    if r.status != 200:
                        return None
                    payload = await r.json()

            pages = payload.get("query", {}).get("pages", {})
            if not pages:
                return None

            page = next(iter(pages.values()))
            title = page.get("title")
            page_url = (
                page.get("fullurl") or page.get("canonicalurl") or page.get("url")
            )

            imageinfo = page.get("imageinfo") or []
            if not imageinfo:
                return None
            thumb_url = imageinfo[0].get("thumburl") or imageinfo[0].get("url")
            if not thumb_url:
                return None

            return {
                "image": thumb_url,
                "image_page": page_url
                or f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}",
                "image_title": title,
            }
        except Exception:
            return None

    async def get_ww2_sitrep_with_image(self) -> dict:
        """
        Returns dict with keys:
        - sitrep (text)
        - image (url or None)
        - image_page (url or None)
        - image_title (str or None)
        """
        date_key, today_str, year = self._date_key_and_year()

        # Use daily cache
        if self._cached_date_key == date_key and self._cached_report:
            return self._cached_report

        data = await self._openai_generate_sitrep_json(today_str, year)

        sitrep = (data.get("sitrep") or "").strip()
        image_query = (data.get("image_query") or "").strip()

        img = await self._wikimedia_commons_image_search(image_query)
        report = {
            "sitrep": (
                sitrep if sitrep else f"(No SITREP text generated for {date_key}.)"
            ),
            "image": img["image"] if img else None,
            "image_page": img["image_page"] if img else None,
            "image_title": img["image_title"] if img else None,
            "date_key": date_key,
            "image_query": image_query,
        }

        # Update caches
        self._cached_date_key = date_key
        self._cached_report = report
        self._last_sitrep_text = report["sitrep"]

        return report

    @tasks.loop(minutes=1)
    async def task(self):
        now_seconds = int(time.time())
        try:
            times = await self.get_scheduled_times()
            for scheduled in times:
                target_time = datetime.strptime(scheduled, "%H:%M").replace(
                    year=datetime.now().year,
                    month=datetime.now().month,
                    day=datetime.now().day,
                )
                target_seconds = int(target_time.timestamp())

                if abs(now_seconds - target_seconds) <= 30:
                    guilds = await self.bot.db.get_guilds()
                    report = await self.get_ww2_sitrep_with_image()
                    date_key = report.get("date_key", "")
                    sitrep = report.get("sitrep", "")
                    image_url = report.get("image")
                    image_page = report.get("image_page")

                    for guild in guilds:
                        channel_data = await self.bot.db.find_channel_data(
                            guild=guild, type="History"
                        )
                        channel_id = channel_data[0]["channel"]
                        channel = self.bot.get_channel(channel_id)

                        if channel is None:
                            continue

                        # Build an embed if possible
                        try:
                            import discord

                            embed = discord.Embed(
                                title=f"📜 On This Day in WWII — {date_key}",
                                description=sitrep,
                            )
                            if image_url:
                                embed.set_image(url=image_url)
                                if image_page:
                                    embed.add_field(
                                        name="Map / Image source",
                                        value=image_page,
                                        inline=False,
                                    )
                            msg = await channel.send(embed=embed)
                        except Exception:
                            # Fallback: plain message
                            extra = f"\nMap/Image: {image_page}" if image_page else ""
                            msg = await channel.send(
                                f"📜 On This Day in WWII — {date_key}\n{sitrep}{extra}"
                            )

                        if hasattr(channel, "is_news") and channel.is_news():
                            await msg.publish()

                        await asyncio.sleep(1)

        except Exception as e:
            print(f"[Task error] {e}")


async def setup(client):
    await client.add_cog(Task_manager(client))
