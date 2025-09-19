import websockets
import asyncio
import threading
import queue
import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import aioconsole
import sys
import aiohttp
import re
import signal
import time
import re

# Nickname storage file
NICKNAME_FILE = '/app/data/nicknames.json'
# Color storage file
COLOR_FILE = '/app/data/colors.json'

# Predefined color options for easy access
PRESET_COLORS = {
    'red': 'F77337',
    'green': '00F61C', 
    'blue': '6BC7F6',
    'purple': '9B59B6',
    'orange': 'FF9500',
    'yellow': 'F1C40F',
    'pink': 'E91E63',
    'cyan': '1ABC9C',
    'lime': '8BC34A',
    'magenta': 'E74C3C',
    'gold': 'FFD700',
    'silver': 'C0C0C0'
}

# Predefined textbox/chatbox appearance options
PRESET_TEXTBOXES = {
    'aa-trilogy': '1',
    'aa-apollo': '2', 
    'aa-classic': '0',
    'aa-ds': '4',
    'fallout-nv': 'cf2f70cf-0054-4b29-976d-1dcbad0b3fda',
    'fallout-3': '2ee23fd4-ca52-4092-a83d-3907efab5a6e',
    'dq8': '7c62da82-88cd-47a2-823a-13828d48863a',
    'dq7': '7c3da016-0849-447c-8fc1-43c34ff1d348',
    'dq5': 'f11d06f2-0252-4387-aa7c-b6e0f01d5c9e',
    'lobotomy': '5d92666c-0f6a-495b-8105-1aa3097a9f58',
    'katawa': '189ecc5d-f84b-4c47-a309-12047b96b121',
    'umineko': '9bf4b29c-9ede-419d-945e-a62eaef35b39',
    'blue-archive': 'f4b2811d-9c67-496b-a962-e69a5173a408'
}

def load_nicknames():
    if os.path.exists(NICKNAME_FILE):
        try:
            with open(NICKNAME_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading nicknames: {e}")
            return {}
    return {}

def save_nicknames(nicknames):
    try:
        with open(NICKNAME_FILE, 'w') as f:
            json.dump(nicknames, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving nicknames: {e}")

def load_colors():
    if os.path.exists(COLOR_FILE):
        try:
            with open(COLOR_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading colors: {e}")
            return {}
    return {}

def save_colors(colors):
    try:
        with open(COLOR_FILE, 'w') as f:
            json.dump(colors, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving colors: {e}")

class Config:
    def __init__(self, config_file='/app/data/config.json'):
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file and override with environment variables"""
        if not os.path.exists(self.config_file):
            self.create_default_config()
        try:
            with open(self.config_file, 'r') as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            print("Creating default config...")
            self.create_default_config()
        
        # Override with environment variables if they exist
        self.apply_env_overrides()
    
    def apply_env_overrides(self):
        """Apply environment variable overrides to configuration - only for sensitive data"""
        # Initialize discord section if it doesn't exist
        if 'discord' not in self.data:
            self.data['discord'] = {}
        
        # Discord settings (sensitive and deployment-specific)
        if os.getenv('DISCORD_TOKEN'):
            self.data['discord']['token'] = os.getenv('DISCORD_TOKEN')
            print("🔐 Discord token loaded from environment variable")
        if os.getenv('DISCORD_CHANNEL_ID'):
            try:
                self.data['discord']['channel_id'] = int(os.getenv('DISCORD_CHANNEL_ID'))
                print("🔐 Discord channel ID loaded from environment variable")
            except ValueError:
                print(f"❌ Invalid DISCORD_CHANNEL_ID environment variable")
        if os.getenv('DISCORD_GUILD_ID'):
            try:
                self.data['discord']['guild_id'] = int(os.getenv('DISCORD_GUILD_ID'))
                print("🔐 Discord guild ID loaded from environment variable")
            except ValueError:
                print(f"❌ Invalid DISCORD_GUILD_ID environment variable")
        
        print("🌍 Environment variable overrides applied")
    def create_default_config(self):
        """Create a default configuration file"""
        default_config = {
            "objection": {
                "room_id": "mm6e7z",
                "bot_username": "CourtBot"
            },
            "settings": {
                "mode": "bridge_only",
                "ignore_patterns": ["[System]", "[Bot]"],
                "character_id": 408757,
                "pose_id": 4998989,
                "max_messages": 50,
                "delete_commands": True,
                "show_join_leave": True
            }
        }
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        self.data = default_config
        print(f"📝 Created default config file: {self.config_file}")
        print("Discord settings will be loaded from environment variables.")
    def get(self, section, key=None):
        """Get configuration value"""
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key)
    def validate(self):
        """Validate configuration"""
        errors = []
        
        # Check Discord settings (should come from environment variables)
        discord_config = self.get('discord')
        if not discord_config.get('token'):
            errors.append("Discord token not configured (check DISCORD_TOKEN environment variable)")
        if not isinstance(discord_config.get('channel_id'), int):
            errors.append("Discord channel ID must be a number (check DISCORD_CHANNEL_ID environment variable)")
        if not isinstance(discord_config.get('guild_id'), int):
            errors.append("Discord guild ID must be a number (check DISCORD_GUILD_ID environment variable)")
        
        # Check objection.lol settings
        if not self.get('objection', 'room_id'):
            errors.append("Objection.lol room ID not configured")
        
        return errors
class DiscordCourtBot(discord.Client):
    async def fetch_music_url(self, bgm_id):
        """Fetch the actual external URL for a BGM ID from objection.lol's API"""
        try:
            # Use the correct API endpoint discovered from testing
            api_url = f"https://objection.lol/api/assets/music/{bgm_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        music_data = await response.json()
                        # Extract the external URL and music name from the response
                        external_url = music_data.get('url')
                        music_name = music_data.get('name', 'Unknown Track')
                        volume = music_data.get('volume', 100)
                        
                        if external_url:
                            # Handle relative URLs by converting them to full objection.lol URLs
                            if external_url.startswith('/'):
                                external_url = f"https://objection.lol{external_url}"
                            
                            print(f"🎵 Found music for BGM {bgm_id}: '{music_name}' -> {external_url}")
                            return {
                                'url': external_url,
                                'name': music_name,
                                'volume': volume,
                                'id': bgm_id
                            }
                        else:
                            print(f"❌ No URL found in BGM data for ID {bgm_id}")
                            return None
                    elif response.status == 404:
                        print(f"❌ BGM ID {bgm_id} not found")
                        return None
                    else:
                        print(f"❌ Failed to fetch BGM data for ID {bgm_id} (status: {response.status})")
                        return None
        except Exception as e:
            print(f"❌ Error fetching music URL for ID {bgm_id}: {e}")
            return None

    def extract_bgm_commands(self, text):
        """Extract BGM IDs from text containing [#bgm123456] commands"""
        bgm_pattern = r'\[#bgm(\d+)\]'
        matches = re.findall(bgm_pattern, text)
        return matches

    def strip_color_codes(self, text):
        """Remove objection.lol color codes from text"""
        import re
        # Pattern to match:
        # [#/r] [#/g] [#/b] etc - single letter generic colors
        # [#/c123456] - custom hex colors with c prefix (exactly 6 hex digits)
        # [/#] - closing tags
        # [#ts123] - text speed commands with any number
        color_pattern = r'\[#/[a-zA-Z]\]|\[#/c[a-fA-F0-9]{6}\]|\[/#\]|\[#ts\d+\]'
        cleaned = re.sub(color_pattern, '', text)
        print(f"🎨 Color strip: '{text}' → '{cleaned}'")  # Debug line
        return cleaned

    def extract_media_urls(self, message):
        """Extract image and video URLs from Discord message attachments"""
        media_urls = []
        
        # Extract from attachments (direct file uploads)
        for attachment in message.attachments:
            # Check if it's an image by file extension or content type
            if (attachment.content_type and attachment.content_type.startswith('image/')) or \
               any(attachment.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp']):
                media_urls.append(attachment.url)
                print(f"🖼️ Found image attachment: {attachment.filename} - {attachment.url}")
            
            # Check if it's a video by file extension or content type
            elif (attachment.content_type and attachment.content_type.startswith('video/')) or \
                 any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']):
                media_urls.append(attachment.url)
                print(f"🎥 Found video attachment: {attachment.filename} - {attachment.url}")
        
        return media_urls
    def __init__(self, objection_bot, config):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.objection_bot = objection_bot
        self.config = config
        self.channel_id = config.get('discord', 'channel_id')
        self.guild_id = config.get('discord', 'guild_id')
        self.bridge_channel = None
        self.startup_message = None
        # Nickname mapping: discord user id (str) -> nickname (str)
        self.nicknames = load_nicknames()
        # Color mapping: discord user id (str) -> color code (str)
        self.colors = load_colors()
        # Create command tree
        self.tree = app_commands.CommandTree(self)
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Add commands to tree
        await self.add_commands()
        # Sync slash commands to the guild
        guild = discord.Object(id=self.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        print("🔄 Slash commands synced!")
    async def add_commands(self):
        """Add all slash commands to the tree"""
        @self.tree.command(name="status", description="Check bridge status and list users in the courtroom")
        async def status(interaction: discord.Interaction):
            """Check bot status and list users"""
            users = list(self.objection_bot.user_names.values())
            user_count = len(users)

            if self.objection_bot.connected:
                embed = discord.Embed(
                    title="🟢 Bridge Status",
                    description=f"Connected to room `{self.config.get('objection', 'room_id')}`",
                    color=0x00ff00
                )

                if users:
                    user_list = '\n'.join([f"• {user}" for user in users])
                    embed.add_field(
                        name=f"👥 Users in Courtroom ({user_count})",
                        value=user_list,
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="👥 Users in Courtroom",
                        value="No users found in courtroom",
                        inline=False
                    )
                
                # Add admin status information
                admin_status = "🛡️ Yes" if self.objection_bot.is_admin else "❌ No"
                embed.add_field(
                    name="Admin Status",
                    value=admin_status,
                    inline=True
                )
            else:
                embed = discord.Embed(
                    title="🔴 Bridge Status",
                    description="Disconnected from objection.lol",
                    color=0xff0000
                )
                embed.add_field(
                    name="👥 Users in Courtroom",
                    value="Unable to retrieve user list (disconnected)",
                    inline=False
                )

            await interaction.response.send_message(embed=embed, ephemeral=False)
        @self.tree.command(name="reconnect", description="Attempt to reconnect to the objection.lol courtroom")
        async def reconnect(interaction: discord.Interaction):
            """Reconnect to objection.lol"""
            await interaction.response.defer(ephemeral=True)
            if self.objection_bot.connected:
                await interaction.followup.send("⚠️ Already connected to objection.lol", ephemeral=True)
                return
            try:
                print("🔄 Attempting manual reconnection...")
                # Reset reconnect attempts for manual reconnection
                self.objection_bot.reconnect_attempts = 0
                success = await self.objection_bot.connect_to_room()
                if success:
                    embed = discord.Embed(
                        title="✅ Reconnection Successful",
                        description=f"Successfully reconnected to room `{self.config.get('objection', 'room_id')}`",
                        color=0x00ff00
                    )
                    # Send reconnection message to courtroom
                    await asyncio.sleep(0.5)  # Wait for connection to stabilize
                    await self.objection_bot.send_message("Ruff (Relaying messages)")
                    
                    # Remove old startup messages and send new one
                    await self.remove_previous_startup_messages()
                    startup_embed = discord.Embed(
                        title="🌉 CourtDog Online",
                        description="Ruff (Bridge reconnected and is now active between Discord and Objection.lol. Only 25 messages will be visible at a time.)",
                        color=0x00ff00
                    )
                    startup_embed.add_field(
                        name="Available Commands",
                        value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set your bridge nickname\n/color - Set your bridge message color\n/shaba\n/help - Show this help",
                        inline=False
                    )
                    startup_embed.add_field(
                        name="Admin Commands",
                        value="/titlebar - Change courtroom title\n/slowmode - Set slow mode (requires 3 confirmations)\n/setpassword - Set password to THE USUAL (requires 3 confirmations)\n/text - Change textbox appearance",
                        inline=False
                    )
                    startup_embed.add_field(
                        name="Color Presets",
                        value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver",
                        inline=False
                    )
                    startup_embed.add_field(
                        name="Textbox Presets",
                        value="aa-trilogy, aa-apollo, aa-classic, aa-ds, fallout-nv, fallout-3, dq8, dq7, dq5, lobotomy, katawa, umineko, blue-archive",
                        inline=False
                    )
                    startup_embed.add_field(
                        name="Room Info",
                        value=f"Room ID: `{self.config.get('objection', 'room_id')}`",
                        inline=False
                    )
                    self.startup_message = await self.bridge_channel.send(startup_embed)
                else:
                    embed = discord.Embed(
                        title="❌ Reconnection Failed",
                        description="Failed to reconnect to objection.lol courtroom",
                        color=0xff0000
                    )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except Exception as e:
                print(f"❌ Reconnection error: {e}")
                embed = discord.Embed(
                    title="❌ Reconnection Error",
                    description=f"Error during reconnection: {str(e)}",
                    color=0xff0000
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
        @self.tree.command(name="help", description="Show help information")
        async def help_command(interaction: discord.Interaction):
            """Show help information"""
            embed = discord.Embed(
                title="🤖 CourtBot Help",
                description="Discord bridge for Objection.lol courtrooms",
                color=0x0099ff
            )
            embed.add_field(
                name="Commands",
                value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set/reset your bridge nickname\n/color - Set your message color\n/shaba\n/help - Show this help",
                inline=False
            )
            embed.add_field(
                name="Admin Commands",
                value="/titlebar - Change courtroom title (admin only)\n/slowmode - Set slow mode (admin only, requires 3 confirmations)\n/setpassword - Set password to THE USUAL (admin only, requires 3 confirmations)\n/text - Change textbox appearance (admin only)",
                inline=False
            )
            embed.add_field(
                name="Color Presets",
                value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver\nOr use custom hex codes like #ff0000",
                inline=False
            )
            embed.add_field(
                name="Textbox Presets",
                value="aa-trilogy, aa-apollo, aa-classic, aa-ds, fallout-nv, fallout-3, dq8, dq7, dq5, lobotomy, katawa, umineko, blue-archive\nOr use custom textbox IDs",
                inline=False
            )
            embed.add_field(
                name="How it works",
                value="Messages sent in this channel are relayed to the objection.lol courtroom, and vice versa.",
                inline=False
            )
            embed.add_field(
                name="Room Info",
                value=f"Room ID: `{self.config.get('objection', 'room_id')}`",
                inline=False
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        @self.tree.command(name="nickname", description="Set your bridge nickname for the dog ('reset' to remove)")
        @app_commands.describe(nickname="Nickname when relaying (use 'reset' to remove)")
        async def nickname_command(interaction: discord.Interaction, nickname: str):
            user_id = str(interaction.user.id)

            # Handle reset/removal
            if nickname.lower() in ['reset', 'remove', 'clear', 'delete']:
                if user_id in self.nicknames:
                    del self.nicknames[user_id]
                    save_nicknames(self.nicknames)
                    await interaction.response.send_message("✅ Your bridge nickname has been reset. Your Discord display name will now be used.", ephemeral=True)
                else:
                    await interaction.response.send_message("ℹ️ You don't have a nickname set.", ephemeral=True)
                return

            if not nickname or len(nickname) > 32:
                await interaction.response.send_message("❌ Nickname must be 1-32 characters.", ephemeral=True)
                return

            self.nicknames[user_id] = nickname
            save_nicknames(self.nicknames)
            await interaction.response.send_message(f"✅ Your bridge nickname is now set to: **{nickname}**\nUse `/nickname reset` to remove it.", ephemeral=True)
        @self.tree.command(name="color", description="Set your message color for the courtroom ('reset' to remove)")
        @app_commands.describe(color="Hex color code like 'ff0000' or '#ff0000', preset name like 'red', or 'reset' to remove")
        async def color_command(interaction: discord.Interaction, color: str):
            user_id = str(interaction.user.id)

            # Handle reset/removal
            if color.lower() in ['reset', 'remove', 'clear', 'delete']:
                if user_id in self.colors:
                    del self.colors[user_id]
                    save_colors(self.colors)
                    await interaction.response.send_message("✅ Your message color has been reset. Messages will use default color.", ephemeral=True)
                else:
                    await interaction.response.send_message("ℹ️ You don't have a custom color set.", ephemeral=True)
                return

            # Check if it's a preset color name
            preset_color = PRESET_COLORS.get(color.lower())
            if preset_color:
                self.colors[user_id] = preset_color.lower()
                save_colors(self.colors)
                await interaction.response.send_message(f"✅ Your message color is now set to: **{color.lower()}** (#{preset_color.upper()})\nYour messages will appear in color in the courtroom. Use `/color reset` to remove it.", ephemeral=True)
                return

            # Remove # if present and validate hex color format
            clean_color = color.lstrip('#')
            if not clean_color or not re.match(r'^[0-9a-fA-F]{6}$', clean_color):
                # Show available preset colors in error message
                preset_list = ', '.join(PRESET_COLORS.keys())
                await interaction.response.send_message(f"❌ Color must be a 6-digit hex code (e.g., 'ff0000' or '#ff0000') or a preset color name.\n\n**Available presets:** {preset_list}", ephemeral=True)
                return

            # Store the color code (without #)
            self.colors[user_id] = clean_color.lower()
            save_colors(self.colors)
            await interaction.response.send_message(f"✅ Your message color is now set to: **#{clean_color.upper()}**\nYour messages will appear in color in the courtroom. Use `/color reset` to remove it.", ephemeral=True)
        @self.tree.command(name="shaba")
        async def shaba_command(interaction: discord.Interaction):
            """Shaba command"""
            await interaction.response.defer(ephemeral=True)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=True)
                return

            try:
                # Revert to original bot username when speaking as the bot itself
                original_username = self.config.get('objection', 'bot_username')
                print(f"🎭 Shaba command: Changing to bot username: {original_username}")
                await self.objection_bot.change_username_and_wait(original_username)
                print(f"🎭 Shaba command: Sending message with background color")
                await self.objection_bot.send_message("[#bgs122964]")
                await interaction.followup.send("What the dog doin??", ephemeral=False)
                print(f"🎭 Shaba command: Successfully executed")
            except Exception as e:
                print(f"❌ Shaba command error: {e}")
                await interaction.followup.send(f"❌ Failed to execute shaba command: {str(e)}", ephemeral=True)

        # Admin Commands Section
        @self.tree.command(name="titlebar", description="Change the chatroom title (admin only)")
        @app_commands.describe(title="New title for the chatroom (1-150 characters)")
        async def titlebar_command(interaction: discord.Interaction, title: str):
            """Change chatroom title (admin only)"""
            await interaction.response.defer(ephemeral=False)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=False)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change the title", ephemeral=False)
                return

            # Validate title length
            if not title or len(title) > 150:
                await interaction.followup.send("❌ Title must be between 1 and 150 characters", ephemeral=False)
                return

            # Strip any potentially problematic characters
            title = title.strip()

            try:
                success = await self.objection_bot.update_room_title(title)
                if success:
                    embed = discord.Embed(
                        title="✅ Title Updated",
                        description=f"Successfully changed room title to: **{title}**",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    print(f"[TITLE] Discord user {interaction.user.display_name} changed title to: {title}")
                else:
                    await interaction.followup.send("❌ Failed to update room title. Check bot status and permissions.", ephemeral=False)
            except Exception as e:
                print(f"❌ Title command error: {e}")
                await interaction.followup.send(f"❌ Failed to change title: {str(e)}", ephemeral=False)

        @self.tree.command(name="slowmode", description="Set room slow mode (admin only, requires 3 confirmations)")
        @app_commands.describe(seconds="Slow mode seconds (0-60, 0 = disabled)")
        async def slowmode_command(interaction: discord.Interaction, seconds: int):
            """Set room slow mode (admin only, requires confirmations)"""
            await interaction.response.defer(ephemeral=True)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=True)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change slow mode", ephemeral=True)
                return

            # Validate seconds range
            if seconds < 0 or seconds > 60:
                await interaction.followup.send("❌ Slow mode seconds must be between 0 and 60", ephemeral=True)
                return

            # Create voting embed
            if seconds == 0:
                embed = discord.Embed(
                    title="⚠️ Disable Slow Mode",
                    description="**This action requires 3 user confirmations**\n\nProposed change: **Disable slow mode**",
                    color=0xff9500
                )
            else:
                embed = discord.Embed(
                    title="⚠️ Enable Slow Mode", 
                    description=f"**This action requires 3 user confirmations**\n\nProposed change: **{seconds} second** slow mode",
                    color=0xff9500
                )
            
            embed.add_field(
                name="Instructions",
                value="React with ✅ to confirm this action. Need 4 total reactions (including bot).",
                inline=False
            )
            embed.add_field(
                name="Initiated by",
                value=f"{interaction.user.display_name}",
                inline=True
            )

            message = await self.bridge_channel.send(embed=embed)
            await message.add_reaction("✅")
            
            await interaction.followup.send(f"✅ Slow mode vote initiated. Need 3 more confirmations.", ephemeral=True)
            
            # Wait for reactions
            def check(reaction, user):
                return (reaction.message.id == message.id and 
                       str(reaction.emoji) == "✅" and 
                       not user.bot and
                       reaction.count >= 4)  # Bot + 3 users
            
            try:
                await self.objection_bot.discord_bot.wait_for('reaction_add', timeout=300.0, check=check)
                
                # Execute the slow mode change
                success = await self.objection_bot.update_room_slowmode(seconds)
                if success:
                    if seconds == 0:
                        result_embed = discord.Embed(
                            title="✅ Slow Mode Disabled",
                            description="Slow mode has been disabled in the courtroom",
                            color=0x00ff00
                        )
                    else:
                        result_embed = discord.Embed(
                            title="✅ Slow Mode Enabled",
                            description=f"Slow mode set to **{seconds} seconds** in the courtroom",
                            color=0x00ff00
                        )
                    await message.edit(embed=result_embed)
                else:
                    error_embed = discord.Embed(
                        title="❌ Failed",
                        description="Failed to update slow mode. Check bot status and permissions.",
                        color=0xff0000
                    )
                    await message.edit(embed=error_embed)
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Vote Expired",
                    description="Slow mode vote timed out after 5 minutes",
                    color=0x808080
                )
                await message.edit(embed=timeout_embed)

        @self.tree.command(name="setpassword", description="Set room password to THE USUAL (admin only, requires 3 confirmations)")
        async def setpassword_command(interaction: discord.Interaction):
            """Set room password (admin only, requires confirmations)"""
            await interaction.response.defer(ephemeral=True)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=True)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change password", ephemeral=True)
                return

            # Create voting embed
            embed = discord.Embed(
                title="⚠️ Set Emergency Password",
                description="**This action requires 3 user confirmations**\n\nProposed change: **Set password to THE USUAL**",
                color=0xff9500
            )
            embed.add_field(
                name="Instructions",
                value="React with ✅ to confirm this action. Need 4 total reactions (including bot).",
                inline=False
            )
            embed.add_field(
                name="Initiated by",
                value=f"{interaction.user.display_name}",
                inline=True
            )

            message = await self.bridge_channel.send(embed=embed)
            await message.add_reaction("✅")
            
            await interaction.followup.send(f"✅ Password change vote initiated. Need 3 more confirmations.", ephemeral=True)
            
            # Wait for reactions
            def check(reaction, user):
                return (reaction.message.id == message.id and 
                       str(reaction.emoji) == "✅" and 
                       not user.bot and
                       reaction.count >= 4)  # Bot + 3 users
            
            try:
                await self.objection_bot.discord_bot.wait_for('reaction_add', timeout=300.0, check=check)
                
                # Execute the password change
                success = await self.objection_bot.update_room_password("sneedemfeedem")
                if success:
                    result_embed = discord.Embed(
                        title="✅ Password Set",
                        description="Room password has been set to **THE USUAL**",
                        color=0x00ff00
                    )
                    await message.edit(embed=result_embed)
                else:
                    error_embed = discord.Embed(
                        title="❌ Failed",
                        description="Failed to update room password. Check bot status and permissions.",
                        color=0xff0000
                    )
                    await message.edit(embed=error_embed)
            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    title="⏰ Vote Expired",
                    description="Password change vote timed out after 5 minutes",
                    color=0x808080
                )
                await message.edit(embed=timeout_embed)

        @self.tree.command(name="text", description="Change the chatroom textbox appearance (admin only)")
        @app_commands.describe(style="Textbox style (preset name or custom ID)")
        async def text_command(interaction: discord.Interaction, style: str):
            """Change chatroom textbox appearance (admin only)"""
            await interaction.response.defer(ephemeral=False)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=False)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change the textbox", ephemeral=False)
                return

            # Check if it's a preset textbox name
            preset_textbox = PRESET_TEXTBOXES.get(style.lower())
            if preset_textbox:
                textbox_id = preset_textbox
                style_name = style.lower()
            else:
                # Use the provided style as a custom ID
                textbox_id = style.strip()
                style_name = f"custom ID: {textbox_id}"

            if not textbox_id:
                # Show available preset textboxes in error message
                preset_list = ', '.join(PRESET_TEXTBOXES.keys())
                await interaction.followup.send(f"❌ Style must be a preset name or custom textbox ID.\n\n**Available presets:** {preset_list}", ephemeral=False)
                return

            try:
                success = await self.objection_bot.update_room_textbox(textbox_id)
                if success:
                    embed = discord.Embed(
                        title="✅ Textbox Updated",
                        description=f"Successfully changed textbox to: **{style_name}**",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    print(f"[TEXTBOX] Discord user {interaction.user.display_name} changed textbox to: {style_name}")
                else:
                    await interaction.followup.send("❌ Failed to update textbox. Check bot status and permissions.", ephemeral=False)
            except Exception as e:
                print(f"❌ Textbox command error: {e}")
                await interaction.followup.send(f"❌ Failed to change textbox: {str(e)}", ephemeral=False)

    async def on_ready(self):
        print(f'🤖 Discord bot logged in as {self.user}')
        self.bridge_channel = self.get_channel(self.channel_id)
        if self.bridge_channel:
            print(f'📺 Connected to Discord channel: #{self.bridge_channel.name}')
            
            # Remove any previous "CourtDog Online" startup messages
            await self.remove_previous_startup_messages()
            
            # Send startup message with commands info
            embed = discord.Embed(
                title="🌉 CourtDog Online",
                description="Ruff (Bridge is now active between Discord and Objection.lol. Only 25 messages will be visible at a time.)",
                color=0x00ff00
            )
            embed.add_field(
                name="Available Commands",
                value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set your bridge nickname\n/color - Set your message color\n/shaba\n/help - Show this help",
                inline=False
            )
            embed.add_field(
                name="Admin Commands",
                value="/titlebar - Change courtroom title (admin only)\n/slowmode - Set slow mode (requires 3 confirmations)\n/setpassword - Set password to THE USUAL (requires 3 confirmations)\n/text - Change textbox appearance (admin only)",
                inline=False
            )
            embed.add_field(
                name="Color Presets",
                value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver",
                inline=False
            )
            embed.add_field(
                name="Textbox Presets",
                value="aa-trilogy, aa-apollo, aa-classic, aa-ds, fallout-nv, fallout-3, dq8, dq7, dq5, lobotomy, katawa, umineko, blue-archive",
                inline=False
            )
            embed.add_field(
                name="Room Info",
                value=f"Room ID: `{self.config.get('objection', 'room_id')}`",
                inline=False
            )
            self.startup_message = await self.bridge_channel.send(embed=embed)
        else:
            print(f'❌ Could not find Discord channel with ID: {self.channel_id}')
    async def on_message(self, message):
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        # Only process messages from the bridge channel
        if message.channel.id == self.channel_id:
            # Check ignore patterns
            ignore_patterns = self.config.get('settings', 'ignore_patterns')
            if any(pattern in message.content for pattern in ignore_patterns):
                return
            
            # Ignore messages with Discord user mentions (<@numbers>)
            if re.search(r'<@\d+>', message.content):
                print(f"🚫 Ignoring message with user mention: {message.content[:50]}...")
                return
            
            # Extract image and video URLs from attachments and embeds
            media_urls = self.extract_media_urls(message)
            
            # Prepare message content with media
            content_parts = []
            if message.content.strip():
                content_parts.append(message.content)
            
            # Add media URLs to the message
            if media_urls:
                for url in media_urls:
                    content_parts.append(url)
            
            # If no text content and no media, skip the message
            if not content_parts:
                return
                
            full_content = "\n".join(content_parts)
            
            # Prepare new username and message content
            base_name = self.config.get('objection', 'bot_username')
            discord_name = message.author.display_name
            user_id = str(message.author.id)
            # Use nickname if set, else display name
            nickname = self.nicknames.get(user_id)
            display_name = nickname if nickname else discord_name
            new_username = f"{display_name} ({base_name})"
            
            # Debug logging to prevent impersonation issues
            print(f"🔍 Processing message from Discord user: {discord_name} (ID: {user_id})")
            print(f"🔍 Display name for message: {display_name}")
            print(f"🔍 Constructed username: {new_username} (length: {len(new_username)})")
            
            # Apply user's custom color if set
            user_color = self.colors.get(user_id)
            if user_color:
                # Add fast text command for media URLs, then apply color
                if media_urls:
                    colored_content = f"[#ts15][#/c{user_color}]{full_content}[/#]"
                else:
                    colored_content = f"[#/c{user_color}]{full_content}[/#]"
            else:
                # Add fast text command for media URLs even without color
                if media_urls:
                    colored_content = f"[#ts15]{full_content}"
                else:
                    colored_content = full_content
            
            # Always check username length limit (30 characters for objection.lol)
            # and always decide whether to prefix the message based on this check
            if len(new_username) <= 30:
                # Username fits, use it and send content without prefix
                target_username = new_username
                send_content = colored_content
                print(f"✅ Username fits, using: {target_username}")
            else:
                # Username too long, ALWAYS use base name and ALWAYS prefix message with user's name
                target_username = base_name
                send_content = f"{display_name}: {colored_content}"
                print(f"📏 Username too long, using base name: {target_username}, prefixing with: {display_name}")
            
            # Always change username for each message to prevent impersonation
            username_changed = await self.objection_bot.change_username_and_wait(target_username)
            if not username_changed:
                print("❌ Failed to change username - skipping message")
                return
                
            actual_username = target_username
            message_sent = await self.objection_bot.send_message(send_content)
            if message_sent:
                print(f"🔄 Discord → Objection: {actual_username}: {send_content}")
            else:
                print(f"❌ Failed to send message to objection.lol")
            await self.cleanup_messages()
    async def send_to_discord(self, username, message):
        """Send a message from objection.lol to Discord"""
        if self.bridge_channel:
            # Strip color codes before sending to Discord
            cleaned_message = self.strip_color_codes(message)
            
            # Check for BGM commands and fetch music URLs
            bgm_ids = self.extract_bgm_commands(message)
            if bgm_ids:
                for bgm_id in bgm_ids:
                    music_data = await self.fetch_music_url(bgm_id)
                    if music_data:
                        # Send the music URL as a rich embed with all available info
                        music_embed = discord.Embed(
                            title="🎵 Background Music",
                            description=f"**{username}** played music",
                            color=0x9b59b6
                        )
                        music_embed.add_field(
                            name="Track Name",
                            value=music_data['name'],
                            inline=True
                        )
                        music_embed.add_field(
                            name="Track ID", 
                            value=f"#{music_data['id']}",
                            inline=True
                        )
                        music_embed.add_field(
                            name="Volume",
                            value=f"{music_data['volume']}%",
                            inline=True
                        )
                        music_embed.add_field(
                            name="Audio File",
                            value=f"[Click to play]({music_data['url']})",
                            inline=False
                        )
                        await self.bridge_channel.send(embed=music_embed)
                        print(f"🎵 Posted music info for BGM {bgm_id}: '{music_data['name']}' -> {music_data['url']}")
            
            unix_timestamp = int(time.time())
            formatted_message = f"**{username}**:\n{cleaned_message}\n-# <t:{unix_timestamp}:T>"
            sent_message = await self.bridge_channel.send(formatted_message)
            print(f"🔄 Objection → Discord: {username}: {cleaned_message}")
            # Clean up old messages if needed
            await self.cleanup_messages()
    async def send_user_notification(self, username, action, user_list=None):
        """Send user join/leave notifications to Discord"""
        if not self.bridge_channel or not self.config.get('settings', 'show_join_leave'):
            return
        if action == "joined":
            embed = discord.Embed(
                title="👋 User Joined",
                description=f"**{username}** has joined the courtroom",
                color=0x00ff00
            )
        elif action == "left":
            embed = discord.Embed(
                title="👋 User Left",
                description=f"**{username}** has left the courtroom",
                color=0xff9900
            )
        else:
            return
        sent_message = await self.bridge_channel.send(embed=embed)
        # Clean up old messages if needed
        await self.cleanup_messages()
    async def send_username_change_notification(self, old_username, new_username):
        """Send username change notifications to Discord"""
        if not self.bridge_channel or not self.config.get('settings', 'show_join_leave'):
            return

        embed = discord.Embed(
            title="✏️ Username Changed",
            description=f"**{old_username}** is now **{new_username}**",
            color=0x0099ff
        )

        sent_message = await self.bridge_channel.send(embed=embed)
        # Clean up old messages if needed
        await self.cleanup_messages()
    async def remove_previous_startup_messages(self):
        """Remove any previous 'CourtDog Online' startup messages from the channel"""
        if not self.bridge_channel:
            return
            
        try:
            # Check if bot has permission to delete messages
            if not self.bridge_channel.permissions_for(self.bridge_channel.guild.me).manage_messages:
                print("⚠️ Bot lacks 'Manage Messages' permission - cannot delete old startup messages")
                return

            deleted_count = 0
            # Look through recent messages for previous startup messages
            async for message in self.bridge_channel.history(limit=50):
                # Check if it's a bot message with "CourtDog Online" embed
                if (message.author == self.user and 
                    message.embeds and 
                    len(message.embeds) > 0 and 
                    message.embeds[0].title == "🌉 CourtDog Online"):
                    try:
                        await message.delete()
                        deleted_count += 1
                        print(f"🧹 Deleted previous startup message")
                    except discord.NotFound:
                        pass  # Message already deleted
                    except Exception as e:
                        print(f"⚠️ Failed to delete startup message: {e}")
            
            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} old startup message(s)")
                
        except Exception as e:
            print(f"⚠️ Error during startup message cleanup: {e}")

    async def cleanup_messages(self):
        """Delete old messages to maintain message limit - keep only last 25 messages"""
        max_messages = 25  # Fixed limit
        buffer_threshold = 3  # Only start deleting when 3+ messages over limit

        try:
            # Check if bot has permission to delete messages
            if not self.bridge_channel.permissions_for(self.bridge_channel.guild.me).manage_messages:
                print("⚠️ Bot lacks 'Manage Messages' permission - cannot delete old messages")
                return

            # Fetch recent messages from the channel (get more than we need to ensure we have enough)
            messages = []
            async for message in self.bridge_channel.history(limit=100):
                # Skip the startup message
                if self.startup_message and message.id == self.startup_message.id:
                    continue
                messages.append(message)

            print(f"🔍 Found {len(messages)} messages in channel (excluding startup message)")

            # Only start deleting if we have more than max_messages + buffer_threshold
            deletion_threshold = max_messages + buffer_threshold

            if len(messages) > deletion_threshold:
                messages_to_delete = messages[max_messages:]  # Get messages beyond the limit
                print(f"🧹 Need to delete {len(messages_to_delete)} old messages (threshold: {deletion_threshold})")

                deleted_count = 0
                for message in messages_to_delete:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        pass  # Message already deleted
                    except discord.Forbidden:
                        print("⚠️ Bot lacks permission to delete this message")
                    except Exception as e:
                        print(f"⚠️ Failed to delete message: {e}")

                print(f"🧹 Successfully deleted {deleted_count} old messages")
            else:
                print(f"✅ No cleanup needed ({len(messages)}/{deletion_threshold} messages, threshold not reached)")

        except Exception as e:
            print(f"⚠️ Error during message cleanup: {e}")
    async def full_cleanup(self):
        """Delete all messages in the bridge channel except the startup message."""
        if not self.bridge_channel:
            return
        try:
            if not self.bridge_channel.permissions_for(self.bridge_channel.guild.me).manage_messages:
                print("⚠️ Bot lacks 'Manage Messages' permission - cannot delete messages for full cleanup")
                return
            messages = []
            async for message in self.bridge_channel.history(limit=200):
                if self.startup_message and message.id == self.startup_message.id:
                    continue
                messages.append(message)
            print(f"🧹 Full cleanup: deleting {len(messages)} messages")
            for message in messages:
                try:
                    await message.delete()
                except Exception as e:
                    print(f"⚠️ Failed to delete message: {e}")
        except Exception as e:
            print(f"⚠️ Error during full cleanup: {e}")
    async def send_pairing_request_to_discord(self, pair_data, objection_bot):
        if not self.bridge_channel:
            print("[PAIRING] No bridge channel to send pairing request.")
            return
        # Pairing request handling removed - bot will handle automatically

    async def send_mod_request_to_discord(self, user_id, username, objection_bot):
        """Send a moderator request to Discord for approval"""
        if not self.bridge_channel:
            print("[MOD] No bridge channel to send mod request.")
            return
        
        embed = discord.Embed(
            title="🛡️ Moderator Request",
            description=f"Ruff (**{username}** has requested moderator status)",
            color=0xff9500  # Orange color
        )
        embed.add_field(
            name="User Info",
            value=f"Username: {username}\nUser ID: `{user_id[:8]}...`",
            inline=False
        )
        embed.add_field(
            name="Action Required",
            value="Click the button below to grant moderator status to this user.",
            inline=False
        )
        
        view = ModRequestView(user_id, username, objection_bot)
        await self.bridge_channel.send(embed=embed, view=view)

class PairingView(discord.ui.View):
    def __init__(self, pair_data, objection_bot):
        super().__init__(timeout=60)
        self.pair_data = pair_data
        self.objection_bot = objection_bot
        self.response_sent = False

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def yes_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.response_sent:
            await interaction.response.send_message("Already responded.", ephemeral=True)
            return
        await interaction.response.send_message("✅ Accepted pairing request!", ephemeral=True)
        await self.objection_bot.accept_pairing(self.pair_data)
        self.response_sent = True
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def no_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.response_sent:
            await interaction.response.send_message("Already responded.", ephemeral=True)
            return
        await interaction.response.send_message("❌ Declined pairing request!", ephemeral=True)
        await self.objection_bot.decline_pairing(self.pair_data)
        self.response_sent = True
        self.stop()

class ModRequestView(discord.ui.View):
    def __init__(self, user_id, username, objection_bot):
        super().__init__(timeout=300)  # 5 minutes timeout
        self.user_id = user_id
        self.username = username
        self.objection_bot = objection_bot
        self.response_sent = False

    @discord.ui.button(label="Grant Moderator", style=discord.ButtonStyle.primary, emoji="🛡️")
    async def grant_mod_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.response_sent:
            await interaction.response.send_message("Already responded.", ephemeral=True)
            return
        
        # Check if bot still has admin status
        if not self.objection_bot.is_admin:
            await interaction.response.send_message("❌ Bot no longer has admin status - cannot grant moderator.", ephemeral=True)
            return
        
        # Attempt to add moderator
        success = await self.objection_bot.add_moderator(self.user_id)
        
        if success:
            # Update the embed to show completion
            embed = discord.Embed(
                title="✅ Moderator Granted",
                description=f"**{self.username}** has been granted moderator status!",
                color=0x00ff00  # Green color
            )
            embed.add_field(
                name="User Info",
                value=f"Username: {self.username}\nUser ID: `{self.user_id[:8]}...`",
                inline=False
            )
            embed.add_field(
                name="Status",
                value="✅ Moderator request completed successfully.",
                inline=False
            )
            
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Update the message with new embed and disabled view
            await interaction.response.edit_message(embed=embed, view=self)
            print(f"[MOD] {self.username} granted moderator status via Discord approval")
        else:
            await interaction.response.send_message(f"❌ Failed to grant moderator status to **{self.username}**. They may no longer be in the room.", ephemeral=True)
        
        self.response_sent = True
        self.stop()

class ObjectionBot:
    def __init__(self, config):
        self.config = config
        self.websocket = None
        self.room_id = config.get('objection', 'room_id')
        self.username = config.get('objection', 'bot_username')
        self.connected = False
        self.user_id = None
        self.message_queue = queue.Queue()
        self.discord_bot = None
        self.user_names = {}  # Changed from users to match existing code
        
        # Connection management
        self.ping_interval = 25000  # Default ping interval in ms
        self.ping_timeout = 5000    # Default ping timeout in ms
        
        # Auto-reconnect settings
        self.auto_reconnect = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds between attempts
        self.reconnect_task = None
        
        # Admin and moderation settings
        self.is_admin = False
        self.current_mods = set()  # Set of current moderator user IDs
        
        # For Discord bridge compatibility
        self._username_change_event = asyncio.Event()
        self._pending_username = None
        self._pending_pair_request = None
    
    async def connect_to_room(self):
        """Connect to the courtroom WebSocket using raw websockets"""
        base_url = "wss://objection.lol"
        # Convert HTTP URL to WebSocket URL and construct with parameters
        websocket_url = f"{base_url}/courtroom-api/socket.io/?roomId={self.room_id}&username={self.username}&password=&EIO=4&transport=websocket"
        
        try:
            # Disconnect first if already connected
            if self.connected:
                await self.graceful_disconnect()
                await asyncio.sleep(2)  # Wait longer for clean disconnection

            print(f"🔌 Connecting to WebSocket: {websocket_url}")
            # Use default WebSocket settings, let server handle ping/pong
            self.websocket = await websockets.connect(websocket_url)
            print(f"✅ WebSocket connection established")
            
            # Wait for initial handshake message
            print("⏳ Waiting for server handshake...")
            initial_message = await self.websocket.recv()
            print(f"📨 Received handshake: {initial_message}")
            
            if initial_message.startswith('0'):
                # Parse ping interval and timeout from handshake
                try:
                    handshake_data = json.loads(initial_message[1:])
                    self.ping_interval = handshake_data.get('pingInterval', self.ping_interval)
                    self.ping_timeout = handshake_data.get('pingTimeout', self.ping_timeout)
                    print(f"⏱️ Ping interval: {self.ping_interval}ms, Timeout: {self.ping_timeout}ms")
                except:
                    print("⚠️ Could not parse handshake data, using defaults")
                
                # Send handshake acknowledgment
                print("🤝 Sending handshake acknowledgment...")
                await self.websocket.send("40")
                
                # Wait for server response
                response = await self.websocket.recv()
                print(f"📨 Server response: {response}")
                
                if response.startswith('40'):
                    print("✅ Handshake completed successfully")
                    self.connected = True
                    self.reconnect_attempts = 0  # Reset reconnect attempts on successful connection
                    
                    # Send "me" message to get user info
                    print("🔍 Sending 'me' message...")
                    await self.websocket.send('42["me"]')
                    
                    # Send "get_room" message to join/get room info
                    print("🏠 Sending 'get_room' message...")
                    await self.websocket.send('42["get_room"]')
                    
                    # Start the message processing loop only - let server handle ping/pong
                    asyncio.create_task(self.message_loop())
                    
                    return True
                else:
                    print(f"❌ Unexpected response after handshake: {response}")
                    return False
            else:
                print(f"❌ Unexpected initial message: {initial_message}")
                return False
            
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            if hasattr(self, 'websocket') and self.websocket:
                try:
                    await self.websocket.close()
                except:
                    pass
            return False
    
    async def message_loop(self):
        """Main message processing loop"""
        try:
            async for message in self.websocket:
                await self.process_message(message)
        except websockets.exceptions.ConnectionClosed:
            print("🔌 WebSocket connection closed")
            self.connected = False
            # Start auto-reconnect if enabled
            if self.auto_reconnect:
                await self.start_auto_reconnect()
        except Exception as e:
            print(f"❌ Error in message loop: {e}")
            self.connected = False
            # Start auto-reconnect if enabled
            if self.auto_reconnect:
                await self.start_auto_reconnect()
    
    async def process_message(self, message: str):
        """Process incoming WebSocket messages"""
        try:
            if message.startswith('42["message"'):
                # Handle chat messages
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1 and isinstance(data[1], dict):
                            await self.handle_message(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for message: {e}")
            
            elif message.startswith('42["update_room"'):
                # Handle room updates
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_room_update(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for room update: {e}")
            
            elif message.startswith('42["me"'):
                # Handle "me" response
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_me_response(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for me response: {e}")
            
            elif message.startswith('42["user_joined"'):
                # Handle user joined events
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_user_joined(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for user joined: {e}")
            
            elif message.startswith('42["user_left"'):
                # Handle user left events
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_user_left(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for user left: {e}")
            
            elif message.startswith('42["update_user"'):
                # Handle user update events
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 2:
                            await self.handle_update_user(data[1], data[2])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for user update: {e}")
            
            elif message.startswith('42["create_pair"'):
                # Handle pairing requests
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_create_pair(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for create pair: {e}")
            
            elif message.startswith('42["owner_transfer"'):
                # Handle owner/admin transfer events
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 2:
                            await self.handle_owner_transfer(data[1], data[2])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for owner transfer: {e}")
            
            elif message.startswith('42["update_mods"'):
                # Handle moderator list updates
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_update_mods(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for update mods: {e}")
            
            elif message.startswith('2'):
                # Ping message from server, respond with pong
                await self.websocket.send("3")
                print("📡 Received ping, sent pong")
                
            elif message.startswith('3'):
                # Pong message from server (response to our ping)
                print("📡 Received pong")
            
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    async def start_auto_reconnect(self):
        """Start the auto-reconnect process"""
        if self.reconnect_task and not self.reconnect_task.done():
            return  # Already attempting to reconnect
        
        self.reconnect_task = asyncio.create_task(self.auto_reconnect_loop())
    
    async def auto_reconnect_loop(self):
        """Auto-reconnect loop with exponential backoff"""
        while self.auto_reconnect and not self.connected and self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            delay = min(self.reconnect_delay * (2 ** (self.reconnect_attempts - 1)), 60)  # Max 60 seconds
            
            print(f"🔄 Auto-reconnect attempt {self.reconnect_attempts}/{self.max_reconnect_attempts} in {delay} seconds...")
            await asyncio.sleep(delay)
            
            try:
                success = await self.connect_to_room()
                if success:
                    print("✅ Auto-reconnect successful!")
                    # Notify Discord of reconnection
                    if self.discord_bot and self.discord_bot.bridge_channel:
                        embed = discord.Embed(
                            title="🔄 Reconnected",
                            description="Successfully reconnected to objection.lol courtroom",
                            color=0x00ff00
                        )
                        await self.discord_bot.bridge_channel.send(embed=embed)
                    return
                else:
                    print(f"❌ Auto-reconnect attempt {self.reconnect_attempts} failed")
            except Exception as e:
                print(f"❌ Auto-reconnect attempt {self.reconnect_attempts} error: {e}")
        
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            print(f"❌ Auto-reconnect failed after {self.max_reconnect_attempts} attempts")
            # Notify Discord of failure
            if self.discord_bot and self.discord_bot.bridge_channel:
                embed = discord.Embed(
                    title="❌ Reconnection Failed",
                    description=f"Failed to reconnect after {self.max_reconnect_attempts} attempts. Use `/reconnect` to try again.",
                    color=0xff0000
                )
                await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_message(self, data):
        """Handle incoming chat messages"""
        user_id = data.get('userId')
        message = data.get('message', {})
        text = message.get('text', '')

        # Check for pairing request message
        if "Please pair with me CourtDog-sama" in text and self._pending_pair_request and user_id != self.user_id:
            print(f"[PAIRING] Auto-accepting pairing due to message: {text}")
            await self.accept_pairing(self._pending_pair_request)
            self._pending_pair_request = None
            return

        # Check for moderator request message
        if "Please mod me CourtDog-sama" in text and self.is_admin and user_id != self.user_id:
            print(f"[MOD] Mod request from user: {text}")
            await self.handle_mod_request(user_id)
            return

        if user_id != self.user_id:
            # Check ignore patterns 
            ignore_patterns = self.config.get('settings', 'ignore_patterns')
            if any(pattern in text for pattern in ignore_patterns):
                return
            
            # Ignore messages with Discord user mentions (<@numbers>)
            if re.search(r'<@\d+>', text):
                print(f"🚫 Ignoring objection.lol message with user mention: {text[:50]}...")
                return
            
            # Get username from our stored mapping
            username = self.user_names.get(user_id)
            # If we don't have the username, request room update and wait briefly
            if username is None:
                print(f"🔄 Unknown user {user_id[:8]}, requesting room update...")
                await self.websocket.send('42["get_room"]')
                username = self.user_names.get(user_id, f"User-{user_id[:8]}")
            print(f"📨 Received: {username}: {text}")
            # Send to Discord if connected
            if self.discord_bot:
                await self.discord_bot.send_to_discord(username, text)
    
    async def handle_room_update(self, data):
        """Handle room updates to get user information"""
        users = data.get('users', [])

        # Update our username mapping
        for user in users:
            if 'id' in user and 'username' in user:
                user_id = user['id']
                username = user['username']
                self.user_names[user_id] = username
        
        # Handle existing moderators when joining room
        if 'mods' in data:
            existing_mods = data.get('mods', [])
            if existing_mods:
                self.current_mods = set(existing_mods)
                # Get usernames for logging
                mod_usernames = []
                for mod_id in existing_mods:
                    username = self.user_names.get(mod_id, f"User-{mod_id[:8]}")
                    mod_usernames.append(username)
                print(f"[MOD] Found existing moderators in room: {mod_usernames}")
            else:
                print(f"[MOD] No existing moderators in room")
        
        # Signal username change event if our username was updated
        if self.user_id:
            for user in users:
                if user.get('id') == self.user_id and self._pending_username:
                    if user.get('username') == self._pending_username:
                        print(f"[DEBUG] Username for our user_id matched pending username: {self._pending_username}")
                        self._username_change_event.set()
        
        usernames = [user.get('username') for user in users]
        print(f"👥 Users in room: {usernames}")
    
    async def handle_me_response(self, data):
        """Handle 'me' response to get our user ID"""
        if 'user' in data and 'id' in data['user']:
            self.user_id = data['user']['id']
            print(f"🤖 Bot ID: {self.user_id}")
    
    async def handle_user_joined(self, data):
        """Handle user_joined events"""
        print(f"[DEBUG] Received user_joined: {data}")

        if isinstance(data, dict):
            user_id = data.get('id')
            username = data.get('username')

            if user_id and username:
                # Add to our user mapping
                self.user_names[user_id] = username

                # Don't show notification for the bot itself
                if user_id != self.user_id:
                    print(f"👋 User joined: {username}")

                    # Send join notification to Discord
                    if self.discord_bot:
                        current_users = list(self.user_names.values())
                        await self.discord_bot.send_user_notification(username, "joined", current_users)
    
    async def handle_user_left(self, user_id):
        """Handle user_left events"""
        print(f"[DEBUG] Received user_left: {user_id}")

        if user_id and user_id in self.user_names:
            username = self.user_names[user_id]

            # Don't show notification for the bot itself
            if user_id != self.user_id:
                print(f"👋 User left: {username}")

                # Send leave notification to Discord
                if self.discord_bot:
                    # Remove from mapping first, then get current users
                    del self.user_names[user_id]
                    current_users = list(self.user_names.values())
                    await self.discord_bot.send_user_notification(username, "left", current_users)
            else:
                # Still remove from mapping even if it's the bot
                del self.user_names[user_id]
    
    async def handle_update_user(self, user_id, user_data):
        """Handle user updates (username changes)"""
        print(f"[DEBUG] Received update_user: user_id={user_id}, data={user_data}")

        if isinstance(user_data, dict) and user_id:
            new_username = user_data.get('username')

            if new_username:
                # Get the old username before updating
                old_username = self.user_names.get(user_id, f"User-{user_id[:8]}")

                # Update our user mapping with the new username
                self.user_names[user_id] = new_username

                # Don't show notification for the bot itself
                if user_id != self.user_id:
                    print(f"✏️ User changed name: {old_username} → {new_username}")

                    # Send name change notification to Discord
                    if self.discord_bot:
                        await self.discord_bot.send_username_change_notification(old_username, new_username)
    
    async def handle_create_pair(self, data):
        """Handle pairing requests"""
        print(f"[PAIRING] Received create_pair: {data}")
        # Only respond if our user_id is in the pairs list
        pairs = data.get('pairs', [])
        if not self.user_id:
            print("[PAIRING] Bot user_id not set yet, ignoring create_pair.")
            return
        found = any(pair.get('userId') == self.user_id for pair in pairs)
        if not found:
            print(f"[PAIRING] Ignoring create_pair: bot user_id {self.user_id} not in pairs.")
            return
        if self.discord_bot:
            await self.discord_bot.send_pairing_request_to_discord(data, self)
        self._pending_pair_request = data
        # Revert to original bot username when speaking as the bot itself
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        await self.send_message("Ruff (You want to pair? Say exactly this: Please pair with me CourtDog-sama)")
    
    async def handle_owner_transfer(self, new_owner_id, room_code):
        """Handle owner/admin transfer events"""
        print(f"[ADMIN] Received owner_transfer: new_owner_id={new_owner_id}, room_code={room_code}")
        
        # Check if the bot received admin status
        if new_owner_id == self.user_id:
            print("🎯 Bot has been granted admin/owner status!")
            self.is_admin = True
            
            # Send notification to Discord
            if self.discord_bot and self.discord_bot.bridge_channel:
                embed = discord.Embed(
                    title="👑 Admin Status Granted",
                    description="Ruff (I am now an admin in the courtroom!)",
                    color=0xffd700  # Gold color
                )
                embed.add_field(
                    name="Status",
                    value="Ruff (I can now perform admin actions including moderator management.)",
                    inline=False
                )
                await self.discord_bot.bridge_channel.send(embed=embed)
        else:
            # Someone else received admin status, bot is no longer admin
            if self.is_admin:
                print("👑 CourtDog is no longer admin")
                self.is_admin = False
            
            # Someone else received admin status
            username = self.user_names.get(new_owner_id, f"User-{new_owner_id[:8]}")
            print(f"👑 {username} has been granted admin/owner status")
            
            # Optional: Send notification to Discord about other admin changes
            if self.discord_bot and self.discord_bot.bridge_channel:
                embed = discord.Embed(
                    title="👑 Admin Status Changed",
                    description=f"**{username}** has been granted admin status in the courtroom",
                    color=0x0099ff
                )
                await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_update_mods(self, mod_list):
        """Handle moderator list updates from the server"""
        print(f"[MOD] Received update_mods: {mod_list}")
        
        # Update our current moderators list with what the server tells us
        if isinstance(mod_list, list):
            self.current_mods = set(mod_list)
            
            # Get usernames for logging
            mod_usernames = []
            for mod_id in mod_list:
                username = self.user_names.get(mod_id, f"User-{mod_id[:8]}")
                mod_usernames.append(username)
            
            print(f"[MOD] Current moderators: {mod_usernames}")
        else:
            print(f"[MOD] Warning: Expected list but got {type(mod_list)}: {mod_list}")
    
    async def handle_mod_request(self, user_id):
        """Handle moderator request from a user"""
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        print(f"[MOD] Processing mod request from {username} ({user_id})")
        
        # Check if user is already a moderator
        if user_id in self.current_mods:
            print(f"[MOD] {username} is already a moderator")
            return
        
        # Send mod request to Discord for approval
        if self.discord_bot and self.discord_bot.bridge_channel:
            await self.discord_bot.send_mod_request_to_discord(user_id, username, self)
    
    async def add_moderator(self, user_id):
        """Add a user as a moderator"""
        if not self.is_admin:
            print("[MOD] Cannot add moderator - bot is not admin")
            return False
        
        # Check if user is still in the room
        if user_id not in self.user_names:
            print(f"[MOD] Cannot add moderator - user {user_id[:8]} not in room")
            return False
        
        # Add to current mods set
        self.current_mods.add(user_id)
        
        # Update moderators on server
        return await self.update_moderators()
    
    async def update_moderators(self):
        """Update the moderator list on the server"""
        if not self.is_admin:
            print("[MOD] Cannot update moderators - bot is not admin")
            return False
        
        # Filter out users who are no longer in the room
        valid_mods = [mod_id for mod_id in self.current_mods if mod_id in self.user_names]
        self.current_mods = set(valid_mods)
        
        # Send update to server
        try:
            # Send as object with "mods" key, not array directly
            update_data = {"mods": valid_mods}
            message = f'42["update_mods",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            
            mod_usernames = [self.user_names.get(mod_id, f"User-{mod_id[:8]}") for mod_id in valid_mods]
            print(f"[MOD] Updated moderators: {mod_usernames}")
            return True
        except Exception as e:
            print(f"[MOD] Failed to update moderators: {e}")
            return False
    
    async def change_username_and_wait(self, new_username, timeout=2.0):
        """Change the bot's username using WebSocket"""
        print(f"[DEBUG] Requesting username change to: {new_username}")
        
        # Check if WebSocket is still connected
        if not self.connected:
            print("❌ Cannot change username - Bot marked as disconnected")
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
            
        if not self.websocket:
            print("❌ Cannot change username - WebSocket is None")
            self.connected = False
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
            
        if self.websocket.close_code is not None:
            print(f"❌ Cannot change username - WebSocket closed with code {self.websocket.close_code}")
            self.connected = False
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
            
        self._pending_username = new_username
        self._username_change_event.clear()
        
        try:
            # Send username change via WebSocket
            message_data = {"username": new_username}
            message = f'42["change_username",{json.dumps(message_data)}]'
            await self.websocket.send(message)
            
            # No waiting or timeout, return immediately for compatibility
            self._pending_username = None
            return True
        except Exception as e:
            print(f"❌ Username change failed: {e}")
            self.connected = False
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
    
    def set_discord_bot(self, discord_bot):
        """Link the Discord bot"""
        self.discord_bot = discord_bot

    async def accept_pairing(self, pair_data):
        """Accept a pairing request"""
        print(f"[PAIRING] Accepting pair: {pair_data}")
        # Extract pairId from the create_pair data
        pair_id = None
        if isinstance(pair_data, dict):
            pair_id = pair_data.get('id')
        if pair_id:
            response_data = {"pairId": pair_id, "status": "accepted"}
            message = f'42["respond_to_pair",{json.dumps(response_data)}]'
            await self.websocket.send(message)
        else:
            print("[PAIRING] Could not find pairId in pair_data, not sending respond_to_pair.")

    async def decline_pairing(self, pair_data):
        """Decline a pairing request"""
        print(f"[PAIRING] Declining pair: {pair_data}")
        # Extract pairId from the create_pair data
        pair_id = None
        if isinstance(pair_data, dict):
            pair_id = pair_data.get('id')
        if pair_id:
            response_data = {"pairId": pair_id, "status": "rejected"}
            message = f'42["respond_to_pair",{json.dumps(response_data)}]'
            await self.websocket.send(message)
            await self.websocket.send('42["leave_pair"]')
        else:
            print("[PAIRING] Could not find pairId in pair_data, only sending leave_pair.")
            await self.websocket.send('42["leave_pair"]')
    
    async def graceful_disconnect(self):
        """Gracefully disconnect: clean up Discord, update room, disconnect socket."""
        print("🔄 Starting graceful disconnect...")
        
        # Cancel auto-reconnect if in progress
        self.auto_reconnect = False
        if self.reconnect_task and not self.reconnect_task.done():
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self.discord_bot:
            try:
                await self.discord_bot.full_cleanup()
            except Exception as e:
                print(f"⚠️ Error during Discord cleanup: {e}")
        
        if self.connected and self.websocket:
            try:
                # Try to emit final room update before disconnecting
                await self.websocket.send('42["get_room"]')
                await asyncio.sleep(0.5)  # Give server time to process
            except Exception as e:
                print(f"⚠️ Could not emit get_room on disconnect: {e}")
            
            try:
                # Explicitly close the websocket
                print("🔌 Closing WebSocket connection...")
                await self.websocket.close()
                
                # Wait for disconnection to complete
                await asyncio.sleep(1)
                
                print("✅ WebSocket closed successfully")
                    
            except Exception as e:
                print(f"⚠️ Error during socket disconnect: {e}")
        
        # Always reset connection state
        self.connected = False
        print("✅ Graceful disconnect completed")
    
    async def send_message(self, text):
        """Send a message to the chatroom"""
        if not self.connected:
            print("❌ Not connected - cannot send message")
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
            
        # Check if socket is actually connected before sending
        if not self.websocket or self.websocket.close_code is not None:
            print("❌ WebSocket connection lost - cannot send message")
            self.connected = False
            # Trigger auto-reconnect if not already in progress
            if self.auto_reconnect:
                await self.start_auto_reconnect()
            return False
            
        character_id = self.config.get('settings', 'character_id')
        pose_id = self.config.get('settings', 'pose_id')
        message_data = {
            "characterId": character_id,
            "poseId": pose_id,
            "text": text
        }
        
        try:
            message = f'42["message",{json.dumps(message_data)}]'
            await self.websocket.send(message)
            print(f"📤 Sent: {text}")
            return True
        except Exception as e:
            print(f"❌ Send failed: {e}")
            # If send fails, it indicates connection issues
            if "closed" in str(e).lower() or "disconnected" in str(e).lower():
                print("🔗 Send failure suggests connection loss - marking as disconnected")
                self.connected = False
                # Trigger auto-reconnect if not already in progress
                if self.auto_reconnect:
                    await self.start_auto_reconnect()
            return False
    def start_input_thread(self):
        """Start a thread to handle console input"""
        def input_worker():
            while self.connected:
                try:
                    message = input("CourtBot> ")
                    if message.lower() in ['quit', 'exit', 'stop']:
                        self.message_queue.put(None)  # Signal to quit
                        break
                    elif message.strip():
                        self.message_queue.put(message)
                except EOFError:
                    break
        thread = threading.Thread(target=input_worker, daemon=True)
        thread.start()
    
    async def interactive_mode(self):
        """Handle interactive messaging"""
        print("💬 Interactive mode started. Type messages to send (or 'quit' to exit):")
        self.start_input_thread()
        while self.connected:
            try:
                # Check for messages from input thread
                if not self.message_queue.empty():
                    message = self.message_queue.get_nowait()
                    if message is None:  # Quit signal
                        break
                    await self.send_message(message)
                await asyncio.sleep(0.1)  # Small delay to prevent busy waiting
            except KeyboardInterrupt:
                break
    
    async def keep_alive(self):
        """Keep the objection bot alive"""
        while self.connected:
            await asyncio.sleep(1)
    
    async def disconnect(self):
        """Disconnect from the server"""
        await self.graceful_disconnect()
    
    async def update_room_title(self, title):
        """Update the room title (admin only)"""
        if not self.is_admin:
            print("[TITLE] Cannot update title - bot is not admin")
            return False
        
        if not title or len(title) > 150:
            print("[TITLE] Title must be 1-150 characters")
            return False
        
        # Send update to server
        try:
            update_data = {"title": title}
            message = f'42["update_room",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            print(f"[TITLE] Updated room title: {title}")
            return True
        except Exception as e:
            print(f"[TITLE] Error updating title: {e}")
            return False

    async def update_room_slowmode(self, seconds):
        """Update the room slow mode (admin only)"""
        if not self.is_admin:
            print("[SLOWMODE] Cannot update slow mode - bot is not admin")
            return False
        
        if seconds < 0 or seconds > 60:
            print("[SLOWMODE] Slow mode seconds must be 0-60")
            return False
        
        # Send update to server
        try:
            update_data = {"slowModeSeconds": seconds}
            message = f'42["update_room",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            if seconds == 0:
                print(f"[SLOWMODE] Disabled slow mode")
            else:
                print(f"[SLOWMODE] Set slow mode to {seconds} seconds")
            return True
        except Exception as e:
            print(f"[SLOWMODE] Error updating slow mode: {e}")
            return False

    async def update_room_password(self, password):
        """Update the room password (admin only)"""
        if not self.is_admin:
            print("[PASSWORD] Cannot update password - bot is not admin")
            return False
        
        # Send update to server using update_room_admin
        try:
            update_data = {"password": password}
            message = f'42["update_room_admin",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            print(f"[PASSWORD] Updated room password")
            return True
        except Exception as e:
            print(f"[PASSWORD] Error updating password: {e}")
            return False

    async def update_room_textbox(self, textbox_id):
        """Update the room textbox appearance (admin only)"""
        if not self.is_admin:
            print("[TEXTBOX] Cannot update textbox - bot is not admin")
            return False
        
        if not textbox_id:
            print("[TEXTBOX] Textbox ID cannot be empty")
            return False
        
        # Send update to server
        try:
            update_data = {"chatbox": textbox_id}
            message = f'42["update_room",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            print(f"[TEXTBOX] Updated room textbox: {textbox_id}")
            return True
        except Exception as e:
            print(f"[TEXTBOX] Error updating textbox: {e}")
            return False

async def shutdown(objection_bot, discord_bot):
    print("Shutting down bots...")
    await objection_bot.disconnect()
    await discord_bot.close()
    print("Bots disconnected. Exiting.")
    sys.exit(0)

def setup_signal_handlers(loop, objection_bot, discord_bot):
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(objection_bot, discord_bot)))
        except NotImplementedError:
            # add_signal_handler may not be implemented on Windows event loop
            pass

async def terminal_command_listener(objection_bot, discord_bot):
    """Listen for terminal commands and handle them."""
    while True:
        try:
            cmd = (await aioconsole.ainput("CourtBot> ")).strip()
            cmd_lower = cmd.lower()
            
            if cmd_lower == "disconnect":
                print("🛑 Disconnect command received. Disconnecting bots (but script will keep running)...")
                await objection_bot.disconnect()
                print("✅ Bots disconnected. Script is still running. Type 'reconnect' to reconnect or 'quit' to exit.")
            elif cmd_lower in ["quit", "exit", "stop"]:
                print("🛑 Quit command received. Shutting down bots and exiting...")
                await shutdown(objection_bot, discord_bot)
            elif cmd_lower == "reconnect":
                print("🔄 Reconnect command received. Attempting to reconnect...")
                await objection_bot.connect_to_room()
                print("✅ Reconnection attempted.")
            elif cmd_lower.startswith("say "):
                # Extract the message after "say "
                message = cmd[4:]  # Remove "say " prefix (preserving original case)
                if message.strip():
                    if objection_bot.connected:
                        # Revert to original bot username when speaking as the bot itself
                        original_username = objection_bot.config.get('objection', 'bot_username')
                        await objection_bot.change_username_and_wait(original_username)
                        # Small delay after username change before sending message
                        await objection_bot.send_message(message)
                        print(f"📤 Sent to courtroom: {message}")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a message after 'say'. Example: say Hello everyone!")
                    if objection_bot.connected:
                        # Revert to original bot username when speaking as the bot itself
                        original_username = objection_bot.config.get('objection', 'bot_username')
                        await objection_bot.change_username_and_wait(original_username)
                        await objection_bot.send_message(message)
                        print(f"📤 Sent to courtroom: {message}")
                print(f"Unknown command: {cmd_lower}. Type 'help' for available commands.")
        except (EOFError, KeyboardInterrupt):
            print("🛑 Terminal closed. Shutting down bots...")
            await shutdown(objection_bot, discord_bot)
async def main():
    # Load configuration
    config = Config()
    # Validate configuration
    errors = config.validate()
    if errors:
        print("❌ Configuration errors found:")
        for error in errors:
            print(f"   - {error}")
        print("\nPlease fix the configuration file and restart the bot.")
        return
    print("📋 Configuration loaded successfully!")
    print(f"🏠 Room: {config.get('objection', 'room_id')}")
    print(f"🤖 Username: {config.get('objection', 'bot_username')}")
    print(f"🎭 Mode: {config.get('settings', 'mode')}")
    # Create bots
    objection_bot = ObjectionBot(config)
    discord_bot = DiscordCourtBot(objection_bot, config)
    # Link them together
    objection_bot.set_discord_bot(discord_bot)
    print("🔌 Attempting to connect to objection.lol...")
    objection_success = await objection_bot.connect_to_room()
    if objection_success:
        print("✅ Objection.lol connection successful!")
        # Start Discord bot in background
        print("🔌 Starting Discord bot...")
        discord_task = asyncio.create_task(discord_bot.start(config.get('discord', 'token')))
        # Start terminal command listener in background
        terminal_task = asyncio.create_task(terminal_command_listener(objection_bot, discord_bot))
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(asyncio.get_running_loop(), objection_bot, discord_bot)
        
        # Send initial greeting
        await asyncio.sleep(3)  # Wait for Discord bot to connect
        # Revert to original bot username for initial greeting
        original_username = objection_bot.config.get('objection', 'bot_username')
        await objection_bot.change_username_and_wait(original_username)
        await objection_bot.send_message("[#bgs20412]Ruff (Relaying messages)")
        
        # Choose mode based on configuration
        mode = config.get('settings', 'mode')
        if mode == "interactive":
            print("💬 Interactive mode enabled")
            await objection_bot.interactive_mode()
        else:
            print("🌉 Bridge mode active. Messages will be relayed between Discord and Objection.lol")
            print("Press Ctrl+C to stop the bot")
        
        try:
            # Keep both bots running
            await asyncio.gather(
                discord_task,
                objection_bot.keep_alive(),
                terminal_task
            )
        except KeyboardInterrupt:
            print("\n🛑 Stopping bots...")
            discord_task.cancel()
            terminal_task.cancel()
            await shutdown(objection_bot, discord_bot)
    else:
        print("❌ Failed to connect to objection.lol")
if __name__ == "__main__":
    asyncio.run(main())