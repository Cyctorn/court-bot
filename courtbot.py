import socketio
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
    def strip_color_codes(self, text):
        """Remove objection.lol color codes from text"""
        import re
        # Pattern to match only the two valid color code formats:
        # [#/r] [#/g] [#/b] etc - single letter generic colors
        # [#/c123456] - custom hex colors with c prefix (exactly 6 hex digits)
        # [/#] - closing tags
        color_pattern = r'\[#/[a-zA-Z]\]|\[#/c[a-fA-F0-9]{6}\]|\[/#\]'
        cleaned = re.sub(color_pattern, '', text)
        print(f"🎨 Color strip: '{text}' → '{cleaned}'")  # Debug line
        return cleaned
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
                        name="Color Presets",
                        value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver",
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
                name="Color Presets",
                value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver\nOr use custom hex codes like #ff0000",
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
                name="Color Presets",
                value="red, green, blue, purple, orange, yellow, pink, cyan, lime, magenta, gold, silver",
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
            # Prepare new username and message content
            base_name = self.config.get('objection', 'bot_username')
            discord_name = message.author.display_name
            user_id = str(message.author.id)
            # Use nickname if set, else display name
            nickname = self.nicknames.get(user_id)
            if nickname:
                new_username = f"{nickname} ({base_name})"
            else:
                new_username = f"{discord_name} ({base_name})"
            
            # Apply user's custom color if set
            user_color = self.colors.get(user_id)
            if user_color:
                colored_content = f"[#/c{user_color}]{message.content}[/#]"
            else:
                colored_content = message.content
            
            if len(new_username) <= 33:
                await self.objection_bot.change_username_and_wait(new_username)
                send_content = colored_content
            else:
                new_username = base_name
                await self.objection_bot.change_username_and_wait(new_username)
                send_content = f"{discord_name}: {colored_content}"
            await self.objection_bot.send_message(send_content)
            print(f"🔄 Discord → Objection: {new_username}: {send_content}")
            await self.cleanup_messages()
    async def send_to_discord(self, username, message):
        """Send a message from objection.lol to Discord"""
        if self.bridge_channel:
            # Strip color codes before sending to Discord
            cleaned_message = self.strip_color_codes(message)
            import time
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

class ObjectionBot:
    def __init__(self, config):
        self.config = config
        self.sio = socketio.AsyncClient(logger=False, engineio_logger=False)
        self.room_id = config.get('objection', 'room_id')
        self.username = config.get('objection', 'bot_username')
        self.connected = False
        self.user_id = None
        self.message_queue = queue.Queue()
        self.discord_bot = None
        self.user_names = {}
        self._username_change_event = asyncio.Event()
        self._pending_username = None
        self._pending_pair_request = None
        self.setup_events()
    async def change_username_and_wait(self, new_username, timeout=2.0):
        """Change the bot's username and return immediately after emitting the event."""
        print(f"[DEBUG] Requesting username change to: {new_username}")
        self._pending_username = new_username
        self._username_change_event.clear()
        await self.sio.emit("change_username", {"username": new_username})
        # No waiting or timeout, return immediately
        self._pending_username = None
    def set_discord_bot(self, discord_bot):
        """Link the Discord bot"""
        self.discord_bot = discord_bot
    def setup_events(self):
        @self.sio.event
        async def connect():
            print(f"✅ Connected as {self.username}")
            self.connected = True
            await self.sio.emit('me')
            await self.sio.emit('get_room')
        @self.sio.event
        async def disconnect():
            print("❌ Disconnected from objection.lol")
            self.connected = False
        @self.sio.on('message')
        async def on_message(data, *args):
            user_id = data.get('userId')
            message = data.get('message', {})
            text = message.get('text', '')

            # Check for pairing request message
            if "Please pair with me CourtDog-sama" in text and self._pending_pair_request and user_id != self.user_id:
                print(f"[PAIRING] Auto-accepting pairing due to message: {text}")
                await self.accept_pairing(self._pending_pair_request)
                self._pending_pair_request = None
                return

            if user_id != self.user_id:
                # Check ignore patterns 
                ignore_patterns = self.config.get('settings', 'ignore_patterns')
                if any(pattern in text for pattern in ignore_patterns):
                    return
                # Get username from our stored mapping
                username = self.user_names.get(user_id)
                # If we don't have the username, request room update and wait briefly
                if username is None:
                    print(f"🔄 Unknown user {user_id[:8]}, requesting room update...")
                    await self.sio.emit('get_room')
                    username = self.user_names.get(user_id, f"User-{user_id[:8]}")
                print(f"📨 Received: {username}: {text}")
                # Send to Discord if connected
                if self.discord_bot:
                    await self.discord_bot.send_to_discord(username, text)
        @self.sio.on('me')
        async def on_me(data, *args):
            if 'user' in data and 'id' in data['user']:
                self.user_id = data['user']['id']
                print(f"🤖 Bot ID: {self.user_id}")
                print(f"[DEBUG] Received bot user ID: {self.user_id}")
        @self.sio.on('user_joined')
        async def on_user_joined(data, *args):
            """Handle user_joined event from server"""
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
        @self.sio.on('user_left')
        async def on_user_left(user_id, *args):
            """Handle user_left event from server"""
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
        @self.sio.on('update_user')
        async def on_update_user(user_id, user_data, *args):
            """Handle user_update event when users change their names"""
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
        @self.sio.on('update_room')
        async def on_update_room(data, *args):
            users = data.get('users', [])

            # Update our username mapping (but don't detect joins/leaves here anymore)
            for user in users:
                if 'id' in user and 'username' in user:
                    user_id = user['id']
                    username = user['username']
                    self.user_names[user_id] = username
            # Signal username change event if our username was updated
            if self.user_id:
                for user in users:
                    if user.get('id') == self.user_id and self._pending_username:
                        if user.get('username') == self._pending_username:
                            print(f"[DEBUG] Username for our user_id matched pending username: {self._pending_username}")
                            self._username_change_event.set()
            usernames = [user.get('username') for user in users]
            print(f"👥 Users in room: {usernames}")
        @self.sio.on('create_pair')
        async def on_create_pair(data, *args):
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

    async def accept_pairing(self, pair_data):
        print(f"[PAIRING] Accepting pair: {pair_data}")
        # Extract pairId from the create_pair data
        pair_id = None
        if isinstance(pair_data, dict):
            pair_id = pair_data.get('id')
        if pair_id:
            await self.sio.emit("respond_to_pair", {"pairId": pair_id, "status": "accepted"})
        else:
            print("[PAIRING] Could not find pairId in pair_data, not sending respond_to_pair.")

    async def decline_pairing(self, pair_data):
        print(f"[PAIRING] Declining pair: {pair_data}")
        # Extract pairId from the create_pair data
        pair_id = None
        if isinstance(pair_data, dict):
            pair_id = pair_data.get('id')
        if pair_id:
            await self.sio.emit("respond_to_pair", {"pairId": pair_id, "status": "rejected"})
            await self.sio.emit("leave_pair")
        else:
            print("[PAIRING] Could not find pairId in pair_data, only sending leave_pair.")
            await self.sio.emit("leave_pair")
    async def graceful_disconnect(self):
        """Gracefully disconnect: clean up Discord, update room, disconnect socket."""
        if self.discord_bot:
            await self.discord_bot.full_cleanup()
        if self.connected:
            try:
                await self.sio.emit('get_room')  # Request room update before disconnect
            except Exception as e:
                print(f"⚠️ Could not emit get_room on disconnect: {e}")
            await self.sio.disconnect()
        self.connected = False
    async def connect_to_room(self):
        base_url = "https://objection.lol"
        socketio_url = f"{base_url}/courtroom-api/socket.io/?roomId={self.room_id}&username={self.username}&password="
        try:
            # Disconnect first if already connected
            if self.connected:
                await self.graceful_disconnect()
                await asyncio.sleep(1)  # Wait for clean disconnection

            # CREATE A NEW SOCKETIO CLIENT INSTANCE FOR RECONNECTION
            print("🔄 Creating fresh socketio client...")
            self.sio = socketio.AsyncClient(logger=False, engineio_logger=False)
            self.setup_events()  # Re-setup event handlers on the new client

            await self.sio.connect(
                socketio_url,
                socketio_path="/courtroom-api/socket.io/",
                wait_timeout=10
            )
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    async def send_message(self, text):
        if not self.connected:
            print("❌ Not connected")
            return 
        character_id = self.config.get('settings', 'character_id')
        pose_id = self.config.get('settings', 'pose_id')
        message_data = {
            "characterId": character_id,
            "poseId": pose_id,
            "text": text
        }
        try:
            await self.sio.emit('message', message_data)
            print(f"📤 Sent: {text}")
        except Exception as e:
            print(f"❌ Send failed: {e}")
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
        await self.graceful_disconnect()
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