import re
import discord
from discord import app_commands
from discord.ext import commands, tasks
import requests
from collections import deque
from datetime import datetime, timedelta
import json
import os
import asyncio
import random
import lyricsgenius


DISCORD_TOKEN = 'MTI1NTI2ODU1MTA3ODQ0NTA5Ng.GkhwqJ.x-vDcmeBL4Dm7JsuIDUmdU7G8ZVZ5kab-Hrb64'
GENIUS_API_TOKEN = 'jXmHAn-6Wup3QQS02rdj2UK2iAF51jtqFAGqEQzXohtJNurJoJb3veQrST0Qrr3w'
LOG_CHANNEL_ID = 1275357929897459722
BOOST_CHANNEL_ID = 1275395136070746227  
log_channels = {
    "commands": [1275357929897459722, ]  
}

genius = lyricsgenius.Genius(GENIUS_API_TOKEN)

eight_ball_responses = [
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes – definitely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful."
    "no nigga"
    "no faggot"
]


# Replace these with your values
GUILD_ID = 1275328786640015383  # Your server ID
ROLE_ID = 1275477324925763634    # The role to assign
VANITY_KEYWORD = "/etc"   # The keyword to look for in the user's status


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.messages = True
intents.guilds = True  

bot = commands.Bot(command_prefix="!", intents=intents)

sniped_messages = deque(maxlen=10)
warnings = {}
banned_users = set()
whitelisted_users = set()

data_file = "hard_banned_users.json"
autorole_file = "autorole.json"

WELCOME_FILE_PATH = 'welcome_settings.json'

PREFIX_FILE = 'prefixes.json'

async def log_command_usage(bot, message):
    channels = log_channels.get("commands", [])
    for channel_id in channels:
        channel = bot.get_channel(channel_id)
        if channel:
            await channel.send(message)



def load_prefixes():
    """Load prefixes from the JSON file."""
    if os.path.exists(PREFIX_FILE):
        with open(PREFIX_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_prefixes(prefixes):
    """Save prefixes to the JSON file."""
    with open(PREFIX_FILE, 'w') as f:
        json.dump(prefixes, f, indent=4)

def get_prefix(bot, message):
    """Get the prefix for the bot."""
    prefixes = load_prefixes()
    return prefixes.get(str(message.guild.id), ',')



def load_welcome_settings():
    if os.path.exists(WELCOME_FILE_PATH):
        with open(WELCOME_FILE_PATH, 'r') as f:
            return json.load(f)
    return {}


def save_welcome_settings(data):
    with open(WELCOME_FILE_PATH, 'w') as f:
        json.dump(data, f)






def load_data():
    global banned_users, whitelisted_users
    if os.path.exists(data_file):  
        with open(data_file, "r") as f:
            data = json.load(f)
            banned_users = set(data.get("banned_users", []))
            whitelisted_users = set(data.get("whitelisted_users", []))



def save_data():
    with open(data_file, "w") as f:
        json.dump({
            "banned_users": list(banned_users),
            "whitelisted_users": list(whitelisted_users)
        }, f, indent=4)

def load_autorole():
    if os.path.exists(autorole_file):
        with open(autorole_file, "r") as f:
            return json.load(f)
    return {}

def save_autorole(autorole_data):
    with open(autorole_file, "w") as f:
        json.dump(autorole_data, f, indent=4)

def get_autorole(guild_id):
    autorole_data = load_autorole()
    return autorole_data.get(str(guild_id))

def set_autorole(guild_id, role_id):
    autorole_data = load_autorole()
    autorole_data[str(guild_id)] = role_id
    save_autorole(autorole_data)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    load_data()
    await bot.tree.sync()
    change_status.start()

@tasks.loop(minutes=2)  # Change status every 2 minutes
async def change_status():
    status_list = [
        discord.Game(name="made by 5np"),
        discord.Streaming(name="regrets.lol", url="https://twitch.tv/streamer"),
        discord.Activity(type=discord.ActivityType.listening, name="utility bot"),
        discord.Activity(type=discord.ActivityType.watching, name="alone.lol")
    ]
    global current_status_index
    status = status_list[current_status_index]
    await bot.change_presence(activity=status)
    print(f"Status updated to: {status.name}")
    current_status_index = (current_status_index + 1) % len(status_list)

@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.premium_since is None and after.premium_since is not None:
        # User has boosted the server
        log_message = f"Congratulations {after.mention}! Thank you for boosting the server ❤️"
        boost_channel = bot.get_channel(BOOST_CHANNEL_ID)
        if boost_channel:
            await boost_channel.send(log_message)



@bot.event
async def on_command(ctx):
    user = ctx.author
    command = ctx.command
    channel = ctx.channel
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    
    log_message = f"[{timestamp}] {user} used the command `{command}` in {channel.name} (ID: {channel.id})"
    
    await log_command_usage(bot, log_message)
    



@bot.event
async def on_message_delete(message: discord.Message):
    if message.author.bot:
        return
    sniped_messages.append({
        "content": message.content,
        "author": message.author,
        "channel": message.channel,
        "time": message.created_at,
        "deleted_at": datetime.utcnow()
    })
    log_message = f"Message deleted in {message.channel.mention} by {message.author.mention}: {message.content}"
    await send_log_to_channel(message.guild, log_message)

@bot.tree.command(name="snipe", description="Retrieve the most recently deleted message within the last 2 hours")
async def snipe(interaction: discord.Interaction):
    two_hours_ago = datetime.utcnow() - timedelta(hours=2)

    for sniped in reversed(sniped_messages):
        if sniped['deleted_at'] >= two_hours_ago:
            embed = discord.Embed(title="Sniped Message", color=0x1E90FF, timestamp=sniped['time'])
            embed.add_field(name="Author", value=sniped['author'].mention, inline=False)
            embed.add_field(name="Channel", value=sniped['channel'].mention, inline=False)
            embed.add_field(name="Message", value=sniped['content'], inline=False)
            await interaction.response.send_message(embed=embed)

            log_message = f"Snipe command used by {interaction.user.mention} in {interaction.channel.mention}"
            await send_log_to_channel(interaction.guild, log_message)
            return

    await interaction.response.send_message("No recently deleted messages found within the last 2 hours.", ephemeral=True)

@bot.tree.command(name="avatar", description="Get the avatar of a specified user")
@app_commands.describe(user="The user to get the avatar of")
async def avatar(interaction: discord.Interaction, user: discord.User = None):
    user = user or interaction.user
    embed = discord.Embed(title=f"{user.name}'s Avatar", color=0x1E90FF)
    embed.set_image(url=user.avatar.url)
    await interaction.response.send_message(embed=embed)

    log_message = f"Avatar command used by {interaction.user.mention} for {user.mention}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="cat", description="Get a random picture of a cat")
async def cat(interaction: discord.Interaction):
    response = requests.get("https://api.thecatapi.com/v1/images/search")
    if response.status_code == 200:
        data = response.json()
        if data:
            cat_image_url = data[0]['url']
            embed = discord.Embed(title="Here's a Random Cat Picture", color=0x1E90FF)
            embed.set_image(url=cat_image_url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No cat picture found.", ephemeral=True)
    else:
        await interaction.response.send_message("Error fetching cat picture.", ephemeral=True)

    log_message = f"Cat command used by {interaction.user.mention}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="dog", description="Get a random picture of a dog")
async def dog(interaction: discord.Interaction):
    response = requests.get("https://dog.ceo/api/breeds/image/random")
    if response.status_code == 200:
        data = response.json()
        if data and data['status'] == 'success':
            dog_image_url = data['message']
            embed = discord.Embed(title="Here's a Random Dog Picture", color=0x1E90FF)
            embed.set_image(url=dog_image_url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("No dog picture found.", ephemeral=True)
    else:
        await interaction.response.send_message("Error fetching dog picture.", ephemeral=True)

    log_message = f"Dog command used by {interaction.user.mention}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="lookup", description="Look up information for an IP address")
@app_commands.describe(ip="The IP address to look up")
async def ip_lookup(interaction: discord.Interaction, ip: str):
    url = f"https://ipapi.co/{ip}/json/"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        if "error" not in data:
            embed = discord.Embed(title=f"IP Lookup for {ip}", color=0x1E90FF)
            embed.add_field(name="IP", value=data.get("ip", "N/A"), inline=False)
            embed.add_field(name="City", value=data.get("city", "N/A"), inline=False)
            embed.add_field(name="Region", value=data.get("region", "N/A"), inline=False)
            embed.add_field(name="Country", value=data.get("country_name", "N/A"), inline=False)
            embed.add_field(name="Postal Code", value=data.get("postal", "N/A"), inline=False)
            embed.add_field(name="Latitude", value=data.get("latitude", "N/A"), inline=False)
            embed.add_field(name="Longitude", value=data.get("longitude", "N/A"), inline=False)
            embed.add_field(name="ISP", value=data.get("org", "N/A"), inline=False)
            embed.add_field(name="Timezone", value=data.get("timezone", "N/A"), inline=False)

            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"Error: {data['reason']}", ephemeral=True)
    else:
        await interaction.response.send_message("Error fetching data from the IP lookup service.", ephemeral=True)

    log_message = f"Lookup command used by {interaction.user.mention} for IP: {ip}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="dm", description="DM all members with a specific role")
@app_commands.describe(role="The role to send a message to", message="The message to send")
async def dm_role(interaction: discord.Interaction, role: discord.Role, message: str):
    members = [member for member in interaction.guild.members if role in member.roles]
    
    if not members:
        await interaction.response.send_message(f"No members found with the role '{role.name}'.", ephemeral=True)
        return

    await interaction.response.send_message(f"Sending message to {len(members)} members with the role '{role.name}'...", ephemeral=True)

    for member in members:
        try:
            await member.send(message)
        except discord.Forbidden:
            await interaction.followup.send(f"Could not send message to {member.display_name} (DMs may be closed).", ephemeral=True)
    
    await interaction.followup.send("Finished sending DMs.", ephemeral=True)

    log_message = f"DM command used by {interaction.user.mention} for role {role.name}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="ban", description="Ban a user from the server")
@app_commands.describe(user="The user to ban", reason="The reason for the ban")
async def ban(interaction: discord.Interaction, user: discord.User, reason: str = None):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You do not have permission to ban members.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    await interaction.guild.ban(user, reason=reason)
    await interaction.response.send_message(f"{user.mention} has been banned.", ephemeral=True)

    try:
        await user.send(f"You have been banned from {interaction.guild.name} for: {reason}")
    except discord.Forbidden:
        pass  

    log_message = f"{user.mention} was banned by {interaction.user.mention} for: {reason}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="kick", description="Kick a user from the server")
@app_commands.describe(user="The user to kick", reason="The reason for the kick")
async def kick(interaction: discord.Interaction, user: discord.User, reason: str = None):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message("You do not have permission to kick members.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    await interaction.guild.kick(user, reason=reason)
    await interaction.response.send_message(f"{user.mention} has been kicked.", ephemeral=True)

    try:
        await user.send(f"You have been kicked from {interaction.guild.name} for: {reason}")
    except discord.Forbidden:
        pass  

    log_message = f"{user.mention} was kicked by {interaction.user.mention} for: {reason}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="warn", description="Warn a user in the server")
@app_commands.describe(user="The user to warn", reason="The reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.User, reason: str):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("You do not have permission to warn members.", ephemeral=True)
        return

    if user.id not in warnings:
        warnings[user.id] = []

    warnings[user.id].append({
        "reason": reason,
        "moderator": interaction.user.name,
        "time": datetime.utcnow()
    })

    await interaction.response.send_message(f"{user.mention} has been warned.", ephemeral=True)

    try:
        await user.send(f"You have been warned in {interaction.guild.name} for: {reason}")
    except discord.Forbidden:
        pass  

    log_message = f"{user.mention} was warned by {interaction.user.mention} for: {reason}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="hardban", description="Hard ban a user from the server (permanent ban)")
@app_commands.describe(user="The user to hard ban", reason="The reason for the hard ban")
async def hardban(interaction: discord.Interaction, user: discord.User, reason: str = None):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You do not have permission to hard ban members.", ephemeral=True)
        return

    if user.id in whitelisted_users:
        await interaction.response.send_message(f"{user.mention} is whitelisted and cannot be hard banned.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    await interaction.guild.ban(user, reason=reason, delete_message_days=0)
    banned_users.add(user.id)
    save_data()
    await interaction.response.send_message(f"{user.mention} has been hard banned.", ephemeral=True)

    try:
        await user.send(f"You have been hard banned from {interaction.guild.name} for: {reason}")
    except discord.Forbidden:
        pass  

    log_message = f"{user.mention} was hard banned by {interaction.user.mention} for: {reason}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="unhardban", description="Unhardban a user from the server")
@app_commands.describe(user="The user to unhardban", reason="The reason for the unhardban")
async def unhardban(interaction: discord.Interaction, user: discord.User, reason: str = None):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message("You do not have permission to unhardban members.", ephemeral=True)
        return

    reason = reason or "No reason provided"
    if user.id not in banned_users:
        await interaction.response.send_message(f"{user.mention} is not hard banned.", ephemeral=True)
        return

    banned_users.remove(user.id)
    save_data()
    await interaction.guild.unban(user)
    await interaction.response.send_message(f"{user.mention} has been unhardbanned.", ephemeral=True)

    try:
        await user.send(f"You have been unhardbanned from {interaction.guild.name}. Reason: {reason}")
    except discord.Forbidden:
        pass  

    log_message = f"{user.mention} was unhardbanned by {interaction.user.mention}. Reason: {reason}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.tree.command(name="autorole", description="Set or view the auto role for new members")
@app_commands.describe(role="The role to set as the auto role")
async def autorole(interaction: discord.Interaction, role: discord.Role = None):
    if role:
        set_autorole(interaction.guild.id, role.id)
        await interaction.response.send_message(f"Auto role has been set to '{role.name}'.", ephemeral=True)
    else:
        current_role_id = get_autorole(interaction.guild.id)
        if current_role_id:
            current_role = interaction.guild.get_role(int(current_role_id))
            await interaction.response.send_message(f"The current auto role is '{current_role.name}'.", ephemeral=True)
        else:
            await interaction.response.send_message("No auto role has been set yet.", ephemeral=True)

    log_message = f"Autorole command used by {interaction.user.mention}. Role set to '{role.name}'" if role else f"Autorole command used by {interaction.user.mention}"
    await send_log_to_channel(interaction.guild, log_message)

@bot.event
async def on_member_join(member: discord.Member):
    role_id = get_autorole(member.guild.id)
    if role_id:
        role = member.guild.get_role(int(role_id))
        if role:
            await member.add_roles(role)
            log_message = f"Assigned auto role '{role.name}' to {member.mention} upon joining."
            await send_log_to_channel(member.guild, log_message)
@bot.event
async def on_member_join(member: discord.Member):
    welcome_settings = load_welcome_settings()
    guild_settings = welcome_settings.get(str(member.guild.id))

    if guild_settings:
        channel_id = guild_settings['channel_id']
        message = guild_settings['message']
        channel = bot.get_channel(channel_id)

        if channel:
            
            message = message.replace("{user}", member.mention)
            await channel.send(message)



    

@bot.tree.command(name="help", description="Shows all available commands")
async def help_command(interaction: discord.Interaction):
    commands = [
        {"name": "avatar", "description": "Get the avatar of a specified user"},
        {"name": "cat", "description": "Get a random picture of a cat"},
        {"name": "dog", "description": "Get a random picture of a dog"},
        {"name": "lookup", "description": "Look up information for an IP address"},
        {"name": "dm", "description": "DM all members with a specific role"},
        {"name": "ban", "description": "Ban a user from the server"},
        {"name": "kick", "description": "Kick a user from the server"},
        {"name": "warn", "description": "Warn a user in the server"},
        {"name": "hardban", "description": "Hard ban a user from the server (permanent ban)"},
        {"name": "unhardban", "description": "Unhardban a user from the server"},
        {"name": "autorole", "description": "Set or view the auto role for new members"},
         {"name": "c", "description": "!c (user) purges msgs by that user then !c is normal purge"},
       {"name": "r", "description": "!r roles a user a role"},
       {"name": "giveaway", "description": "!giveaway ``(time)`` (prize)``"},
    ]

    embed = discord.Embed(title="Available Commands", color=0x1E90FF)
    for command in commands:
        embed.add_field(name=f"/{command['name']}", value=command["description"], inline=False)

    await interaction.response.send_message(embed=embed)


    


async def send_log_to_channel(guild: discord.Guild, message: str):
    log_channel = guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="alone.lol",
            description=message,
            color=0x1E90FF,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text="Log generated on")
        await log_channel.send(embed=embed)



@bot.tree.command(name="createembed", description="Create and send a custom embed")
@app_commands.describe(
    title="Title of the embed",
    description="Description of the embed",
    color="Hex color code for the embed",
    footer="Footer text of the embed",
    channel="Channel to send the embed in"
)
async def create_embed(interaction: discord.Interaction,
                       title: str,
                       description: str,
                       color: str,
                       footer: str,
                       channel: discord.TextChannel):
    
    embed = discord.Embed(
        title=title,
        description=description,
        color=int(color, 16)  # Convert hex color code to an integer
    )
    
   
    if footer:
        embed.set_footer(text=footer)
    
    
    try:
        await channel.send(embed=embed)
        await interaction.response.send_message("Embed sent successfully!", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("I do not have permission to send messages in that channel.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)


@bot.tree.command(name="setwelcome", description="Set a welcome message and channel.")
@app_commands.describe(
    channel="Channel to send the welcome message",
    message="Welcome message. Use {user} to mention the new member."
)
async def set_welcome(interaction: discord.Interaction, 
                      channel: discord.TextChannel, 
                      message: str):
    welcome_settings = load_welcome_settings()
    welcome_settings[str(interaction.guild.id)] = {
        'channel_id': channel.id,
        'message': message
    }
    save_welcome_settings(welcome_settings)
    await interaction.response.send_message(f"Welcome message set successfully! I will send the message in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="removewelcome", description="Remove the welcome message configuration.")
async def remove_welcome(interaction: discord.Interaction):
    welcome_settings = load_welcome_settings()
    guild_id = str(interaction.guild.id)

    if guild_id in welcome_settings:
        del welcome_settings[guild_id]
        save_welcome_settings(welcome_settings)
        await interaction.response.send_message("Welcome message configuration removed.", ephemeral=True)
    else:
        await interaction.response.send_message("No welcome message configuration found for this server.", ephemeral=True)


@bot.command(name='c')
@commands.has_permissions(manage_messages=True)  
async def purge(ctx, num: int, user: discord.Member = None):
    if num < 1:
        embed = discord.Embed(title="Error", description="The number of messages to purge must be at least 1.", color=discord.Color.red())
        await ctx.send(embed=embed, delete_after=5)
        return
    
    if num > 100:
        embed = discord.Embed(title="Error", description="You can only purge up to 100 messages at a time.", color=discord.Color.red())
        await ctx.send(embed=embed, delete_after=5)
        return
    
    def check(msg):
        if user:
            return msg.author == user
        return True

    deleted = await ctx.channel.purge(limit=num, check=check)

    embed = discord.Embed(
        
        description=f"Purged {len(deleted)} messages.",
        color=discord.Color.green()
    )
    
    if user:
        embed.add_field(name="User", value=user.mention)
    
    await ctx.send(embed=embed, delete_after=5)

@bot.command(name='setprefix')
@commands.has_permissions(administrator=True)
async def set_prefix(ctx, new_prefix: str):
    """Command to change the bot's prefix."""
    if len(new_prefix) > 5:
        await ctx.send("Prefix must be 5 characters or less.")
        return

    prefixes = load_prefixes()
    prefixes[str(ctx.guild.id)] = new_prefix
    save_prefixes(prefixes)

    embed = discord.Embed(
        title="Prefix Changed",
        description=f"Bot prefix has been changed to `{new_prefix}`.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='userinfo')
async def userinfo(ctx, member: discord.Member = None):
    # If no member is mentioned, use the command invoker
    if member is None:
        member = ctx.author

    # Create an embed to display user information
    embed = discord.Embed(title=f"User Info for {member}", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.avatar.url)  # Display user's avatar
    embed.add_field(name="User ID", value=member.id, inline=True)
    embed.add_field(name="Nickname", value=member.display_name, inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
    embed.add_field(name="Roles", value=", ".join([role.mention for role in member.roles[1:]]), inline=False)  # Skip @everyone role
    embed.add_field(name="Status", value=str(member.status).capitalize(), inline=True)
    embed.add_field(name="Bot", value=member.bot, inline=True)

    # Send the embed message
    await ctx.send(embed=embed)



@bot.command()
@commands.has_permissions(manage_roles=True)  # Ensure the user has permission to manage roles
async def r(ctx, member: discord.Member, *, role_name: str):
    guild = ctx.guild
    role = discord.utils.get(guild.roles, name=role_name)

    # Create an embed for responses
    embed = discord.Embed(color=discord.Color.blurple())
    
    if role is None:
        embed.title = "Error"
        embed.description = f"Role '{role_name}' not found."
        embed.color = discord.Color.red()
        await ctx.send(embed=embed)
        return

    # Check if the role can be assigned (user's top role must be higher than the role)
    if role.position >= ctx.author.top_role.position:
        embed.title = "Error"
        embed.description = "You cannot assign this role because it is higher than or equal to your top role."
        embed.color = discord.Color.red()
        await ctx.send(embed=embed)
        return

    # Check if the bot can assign the role
    if role.position >= ctx.me.top_role.position:
        embed.title = "Error"
        embed.description = "I cannot assign this role because it is higher than or equal to my top role."
        embed.color = discord.Color.red()
        await ctx.send(embed=embed)
        return

    # Check if the member already has the role
    if role in member.roles:
        # Remove the role
        await member.remove_roles(role)
        embed.title = "Role Removed"
        embed.description = f"Successfully removed the role '{role_name}' from {member.mention}."
        embed.color = discord.Color.orange()
        await ctx.send(embed=embed)

        # Log the command usage
        await log_command_usage(ctx.guild, "Role Removed", f"Removed role: `{role_name}` from {member.mention}", ctx.author, ctx.channel)
    else:
        # Add the role
        await member.add_roles(role)
        embed.title = "Role Assigned"
        embed.description = f"Successfully assigned the role '{role_name}' to {member.mention}."
        embed.color = discord.Color.green()
        await ctx.send(embed=embed)

        # Log the command usage
        await log_command_usage(ctx.guild, "Role Assigned", f"Assigned role: `{role_name}` to {member.mention}", ctx.author, ctx.channel)



@bot.event
async def on_member_update(before, after):
    if before.activity != after.activity and after.activity:
        activity = after.activity
        if isinstance(activity, discord.CustomActivity):
            status_message = activity.name.lower() if activity.name else ""
            if VANITY_KEYWORD.lower() in status_message:
                guild = bot.get_guild(GUILD_ID)
                role = guild.get_role(ROLE_ID)
                member = after
                
                if role not in member.roles:
                    await member.add_roles(role)
                    print(f"Assigned role to {member.display_name} for having '{VANITY_KEYWORD}' in their status.")
            else:
                guild = bot.get_guild(GUILD_ID)
                role = guild.get_role(ROLE_ID)
                member = after
                
                if role in member.roles:
                    await member.remove_roles(role)
                    print(f"Removed role from {member.display_name} as they no longer have '{VANITY_KEYWORD}' in their status.")


    


@bot.command(name='giveaway', help='Starts a giveaway. Usage: !giveaway <duration in seconds> <prize>')
async def giveaway(ctx, duration: int, *, prize: str):
    # Announce the giveaway
    embed = discord.Embed(title="🎉 **GIVEAWAY** 🎉", description=f"Prize: **{prize}**\nReact with 🎉 to enter!\nGiveaway ends in {duration} seconds!", color=discord.Color.blue())
    giveaway_message = await ctx.send(embed=embed)
    
    # Add the reaction to the giveaway message
    await giveaway_message.add_reaction("🎉")
    
    # Wait for the specified duration
    await asyncio.sleep(duration)
    
    # Fetch the message again to get the updated reaction count
    giveaway_message = await ctx.channel.fetch_message(giveaway_message.id)
    
    # Get all the users who reacted with 🎉
    reaction = discord.utils.get(giveaway_message.reactions, emoji="🎉")
    users = [user async for user in reaction.users() if user != bot.user]
    
    # Choose a random winner
    if len(users) > 0:
        winner = random.choice(users)
        await ctx.send(f"🎉 Congratulations {winner.mention}! You won **{prize}**!")
    else:
        await ctx.send("No one entered the giveaway. 😢")


@bot.tree.command(name="8ball", description="Ask the magic 8ball a question!")
async def eightball(interaction: discord.Interaction, question: str):
    response = random.choice(eight_ball_responses)
    await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {response}")

# Slash command to fetch lyrics
@bot.tree.command(name="lyrics", description="Get lyrics of a song")
async def lyrics(interaction: discord.Interaction, song_title: str):
    await interaction.response.defer()  # Defer the response while processing
    try:
        # Search for the song on Genius
        song = genius.search_song(song_title)
        if song:
            # If the song is found, send the lyrics
            lyrics = song.lyrics
            # If the lyrics are too long for one message, split and send in parts
            for i in range(0, len(lyrics), 2000):
                await interaction.followup.send(lyrics[i:i+2000])
        else:
            await interaction.followup.send("Sorry, I couldn't find the lyrics for that song.")
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}")
 

# Load data and start the bot
load_data()
current_status_index = 0
bot.run(DISCORD_TOKEN)



