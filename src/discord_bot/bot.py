import os
import asyncio
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

from services.riot_api import (
    get_recent_matches_by_riot_id,
    get_match_detail_by_riot_id,
)
from services.agent_runner import run_agent
from services.riot_bind_store import (
    bind_riot_account,
    get_riot_binding,
    unbind_riot_account,
)

TOKEN = os.getenv("DISCORD_TOKEN")
guild_ids_env = os.getenv("DISCORD_GUILD_IDS")

if TOKEN is None:
    raise ValueError("DISCORD_TOKEN was not loaded. Please check your .env file.")

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

MATCH_SELECTION_TIMEOUT = 60


def format_match_list(binding: dict, matches: list[dict]) -> str:
    if not matches:
        return "No recent matches were found."

    lines = [
        f"**Recent Matches for** `{binding['game_name']}#{binding['tag_line']}`",
        "",
    ]

    for i, match in enumerate(matches, start=1):
        result = "Win" if match["win"] else "Loss"
        lines.append(
            f"[{i}] {match['champion']} | {result} | {match['queue_name']} | "
            f"{match['kda_text']} | {match['game_duration_minutes']}m"
        )

    lines.extend(
        [
            "",
            f"Send a number from `1` to `{len(matches)}` in this channel within **{MATCH_SELECTION_TIMEOUT} seconds** to view details.",
            "Send `cancel` to cancel.",
        ]
    )

    return "\n".join(lines)


def format_match_detail(binding: dict, match: dict, index: int | None = None) -> str:
    title = f"**Match Details**"
    if index is not None:
        title += f" `[{index}]`"

    return (
        f"{title}\n"
        f"**Riot ID:** `{binding['game_name']}#{binding['tag_line']}`\n"
        f"**Champion:** {match['champion']}\n"
        f"**Queue:** {match['queue_name']}\n"
        f"**Game Mode:** {match['game_mode']}\n"
        f"**Result:** {'Win' if match['win'] else 'Loss'}\n"
        f"**K/D/A:** {match['kda_text']}\n"
        f"**CS:** {match['cs']}\n"
        f"**Damage to Champions:** {match['damage_to_champions']}\n"
        f"**Vision Score:** {match['vision_score']}\n"
        f"**Gold Earned:** {match['gold_earned']}\n"
        f"**Champion Level:** {match['champion_level']}\n"
        f"**Duration:** {match['game_duration_minutes']} min\n"
        f"**Match ID:** `{match['match_id']}`"
    )


@client.event
async def on_ready():
    print(f"Bot is online: {client.user}")

    try:
        if guild_ids_env:
            guild_ids = [int(gid.strip()) for gid in guild_ids_env.split(",") if gid.strip()]

            for gid in guild_ids:
                guild = discord.Object(id=gid)
                tree.clear_commands(guild=guild)
                tree.copy_global_to(guild=guild)
                synced = await tree.sync(guild=guild)
                print(f"Synced {len(synced)} commands to guild {gid}")
        else:
            synced = await tree.sync()
            print(f"Synced {len(synced)} global commands")

        print("Registered commands:", [cmd.name for cmd in tree.get_commands()])

    except Exception as e:
        print(f"Command sync failed: {e}")


@tree.command(name="ping", description="Check if the bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("pong!")


@tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hello {interaction.user.display_name}!")


@tree.command(name="bindriot", description="Bind your Riot account")
@app_commands.describe(
    game_name="Your Riot game name",
    tag_line="Your Riot tag line",
    platform="Choose your server"
)
@app_commands.choices(
    platform=[
        app_commands.Choice(name="NA (North America)", value="na1"),
        app_commands.Choice(name="KR (Korea)", value="kr"),
        app_commands.Choice(name="EUW (Europe West)", value="euw1"),
        app_commands.Choice(name="EUNE (Europe Nordic & East)", value="eun1"),
        app_commands.Choice(name="JP (Japan)", value="jp1"),
        app_commands.Choice(name="BR (Brazil)", value="br1"),
        app_commands.Choice(name="LAN (Latin America North)", value="la1"),
        app_commands.Choice(name="LAS (Latin America South)", value="la2"),
        app_commands.Choice(name="OCE (Oceania)", value="oc1"),
    ]
)
async def bindriot(
    interaction: discord.Interaction,
    game_name: str,
    tag_line: str,
    platform: app_commands.Choice[str]
):
    try:
        binding = bind_riot_account(
            discord_user_id=str(interaction.user.id),
            game_name=game_name,
            tag_line=tag_line,
            platform=platform.value
        )
    except ValueError as e:
        await interaction.response.send_message(
            f"Binding failed: {e}",
            ephemeral=True
        )
        return
    except Exception as e:
        await interaction.response.send_message(
            f"Binding failed: `{e}`",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        (
            f"Bound successfully.\n"
            f"**Riot ID:** `{binding['game_name']}#{binding['tag_line']}`\n"
            f"**Platform:** `{binding['platform']}`\n"
            f"**Region:** `{binding['region']}`\n"
            f"**PUUID saved:** `{bool(binding.get('puuid'))}`"
        ),
        ephemeral=True
    )



@tree.command(name="myriot", description="Show your current Riot account binding")
async def myriot(interaction: discord.Interaction):
    binding = get_riot_binding(str(interaction.user.id))

    if not binding:
        await interaction.response.send_message(
            "You do not have a Riot account bound yet. Use `/bindriot` first.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        (
            f"Your current Riot binding:\n"
            f"**Riot ID:** `{binding['game_name']}#{binding['tag_line']}`\n"
            f"**Platform:** `{binding['platform']}`\n"
            f"**Region:** `{binding['region']}`\n"
            f"**PUUID saved:** `{bool(binding.get('puuid'))}`"
        ),
        ephemeral=True
    )

@tree.command(name="unbindriot", description="Remove your current Riot account binding")
async def unbindriot(interaction: discord.Interaction):
    removed = unbind_riot_account(str(interaction.user.id))

    if not removed:
        await interaction.response.send_message(
            "You do not have a Riot account bound right now.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        "Your Riot account binding has been removed.",
        ephemeral=True
    )

@tree.command(name="duo", description="Recommend duo partners using the pairing model")
async def duo(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)

    discord_id = str(interaction.user.id)
    binding = get_riot_binding(discord_id)

    if not binding:
        await interaction.followup.send("你还没有绑定 Riot ID，请先用 `/bindriot`。")
        return

    puuid = binding.get("puuid")

    if not puuid:
        await interaction.followup.send(
            "你的绑定记录里还没有 PUUID。请重新使用 `/bindriot` 绑定一次。"
        )
        return

    prompt = f"""
Discord user id: {discord_id}

User message:
请使用 recommend_duo 工具给我推荐双排队友。

Force call recommend_duo.
user_puuid: {puuid}
top_k: 5
sample_size: 300
rank_check_top_n: 50
platform: na1

For EACH player, ALWAYS show:
- player name
- role
- rank
- predicted_win_probability

Do NOT omit rank.
Do NOT use the word "score".
"""

    try:
        result = await asyncio.to_thread(run_agent, prompt)
    except Exception as e:
        await interaction.followup.send(f"/duo failed: `{e}`")
        return

    if len(result) > 1900:
        result = result[:1900] + "\n\n...[output too long, truncated]"

    await interaction.followup.send(result)



@tree.command(name="findmatch", description="Show recent League matches and let you choose one")
@app_commands.describe(count="How many recent matches to list (1-10)")
async def findmatch(
    interaction: discord.Interaction,
    count: app_commands.Range[int, 1, 10] = 5
):
    binding = get_riot_binding(str(interaction.user.id))

    if not binding:
        await interaction.response.send_message(
            "You do not have a Riot account bound yet. Use `/bindriot` first.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True, thinking=True)

    try:
        matches = get_recent_matches_by_riot_id(
            game_name=binding["game_name"],
            tag_line=binding["tag_line"],
            region=binding["region"],
            count=count,
        )
    except Exception as e:
        await interaction.followup.send(
            f"Failed to fetch recent matches.\nError: `{e}`",
            ephemeral=True
        )
        return

    if not matches:
        await interaction.followup.send(
            "No recent matches were found for this account.",
            ephemeral=True
        )
        return

    await interaction.followup.send(
        format_match_list(binding, matches),
        ephemeral=True
    )

    def check(message: discord.Message) -> bool:
        return (
            message.author.id == interaction.user.id
            and interaction.channel is not None
            and message.channel.id == interaction.channel.id
            and (
                message.content.strip().lower() == "cancel"
                or (
                    message.content.strip().isdigit()
                    and 1 <= int(message.content.strip()) <= len(matches)
                )
            )
        )

    try:
        msg = await client.wait_for("message", check=check, timeout=MATCH_SELECTION_TIMEOUT)
    except asyncio.TimeoutError:
        await interaction.followup.send(
            "Match selection timed out. Please use `/findmatch` again.",
            ephemeral=True
        )
        return

    content = msg.content.strip().lower()

    if content == "cancel":
        await interaction.followup.send(
            "Match selection cancelled.",
            ephemeral=True
        )
        return

    index = int(content)
    selected_match = matches[index - 1]

    try:
        detail = get_match_detail_by_riot_id(
            game_name=binding["game_name"],
            tag_line=binding["tag_line"],
            region=binding["region"],
            match_id=selected_match["match_id"],
        )
    except Exception as e:
        await interaction.followup.send(
            f"Failed to fetch match detail.\nError: `{e}`",
            ephemeral=True
        )
        return

    await interaction.followup.send(
        format_match_detail(binding, detail, index=index),
        ephemeral=True
    )

    try:
        await msg.delete()
    except Exception:
        pass


@tree.command(name="ask_agent", description="Send a request to the AI agent")
@app_commands.describe(prompt="What do you want the agent to do?")
async def ask_agent(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)

    agent_input = f"""
Discord user id: {interaction.user.id}

User message:
{prompt}
"""

    result = run_agent(agent_input)

    lines = [line.strip() for line in result.splitlines() if line.strip()]
    image_url = None
    text_parts = []

    for line in lines:
        if line.startswith(("http://", "https://")) and line.lower().endswith(
            (".png", ".jpg", ".jpeg", ".webp", ".gif")
        ):
            image_url = line
        else:
            text_parts.append(line)

    text_message = "\n".join(text_parts).strip() or "Here is the generated content."

    if image_url:
        embed = discord.Embed(description=text_message)
        embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed)
        return

    if len(result) > 1900:
        result = result[:1900] + "\n\n...[output too long, truncated]"

    await interaction.followup.send(result)


client.run(TOKEN)