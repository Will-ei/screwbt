import discord
from discord.ext import commands
import os
import httpx
import datetime

# ============================================================
# CONFIG
# ============================================================
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TIMEOUT_SECONDS = 300  # 5 minutes

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

# ============================================================
# HELPERS
# ============================================================
async def ask_groq(question: str) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama3-8b-8192",
                "messages": [{"role": "user", "content": question}],
                "max_tokens": 500
            },
            timeout=20
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"]

async def duckduckgo_search(query: str):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=10
        )
        return resp.json()

# ============================================================
# EVENTS
# ============================================================
@bot.event
async def on_ready():
    print(f"✅ Bot is online as {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    content_lower = message.content.lower()
    found_bad_word = any(word in content_lower for word in BAD_WORDS)

    if found_bad_word:
        await message.delete()
        try:
            timeout_duration = datetime.timedelta(seconds=TIMEOUT_SECONDS)
            await message.author.timeout(timeout_duration, reason="Used a bad word")
            await message.channel.send(
                f"⚠️ {message.author.mention} was timed out for {TIMEOUT_SECONDS // 60} minute(s) for using bad language.",
                delete_after=10
            )
        except discord.Forbidden:
            await message.channel.send(
                f"⚠️ {message.author.mention} used bad language! (Bot lacks timeout permission)",
                delete_after=10
            )

    await bot.process_commands(message)

# ============================================================
# COMMANDS
# ============================================================

# --- AI Chat (Groq - free) ---
@bot.command(name="ai")
async def ai_chat(ctx, *, question: str):
    """Ask the AI a question. Usage: !ai what is the meaning of life"""
    async with ctx.typing():
        try:
            answer = await ask_groq(question)
            if len(answer) > 1900:
                answer = answer[:1900] + "..."
            await ctx.reply(f"🤖 {answer}")
        except Exception as e:
            await ctx.reply(f"❌ AI error: {str(e)}")

# --- DuckDuckGo Search (no API key needed) ---
@bot.command(name="search", aliases=["s", "ddg"])
async def search(ctx, *, query: str):
    """Search the web. Usage: !search minecraft best seeds"""
    async with ctx.typing():
        try:
            data = await duckduckgo_search(query)

            embed = discord.Embed(
                title=f"🔍 {query}",
                color=discord.Color.orange()
            )

            # Abstract (main answer if exists)
            if data.get("AbstractText"):
                embed.add_field(
                    name=data.get("Heading", "Answer"),
                    value=data["AbstractText"][:300],
                    inline=False
                )
                if data.get("AbstractURL"):
                    embed.add_field(name="Source", value=data["AbstractURL"], inline=False)

            # Related topics
            topics = data.get("RelatedTopics", [])[:3]
            for topic in topics:
                if "Text" in topic and "FirstURL" in topic:
                    embed.add_field(
                        name="🔗 Related",
                        value=f"[{topic['Text'][:100]}]({topic['FirstURL']})",
                        inline=False
                    )

            if not embed.fields:
                embed.description = "No results found. Try different keywords."

            await ctx.reply(embed=embed)

        except Exception as e:
            await ctx.reply(f"❌ Search error: {str(e)}")

# --- Minecraft Server Status ---
@bot.command(name="mc")
async def mc_status(ctx):
    """Check Minecraft server status. Usage: !mc"""
    mc_ip = os.environ.get("MC_SERVER_IP", "")
    if not mc_ip:
        await ctx.reply("❌ No Minecraft server IP set. Add MC_SERVER_IP to your environment variables.")
        return

    async with ctx.typing():
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://api.mcsrvstat.us/3/{mc_ip}", timeout=10)
                data = resp.json()

            if data.get("online"):
                players = data.get("players", {})
                online = players.get("online", 0)
                max_p = players.get("max", 0)
                names = [p["name"] for p in players.get("list", [])]
                player_list = ", ".join(names) if names else "No one online"

                embed = discord.Embed(title=f"🟢 {mc_ip} is Online", color=discord.Color.green())
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
    embed.add_field(name="!ai <question>", value="Ask the AI anything (powered by Groq, free)", inline=False)
    embed.add_field(name="!search <query>", value="Search the web with DuckDuckGo (!s also works)", inline=False)
    embed.add_field(name="!mc", value="Check Minecraft server status + who's online", inline=False)
    embed.add_field(name="Auto-mod", value="Bad words are auto-deleted + user gets timed out", inline=False)
    await ctx.reply(embed=embed)

# ============================================================
# RUN
# ============================================================
bot.run(DISCORD_TOKEN)
