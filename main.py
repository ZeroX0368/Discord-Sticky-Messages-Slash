
import discord
from discord.ext import commands
import os
import time
from datetime import datetime, timedelta

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Channel ID where notifications will be sent
NOTIFY_CHANNEL_ID = 1335597135202353224

# Bot start time for uptime tracking
bot_start_time = None

# AFK system storage
afk_users = {}

# Sticky message system storage
sticky_messages = {}  # {channel_id: {'message': str, 'active': bool, 'last_message_id': int}}

@bot.event
async def on_ready():
    global bot_start_time
    bot_start_time = datetime.utcnow()
    print(f'{bot.user} has connected to Discord!')
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if channel:
        await channel.send("Bot is now online and monitoring!")

@bot.event
async def on_guild_join(guild):
    """Triggered when the bot joins a new server"""
    # Try to find the system channel or general channel to send welcome message
    channel = None
    
    # Priority order: system channel > general > first text channel
    if guild.system_channel:
        channel = guild.system_channel
    else:
        # Look for a general channel
        for ch in guild.text_channels:
            if ch.name.lower() in ['general', 'welcome', 'lobby', 'main']:
                channel = ch
                break
        
        # If no general channel found, use the first available text channel
        if not channel and guild.text_channels:
            channel = guild.text_channels[0]
    
    if channel:
        embed = discord.Embed(
            title="🤖 Thanks for adding me!",
            description="Use `/help` to see all available commands!",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Thanks for adding me")
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            print(f"Could not send welcome message to {guild.name} - missing permissions")
    
    print(f"Joined server: {guild.name} (ID: {guild.id}) with {guild.member_count} members")

@bot.event
async def on_message(message):
    # Handle AFK system
    if message.author.bot and message.author != bot.user:
        return
    
    # Handle sticky message reposting
    if not message.author.bot and message.channel.id in sticky_messages:
        sticky_data = sticky_messages[message.channel.id]
        if sticky_data['active']:
            try:
                # Delete the previous sticky message if it exists
                if sticky_data.get('last_message_id'):
                    try:
                        old_message = await message.channel.fetch_message(sticky_data['last_message_id'])
                        await old_message.delete()
                    except:
                        pass
                
                # Post the new sticky message
                sticky_embed = discord.Embed(
                    title="📌 Sticky Message",
                    description=sticky_data['message'],
                    color=discord.Color.gold()
                )
                sticky_embed.set_footer(text="This message is pinned to this channel")
                
                new_sticky = await message.channel.send(embed=sticky_embed)
                sticky_data['last_message_id'] = new_sticky.id
                
            except discord.Forbidden:
                pass
    
    # Check if user is coming back from AFK
    if not message.author.bot and message.author.id in afk_users:
        afk_info = afk_users.pop(message.author.id)
        afk_time = datetime.utcnow() - afk_info['time']
        hours, remainder = divmod(int(afk_time.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        time_str = ""
        if hours > 0:
            time_str += f"{hours}h "
        if minutes > 0:
            time_str += f"{minutes}m "
        time_str += f"{seconds}s"
        
        embed = discord.Embed(
            title="Welcome back!",
            description=f"{message.author.mention} is no longer AFK\nYou were away for: {time_str}",
            color=discord.Color.green()
        )
        await message.channel.send(embed=embed, delete_after=10)
    
    # Check if someone mentioned an AFK user
    if not message.author.bot:
        for mention in message.mentions:
            if mention.id in afk_users and mention.id != message.author.id:
                afk_info = afk_users[mention.id]
                embed = discord.Embed(
                    title="User is AFK",
                    description=f"{mention.display_name} is currently AFK: {afk_info['reason']}",
                    color=discord.Color.orange(),
                    timestamp=afk_info['time']
                )
                await message.channel.send(embed=embed, delete_after=15)
    
    await bot.process_commands(message)

@bot.event
async def on_member_join(member):
    """Triggered when a member joins the server"""
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🟢 Member Joined",
            description=f"{member.mention} ({member.display_name}) joined the server",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=True)
        embed.add_field(name="Member ID", value=member.id, inline=True)
        embed.add_field(name="Total Members", value=len(member.guild.members), inline=True)
        embed.set_footer(text=f"Join #{len(member.guild.members)}")
        await channel.send(embed=embed)

@bot.event
async def on_member_remove(member):
    """Triggered when a member leaves the server"""
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    if channel:
        embed = discord.Embed(
            title="🔴 Member Left",
            description=f"{member.display_name} left the server",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        embed.add_field(name="Member ID", value=member.id, inline=True)
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Total Members", value=len(member.guild.members), inline=True)
        embed.set_footer(text=f"Member #{len(member.guild.members) + 1} left")
        await channel.send(embed=embed)

@bot.event
async def on_presence_update(before, after):
    """Triggered when a member's presence changes (online/offline/etc.)"""
    # Only notify for online/offline changes, not idle/dnd
    if before.status != after.status:
        channel = bot.get_channel(NOTIFY_CHANNEL_ID)
        if channel:
            # Online status changes
            if after.status == discord.Status.online and before.status == discord.Status.offline:
                embed = discord.Embed(
                    title="Member Online",
                    description=f"{after.mention} ({after.display_name}) is now online",
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
                await channel.send(embed=embed)
            
            # Offline status changes
            elif after.status == discord.Status.offline and before.status != discord.Status.offline:
                embed = discord.Embed(
                    title="Member Offline",
                    description=f"{after.display_name} is now offline",
                    color=discord.Color.greyple()
                )
                embed.set_thumbnail(url=after.avatar.url if after.avatar else after.default_avatar.url)
                await channel.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """Simple ping command to test bot responsiveness"""
    await ctx.send(f'Pong! Latency: {round(bot.latency * 1000)}ms')

@bot.command(name='status')
async def status(ctx):
    """Check bot status and monitored channel"""
    channel = bot.get_channel(NOTIFY_CHANNEL_ID)
    embed = discord.Embed(
        title="Bot Status",
        description="Bot is running and monitoring",
        color=discord.Color.blue()
    )
    embed.add_field(name="Monitored Channel", value=f"<#{NOTIFY_CHANNEL_ID}>", inline=True)
    embed.add_field(name="Servers", value=len(bot.guilds), inline=True)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=True)
    await ctx.send(embed=embed)

@bot.command(name='membercount')
async def membercount(ctx):
    """Show current member count and online members"""
    guild = ctx.guild
    if guild:
        online_members = sum(1 for member in guild.members if member.status != discord.Status.offline)
        embed = discord.Embed(
            title="Server Statistics",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Total Members", value=guild.member_count, inline=True)
        embed.add_field(name="Online Members", value=online_members, inline=True)
        embed.add_field(name="Offline Members", value=guild.member_count - online_members, inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        await ctx.send(embed=embed)

# Slash Commands
@bot.tree.command(name="afk", description="Set your AFK status")
async def afk_slash(interaction: discord.Interaction, reason: str = "No reason provided"):
    """Set AFK status"""
    afk_users[interaction.user.id] = {
        'reason': reason,
        'time': datetime.utcnow()
    }
    
    embed = discord.Embed(
        title="AFK Status Set",
        description=f"{interaction.user.mention} is now AFK: {reason}",
        color=discord.Color.orange(),
        timestamp=datetime.utcnow()
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="invite", description="Get bot invite link")
async def invite_slash(interaction: discord.Interaction):
    """Get bot invite link"""
    permissions = discord.Permissions(
        read_messages=True,
        send_messages=True,
        embed_links=True,
        attach_files=True,
        read_message_history=True,
        use_external_emojis=True,
        add_reactions=True
    )
    
    invite_url = discord.utils.oauth_url(bot.user.id, permissions=permissions)
    
    embed = discord.Embed(
        title="📨 Invite Bot",
        description="Click the button below to invite me to your server!",
        color=discord.Color.green()
    )
    
    view = discord.ui.View()
    button = discord.ui.Button(
        label="Invite Bot",
        url=invite_url,
        style=discord.ButtonStyle.link,
        emoji="📨"
    )
    view.add_item(button)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="ping", description="Check bot latency")
async def ping_slash(interaction: discord.Interaction):
    """Check bot latency"""
    latency = round(bot.latency * 1000)
    
    if latency < 100:
        color = discord.Color.green()
        status = "Excellent"
    elif latency < 200:
        color = discord.Color.yellow()
        status = "Good"
    else:
        color = discord.Color.red()
        status = "Poor"
    
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"**Latency:** {latency}ms\n**Status:** {status}",
        color=color
    )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="uptime", description="Check bot uptime")
async def uptime_slash(interaction: discord.Interaction):
    """Check bot uptime"""
    if bot_start_time:
        uptime = datetime.utcnow() - bot_start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        uptime_str = ""
        if days > 0:
            uptime_str += f"{days}d "
        if hours > 0:
            uptime_str += f"{hours}h "
        if minutes > 0:
            uptime_str += f"{minutes}m "
        uptime_str += f"{seconds}s"
        
        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description=f"**Uptime:** {uptime_str}\n**Started:** <t:{int(bot_start_time.timestamp())}:R>",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
    else:
        embed = discord.Embed(
            title="⏰ Bot Uptime",
            description="Uptime information not available",
            color=discord.Color.red()
        )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="help", description="Show help menu")
async def help_slash(interaction: discord.Interaction):
    """Show help menu"""
    embed = discord.Embed(
        title="🤖 Bot Commands",
        description="Here are all available commands:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="**User Commands**",
        value=(
            "`/afk` - Set AFK status\n"
            "`/invite` - Get bot invite link\n"
            "`/ping` - Check bot latency\n"
            "`/uptime` - Check bot uptime\n"
            "`/help` - Show this help menu"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Sticky Messages** (Manage Messages required)",
        value=(
            "`/stick <message>` - Sticks message to channel\n"
            "`/stickstop` - Stops sticky message\n"
            "`/stickstart` - Restarts stopped sticky\n"
            "`/stickremove` - Completely removes sticky\n"
            "`/getstickies` - Show all server stickies"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Text Commands**",
        value=(
            "`!ping` - Simple ping command\n"
            "`!status` - Check bot status\n"
            "`!membercount` - Server statistics"
        ),
        inline=False
    )
    
    embed.add_field(
        name="**Features**",
        value=(
            "• Member join/leave notifications\n"
            "• Online/offline status tracking\n"
            "• AFK system with auto-detection\n"
            "• Server statistics tracking"
        ),
        inline=False
    )
    
    embed.set_footer(text="Bot is monitoring and ready!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stick", description="Sticks a message to the channel")
async def stick_message(interaction: discord.Interaction, message: str):
    """Stick a message to the channel"""
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need the 'Manage Messages' permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    channel_id = interaction.channel.id
    
    # Remove existing sticky if any
    if channel_id in sticky_messages:
        old_data = sticky_messages[channel_id]
        if old_data.get('last_message_id'):
            try:
                old_message = await interaction.channel.fetch_message(old_data['last_message_id'])
                await old_message.delete()
            except:
                pass
    
    # Create new sticky
    sticky_messages[channel_id] = {
        'message': message,
        'active': True,
        'last_message_id': None
    }
    
    # Post the sticky message
    sticky_embed = discord.Embed(
        title="📌 Sticky Message",
        description=message,
        color=discord.Color.gold()
    )
    sticky_embed.set_footer(text="This message is pinned to this channel")
    
    sticky_msg = await interaction.channel.send(embed=sticky_embed)
    sticky_messages[channel_id]['last_message_id'] = sticky_msg.id
    
    embed = discord.Embed(
        title="✅ Sticky Message Created",
        description=f"Successfully created sticky message in {interaction.channel.mention}",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stickstop", description="Stops the stickied message in the channel")
async def stick_stop(interaction: discord.Interaction):
    """Stop the sticky message in the channel"""
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need the 'Manage Messages' permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    channel_id = interaction.channel.id
    
    if channel_id not in sticky_messages:
        embed = discord.Embed(
            title="❌ No Sticky Message",
            description="There is no sticky message in this channel.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    sticky_messages[channel_id]['active'] = False
    
    embed = discord.Embed(
        title="⏸️ Sticky Message Stopped",
        description="The sticky message has been stopped but not deleted. Use `/stickstart` to resume it.",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stickstart", description="Restarts a stopped sticky message using the previous message")
async def stick_start(interaction: discord.Interaction):
    """Restart the sticky message in the channel"""
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need the 'Manage Messages' permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    channel_id = interaction.channel.id
    
    if channel_id not in sticky_messages:
        embed = discord.Embed(
            title="❌ No Sticky Message",
            description="There is no sticky message configured for this channel.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    sticky_data = sticky_messages[channel_id]
    sticky_data['active'] = True
    
    # Post the sticky message
    sticky_embed = discord.Embed(
        title="📌 Sticky Message",
        description=sticky_data['message'],
        color=discord.Color.gold()
    )
    sticky_embed.set_footer(text="This message is pinned to this channel")
    
    sticky_msg = await interaction.channel.send(embed=sticky_embed)
    sticky_data['last_message_id'] = sticky_msg.id
    
    embed = discord.Embed(
        title="▶️ Sticky Message Restarted",
        description="The sticky message has been reactivated.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="stickremove", description="Stops and completely deletes the stickied message in this channel")
async def stick_remove(interaction: discord.Interaction):
    """Remove the sticky message from the channel"""
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need the 'Manage Messages' permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    channel_id = interaction.channel.id
    
    if channel_id not in sticky_messages:
        embed = discord.Embed(
            title="❌ No Sticky Message",
            description="There is no sticky message in this channel.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Delete the sticky message if it exists
    sticky_data = sticky_messages[channel_id]
    if sticky_data.get('last_message_id'):
        try:
            old_message = await interaction.channel.fetch_message(sticky_data['last_message_id'])
            await old_message.delete()
        except:
            pass
    
    # Remove from storage
    del sticky_messages[channel_id]
    
    embed = discord.Embed(
        title="🗑️ Sticky Message Removed",
        description="The sticky message has been completely removed from this channel.",
        color=discord.Color.green()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="getstickies", description="Show all active and stopped stickies in your server")
async def get_stickies(interaction: discord.Interaction):
    """Show all sticky messages in the server"""
    if not interaction.user.guild_permissions.manage_messages:
        embed = discord.Embed(
            title="❌ Permission Denied",
            description="You need the 'Manage Messages' permission to use this command.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    guild = interaction.guild
    server_stickies = []
    
    for channel_id, sticky_data in sticky_messages.items():
        channel = guild.get_channel(channel_id)
        if channel:
            status = "🟢 Active" if sticky_data['active'] else "🔴 Stopped"
            message_preview = sticky_data['message'][:50] + "..." if len(sticky_data['message']) > 50 else sticky_data['message']
            server_stickies.append(f"**{channel.mention}** - {status}\n`{message_preview}`")
    
    if not server_stickies:
        embed = discord.Embed(
            title="📌 Server Sticky Messages",
            description="No sticky messages found in this server.",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="📌 Server Sticky Messages",
            description="\n\n".join(server_stickies),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Total: {len(server_stickies)} sticky message(s)")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

bot.run('Discord-Token')
