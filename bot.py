import discord
from discord.ext import commands
import anthropic
import os
import httpx
import json

# ============================================================
# CONFIG - You'll fill these in with your own keys
# ============================================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")  # Custom Search Engine ID

# How long to timeout someone for cursing (in seconds)
TIMEOUT_SECONDS = 300  # 5 minutes

# Add/remove bad words here
BAD_WORDS = [
    "fuck", "shit", "ass", "bitch", "cunt", "dick", "piss",
    "bastard", "damn", "crap"
    # Add more as needed
]

# ============================================================
# BOT SETUP
# ============================================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    # Ignore bot's own messages
    if message.author.bot:
        return

    # Check for bad words
    content_lower = message.content.lower()
    found_bad_word = any(word in content_lower for word in BAD_WORDS)

    if found_bad_word:
        # Delete the message
        await message.delete()

        # Timeout the user
        try:
            import datetime
            timeout_duration = datetime.timedelta(seconds=TIMEOUT_SECONDS)
            await message.author.timeout(timeout_duration, reason="Used a bad word")
            await message.channel.send(
                f"⚠️ {message.author.mention} was timed out for {TIMEOUT_SECONDS // 60} minute(s) for using bad language.",
                delete_after=10
            )
        except discord.Forbidden:
            await message.channel.send(
                f"⚠️ {message.author.mention} used bad language! (Bot lacks permission to timeout)",
                delete_after=10
            )

    # Process commands even after automod check
    await bot.process_commands(message)

# ============================================================
# COMMANDS
# ============================================================

# --- AI Chat ---
@bot.command(name="ai")
async def ai_chat(ctx, *, question: str):
    """Ask the AI a question. Usage: !ai what is the meaning of life"""
    async with ctx.typing():
        try:
            response = claude.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=500,
                messages=[{"role": "user", "content": question}]
            )
            answer = response.content[0].text
            # Split if too long for Discord
            if len(answer) > 1900:
                answer = answer[:1900] + "..."
            await ctx.reply(f"🤖 {answer}")
        except Exception as e:
            await ctx.reply(f"❌ AI error: {str(e)}")

# --- Google Search ---
@bot.command(name="search", aliases=["google", "g"])
async def google_search(ctx, *, query: str):
    """Search Google. Usage: !search minecraft seeds"""
    async with ctx.typing():
        try:
            url = "https://www.googleapis.com/customsearch/v1"
            params = {
                "key": GOOGLE_API_KEY,
                "cx": GOOGLE_CX,
                "q": query,
                "num": 3
            }
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                data = resp.json()

            if "items" not in data:
                await ctx.reply("❌ No results found.")
                return

            embed = discord.Embed(
                title=f"🔍 Search: {query}",
                color=discord.Color.blue()
            )
            for item in data["items"][:3]:
                embed.add_field(
                    name=item["title"][:100],
                    value=f"[{item['snippet'][:150]}...]({item['link']})",
                    inline=False
                )
            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"❌ Search error: {str(e)}")

# --- Minecraft Chat Bridge ---
@bot.command(name="mc")
async def mc_status(ctx):
    """Check Minecraft server status. Usage: !mc"""
    mc_ip = os.environ.get("MC_SERVER_IP", "")
    if not mc_ip:
        await ctx.reply("❌ No Minecraft server IP configured.")
        return

    async with ctx.typing():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.mcsrvstat.us/3/{mc_ip}")
                data = resp.json()

            if data.get("online"):
                players = data.get("players", {})
                online = players.get("online", 0)
                max_p = players.get("max", 0)
                names = [p["name"] for p in players.get("list", [])]
                player_list = ", ".join(names) if names else "None"

                embed = discord.Embed(
                    title=f"🟢 {mc_ip} is Online",
                    color=discord.Color.green()
                )
                embed.add_field(name="Players", value=f"{online}/{max_p}", inline=True)
                embed.add_field(name="Online Now", value=player_list, inline=True)
                await ctx.reply(embed=embed)
            else:
                await ctx.reply(f"🔴 **{mc_ip}** is offline.")
        except Exception as e:
            await ctx.reply(f"❌ MC error: {str(e)}")

# --- Help ---
@bot.command(name="help2")
async def custom_help(ctx):
    embed = discord.Embed(title="📖 Bot Commands", color=discord.Color.purple())
    embed.add_field(name="!ai <question>", value="Ask the AI anything", inline=False)
    embed.add_field(name="!search <query>", value="Google something (!g also works)", inline=False)
    embed.add_field(name="!mc", value="Check Minecraft server status", inline=False)
    embed.add_field(name="Auto-mod", value="Bad words are auto-deleted + timeout", inline=False)
    await ctx.reply(embed=embed)

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)
