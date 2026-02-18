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
from aiohttp import web
import re
import signal
import time
import random
from datetime import datetime, timezone
import re

# Nickname storage file
NICKNAME_FILE = '/app/data/nicknames.json'
# Color storage file
COLOR_FILE = '/app/data/colors.json'
# Character/Pose storage file
CHARACTER_FILE = '/app/data/characters.json'
# Autoban patterns storage file
AUTOBAN_FILE = '/app/data/autobans.json'
# Ping nickname storage file (for courtroom users to ping Discord users)
PING_NICKNAME_FILE = '/app/data/ping_nicknames.json'

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

def load_characters():
    if os.path.exists(CHARACTER_FILE):
        try:
            with open(CHARACTER_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading characters: {e}")
            return {}
    return {}

def save_characters(characters):
    try:
        with open(CHARACTER_FILE, 'w') as f:
            json.dump(characters, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving characters: {e}")

def load_autobans():
    """Load autoban patterns from file"""
    if os.path.exists(AUTOBAN_FILE):
        try:
            with open(AUTOBAN_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading autobans: {e}")
            return []
    return []

def save_autobans(autobans):
    """Save autoban patterns to file"""
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(AUTOBAN_FILE), exist_ok=True)
        with open(AUTOBAN_FILE, 'w') as f:
            json.dump(autobans, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving autobans: {e}")

def load_ping_nicknames():
    """Load ping nicknames from file. Format: {discord_user_id: [nick1, nick2, ...]}"""
    if os.path.exists(PING_NICKNAME_FILE):
        try:
            with open(PING_NICKNAME_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading ping nicknames: {e}")
            return {}
    return {}

def save_ping_nicknames(ping_nicknames):
    """Save ping nicknames to file"""
    try:
        os.makedirs(os.path.dirname(PING_NICKNAME_FILE), exist_ok=True)
        with open(PING_NICKNAME_FILE, 'w') as f:
            json.dump(ping_nicknames, f, indent=2)
    except Exception as e:
        print(f"❌ Error saving ping nicknames: {e}")

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
        """Apply environment variable overrides to configuration"""
        # Initialize sections if they don't exist
        if 'discord' not in self.data:
            self.data['discord'] = {}
        if 'objection' not in self.data:
            self.data['objection'] = {}
        if 'settings' not in self.data:
            self.data['settings'] = {}
        
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
        
        # Objection.lol settings
        if os.getenv('ROOM_ID'):
            self.data['objection']['room_id'] = os.getenv('ROOM_ID')
            print("🌍 Room ID loaded from environment variable")
        if os.getenv('BOT_USERNAME'):
            self.data['objection']['bot_username'] = os.getenv('BOT_USERNAME')
            print("🌍 Bot username loaded from environment variable")
        
        # Bot settings
        if os.getenv('CHARACTER_ID'):
            try:
                self.data['settings']['character_id'] = int(os.getenv('CHARACTER_ID'))
                print("🌍 Character ID loaded from environment variable")
            except ValueError:
                print(f"❌ Invalid CHARACTER_ID environment variable")
        if os.getenv('POSE_ID'):
            try:
                self.data['settings']['pose_id'] = int(os.getenv('POSE_ID'))
                print("🌍 Pose ID loaded from environment variable")
            except ValueError:
                print(f"❌ Invalid POSE_ID environment variable")
        if os.getenv('MAX_MESSAGES'):
            try:
                self.data['settings']['max_messages'] = int(os.getenv('MAX_MESSAGES'))
                print("🌍 Max messages loaded from environment variable")
            except ValueError:
                print(f"❌ Invalid MAX_MESSAGES environment variable")
        if os.getenv('DELETE_COMMANDS'):
            delete_commands_str = os.getenv('DELETE_COMMANDS').lower()
            self.data['settings']['delete_commands'] = delete_commands_str in ('true', '1', 'yes', 'on')
            print(f"🌍 Delete commands loaded from environment variable: {self.data['settings']['delete_commands']}")
        if os.getenv('SHOW_JOIN_LEAVE'):
            show_join_leave_str = os.getenv('SHOW_JOIN_LEAVE').lower()
            self.data['settings']['show_join_leave'] = show_join_leave_str in ('true', '1', 'yes', 'on')
            print(f"🌍 Show join/leave loaded from environment variable: {self.data['settings']['show_join_leave']}")
        if os.getenv('VERBOSE'):
            verbose_str = os.getenv('VERBOSE').lower()
            self.data['settings']['verbose'] = verbose_str in ('true', '1', 'yes', 'on')
            print(f"🌍 Verbose logging loaded from environment variable: {self.data['settings']['verbose']}")
        if os.getenv('ENABLE_PINGS'):
            pings_str = os.getenv('ENABLE_PINGS').lower()
            self.data['settings']['enable_pings'] = pings_str in ('true', '1', 'yes', 'on')
            print(f"🌍 Pings loaded from environment variable: {self.data['settings']['enable_pings']}")
        
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
                "show_join_leave": True,
                "verbose": False,
                "enable_pings": False
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

# Global logging configuration
VERBOSE_MODE = True

def log_verbose(message):
    """Log message only if verbose mode is enabled"""
    if VERBOSE_MODE:
        print(message)

def log_message(source, username, message):
    """Log a message in simple format for non-verbose mode"""
    if VERBOSE_MODE:
        # In verbose mode, this is handled by existing logs
        pass
    else:
        # Simple format: (Source) Username: message
        print(f"({source}) {username}: {message}")

class DiscordCourtBot(discord.Client):
    def __init__(self, objection_bot, config):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True  # Required for guild member lookup (ping feature)
        super().__init__(intents=intents)
        
        self.objection_bot = objection_bot
        self.config = config
        self.bridge_channel = None
        self.channel_id = config.get('discord', 'channel_id')
        self.guild_id = config.get('discord', 'guild_id')
        self.tree = app_commands.CommandTree(self)
        
        # Track last message info for avatar embed logic
        self.last_discord_message = None
        self.last_message_username = None
        self.last_message_pose_id = None
        self.show_avatars = True  # Track whether avatars are enabled
        self.startup_message = None  # Track startup message to avoid deleting it
        
        # Load persistent data for nickname, color, and character customization
        self.nicknames = load_nicknames()
        self.colors = load_colors()
        self.characters = load_characters()
        self.ping_nicknames = load_ping_nicknames()
        
        # Rate limiting for pings: {discord_user_id: [timestamp1, timestamp2, ...]}
        self._ping_rate_limit = {}
        
        # Pre-compile regex patterns for performance
        self._mention_pattern = re.compile(r'<@\d+>')
        self._bgm_pattern = re.compile(r'\[#bgm(\d+)\]')
        self._sfx_pattern = re.compile(r'\[#bgs(\d+)\]')
        self._evidence_pattern = re.compile(r'\[#evdi?(\d+)\]')
        self._color_code_pattern = re.compile(r'\[#/[a-zA-Z]\]|\[#/c[a-fA-F0-9]{6}\]|\[/#\]|\[#ts\d+\]')
    
    async def fetch_music_url(self, bgm_id, validate_url=False):
        """Fetch the actual external URL for a BGM ID from objection.lol's API
        
        Args:
            bgm_id: The BGM ID to fetch
            validate_url: If True, also verify the external URL is accessible (for random rolls)
        """
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
                            
                            # If validation is requested, verify the external URL is accessible
                            if validate_url:
                                try:
                                    # Use HEAD request to check if URL is accessible without downloading
                                    async with session.head(external_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as url_check:
                                        if url_check.status == 404:
                                            log_verbose(f"❌ BGM {bgm_id} URL returns 404: {external_url}")
                                            return None
                                        elif url_check.status >= 400:
                                            log_verbose(f"❌ BGM {bgm_id} URL returns error {url_check.status}: {external_url}")
                                            return None
                                        
                                        # Check Content-Type to ensure it's actually an audio file
                                        content_type = url_check.headers.get('Content-Type', '').lower()
                                        valid_audio_types = ['audio/', 'application/ogg', 'application/octet-stream']
                                        if content_type and not any(t in content_type for t in valid_audio_types):
                                            log_verbose(f"❌ BGM {bgm_id} URL is not audio (Content-Type: {content_type}): {external_url}")
                                            return None
                                        
                                        # Check Content-Length to ensure file has reasonable size (> 1KB)
                                        content_length = url_check.headers.get('Content-Length')
                                        if content_length:
                                            try:
                                                size = int(content_length)
                                                if size < 1024:  # Less than 1KB is likely invalid
                                                    log_verbose(f"❌ BGM {bgm_id} URL file too small ({size} bytes): {external_url}")
                                                    return None
                                            except ValueError:
                                                pass  # Ignore invalid Content-Length header
                                except asyncio.TimeoutError:
                                    log_verbose(f"⚠️ BGM {bgm_id} URL timeout, assuming valid: {external_url}")
                                    # Don't fail on timeout - the URL might still work
                                except aiohttp.ClientConnectorError as conn_error:
                                    # DNS resolution failure, connection refused, etc. - definitely invalid
                                    log_verbose(f"❌ BGM {bgm_id} URL connection failed (DNS/network error): {conn_error}")
                                    return None
                                except aiohttp.ClientError as client_error:
                                    # Other client errors - likely invalid
                                    log_verbose(f"❌ BGM {bgm_id} URL client error: {client_error}")
                                    return None
                                except Exception as url_error:
                                    log_verbose(f"⚠️ BGM {bgm_id} URL check failed: {url_error}")
                                    # Don't fail on other errors - the URL might still work
                            
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
        matches = self._bgm_pattern.findall(text)
        return matches

    async def fetch_sfx_url(self, sfx_id, validate_url=False):
        """Fetch the actual external URL for a SFX ID from objection.lol's API
        
        Args:
            sfx_id: The SFX ID to fetch
            validate_url: If True, also verify the external URL is accessible (for random rolls)
        """
        try:
            # Use the sound effect API endpoint
            api_url = f"https://objection.lol/api/assets/sound/{sfx_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        sfx_data = await response.json()
                        # Extract the external URL and sound name from the response
                        external_url = sfx_data.get('url')
                        sfx_name = sfx_data.get('name', 'Unknown Sound')
                        volume = sfx_data.get('volume', 100)
                        
                        if external_url:
                            # Handle relative URLs by converting them to full objection.lol URLs
                            if external_url.startswith('/'):
                                external_url = f"https://objection.lol{external_url}"
                            
                            # If validation is requested, verify the external URL is accessible
                            if validate_url:
                                try:
                                    # Use HEAD request to check if URL is accessible without downloading
                                    async with session.head(external_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as url_check:
                                        if url_check.status == 404:
                                            log_verbose(f"❌ SFX {sfx_id} URL returns 404: {external_url}")
                                            return None
                                        elif url_check.status >= 400:
                                            log_verbose(f"❌ SFX {sfx_id} URL returns error {url_check.status}: {external_url}")
                                            return None
                                        
                                        # Check Content-Type to ensure it's actually an audio file
                                        content_type = url_check.headers.get('Content-Type', '').lower()
                                        valid_audio_types = ['audio/', 'application/ogg', 'application/octet-stream']
                                        if content_type and not any(t in content_type for t in valid_audio_types):
                                            log_verbose(f"❌ SFX {sfx_id} URL is not audio (Content-Type: {content_type}): {external_url}")
                                            return None
                                        
                                        # Check Content-Length to ensure file has reasonable size (> 1KB)
                                        content_length = url_check.headers.get('Content-Length')
                                        if content_length:
                                            try:
                                                size = int(content_length)
                                                if size < 1024:  # Less than 1KB is likely invalid
                                                    log_verbose(f"❌ SFX {sfx_id} URL file too small ({size} bytes): {external_url}")
                                                    return None
                                            except ValueError:
                                                pass  # Ignore invalid Content-Length header
                                except asyncio.TimeoutError:
                                    log_verbose(f"⚠️ SFX {sfx_id} URL timeout, assuming valid: {external_url}")
                                    # Don't fail on timeout - the URL might still work
                                except aiohttp.ClientConnectorError as conn_error:
                                    # DNS resolution failure, connection refused, etc. - definitely invalid
                                    log_verbose(f"❌ SFX {sfx_id} URL connection failed (DNS/network error): {conn_error}")
                                    return None
                                except aiohttp.ClientError as client_error:
                                    # Other client errors - likely invalid
                                    log_verbose(f"❌ SFX {sfx_id} URL client error: {client_error}")
                                    return None
                                except Exception as url_error:
                                    log_verbose(f"⚠️ SFX {sfx_id} URL check failed: {url_error}")
                                    # Don't fail on other errors - the URL might still work
                            
                            print(f"🔊 Found sound effect for SFX {sfx_id}: '{sfx_name}' -> {external_url}")
                            return {
                                'url': external_url,
                                'name': sfx_name,
                                'volume': volume,
                                'id': sfx_id
                            }
                        else:
                            print(f"❌ No URL found in SFX data for ID {sfx_id}")
                            return None
                    elif response.status == 404:
                        print(f"❌ SFX ID {sfx_id} not found")
                        return None
                    else:
                        print(f"❌ Failed to fetch SFX data for ID {sfx_id} (status: {response.status})")
                        return None
        except Exception as e:
            print(f"❌ Error fetching sound effect URL for ID {sfx_id}: {e}")
            return None

    def extract_sfx_commands(self, text):
        """Extract SFX IDs from text containing [#bgs123456] commands"""
        matches = self._sfx_pattern.findall(text)
        return matches

    def extract_evidence_commands(self, text):
        """Extract evidence IDs from text containing [#evdi123456] commands"""
        matches = self._evidence_pattern.findall(text)
        return matches

    async def fetch_evidence_data(self, evidence_id, validate_url=False):
        """Fetch evidence data from objection.lol's API by evidence ID
        
        Args:
            evidence_id: The evidence ID to fetch
            validate_url: If True, also verify the external URL is accessible (for random rolls)
        """
        try:
            # Use the evidence API endpoint
            api_url = f"https://objection.lol/api/assets/evidence/{evidence_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        evidence_data = await response.json()
                        # Extract evidence information
                        evidence_url = evidence_data.get('url')
                        evidence_name = evidence_data.get('name', 'Unknown Evidence')
                        evidence_type = evidence_data.get('type', 'image')
                        is_icon = evidence_data.get('isIcon', False)
                        
                        if evidence_url:
                            # Handle relative URLs by converting them to full objection.lol URLs
                            if evidence_url.startswith('/'):
                                evidence_url = f"https://objection.lol{evidence_url}"
                            
                            # If validation is requested, verify the external URL is accessible
                            if validate_url:
                                try:
                                    # Use HEAD request to check if URL is accessible without downloading
                                    async with session.head(evidence_url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as url_check:
                                        if url_check.status == 404:
                                            log_verbose(f"❌ Evidence {evidence_id} URL returns 404: {evidence_url}")
                                            return None
                                        elif url_check.status >= 400:
                                            log_verbose(f"❌ Evidence {evidence_id} URL returns error {url_check.status}: {evidence_url}")
                                            return None
                                        
                                        # Check Content-Type to ensure it's actually an image or video file
                                        content_type = url_check.headers.get('Content-Type', '').lower()
                                        valid_media_types = ['image/', 'video/']
                                        if content_type and not any(t in content_type for t in valid_media_types):
                                            log_verbose(f"❌ Evidence {evidence_id} URL is not an image/video (Content-Type: {content_type}): {evidence_url}")
                                            return None
                                        
                                        # Check Content-Length to ensure file has reasonable size
                                        # For images/videos, require at least 5KB to filter out error placeholders
                                        content_length = url_check.headers.get('Content-Length')
                                        if content_length:
                                            try:
                                                size = int(content_length)
                                                if size < 5120:  # Less than 5KB is likely an error placeholder
                                                    log_verbose(f"❌ Evidence {evidence_id} URL file too small ({size} bytes): {evidence_url}")
                                                    return None
                                            except ValueError:
                                                pass  # Ignore invalid Content-Length header
                                except asyncio.TimeoutError:
                                    log_verbose(f"⚠️ Evidence {evidence_id} URL timeout, assuming valid: {evidence_url}")
                                    # Don't fail on timeout - the URL might still work
                                except aiohttp.ClientConnectorError as conn_error:
                                    # DNS resolution failure, connection refused, etc. - definitely invalid
                                    log_verbose(f"❌ Evidence {evidence_id} URL connection failed (DNS/network error): {conn_error}")
                                    return None
                                except aiohttp.ClientError as client_error:
                                    # Other client errors - likely invalid
                                    log_verbose(f"❌ Evidence {evidence_id} URL client error: {client_error}")
                                    return None
                                except Exception as url_error:
                                    log_verbose(f"⚠️ Evidence {evidence_id} URL check failed: {url_error}")
                                    # Don't fail on other errors - the URL might still work
                            
                            print(f"📄 Found evidence {evidence_id}: '{evidence_name}' -> {evidence_url}")
                            return {
                                'url': evidence_url,
                                'name': evidence_name,
                                'type': evidence_type,
                                'isIcon': is_icon,
                                'id': evidence_id
                            }
                        else:
                            print(f"❌ No URL found in evidence data for ID {evidence_id}")
                            return None
                    elif response.status == 404:
                        print(f"❌ Evidence ID {evidence_id} not found")
                        return None
                    else:
                        print(f"❌ Failed to fetch evidence data for ID {evidence_id} (status: {response.status})")
                        return None
        except Exception as e:
            print(f"❌ Error fetching evidence data for ID {evidence_id}: {e}")
            return None

    async def fetch_character_avatar(self, character_id, pose_id):
        """Fetch character avatar (idle image) from objection.lol's API"""
        try:
            # Use the character API endpoint
            api_url = f"https://objection.lol/api/assets/character/{character_id}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        character_data = await response.json()
                        character_name = character_data.get('name', 'Unknown')
                        poses = character_data.get('poses', [])
                        
                        # Find the matching pose
                        for pose in poses:
                            if pose.get('id') == pose_id:
                                idle_image_url = pose.get('idleImageUrl')
                                pose_name = pose.get('name', 'Unknown Pose')
                                
                                if idle_image_url:
                                    # Convert relative URLs to absolute URLs
                                    if idle_image_url.startswith('/'):
                                        idle_image_url = f"https://objection.lol{idle_image_url}"
                                    
                                    log_verbose(f"🎭 Found avatar for character {character_id} ({character_name}), pose {pose_id} ({pose_name}): {idle_image_url}")
                                    return {
                                        'url': idle_image_url,
                                        'character_name': character_name,
                                        'pose_name': pose_name,
                                        'character_id': character_id,
                                        'pose_id': pose_id
                                    }
                                else:
                                    log_verbose(f"❌ No idle image URL found for character {character_id}, pose {pose_id}")
                                    return None
                        
                        # Pose not found
                        log_verbose(f"❌ Pose {pose_id} not found for character {character_id}")
                        return None
                    elif response.status == 404:
                        log_verbose(f"❌ Character ID {character_id} not found")
                        return None
                    else:
                        log_verbose(f"❌ Failed to fetch character data for ID {character_id} (status: {response.status})")
                        return None
        except Exception as e:
            log_verbose(f"❌ Error fetching character avatar for ID {character_id}: {e}")
            return None

    def strip_color_codes(self, text):
        """Remove objection.lol color codes from text"""
        # Pattern to match:
        # [#/r] [#/g] [#/b] etc - single letter generic colors
        # [#/c123456] - custom hex colors with c prefix (exactly 6 hex digits)
        # [/#] - closing tags
        # [#ts123] - text speed commands with any number
        cleaned = self._color_code_pattern.sub('', text)
        log_verbose(f"🎨 Color strip: '{text}' → '{cleaned}'")  # Debug line
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
                log_verbose(f"🖼️ Found image attachment: {attachment.filename} - {attachment.url}")
            
            # Check if it's a video by file extension or content type
            elif (attachment.content_type and attachment.content_type.startswith('video/')) or \
                 any(attachment.filename.lower().endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv', '.wmv', '.m4v']):
                media_urls.append(attachment.url)
                log_verbose(f"🎥 Found video attachment: {attachment.filename} - {attachment.url}")
        
        return media_urls
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Sync slash commands ONLY to the specific guild (not globally)
        guild = discord.Object(id=self.guild_id)
        
        # Clear global commands FIRST to remove any previously registered ones
        self.tree.clear_commands(guild=None)  # Clear local cache of global commands
        await self.tree.sync(guild=None)  # Sync the empty global command list to Discord
        print("🧹 Cleared global commands")
        
        # Now add guild-specific commands to tree
        await self.add_commands()
        
        # Finally sync only to this specific guild
        await self.tree.sync(guild=guild)
        print(f"🔄 Slash commands synced to guild {self.guild_id}!")
    
    async def add_commands(self):
        """Add all slash commands to the tree"""
        
        def check_guild_and_channel(interaction: discord.Interaction) -> bool:
            """Check if command is used in the correct guild and channel"""
            if interaction.guild_id != self.guild_id:
                return False
            if interaction.channel_id != self.channel_id:
                return False
            return True
        
        @self.tree.command(name="status", description="Check bridge status and list users in the courtroom", guild=discord.Object(id=self.guild_id))
        async def status(interaction: discord.Interaction):
            """Check bot status and list users"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=False)
            
            # Refresh room data before showing status if connected
            if self.objection_bot.connected:
                await self.objection_bot.refresh_room_data()
                # Small delay to let the response come back
                await asyncio.sleep(0.5)
            
            # Get unique usernames and sort them
            users = list(set(self.objection_bot.user_names.values()))
            users.sort()  # Sort alphabetically for consistent display
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

            await interaction.followup.send(embed=embed, ephemeral=False)
        @self.tree.command(name="reconnect", description="Attempt to reconnect to the objection.lol courtroom", guild=discord.Object(id=self.guild_id))
        async def reconnect(interaction: discord.Interaction):
            """Reconnect to objection.lol"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)
            
            # Disconnect if already connected
            if self.objection_bot.connected:
                print("🔌 Disconnecting before reconnection...")
                await self.objection_bot.disconnect()
                await asyncio.sleep(1)  # Give time for clean disconnect
            
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
                    max_messages = self.config.get('settings', 'max_messages')
                    startup_embed = discord.Embed(
                        title="🌉 CourtDog Online",
                        description=f"Ruff (Bridge reconnected and is now active between Discord and Objection.lol. Only {max_messages} messages will be visible at a time.)",
                        color=0x00ff00
                    )
                    startup_embed.add_field(
                        name="Available Commands",
                        value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set your bridge nickname\n/pingname - Manage your ping nicknames\n/color - Set your bridge message color\n/character - Set your character/pose\n/avatars - Toggle avatar display\n/shaba\n/help - Show this help",
                        inline=False
                    )
                    startup_embed.add_field(
                        name="Admin Commands",
                        value="/titlebar - Change courtroom title\n/slowmode - Set slow mode (requires 3 confirmations)\n/setpassword - Set/remove room password (requires 3 confirmations)\n/text - Change textbox appearance\n/aspect - Change aspect ratio\n/spectating - Enable/disable spectating\n/bans - Show banned users list",
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
                    self.startup_message = await self.bridge_channel.send(embed=startup_embed)
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
        @self.tree.command(name="help", description="Show help information", guild=discord.Object(id=self.guild_id))
        async def help_command(interaction: discord.Interaction):
            """Show help information"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            embed = discord.Embed(
                title="🤖 CourtBot Help",
                description="Discord bridge for Objection.lol courtrooms",
                color=0x0099ff
            )
            embed.add_field(
                name="Commands",
                value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set/reset your bridge nickname\n/pingname - Manage your ping nicknames\n/color - Set your message color\n/character - Set your character/pose\n/avatars - Toggle avatar display\n/shaba\n/help - Show this help",
                inline=False
            )
            embed.add_field(
                name="Admin Commands",
                value="/titlebar - Change courtroom title (admin only)\n/slowmode - Set slow mode (admin only, requires 3 confirmations)\n/setpassword - Set/remove room password (admin only, requires 3 confirmations)\n/text - Change textbox appearance (admin only)\n/aspect - Change aspect ratio (admin only)\n/spectating - Enable/disable spectating (admin only)\n/bans - Show banned users list",
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
        @self.tree.command(name="nickname", description="Set your bridge nickname for the dog ('reset' to remove)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(nickname="Nickname when relaying (use 'reset' to remove)")
        async def nickname_command(interaction: discord.Interaction, nickname: str):
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
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

        @self.tree.command(name="pingname", description="Manage your ping nicknames so courtroom users can mention you. Recommend prefixing with @", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(action="Action: add, remove, list, or clear", nickname="The ping nickname (required for add/remove)")
        async def pingname_command(interaction: discord.Interaction, action: str, nickname: str = None):
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)
            action_lower = action.lower().strip()
            
            if action_lower == 'list':
                nicks = self.ping_nicknames.get(user_id, [])
                if nicks:
                    nick_list = ', '.join([f'`{n}`' for n in nicks])
                    await interaction.response.send_message(f"📋 Your ping nicknames: {nick_list}", ephemeral=True)
                else:
                    await interaction.response.send_message("ℹ️ You don't have any ping nicknames set. Use `/pingname add <nickname>` to add one.", ephemeral=True)
                return
            
            if action_lower == 'clear':
                if user_id in self.ping_nicknames:
                    del self.ping_nicknames[user_id]
                    save_ping_nicknames(self.ping_nicknames)
                    await interaction.response.send_message("✅ All your ping nicknames have been cleared.", ephemeral=True)
                else:
                    await interaction.response.send_message("ℹ️ You don't have any ping nicknames to clear.", ephemeral=True)
                return
            
            if action_lower == 'add':
                if not nickname:
                    await interaction.response.send_message("❌ Please provide a nickname to add. Example: `/pingname add myname`", ephemeral=True)
                    return
                nick_lower = nickname.lower().strip()
                if not nick_lower or len(nick_lower) > 32:
                    await interaction.response.send_message("❌ Nickname must be 1-32 characters.", ephemeral=True)
                    return
                
                # Check if this nickname is already taken by another user
                for uid, nicks in self.ping_nicknames.items():
                    if uid != user_id and nick_lower in nicks:
                        await interaction.response.send_message(f"❌ The ping nickname `{nick_lower}` is already registered by another user.", ephemeral=True)
                        return
                
                if user_id not in self.ping_nicknames:
                    self.ping_nicknames[user_id] = []
                if nick_lower in self.ping_nicknames[user_id]:
                    await interaction.response.send_message(f"ℹ️ You already have `{nick_lower}` as a ping nickname.", ephemeral=True)
                    return
                self.ping_nicknames[user_id].append(nick_lower)
                save_ping_nicknames(self.ping_nicknames)
                await interaction.response.send_message(f"✅ Added ping nickname: `{nick_lower}`\nCourtroom users can now ping you with `@{nick_lower}`", ephemeral=True)
                return
            
            if action_lower == 'remove':
                if not nickname:
                    await interaction.response.send_message("❌ Please provide a nickname to remove. Example: `/pingname remove myname`", ephemeral=True)
                    return
                nick_lower = nickname.lower().strip()
                if user_id in self.ping_nicknames and nick_lower in self.ping_nicknames[user_id]:
                    self.ping_nicknames[user_id].remove(nick_lower)
                    if not self.ping_nicknames[user_id]:
                        del self.ping_nicknames[user_id]
                    save_ping_nicknames(self.ping_nicknames)
                    await interaction.response.send_message(f"✅ Removed ping nickname: `{nick_lower}`", ephemeral=True)
                else:
                    await interaction.response.send_message(f"❌ You don't have `{nick_lower}` as a ping nickname.", ephemeral=True)
                return
            
            await interaction.response.send_message("❌ Invalid action. Use `add`, `remove`, `list`, or `clear`.", ephemeral=True)

        @self.tree.command(name="color", description="Set your message color for the courtroom ('reset' to remove)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(color="Hex color code like 'ff0000' or '#ff0000', preset name like 'red', or 'reset' to remove")
        async def color_command(interaction: discord.Interaction, color: str):
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
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
        
        @self.tree.command(name="character", description="Set your character and pose for the courtroom ('reset' to remove)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(
            character_id="Character ID (e.g., 408757) or 'reset' to remove",
            pose_id="Pose ID (e.g., 4998989) - required if setting character"
        )
        async def character_command(interaction: discord.Interaction, character_id: str, pose_id: str = None):
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            user_id = str(interaction.user.id)

            # Handle reset/removal
            if character_id.lower() in ['reset', 'remove', 'clear', 'delete']:
                if user_id in self.characters:
                    del self.characters[user_id]
                    save_characters(self.characters)
                    await interaction.response.send_message("✅ Your character/pose has been reset. The bot's default character will be used.", ephemeral=True)
                else:
                    await interaction.response.send_message("ℹ️ You don't have a custom character set.", ephemeral=True)
                return

            # Validate that both character_id and pose_id are provided
            if not pose_id:
                await interaction.response.send_message("❌ Both character ID and pose ID are required. Example: `/character 408757 4998989`", ephemeral=True)
                return

            # Validate that both are numeric
            try:
                char_id_int = int(character_id)
                pose_id_int = int(pose_id)
            except ValueError:
                await interaction.response.send_message("❌ Character ID and Pose ID must be numbers. Example: `/character 408757 4998989`", ephemeral=True)
                return

            # Store the character and pose
            self.characters[user_id] = {
                'character_id': char_id_int,
                'pose_id': pose_id_int
            }
            save_characters(self.characters)
            await interaction.response.send_message(
                f"✅ Your character/pose is now set to:\n**Character ID:** {char_id_int}\n**Pose ID:** {pose_id_int}\n\nYour messages will appear with this character in the courtroom. Use `/character reset` to remove it.",
                ephemeral=True
            )

        @self.tree.command(name="avatars", description="Toggle character avatar display in Discord", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(enabled="Enable or disable avatar display")
        @app_commands.choices(enabled=[
            app_commands.Choice(name="Enable", value="enable"),
            app_commands.Choice(name="Disable", value="disable")
        ])
        async def avatars_command(interaction: discord.Interaction, enabled: app_commands.Choice[str]):
            """Toggle avatar display"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            if enabled.value == "enable":
                self.show_avatars = True
                status_emoji = "✅"
                status_text = "enabled"
                description = "Character avatars will now be displayed in Discord messages."
            else:
                self.show_avatars = False
                status_emoji = "❌"
                status_text = "disabled"
                description = "Character avatars will no longer be displayed. All messages will be plain text."
                
                # Convert any existing avatar embeds to plain text
                try:
                    log_verbose(f"🔍 Converting existing avatar embeds to plain text...")
                    converted_count = 0
                    
                    async for message in self.bridge_channel.history(limit=50):
                        if message == self.startup_message or message.author != self.user:
                            continue
                        
                        if message.embeds and len(message.embeds) > 0:
                            embed = message.embeds[0]
                            if embed.title and embed.description and embed.image:
                                msg_timestamp = int(message.created_at.timestamp())
                                embed_username = embed.title
                                embed_message = embed.description
                                
                                formatted_plain = f"**{embed_username}**:\n{embed_message}\n-# <t:{msg_timestamp}:T>"
                                await message.edit(content=formatted_plain, embeds=[])
                                converted_count += 1
                    
                    if converted_count > 0:
                        log_verbose(f"✅ Converted {converted_count} existing avatar embed(s) to plain text")
                except Exception as e:
                    log_verbose(f"⚠️ Error converting existing embeds: {e}")
            
            embed = discord.Embed(
                title=f"{status_emoji} Avatars {status_text.capitalize()}",
                description=description,
                color=0x00ff00 if enabled.value == "enable" else 0xff9900
            )
            await interaction.response.send_message(embed=embed, ephemeral=False)
            print(f"[AVATARS] Avatar display {status_text} by {interaction.user.display_name}")

        @self.tree.command(name="shaba", guild=discord.Object(id=self.guild_id))
        async def shaba_command(interaction: discord.Interaction):
            """Shaba command"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=True)
                return

            try:
                # Revert to original bot username when speaking as the bot itself
                original_username = self.config.get('objection', 'bot_username')
                log_verbose(f"🎭 Shaba command: Changing to bot username: {original_username}")
                await self.objection_bot.change_username_and_wait(original_username)
                log_verbose(f"🎭 Shaba command: Sending message with background color")
                await self.objection_bot.send_message("[#bgs122964]")
                await interaction.followup.send("What the dog doin??", ephemeral=False)
                log_verbose(f"🎭 Shaba command: Successfully executed")
            except Exception as e:
                print(f"❌ Shaba command error: {e}")
                await interaction.followup.send(f"❌ Failed to execute shaba command: {str(e)}", ephemeral=True)

        # Admin Commands Section
        @self.tree.command(name="titlebar", description="Change the chatroom title (admin only)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(title="New title for the chatroom (1-150 characters)")
        async def titlebar_command(interaction: discord.Interaction, title: str):
            """Change chatroom title (admin only)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
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

        @self.tree.command(name="slowmode", description="Set room slow mode (admin only, requires 3 confirmations)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(seconds="Slow mode seconds (0-60, 0 = disabled)")
        async def slowmode_command(interaction: discord.Interaction, seconds: int):
            """Set room slow mode (admin only, requires confirmations)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
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

        @self.tree.command(name="setpassword", description="Set or remove room password (admin only, requires 3 confirmations)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(password="Password to set (leave blank to remove password)")
        async def setpassword_command(interaction: discord.Interaction, password: str = ""):
            """Set or remove room password (admin only, requires confirmations)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=True)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=True)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change password", ephemeral=True)
                return

            # Determine action based on password input
            if password.strip() == "":
                action_description = "**Remove password** (make room public)"
                password_to_set = ""
                action_title = "⚠️ Remove Room Password"
                result_title = "✅ Password Removed"
                result_description = "Room password has been **removed** - room is now public"
            else:
                # Truncate password display for security (show first 3 and last 3 chars if long enough)
                if len(password) > 6:
                    password_display = f"{password[:3]}...{password[-3:]}"
                else:
                    password_display = "*" * len(password)
                action_description = f"**Set password** to: `{password_display}`"
                password_to_set = password
                action_title = "⚠️ Set Room Password"
                result_title = "✅ Password Set"
                result_description = f"Room password has been **set** to: `{password_display}`"

            # Create voting embed
            embed = discord.Embed(
                title=action_title,
                description=f"**This action requires 3 user confirmations**\n\nProposed change: {action_description}",
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
                success = await self.objection_bot.update_room_password(password_to_set)
                if success:
                    result_embed = discord.Embed(
                        title=result_title,
                        description=result_description,
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

        @self.tree.command(name="text", description="Change the chatroom textbox appearance (admin only)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(style="Textbox style (preset name or custom ID)")
        async def text_command(interaction: discord.Interaction, style: str):
            """Change chatroom textbox appearance (admin only)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
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

        @self.tree.command(name="aspect", description="Change the chatroom aspect ratio (admin only)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(ratio="Aspect ratio (3:2, 4:3, 16:9, 16:10)")
        @app_commands.choices(ratio=[
            app_commands.Choice(name="3:2", value="3:2"),
            app_commands.Choice(name="4:3", value="4:3"), 
            app_commands.Choice(name="16:9", value="16:9"),
            app_commands.Choice(name="16:10", value="16:10")
        ])
        async def aspect_command(interaction: discord.Interaction, ratio: app_commands.Choice[str]):
            """Change chatroom aspect ratio (admin only)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=False)

            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=False)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change the aspect ratio", ephemeral=False)
                return

            try:
                success = await self.objection_bot.update_room_aspect_ratio(ratio.value)
                if success:
                    embed = discord.Embed(
                        title="✅ Aspect Ratio Updated",
                        description=f"Successfully changed aspect ratio to: **{ratio.value}**",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    print(f"[ASPECT] Discord user {interaction.user.display_name} changed aspect ratio to: {ratio.value}")
                else:
                    await interaction.followup.send("❌ Failed to update aspect ratio. Check bot status and permissions.", ephemeral=False)
            except Exception as e:
                print(f"❌ Aspect ratio command error: {e}")
                await interaction.followup.send(f"❌ Failed to change aspect ratio: {str(e)}", ephemeral=False)

        @self.tree.command(name="spectating", description="Enable or disable spectating in the courtroom (admin only)", guild=discord.Object(id=self.guild_id))
        @app_commands.describe(enabled="Whether spectating should be enabled")
        @app_commands.choices(enabled=[
            app_commands.Choice(name="Enable", value="true"),
            app_commands.Choice(name="Disable", value="false")
        ])
        async def spectating_command(interaction: discord.Interaction, enabled: app_commands.Choice[str]):
            """Enable or disable spectating (admin only)"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=False)
            
            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=False)
                return

            if not self.objection_bot.is_admin:
                await interaction.followup.send("❌ Need admin status in the courtroom to change spectating settings", ephemeral=False)
                return
            
            try:
                enable_spectating = enabled.value == "true"
                success = await self.objection_bot.update_room_spectating(enable_spectating)
                
                if success:
                    status = "enabled" if enable_spectating else "disabled"
                    embed = discord.Embed(
                        title="✅ Spectating Updated",
                        description=f"Spectating has been **{status}** in the courtroom",
                        color=0x00ff00
                    )
                    await interaction.followup.send(embed=embed, ephemeral=False)
                    print(f"[SPECTATING] Discord user {interaction.user.display_name} {status} spectating")
                else:
                    await interaction.followup.send("❌ Failed to update spectating settings. Check bot status and permissions.", ephemeral=False)
            except Exception as e:
                print(f"❌ Spectating command error: {e}")
                await interaction.followup.send(f"❌ Failed to change spectating settings: {str(e)}", ephemeral=False)

        @self.tree.command(name="bans", description="Show list of banned users in the courtroom", guild=discord.Object(id=self.guild_id))
        async def bans_command(interaction: discord.Interaction):
            """Show list of banned users"""
            if not check_guild_and_channel(interaction):
                await interaction.response.send_message("❌ This command can only be used in the configured bridge channel.", ephemeral=True)
                return
            
            await interaction.response.defer(ephemeral=False)
            
            if not self.objection_bot.connected:
                await interaction.followup.send("❌ Not connected to objection.lol", ephemeral=False)
                return
            
            # Refresh room data before showing bans
            await self.objection_bot.refresh_room_data()
            # Wait for the response to be processed
            await asyncio.sleep(0.5)
            
            # Create embed with ban information
            embed = discord.Embed(
                title="🚫 Banned Users",
                color=0xff0000
            )
            
            # Add disclaimer if not admin
            if not self.objection_bot.is_admin:
                embed.add_field(
                    name="⚠️ Accuracy Notice",
                    value="The bot is currently not an admin, so this list may not be accurate or up-to-date. The ban list is only visible to room admins.",
                    inline=False
                )
            
            # Show ban list
            if self.objection_bot.banned_users:
                ban_list = []
                for ban in self.objection_bot.banned_users:
                    username = ban.get('username', 'Unknown')
                    user_id = ban.get('id', 'Unknown ID')
                    # Truncate ID for display
                    short_id = user_id[:8] + "..." if len(user_id) > 8 else user_id
                    ban_list.append(f"• **{username}** (`{short_id}`)")
                
                embed.add_field(
                    name=f"Banned Users ({len(self.objection_bot.banned_users)})",
                    value="\n".join(ban_list),
                    inline=False
                )
            else:
                if self.objection_bot.is_admin:
                    embed.add_field(
                        name="Status",
                        value="No users are currently banned from this courtroom.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Status",
                        value="No ban data available. The bot must be an admin to view the ban list.",
                        inline=False
                    )
            
            # Add admin status indicator
            admin_status = "🛡️ Yes" if self.objection_bot.is_admin else "❌ No"
            embed.add_field(
                name="Bot Admin Status",
                value=admin_status,
                inline=True
            )
            
            await interaction.followup.send(embed=embed, ephemeral=False)

    async def on_ready(self):
        print(f'🤖 Discord bot logged in as {self.user}')
        self.bridge_channel = self.get_channel(self.channel_id)
        if self.bridge_channel:
            print(f'📺 Connected to Discord channel: #{self.bridge_channel.name}')
            
            # Remove any previous "CourtDog Online" startup messages
            await self.remove_previous_startup_messages()
            
            # Send startup message with commands info
            max_messages = self.config.get('settings', 'max_messages')
            embed = discord.Embed(
                title="🌉 CourtDog Online",
                description=f"Ruff (Bridge is now active between Discord and Objection.lol. Only {max_messages} messages will be visible at a time.)",
                color=0x00ff00
            )
            embed.add_field(
                name="Available Commands",
                value="/status - Check bridge status\n/reconnect - Reconnect to courtroom\n/nickname - Set your bridge nickname\n/pingname - Manage your ping nicknames\n/color - Set your message color\n/character - Set your character/pose\n/avatars - Toggle avatar display\n/shaba\n/help - Show this help",
                inline=False
            )
            embed.add_field(
                name="Admin Commands",
                value="/titlebar - Change courtroom title\n/slowmode - Set slow mode (requires 3 confirmations)\n/setpassword - Set/remove room password (requires 3 confirmations)\n/text - Change textbox appearance\n/aspect - Change aspect ratio\n/spectating - Enable/disable spectating\n/bans - Show banned users list",
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
            if self._mention_pattern.search(message.content):
                print(f"🚫 Ignoring message with user mention: {message.content[:50]}...")
                return
            
            # Note: !commands (8ball, slap, roll) are NOT handled here on Discord side
            # They get relayed to courtroom where the bot processes them and sends embeds back
            # This prevents duplicate responses
            
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
            
            # Batch lookup all user preferences at once (optimization)
            user_prefs = {
                'nickname': self.nicknames.get(user_id),
                'color': self.colors.get(user_id),
                'character': self.characters.get(user_id)
            }
            
            # Use nickname if set, else display name
            display_name = user_prefs['nickname'] if user_prefs['nickname'] else discord_name
            new_username = f"{display_name} ({base_name})"
            
            # Debug logging to prevent impersonation issues
            log_verbose(f"🔍 Processing message from Discord user: {discord_name} (ID: {user_id})")
            log_verbose(f"🔍 Display name for message: {display_name}")
            log_verbose(f"🔍 Constructed username: {new_username} (length: {len(new_username)})")
            
            # Apply user's custom color if set
            if user_prefs['color']:
                # Add fast text command for media URLs, then apply color
                if media_urls:
                    colored_content = f"[#ts15][#/c{user_prefs['color']}]{full_content}[/#]"
                else:
                    colored_content = f"[#/c{user_prefs['color']}]{full_content}[/#]"
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
                log_verbose(f"✅ Username fits, using: {target_username}")
            else:
                # Username too long, ALWAYS use base name and ALWAYS prefix message with user's name
                target_username = base_name
                send_content = f"{display_name}: {colored_content}"
                log_verbose(f"📏 Username too long, using base name: {target_username}, prefixing with: {display_name}")
            
            # Queue message for high-performance relay (NEW QUEUE SYSTEM)
            # Get user's custom character/pose if set (already batched in user_prefs)
            char_id = None
            p_id = None
            if user_prefs['character']:
                char_id = user_prefs['character']['character_id']
                p_id = user_prefs['character']['pose_id']
            
            # Queue the message - it will be processed by the background queue processor
            message_queued = await self.objection_bot.queue_message(target_username, send_content, character_id=char_id, pose_id=p_id)
            
            if message_queued:
                # Reset avatar embed tracking so next courtroom message shows an embed
                # This allows Discord-to-courtroom conversations to alternate with avatar embeds
                self.last_message_username = None
                self.last_message_pose_id = None
                log_verbose(f"🔄 Reset avatar tracking after Discord message")
                
                # Log the message in simple format for non-verbose mode
                log_message("Discord", display_name, message.content if message.content else "[media]")
                log_verbose(f"🔄 Discord → Queue: {target_username}: {send_content[:50]}...")
            else:
                log_verbose(f"❌ Failed to queue message to objection.lol")
            
            await self.cleanup_messages()

    async def send_to_discord(self, username, message, character_id=None, pose_id=None):
        """Send a message from objection.lol to Discord"""
        if self.bridge_channel:
            # Strip color codes before sending to Discord
            cleaned_message = self.strip_color_codes(message)
            
            # Check for BGM commands and fetch music URLs (limit to 3 per message to prevent spam)
            bgm_ids = self.extract_bgm_commands(message)
            if bgm_ids:
                if len(bgm_ids) > 3:
                    log_verbose(f"⚠️ BGM spam detected: {len(bgm_ids)} commands in one message, limiting to 3")
                    bgm_ids = bgm_ids[:3]
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
                            value=music_data['url'],
                            inline=False
                        )
                        await self.bridge_channel.send(embed=music_embed)
                        log_verbose(f"🎵 Posted music info for BGM {bgm_id}: '{music_data['name']}' -> {music_data['url']}")
            
            # Check for SFX commands and fetch sound effect URLs (limit to 3 per message to prevent spam)
            sfx_ids = self.extract_sfx_commands(message)
            if sfx_ids:
                if len(sfx_ids) > 3:
                    log_verbose(f"⚠️ SFX spam detected: {len(sfx_ids)} commands in one message, limiting to 3")
                    sfx_ids = sfx_ids[:3]
                for sfx_id in sfx_ids:
                    sfx_data = await self.fetch_sfx_url(sfx_id)
                    if sfx_data:
                        # Send the sound effect URL as a rich embed with all available info
                        sfx_embed = discord.Embed(
                            title="🔊 Sound Effect",
                            description=f"**{username}** played a sound effect",
                            color=0xe67e22
                        )
                        sfx_embed.add_field(
                            name="Sound Name",
                            value=sfx_data['name'],
                            inline=True
                        )
                        sfx_embed.add_field(
                            name="Sound ID",
                            value=f"#{sfx_data['id']}",
                            inline=True
                        )
                        sfx_embed.add_field(
                            name="Volume",
                            value=f"{sfx_data['volume']}%",
                            inline=True
                        )
                        sfx_embed.add_field(
                            name="Audio File",
                            value=sfx_data['url'],
                            inline=False
                        )
                        await self.bridge_channel.send(embed=sfx_embed)
                        log_verbose(f"🔊 Posted sound effect info for SFX {sfx_id}: '{sfx_data['name']}' -> {sfx_data['url']}")
            
            # Check for evidence commands and fetch evidence data (limit to 3 per message to prevent spam)
            evidence_ids = self.extract_evidence_commands(message)
            if evidence_ids:
                if len(evidence_ids) > 3:
                    log_verbose(f"⚠️ Evidence spam detected: {len(evidence_ids)} commands in one message, limiting to 3")
                    evidence_ids = evidence_ids[:3]
                for evidence_id in evidence_ids:
                    evidence_data = await self.fetch_evidence_data(evidence_id)
                    if evidence_data:
                        # Send the evidence as a rich embed with image
                        evidence_embed = discord.Embed(
                            title="📄 Evidence Presented",
                            description=f"**{username}** presented evidence",
                            color=0xe67e22
                        )
                        evidence_embed.add_field(
                            name="Evidence Name",
                            value=evidence_data['name'],
                            inline=True
                        )
                        evidence_embed.add_field(
                            name="Evidence ID",
                            value=f"#{evidence_data['id']}",
                            inline=True
                        )
                        evidence_embed.add_field(
                            name="Type",
                            value=evidence_data['type'].capitalize(),
                            inline=True
                        )
                        
                        # Set the image in the embed
                        if evidence_data['type'] == 'image':
                            evidence_embed.set_image(url=evidence_data['url'])
                        else:
                            # For non-image evidence, include the URL as a field
                            evidence_embed.add_field(
                                name="Evidence File",
                                value=evidence_data['url'],
                                inline=False
                            )
                        
                        await self.bridge_channel.send(embed=evidence_embed)
                        log_verbose(f"📄 Posted evidence {evidence_id}: '{evidence_data['name']}' -> {evidence_data['url']}")
            
            # Fetch character avatar if character_id and pose_id are provided
            avatar_url = None
            if character_id is not None and pose_id is not None:
                try:
                    avatar_data = await self.fetch_character_avatar(character_id, pose_id)
                    if avatar_data:
                        avatar_url = avatar_data['url']
                        log_verbose(f"🎭 Fetched avatar for {avatar_data['character_name']} - {avatar_data['pose_name']}")
                    else:
                        log_verbose(f"⚠️ Could not fetch avatar for character {character_id}, pose {pose_id} - will send as plain text")
                except Exception as e:
                    log_verbose(f"⚠️ Error fetching avatar for character {character_id}, pose {pose_id}: {e} - will send as plain text")
                    avatar_url = None
            
            unix_timestamp = int(time.time())
            
            # Show avatar embed if: avatars enabled AND avatar exists AND (different user OR different pose)
            # This allows same user to show new avatar when they change their pose
            pose_changed = pose_id is not None and self.last_message_pose_id != pose_id
            user_changed = self.last_message_username != username
            
            # Check if message contains URLs that Discord might preview (to avoid embed conflicts)
            # Simple URL detection: look for http:// or https://
            contains_url = 'http://' in cleaned_message or 'https://' in cleaned_message
            
            # Determine if we're showing an avatar embed for this new message
            # Don't show avatar if message contains URLs (Discord will add link preview embeds)
            showing_new_avatar = self.show_avatars and avatar_url and (user_changed or pose_changed) and not contains_url
            
            if contains_url and avatar_url:
                log_verbose(f"🔗 Message contains URL, skipping avatar embed to avoid conflicts with link preview")
            
            # Edit the last avatar embed to plain text BEFORE sending new message
            # Scan the last 10 messages to find and convert any avatar embeds (more robust than tracking)
            if showing_new_avatar:
                try:
                    log_verbose(f"🔍 Scanning last 10 messages for avatar embeds to convert...")
                    converted_count = 0
                    async for message in self.bridge_channel.history(limit=10):
                        # Skip messages that aren't from the bot
                        if message.author != self.user:
                            continue
                        # Skip the startup message
                        if self.startup_message and message.id == self.startup_message.id:
                            continue
                        # Check if this message has an embed
                        if message.embeds and len(message.embeds) > 0:
                            try:
                                embed = message.embeds[0]
                                
                                # Skip link preview embeds (they have embed.url set)
                                # Avatar embeds are created with set_image() and don't have a URL field
                                if embed.url:
                                    log_verbose(f"⏭️ Skipping link preview embed: {embed.title}")
                                    continue
                                
                                # Skip system embeds (BGM, SFX, Evidence, notifications, etc.)
                                # Avatar embeds have the username as the title (no emoji prefixes)
                                # System embeds have emoji prefixes like "🎵", "🔊", "📄", "✏️", etc.
                                embed_title = embed.title if embed.title else ""
                                
                                # List of emoji prefixes used in system embeds
                                system_prefixes = ["🎵", "🔊", "📄", "✏️", "👋", "🌉", "🔄", "❌", "👑", "🛡️"]
                                is_system_embed = any(embed_title.startswith(prefix) for prefix in system_prefixes)
                                
                                if is_system_embed:
                                    log_verbose(f"⏭️ Skipping system embed: {embed_title}")
                                    continue
                                
                                # This is an avatar embed - convert it to plain text
                                # Extract the timestamp from the message
                                msg_timestamp = int(message.created_at.timestamp())
                                embed_username = embed.title
                                # Handle empty/zero-width space descriptions
                                embed_message = embed.description if embed.description else ""
                                # Replace zero-width space with empty string for display
                                if embed_message == "\u200b":
                                    embed_message = ""
                                
                                # Format as plain message without avatar (handle empty messages)
                                if embed_message:
                                    formatted_plain = f"**{embed_username}**:\n{embed_message}\n-# <t:{msg_timestamp}:T>"
                                else:
                                    formatted_plain = f"**{embed_username}**:\n-# <t:{msg_timestamp}:T>"
                                await message.edit(content=formatted_plain, embeds=[])
                                converted_count += 1
                                log_verbose(f"✏️ Converted avatar embed from {embed_username} to plain text")
                            except discord.NotFound:
                                log_verbose(f"⚠️ Message was deleted during conversion")
                            except discord.Forbidden:
                                log_verbose(f"⚠️ No permission to edit message")
                            except Exception as e:
                                log_verbose(f"⚠️ Failed to convert embed: {e}")
                    if converted_count > 0:
                        log_verbose(f"✅ Converted {converted_count} avatar embed(s) to plain text")
                except Exception as e:
                    log_verbose(f"⚠️ Error scanning for avatar embeds: {e}")
            
            # Now send the new message - ALWAYS send even if there are errors
            try:
                if showing_new_avatar:
                    # Create embed with avatar at top, then username and message below
                    # Use a zero-width space if message is empty to ensure embed has a description
                    embed_description = cleaned_message if cleaned_message and cleaned_message.strip() else "\u200b"
                    
                    # Use Discord's timestamp format for user-relative time display
                    from datetime import datetime, timezone
                    
                    avatar_embed = discord.Embed(
                        title=f"{username}",
                        description=embed_description,
                        color=0x1e1e1e,
                        timestamp=datetime.fromtimestamp(unix_timestamp, tz=timezone.utc)
                    )
                    avatar_embed.set_image(url=avatar_url)
                    sent_message = await self.bridge_channel.send(embed=avatar_embed)
                    log_verbose(f"🖼️ Sent message as embed with avatar (user_changed={user_changed}, pose_changed={pose_changed})")
                else:
                    # Send as plain text without avatar (no avatar available OR same user+pose as last message)
                    formatted_message = f"**{username}**:\n{cleaned_message}\n-# <t:{unix_timestamp}:T>"
                    sent_message = await self.bridge_channel.send(formatted_message)
            except Exception as e:
                # If embed sending fails (e.g., bad avatar URL), fall back to plain text
                print(f"⚠️ Failed to send message as embed: {e}")
                log_verbose(f"⚠️ Falling back to plain text for: {username}: {cleaned_message}")
                try:
                    formatted_message = f"**{username}**:\n{cleaned_message}\n-# <t:{unix_timestamp}:T>"
                    sent_message = await self.bridge_channel.send(formatted_message)
                except Exception as e2:
                    print(f"❌ Failed to send message even as plain text: {e2}")
                    return  # Exit early if we can't send at all
            
            # Update tracking for next message
            self.last_discord_message = sent_message
            self.last_message_username = username
            self.last_message_pose_id = pose_id
            
            # Log the message in simple format for non-verbose mode
            log_message("Chatroom", username, cleaned_message)
            log_verbose(f"🔄 Objection → Discord: {username}: {cleaned_message}")
            
            # --- Ping detection: scan for @mentions and nickname matches in courtroom messages ---
            if self.config.get('settings', 'enable_pings'):
                try:
                    pinged_user_ids = set()  # Deduplicate pings
                    guild = self.bridge_channel.guild
                    now = time.time()
                    
                    # 1. Check for ping nickname matches
                    # Nicknames starting with @ require @prefix in message, bare nicknames match bare words
                    message_lower = cleaned_message.lower()
                    message_words = re.findall(r'\w+', message_lower)
                    at_words = re.findall(r'@(\w+)', message_lower)  # words after @
                    for uid, nicks in self.ping_nicknames.items():
                        for nick in nicks:
                            matched = False
                            if nick.startswith('@'):
                                # @-prefixed nickname: only match if message has @name
                                if nick[1:] in at_words:
                                    matched = True
                            else:
                                # Bare nickname: match if bare word appears
                                if nick in message_words:
                                    matched = True
                            
                            if matched and uid not in pinged_user_ids:
                                # Rate limit check: max 3 pings per 60 seconds per target user
                                if uid not in self._ping_rate_limit:
                                    self._ping_rate_limit[uid] = []
                                # Clean old timestamps (older than 60 seconds)
                                self._ping_rate_limit[uid] = [t for t in self._ping_rate_limit[uid] if now - t < 60]
                                if len(self._ping_rate_limit[uid]) >= 3:
                                    log_verbose(f"📢 Rate limited: skipping ping for user {uid} (3 pings in last 60s)")
                                    continue
                                
                                pinged_user_ids.add(uid)
                                self._ping_rate_limit[uid].append(now)
                                ping_message = f"📢 Courtroom user **{username}** pinged <@{uid}>"
                                await self.bridge_channel.send(ping_message)
                                log_verbose(f"📢 Ping nickname match: '{nick}' → user ID {uid}")
                                break  # Only ping once per user even if multiple nicknames match
                    
                    # 2. Check for @username mentions (requires @ prefix, for guild member lookup)
                    at_mentions = re.findall(r'@(\w+)', cleaned_message)
                    for mention_name in at_mentions:
                        mention_lower = mention_name.lower()
                        resolved_user_id = None
                        
                        # Search guild members by username/display name
                        for member in guild.members:
                            if (member.name.lower() == mention_lower or 
                                (member.display_name and member.display_name.lower() == mention_lower)):
                                resolved_user_id = str(member.id)
                                log_verbose(f"📢 Guild member match: @{mention_name} → {member.name} (ID: {member.id})")
                                break
                        
                        # Send ping notification if resolved and not already pinged (by nickname or earlier @)
                        if resolved_user_id and resolved_user_id not in pinged_user_ids:
                            # Rate limit check
                            if resolved_user_id not in self._ping_rate_limit:
                                self._ping_rate_limit[resolved_user_id] = []
                            self._ping_rate_limit[resolved_user_id] = [t for t in self._ping_rate_limit[resolved_user_id] if now - t < 60]
                            if len(self._ping_rate_limit[resolved_user_id]) >= 3:
                                log_verbose(f"📢 Rate limited: skipping ping for @{mention_name} (3 pings in last 60s)")
                                continue
                            
                            pinged_user_ids.add(resolved_user_id)
                            self._ping_rate_limit[resolved_user_id].append(now)
                            ping_message = f"📢 Courtroom user **{username}** pinged <@{resolved_user_id}>"
                            await self.bridge_channel.send(ping_message)
                            log_verbose(f"📢 Sent ping notification: {username} → <@{resolved_user_id}>")
                except Exception as e:
                    log_verbose(f"⚠️ Error processing pings: {e}")
            
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
                log_verbose("⚠️ Bot lacks 'Manage Messages' permission - cannot delete old startup messages")
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
                        log_verbose(f"🧹 Deleted previous startup message")
                    except discord.NotFound:
                        pass  # Message already deleted
                    except Exception as e:
                        log_verbose(f"⚠️ Failed to delete startup message: {e}")
            
            if deleted_count > 0:
                log_verbose(f"🧹 Cleaned up {deleted_count} old startup message(s)")
                
        except Exception as e:
            log_verbose(f"⚠️ Error during startup message cleanup: {e}")

    async def cleanup_messages(self):
        """Delete old messages to maintain message limit"""
        max_messages = self.config.get('settings', 'max_messages')
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

            log_verbose(f"🔍 Found {len(messages)} messages in channel (excluding startup message)")

            # Only start deleting if we have more than max_messages + buffer_threshold
            deletion_threshold = max_messages + buffer_threshold

            if len(messages) > deletion_threshold:
                messages_to_delete = messages[max_messages:]  # Get messages beyond the limit
                log_verbose(f"🧹 Need to delete {len(messages_to_delete)} old messages (threshold: {deletion_threshold})")

                deleted_count = 0
                for message in messages_to_delete:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.NotFound:
                        pass  # Message already deleted
                    except discord.Forbidden:
                        log_verbose("⚠️ Bot lacks permission to delete this message")
                    except Exception as e:
                        log_verbose(f"⚠️ Failed to delete message: {e}")

                log_verbose(f"🧹 Successfully deleted {deleted_count} old messages")
            else:
                log_verbose(f"✅ No cleanup needed ({len(messages)}/{deletion_threshold} messages, threshold not reached)")

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
        self.message_queue = asyncio.Queue()  # Changed to async queue
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
        self.banned_users = []  # List of banned users (only available when admin)
        
        # Autoban patterns (regex patterns for automatic banning)
        self.autoban_patterns = load_autobans()
        
        # For Discord bridge compatibility and message queueing
        self._username_change_event = asyncio.Event()
        self._pending_username = None
        self._pending_pair_request = None
        self._message_lock = asyncio.Lock()  # Lock to prevent concurrent message sends
        self._current_username = self.username  # Track current username
        
        # Advanced message queue system for high-performance relay
        self._relay_queue = asyncio.Queue()  # Queue for Discord->Courtroom messages
        self._queue_processor_task = None  # Background task processing the queue
        self._last_queued_username = None  # Track last username to skip redundant changes
        
        # Queue for Courtroom->Discord messages (ensures order is preserved)
        self._discord_send_queue = asyncio.Queue()
        self._discord_queue_processor_task = None
        
        # Pre-compile regex patterns for performance
        self._mention_pattern = re.compile(r'<@\d+>')
        self._color_code_pattern = re.compile(r'\[#/[a-zA-Z]\]|\[#/c[a-fA-F0-9]{6}\]|\[/#\]|\[#ts\d+\]')
        
        # Radio integration state
        self.radio_bgm_id = os.getenv('RADIO_BGM_ID', '#bgm392416')
        self.radio_api_url = os.getenv('RADIO_API_URL', 'http://courtfm:3000/api/now-streaming')
        self.radio_active = False  # Whether radio is currently playing in courtroom
        self.radio_last_title = None  # Last known track title from webhook
        self.radio_last_artist = None  # Last known track artist from webhook
        self._radio_bgm_pattern = re.compile(r'\[#bgm(\d+)\]')  # Pattern to detect BGM commands in messages
    
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
                    
                    # Start the relay queue processor for high-performance message relay
                    self._queue_processor_task = asyncio.create_task(self._process_relay_queue())
                    print("🚀 Started high-performance message queue processor")
                    
                    # Start the Discord send queue processor (ensures message order)
                    self._discord_queue_processor_task = asyncio.create_task(self._process_discord_queue())
                    print("📤 Started Discord message queue processor")
                    
                    # Start webhook server for radio notifications
                    asyncio.create_task(self.start_webhook_server())
                    
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
            # PRIORITY: Handle ping/pong FIRST to prevent disconnects during high load
            # Server pings must be answered quickly or connection will be closed
            if message.startswith('2'):
                # Ping message from server, respond with pong IMMEDIATELY
                await self.websocket.send("3")
                log_verbose("📡 Received ping, sent pong")
                return
            
            if message.startswith('3'):
                # Pong message from server (response to our ping)
                log_verbose("📡 Received pong")
                return
            
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
            
            elif message.startswith('42["plain_message"'):
                # Handle plain messages (no avatar/character)
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1 and isinstance(data[1], dict):
                            await self.handle_plain_message(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for plain message: {e}")
            
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
            
            elif message.startswith('42["update_room_admin"'):
                # Handle admin-only room updates (includes ban list)
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_update_room_admin(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for update_room_admin: {e}")
            
            elif message.startswith('42["add_evidence"'):
                # Handle evidence added events
                start = message.find('[')
                if start > 0:
                    json_str = message[start:]
                    try:
                        data = json.loads(json_str)
                        if len(data) > 1:
                            await self.handle_add_evidence(data[1])
                    except json.JSONDecodeError as e:
                        print(f"JSON decode error for add_evidence: {e}")
            
            # Note: ping/pong (messages starting with '2' or '3') are handled at the TOP
            # of this function for priority processing
            
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
            log_verbose(f"[PAIRING] Auto-accepting pairing due to message: {text}")
            await self.accept_pairing(self._pending_pair_request)
            self._pending_pair_request = None
            return

        # Check for moderator request message - flexible patterns
        text_lower = text.lower()
        courtdog_variants = ["courtdog-sama", "courtdog"]
        
        # Check if at least one courtdog variant is present
        has_courtdog = any(variant in text_lower for variant in courtdog_variants)
        
        # Check for various mod request patterns:
        # - "mod me courtdog" 
        # - "please mod me courtdog"
        # - "grant me mod courtdog"
        # - "grant me blessing courtdog"
        # - "bless me courtdog"
        # - "fuck my wife courtdog"
        has_mod_request = False
        if has_courtdog:
            # Pattern 1: "mod me" (with or without "please")
            if "mod" in text_lower and "me" in text_lower:
                has_mod_request = True
            # Pattern 2: "grant me mod" or "grant me blessing"
            elif "grant" in text_lower and "me" in text_lower and ("mod" in text_lower or "blessing" in text_lower):
                has_mod_request = True
            # Pattern 3: "bless me"
            elif "bless" in text_lower and "me" in text_lower:
                has_mod_request = True
            # Pattern 4: "fuck" + "wife"
            elif "fuck" in text_lower and "wife" in text_lower:
                has_mod_request = True
        
        if has_mod_request and self.is_admin and user_id != self.user_id:
            print(f"[MOD] Mod request from user: {text}")
            await self.handle_mod_request(user_id)
            return

        # --- Radio BGM state tracking ---
        # Monitor ALL incoming messages (including bot's own) for BGM patterns
        # to track whether the radio BGM is currently playing
        bgm_matches = self._radio_bgm_pattern.findall(text)
        if bgm_matches:
            # Extract the radio BGM numeric ID from the env var (e.g., '#bgm392416' -> '392416')
            radio_bgm_numeric = self.radio_bgm_id.replace('#bgm', '')
            
            # Check if any of the BGM commands match the radio BGM ID
            has_radio_bgm = radio_bgm_numeric in bgm_matches
            has_other_bgm = any(bgm_id != radio_bgm_numeric for bgm_id in bgm_matches)
            
            if has_radio_bgm and user_id == self.user_id:
                # Bot sent the radio BGM itself (e.g., via !radio command) - activate radio
                self.radio_active = True
                print(f"📻 Radio state: ACTIVE (bot played radio BGM [{self.radio_bgm_id}])")
            elif has_radio_bgm and user_id != self.user_id:
                # Someone else played the radio BGM - activate radio
                self.radio_active = True
                print(f"📻 Radio state: ACTIVE (user played radio BGM [{self.radio_bgm_id}])")
            
            if has_other_bgm and user_id != self.user_id:
                # Someone else played a DIFFERENT BGM - deactivate radio
                self.radio_active = False
                print(f"📻 Radio state: INACTIVE (different BGM played by user)")
            elif has_other_bgm and user_id == self.user_id:
                # Bot played a different BGM (e.g., !bgm command) - only deactivate if no radio BGM also present
                if not has_radio_bgm:
                    self.radio_active = False
                    print(f"📻 Radio state: INACTIVE (different BGM played by bot)")

        # Check for chat commands (only if bot name doesn't contain "jr" - junior bots don't respond)
        # Use "in" instead of "startswith" to handle color codes before the command
        # Allow commands from anyone including the bot itself (for Discord relay)
        # Feedback loops are prevented by emoji checks (🎱, 🐟, 🎲)
        bot_username = self.config.get('objection', 'bot_username').lower()
        if 'jr' not in bot_username:
            # !8ball command - skip if message contains 🎱 (prevents feedback loop)
            if '!8ball' in text_lower and '🎱' not in text:
                await self.handle_8ball_command(user_id, text)
                # Still relay the question to Discord, so don't return here
            
            # !slap command - skip if message contains 🐟 (prevents feedback loop)
            if '!slap' in text_lower and '🐟' not in text:
                await self.handle_slap_command(user_id, text)
            
            # !roll command - skip if message contains 🎲 (prevents feedback loop)
            if '!roll' in text_lower and '🎲' not in text:
                await self.handle_roll_command(user_id, text)
            
            # !need command - skip if message contains 🎯 (prevents feedback loop)
            if '!need' in text_lower and '🎯' not in text:
                await self.handle_need_command(user_id, text)
            
            # !greed command - skip if message contains 💰 (prevents feedback loop)
            if '!greed' in text_lower and '💰' not in text:
                await self.handle_greed_command(user_id, text)
            
            # !bgm command - skip if message contains 🎵 (prevents feedback loop)
            if '!bgm' in text_lower and '🎵' not in text:
                await self.handle_random_bgm_command(user_id, text)
            
            # !bgs command - skip if message contains 🔊 (prevents feedback loop)
            if '!bgs' in text_lower and '🔊' not in text:
                await self.handle_random_bgs_command(user_id, text)
            
            # !evd command - skip if message contains 📄 (prevents feedback loop)
            if '!evd' in text_lower and '📄' not in text:
                await self.handle_random_evd_command(user_id, text)
            
            # !radio command is handled outside the jr gate (Jr bot handles radio)
        
        # !radio command - skip if message contains 📻 (prevents feedback loop)
        if '!radio' in text_lower and '📻' not in text:
            await self.handle_radio_command(user_id, text)

        if user_id != self.user_id:
            # Check ignore patterns 
            ignore_patterns = self.config.get('settings', 'ignore_patterns')
            if any(pattern in text for pattern in ignore_patterns):
                return
            
            # Ignore messages with Discord user mentions (<@numbers>)
            if self._mention_pattern.search(text):
                log_verbose(f"🚫 Ignoring objection.lol message with user mention: {text[:50]}...")
                return
            
            # Get username from our stored mapping
            username = self.user_names.get(user_id)
            # If we don't have the username, request room update and wait for response
            if username is None:
                log_verbose(f"🔄 Unknown user {user_id[:8]}, requesting room update...")
                await self.websocket.send('42["get_room"]')
                # Wait a moment for the room update to be processed
                await asyncio.sleep(0.5)
                # Try again after the refresh
                username = self.user_names.get(user_id)
                if username is None:
                    # Still unknown after refresh, use fallback
                    username = f"User-{user_id[:8]}"
                    log_verbose(f"⚠️ User {user_id[:8]} still unknown after refresh, using fallback: {username}")
                else:
                    log_verbose(f"✅ Found username after refresh: {username}")
            log_verbose(f"📨 Received: {username}: {text}")
            # Queue message for Discord - uses a dedicated queue processor to:
            # 1. Not block the WebSocket loop (prevents ping timeout disconnects)
            # 2. Preserve message order (messages arrive in Discord in the same order)
            if self.discord_bot:
                # Extract character and pose IDs from the message data
                character_id = message.get('characterId')
                pose_id = message.get('poseId')
                self.queue_discord_message(username, text, character_id, pose_id)
    
    async def handle_plain_message(self, data):
        """Handle plain messages (without avatar/character info)"""
        user_id = data.get('userId')
        text = data.get('text', '')
        
        # --- Radio BGM state tracking (same as handle_message) ---
        text_lower = text.lower()
        bgm_matches = self._radio_bgm_pattern.findall(text)
        if bgm_matches:
            radio_bgm_numeric = self.radio_bgm_id.replace('#bgm', '')
            has_radio_bgm = radio_bgm_numeric in bgm_matches
            has_other_bgm = any(bgm_id != radio_bgm_numeric for bgm_id in bgm_matches)
            
            if has_radio_bgm and user_id == self.user_id:
                self.radio_active = True
                print(f"📻 Radio state (plain): ACTIVE (bot played radio BGM [{self.radio_bgm_id}])")
            elif has_radio_bgm and user_id != self.user_id:
                self.radio_active = True
                print(f"📻 Radio state (plain): ACTIVE (user played radio BGM [{self.radio_bgm_id}])")
            
            if has_other_bgm and user_id != self.user_id:
                self.radio_active = False
                print(f"📻 Radio state (plain): INACTIVE (different BGM played by user)")
            elif has_other_bgm and user_id == self.user_id:
                if not has_radio_bgm:
                    self.radio_active = False
                    print(f"📻 Radio state (plain): INACTIVE (different BGM played by bot)")

        # Check for chat commands in plain messages (same as handle_message)
        # Plain messages come from users without a character/pose selected
        bot_username = self.config.get('objection', 'bot_username').lower()
        if 'jr' not in bot_username:
            if '!8ball' in text_lower and '🎱' not in text:
                await self.handle_8ball_command(user_id, text)
            
            if '!slap' in text_lower and '🐟' not in text:
                await self.handle_slap_command(user_id, text)
            
            if '!roll' in text_lower and '🎲' not in text:
                await self.handle_roll_command(user_id, text)
            
            if '!need' in text_lower and '🎯' not in text:
                await self.handle_need_command(user_id, text)
            
            if '!greed' in text_lower and '💰' not in text:
                await self.handle_greed_command(user_id, text)
            
            if '!bgm' in text_lower and '🎵' not in text:
                await self.handle_random_bgm_command(user_id, text)
            
            if '!bgs' in text_lower and '🔊' not in text:
                await self.handle_random_bgs_command(user_id, text)
            
            if '!evd' in text_lower and '📄' not in text:
                await self.handle_random_evd_command(user_id, text)
            
            # !radio command is handled outside the jr gate (Jr bot handles radio)
        
        # !radio command - skip if message contains 📻 (prevents feedback loop)
        if '!radio' in text_lower and '📻' not in text:
            await self.handle_radio_command(user_id, text)

        if user_id != self.user_id:
            # Check ignore patterns
            ignore_patterns = self.config.get('settings', 'ignore_patterns')
            if any(pattern in text for pattern in ignore_patterns):
                return
            
            # Ignore messages with Discord user mentions (<@numbers>)
            if self._mention_pattern.search(text):
                log_verbose(f"🚫 Ignoring objection.lol plain message with user mention: {text[:50]}...")
                return
            
            # Get username from our stored mapping
            username = self.user_names.get(user_id)
            # If we don't have the username, request room update and wait for response
            if username is None:
                log_verbose(f"🔄 Unknown user {user_id[:8]}, requesting room update...")
                await self.websocket.send('42["get_room"]')
                # Wait a moment for the room update to be processed
                await asyncio.sleep(0.5)
                # Try again after the refresh
                username = self.user_names.get(user_id)
                if username is None:
                    # Still unknown after refresh, use fallback
                    username = f"User-{user_id[:8]}"
                    log_verbose(f"⚠️ User {user_id[:8]} still unknown after refresh, using fallback: {username}")
                else:
                    log_verbose(f"✅ Found username after refresh: {username}")
            log_verbose(f"📨 Received (plain): {username}: {text}")
            # Queue message for Discord - plain messages don't have character/pose info
            if self.discord_bot:
                self.queue_discord_message(username, text, None, None)
    
    async def handle_room_update(self, data):
        """Handle room updates to get user information"""
        # Log the raw data structure for debugging
        log_verbose(f"[DEBUG] Room update data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
        
        # The data parameter IS the room object, users are nested inside it
        users = data.get('users', [])
        
        # Validate room update data - only process if we have valid user data
        if not isinstance(users, list):
            log_verbose(f"⚠️ Invalid room update: users is not a list: {type(users)}")
            log_verbose(f"[DEBUG] Full data structure: {data}")
            return
            
        # Check if this looks like a valid room update with actual user data
        valid_users = []
        for user in users:
            if isinstance(user, dict) and 'id' in user and 'username' in user:
                valid_users.append(user)
        
        log_verbose(f"[DEBUG] Found {len(users)} users in update, {len(valid_users)} valid users")
        
        # Don't update user mapping if we got empty or invalid user data
        # This prevents losing all users due to incomplete server responses
        if not valid_users and self.user_names:
            log_verbose(f"⚠️ Received empty user list in room update - keeping existing user data")
            log_verbose(f"👥 Existing users preserved: {list(self.user_names.values())}")
            # Still process other room data like mods, but don't touch user mapping
        else:
            # Build new username mapping from authoritative room data
            # This ensures we don't have stale entries from users who left
            old_user_names = self.user_names.copy()
            new_user_names = {}
            
            # Build the new mapping with current room users
            for user in valid_users:
                user_id = user['id']
                username = user['username']
                new_user_names[user_id] = username
                log_verbose(f"[DEBUG] Mapping user: {user_id[:8]}... → {username}")
            
            # Atomically replace the old mapping to avoid race conditions
            self.user_names = new_user_names
            
            # Log if we cleared any stale entries
            current_user_ids = set(self.user_names.keys())
            old_user_ids = set(old_user_names.keys())
            removed_users = old_user_ids - current_user_ids
            added_users = current_user_ids - old_user_ids
            
            if removed_users:
                removed_usernames = [old_user_names.get(uid, f"User-{uid[:8]}") for uid in removed_users]
                log_verbose(f"🧹 Cleaned up {len(removed_users)} stale user entries: {removed_usernames}")
            
            if added_users:
                added_usernames = [new_user_names.get(uid, f"User-{uid[:8]}") for uid in added_users]
                log_verbose(f"➕ Added {len(added_users)} new users: {added_usernames}")
            
            # Log current users
            usernames = [user.get('username') for user in valid_users]
            print(f"👥 Users in room: {usernames}")
        
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
            for user in valid_users:
                if user.get('id') == self.user_id and self._pending_username:
                    if user.get('username') == self._pending_username:
                        log_verbose(f"[DEBUG] Username for our user_id matched pending username: {self._pending_username}")
                        self._username_change_event.set()
    
    async def handle_me_response(self, data):
        """Handle 'me' response to get our user ID"""
        if 'user' in data and 'id' in data['user']:
            self.user_id = data['user']['id']
            log_verbose(f"🤖 Bot ID: {self.user_id}")
    
    async def handle_user_joined(self, data):
        """Handle user_joined events"""
        log_verbose(f"[DEBUG] Received user_joined: {data}")

        if isinstance(data, dict):
            user_id = data.get('id')
            username = data.get('username')

            if user_id and username:
                # Add to our user mapping
                self.user_names[user_id] = username

                # Don't show notification for the bot itself
                if user_id != self.user_id:
                    # Check autoban patterns
                    matched_pattern = self.check_autoban(username)
                    if matched_pattern and self.is_admin:
                        print(f"🚫 AUTOBAN: User '{username}' matched pattern '{matched_pattern}' - banning immediately...")
                        
                        # Send "Ruff (Banned undesirable)" message to courtroom
                        original_username = self.config.get('objection', 'bot_username')
                        await self.change_username_and_wait(original_username)
                        await self.send_message("Ruff (Banned undesirable)")
                        
                        # Execute the ban
                        await self.create_ban(user_id)
                        
                        # Remove from user mapping since they're banned
                        if user_id in self.user_names:
                            del self.user_names[user_id]
                        
                        return  # Don't send join notification for banned users
                    elif matched_pattern and not self.is_admin:
                        print(f"⚠️ AUTOBAN: User '{username}' matched pattern '{matched_pattern}' but bot is not admin - cannot ban")
                    
                    # Always show join messages, even in non-verbose mode
                    print(f"👋 User joined: {username}")

                    # Queue join notification for Discord (preserves order, doesn't block WebSocket)
                    if self.discord_bot:
                        current_users = list(self.user_names.values())
                        self.queue_discord_notification(username, "joined", current_users)
    
    async def handle_user_left(self, user_id):
        """Handle user_left events"""
        log_verbose(f"[DEBUG] Received user_left: {user_id}")

        if user_id and user_id in self.user_names:
            username = self.user_names[user_id]

            # Don't show notification for the bot itself
            if user_id != self.user_id:
                # Always show leave messages, even in non-verbose mode
                print(f"👋 User left: {username}")

                # Queue leave notification for Discord (preserves order, doesn't block WebSocket)
                if self.discord_bot:
                    # Remove from mapping first, then get current users
                    del self.user_names[user_id]
                    current_users = list(self.user_names.values())
                    self.queue_discord_notification(username, "left", current_users)
            else:
                # Still remove from mapping even if it's the bot
                del self.user_names[user_id]
    
    async def handle_update_user(self, user_id, user_data):
        """Handle user updates (username changes)"""
        log_verbose(f"[DEBUG] Received update_user: user_id={user_id}, data={user_data}")

        if isinstance(user_data, dict) and user_id:
            new_username = user_data.get('username')

            if new_username:
                # Get the old username before updating
                old_username = self.user_names.get(user_id, f"User-{user_id[:8]}")

                # Update our user mapping with the new username
                self.user_names[user_id] = new_username

                # Don't show notification for the bot itself
                if user_id != self.user_id:
                    # Don't show notification for other court bots (check if either old or new username contains "courtdog")
                    old_has_courtdog = "courtdog" in old_username.lower()
                    new_has_courtdog = "courtdog" in new_username.lower()
                    
                    if not old_has_courtdog and not new_has_courtdog:
                        # Always show username changes, even in non-verbose mode
                        print(f"✏️ User changed name: {old_username} → {new_username}")

                        # Queue name change notification for Discord (preserves order, doesn't block WebSocket)
                        if self.discord_bot:
                            self.queue_discord_username_change(old_username, new_username)
                    else:
                        log_verbose(f"🤖 Court bot name change ignored: {old_username} → {new_username}")
    
    async def handle_create_pair(self, data):
        """Handle pairing requests"""
        log_verbose(f"[PAIRING] Received create_pair: {data}")
        # Only respond if our user_id is in the pairs list
        pairs = data.get('pairs', [])
        if not self.user_id:
            log_verbose("[PAIRING] Bot user_id not set yet, ignoring create_pair.")
            return
        found = any(pair.get('userId') == self.user_id for pair in pairs)
        if not found:
            log_verbose(f"[PAIRING] Ignoring create_pair: bot user_id {self.user_id} not in pairs.")
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
            
            # Initialize room settings with admin permissions
            print("[ADMIN] Initializing room settings...")
            
            # Set aspect ratio to 16:9
            try:
                await self.update_room_aspect_ratio("16:9")
                print("[ADMIN] ✅ Set aspect ratio to 16:9")
            except Exception as e:
                print(f"[ADMIN] ⚠️ Failed to set aspect ratio: {e}")
            
            # Turn off restricting evidence
            try:
                update_data = {"restrictEvidence": False}
                message = f'42["update_room",{json.dumps(update_data)}]'
                await self.websocket.send(message)
                print("[ADMIN] ✅ Disabled evidence restrictions")
            except Exception as e:
                print(f"[ADMIN] ⚠️ Failed to disable evidence restrictions: {e}")
            
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
    
    async def handle_update_room_admin(self, admin_data):
        """Handle admin-only room updates (includes ban list and other admin settings)"""
        print(f"[ADMIN] Received update_room_admin: {admin_data}")
        
        # Extract ban list if present
        if isinstance(admin_data, dict) and 'bans' in admin_data:
            self.banned_users = admin_data['bans']
            if self.banned_users:
                print(f"[ADMIN] Updated ban list: {len(self.banned_users)} banned user(s)")
                for ban in self.banned_users:
                    username = ban.get('username', 'Unknown')
                    user_id = ban.get('id', 'Unknown')
                    print(f"  - {username} (ID: {user_id[:8]}...)")
            else:
                print(f"[ADMIN] Ban list is empty")
        else:
            print(f"[ADMIN] No ban data in update_room_admin")
    
    async def handle_add_evidence(self, evidence_data):
        """Handle evidence added events"""
        print(f"[EVIDENCE] Received add_evidence: {evidence_data}")
        
        if isinstance(evidence_data, dict):
            evidence_id = evidence_data.get('evidenceId')
            evidence_name = evidence_data.get('name', 'Unknown Evidence')
            evidence_url = evidence_data.get('url', '')
            icon_url = evidence_data.get('iconUrl', '')
            evidence_type = evidence_data.get('type', 'image')
            username = evidence_data.get('username', 'Unknown')
            description = evidence_data.get('description', '')
            
            print(f"[EVIDENCE] {username} added evidence: '{evidence_name}' (ID: {evidence_id})")
            
            # Send to Discord if connected
            if self.discord_bot and self.discord_bot.bridge_channel:
                evidence_embed = discord.Embed(
                    title="📄 Evidence Added",
                    description=f"**{username}** added new evidence to the court record",
                    color=0xe67e22
                )
                evidence_embed.add_field(
                    name="Evidence Name",
                    value=evidence_name,
                    inline=True
                )
                evidence_embed.add_field(
                    name="Evidence ID",
                    value=f"#{evidence_id}",
                    inline=True
                )
                evidence_embed.add_field(
                    name="Type",
                    value=evidence_type.capitalize(),
                    inline=True
                )
                
                if description:
                    evidence_embed.add_field(
                        name="Description",
                        value=description,
                        inline=False
                    )
                
                # Use the image URL for display
                display_url = icon_url if icon_url else evidence_url
                if evidence_type == 'image' and display_url:
                    evidence_embed.set_image(url=display_url)
                elif display_url:
                    evidence_embed.add_field(
                        name="Evidence File",
                        value=display_url,
                        inline=False
                    )
                
                await self.discord_bot.bridge_channel.send(embed=evidence_embed)
                print(f"[EVIDENCE] Posted evidence to Discord: {evidence_name}")
    
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
    
    async def create_ban(self, user_id):
        """Ban a user from the courtroom (admin only)"""
        if not self.is_admin:
            print("[BAN] Cannot ban user - bot is not admin")
            return False
        
        if not self.connected or not self.websocket:
            print("[BAN] Cannot ban user - not connected")
            return False
        
        try:
            # Send ban message via WebSocket
            ban_data = {"userId": user_id}
            message = f'42["create_ban",{json.dumps(ban_data)}]'
            await self.websocket.send(message)
            
            username = self.user_names.get(user_id, f"User-{user_id[:8]}")
            print(f"[BAN] Banned user: {username} ({user_id[:8]}...)")
            return True
        except Exception as e:
            print(f"[BAN] Error banning user: {e}")
            return False
    
    async def remove_ban(self, user_id):
        """Unban a user from the courtroom (admin only)
        
        Uses the update_room_admin WebSocket message to update the ban list.
        Format: 42["update_room_admin",{"bans":[...],"password":"","autoTransferAdmin":true},"roomCode"]
        """
        if not self.is_admin:
            print("[UNBAN] Cannot unban user - bot is not admin")
            return False
        
        if not self.connected or not self.websocket:
            print("[UNBAN] Cannot unban user - not connected")
            return False
        
        try:
            # Find and remove the user from the banned_users list
            user_to_unban = None
            for ban in self.banned_users:
                if ban.get('id') == user_id:
                    user_to_unban = ban
                    break
            
            if not user_to_unban:
                print(f"[UNBAN] User ID {user_id[:8]}... not found in ban list")
                return False
            
            # Create new ban list without the unbanned user
            new_bans = [ban for ban in self.banned_users if ban.get('id') != user_id]
            
            # Send update_room_admin message with the new ban list
            # Format: 42["update_room_admin",{"bans":[{"id":"...","username":"..."},...],"password":"","autoTransferAdmin":true},"roomCode"]
            update_data = {
                "bans": new_bans,
                "password": "",  # Keep existing password (empty string means no change)
                "autoTransferAdmin": True  # Keep auto-transfer enabled
            }
            message = f'42["update_room_admin",{json.dumps(update_data)},"{self.room_id}"]'
            await self.websocket.send(message)
            
            # Update local ban list
            username = user_to_unban.get('username', f"User-{user_id[:8]}")
            self.banned_users = new_bans
            print(f"[UNBAN] Unbanned user: {username} ({user_id[:8]}...)")
            return True
        except Exception as e:
            print(f"[UNBAN] Error unbanning user: {e}")
            return False
    
    def check_autoban(self, username):
        """Check if a username matches any autoban pattern"""
        for pattern in self.autoban_patterns:
            try:
                # Try to match as regex pattern
                if re.search(pattern, username, re.IGNORECASE):
                    return pattern
            except re.error:
                # If regex is invalid, try exact match (case-insensitive)
                if pattern.lower() == username.lower():
                    return pattern
        return None
    
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
    
    def strip_color_codes(self, text):
        """Remove objection.lol color codes from text for command parsing"""
        return self._color_code_pattern.sub('', text)
    
    async def handle_8ball_command(self, user_id, text):
        """Handle !8ball command - respond with a random 8-ball answer"""
        # Strip color codes for clean command parsing
        text = self.strip_color_codes(text)
        
        # Classic Magic 8-Ball responses
        responses = [
            # Affirmative
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Yes, definitely.",
            "You may rely on it.",
            "As I see it, yes.",
            "Most likely.",
            "Outlook good.",
            "Yes.",
            "Signs point to yes.",
            # Non-committal
            "Reply hazy, try again.",
            "Ask again later.",
            "Better not tell you now.",
            "Cannot predict now.",
            "Concentrate and ask again.",
            # Negative
            "Don't count on it.",
            "My reply is no.",
            "My sources say no.",
            "Outlook not so good.",
            "Very doubtful."
        ]
        
        response = random.choice(responses)
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        print(f"[8BALL] {username} asked: {text}")
        print(f"[8BALL] Response: {response}")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the response to the courtroom
        await self.send_message(f"🎱 {response}")
        
        # Also send the response to Discord so Discord users see it
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🎱 Magic 8-Ball",
                description=response,
                color=0x000000  # Black like an 8-ball
            )
            embed.set_footer(text=f"Asked by {username} (in courtroom)")
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_slap_command(self, user_id, text):
        """Handle !slap command - slap someone with a fish"""
        # Strip color codes for clean command parsing
        text = self.strip_color_codes(text)
        
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        # Extract the target name after !slap
        text_lower = text.lower()
        slap_index = text_lower.find('!slap')
        target = text[slap_index + 5:].strip()  # Get everything after !slap
        
        if not target:
            target = "themselves"
        
        # Fish only!
        fish = [
            "a large trout",
            "a wet salmon",
            "a slippery mackerel",
            "an angry catfish",
            "a frozen tuna",
            "a flailing carp",
            "a slimy eel",
            "a smelly herring",
            "a flopping bass",
            "a massive halibut",
            "a spiky pufferfish",
            "a legendary swordfish",
            "a majestic bluefin tuna",
            "a wiggling sardine",
            "a prehistoric coelacanth"
        ]
        
        # Various action phrases
        phrases = [
            f"🐟 {username} slaps {target} with {{fish}}!",
            f"🐟 {username} smacks {target} across the face with {{fish}}!",
            f"🐟 {username} wallops {target} using {{fish}}!",
            f"🐟 {username} whacks {target} upside the head with {{fish}}!",
            f"🐟 {username} delivers a devastating blow to {target} with {{fish}}!",
            f"🐟 {username} bonks {target} on the noggin with {{fish}}!",
            f"🐟 {username} thwacks {target} silly with {{fish}}!",
            f"🐟 *SLAP!* {username} hits {target} with {{fish}}!",
            f"🐟 {username} winds up and absolutely CLOBBERS {target} with {{fish}}!",
            f"🐟 {username} gently caresses {target}'s face with {{fish}}. Just kidding, it's a slap!",
        ]
        
        chosen_fish = random.choice(fish)
        response = random.choice(phrases).format(fish=chosen_fish)
        
        print(f"[SLAP] {username} slapped {target}")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the response to the courtroom
        await self.send_message(response)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🐟 Fish Slap!",
                description=response.replace("🐟 ", ""),  # Remove emoji for embed
                color=0x3498db  # Blue like water
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_roll_command(self, user_id, text):
        """Handle !roll command - roll a number between 1-1000 (or custom range)"""
        # Strip color codes for clean command parsing
        text = self.strip_color_codes(text)
        
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        # Default range
        max_roll = 1000
        
        # Try to extract a custom max from the text
        text_lower = text.lower()
        roll_index = text_lower.find('!roll')
        after_roll = text[roll_index + 5:].strip()
        
        # Check if there's a number after !roll
        if after_roll:
            # Try to parse the first number found
            import re
            match = re.search(r'\d+', after_roll)
            if match:
                parsed_max = int(match.group())
                if 1 <= parsed_max <= 1000000:  # Reasonable limit
                    max_roll = parsed_max
        
        result = random.randint(1, max_roll)
        response = f"🎲 {username} rolls {result} (1-{max_roll})"
        
        print(f"[ROLL] {username} rolled {result} (1-{max_roll})")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the response to the courtroom
        await self.send_message(response)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🎲 Dice Roll",
                description=f"**{username}** rolls **{result}** (1-{max_roll})",
                color=0x9b59b6  # Purple color
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_need_command(self, user_id, text):
        """Handle !need command - roll 1-100 for loot (Need roll)"""
        # Strip color codes for clean command parsing
        text = self.strip_color_codes(text)
        
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        result = random.randint(1, 100)
        response = f"🎯 {username} rolls Need: {result}"
        
        print(f"[NEED] {username} rolled {result}")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the response to the courtroom
        await self.send_message(response)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🎯 Need Roll",
                description=f"**{username}** rolls **{result}**",
                color=0x2ecc71  # Green color
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_greed_command(self, user_id, text):
        """Handle !greed command - roll 1-100 for loot (Greed roll)"""
        # Strip color codes for clean command parsing
        text = self.strip_color_codes(text)
        
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        result = random.randint(1, 100)
        response = f"💰 {username} rolls Greed: {result}"
        
        print(f"[GREED] {username} rolled {result}")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the response to the courtroom
        await self.send_message(response)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="💰 Greed Roll",
                description=f"**{username}** rolls **{result}**",
                color=0xf1c40f  # Gold color
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_random_bgm_command(self, user_id, text):
        """Handle !bgm command - roll a random BGM and play it in the courtroom"""
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        print(f"[BGM] {username} requested random BGM")
        
        # Maximum BGM ID
        max_bgm_id = 388326
        batch_size = 10  # Check 10 IDs in parallel per batch
        max_batches = 5  # Maximum 5 batches (50 total attempts)
        
        # Try to find a valid BGM using parallel validation
        bgm_data = None
        total_attempts = 0
        
        for batch_num in range(max_batches):
            # Generate a batch of random IDs
            random_ids = [random.randint(1, max_bgm_id) for _ in range(batch_size)]
            total_attempts += batch_size
            
            # Validate all IDs in parallel
            if self.discord_bot:
                tasks = [self.discord_bot.fetch_music_url(rid, validate_url=True) for rid in random_ids]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Find the first valid result
                for i, result in enumerate(results):
                    if result and not isinstance(result, Exception):
                        bgm_data = result
                        print(f"[BGM] Found valid BGM after {batch_num * batch_size + i + 1} attempt(s): #{random_ids[i]} - {bgm_data['name']}")
                        break
                
                if bgm_data:
                    break
        
        if not bgm_data:
            print(f"[BGM] Failed to find valid BGM after {total_attempts} attempts")
            return
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the BGM command to the courtroom
        bgm_command = f"🎵 [#bgm{bgm_data['id']}]"
        await self.send_message(bgm_command)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🎵 Random BGM Roll",
                description=f"**{username}** rolled a random track!",
                color=0x9b59b6  # Purple color
            )
            embed.add_field(
                name="Track Name",
                value=bgm_data['name'],
                inline=True
            )
            embed.add_field(
                name="Track ID",
                value=f"#{bgm_data['id']}",
                inline=True
            )
            embed.add_field(
                name="Volume",
                value=f"{bgm_data['volume']}%",
                inline=True
            )
            embed.add_field(
                name="Audio File",
                value=bgm_data['url'],
                inline=False
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_random_bgs_command(self, user_id, text):
        """Handle !bgs command - roll a random BGS/SFX and play it in the courtroom"""
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        print(f"[BGS] {username} requested random BGS/SFX")
        
        # Maximum BGS ID
        max_bgs_id = 139315
        batch_size = 10  # Check 10 IDs in parallel per batch
        max_batches = 5  # Maximum 5 batches (50 total attempts)
        
        # Try to find a valid BGS using parallel validation
        bgs_data = None
        total_attempts = 0
        
        for batch_num in range(max_batches):
            # Generate a batch of random IDs
            random_ids = [random.randint(1, max_bgs_id) for _ in range(batch_size)]
            total_attempts += batch_size
            
            # Validate all IDs in parallel
            if self.discord_bot:
                tasks = [self.discord_bot.fetch_sfx_url(rid, validate_url=True) for rid in random_ids]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Find the first valid result
                for i, result in enumerate(results):
                    if result and not isinstance(result, Exception):
                        bgs_data = result
                        print(f"[BGS] Found valid BGS after {batch_num * batch_size + i + 1} attempt(s): #{random_ids[i]} - {bgs_data['name']}")
                        break
                
                if bgs_data:
                    break
        
        if not bgs_data:
            print(f"[BGS] Failed to find valid BGS after {total_attempts} attempts")
            return
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the BGS command to the courtroom
        bgs_command = f"🔊 [#bgs{bgs_data['id']}]"
        await self.send_message(bgs_command)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="🔊 Random BGS Roll",
                description=f"**{username}** rolled a random sound effect!",
                color=0xe67e22  # Orange color
            )
            embed.add_field(
                name="Sound Name",
                value=bgs_data['name'],
                inline=True
            )
            embed.add_field(
                name="Sound ID",
                value=f"#{bgs_data['id']}",
                inline=True
            )
            embed.add_field(
                name="Volume",
                value=f"{bgs_data['volume']}%",
                inline=True
            )
            embed.add_field(
                name="Audio File",
                value=bgs_data['url'],
                inline=False
            )
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def handle_random_evd_command(self, user_id, text):
        """Handle !evd command - roll a random evidence and display it in the courtroom"""
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        print(f"[EVD] {username} requested random evidence")
        
        # Maximum evidence ID
        max_evd_id = 946161
        batch_size = 10  # Check 10 IDs in parallel per batch
        max_batches = 5  # Maximum 5 batches (50 total attempts)
        
        # Try to find a valid evidence using parallel validation
        evd_data = None
        total_attempts = 0
        
        for batch_num in range(max_batches):
            # Generate a batch of random IDs
            random_ids = [random.randint(1, max_evd_id) for _ in range(batch_size)]
            total_attempts += batch_size
            
            # Validate all IDs in parallel
            if self.discord_bot:
                tasks = [self.discord_bot.fetch_evidence_data(rid, validate_url=True) for rid in random_ids]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Find the first valid result
                for i, result in enumerate(results):
                    if result and not isinstance(result, Exception):
                        evd_data = result
                        print(f"[EVD] Found valid evidence after {batch_num * batch_size + i + 1} attempt(s): #{random_ids[i]} - {evd_data['name']}")
                        break
                
                if evd_data:
                    break
        
        if not evd_data:
            print(f"[EVD] Failed to find valid evidence after {total_attempts} attempts")
            return
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send the evidence command to the courtroom
        evd_command = f"📄 [#evd{evd_data['id']}]"
        await self.send_message(evd_command)
        
        # Also send the response to Discord
        if self.discord_bot and self.discord_bot.bridge_channel:
            embed = discord.Embed(
                title="📄 Random Evidence Roll",
                description=f"**{username}** rolled random evidence!",
                color=0xe67e22  # Orange color
            )
            embed.add_field(
                name="Evidence Name",
                value=evd_data['name'],
                inline=True
            )
            embed.add_field(
                name="Evidence ID",
                value=f"#{evd_data['id']}",
                inline=True
            )
            embed.add_field(
                name="Type",
                value=evd_data['type'].capitalize(),
                inline=True
            )
            
            # Set the image in the embed if it's an image type
            if evd_data['type'] == 'image':
                embed.set_image(url=evd_data['url'])
            else:
                embed.add_field(
                    name="Evidence File",
                    value=evd_data['url'],
                    inline=False
                )
            
            await self.discord_bot.bridge_channel.send(embed=embed)
    
    async def _process_relay_queue(self):
        """
        High-performance message queue processor.
        Processes Discord->Courtroom messages with intelligent username change batching.
        """
        print("📋 Message queue processor started")
        
        while self.connected:
            try:
                # Get the next message from the queue (blocks until available)
                queue_item = await self._relay_queue.get()
                
                # Check for shutdown signal
                if queue_item is None:
                    print("📋 Queue processor received shutdown signal")
                    break
                
                username, message_text, character_id, pose_id = queue_item
                
                # Use lock to ensure the entire sequence is atomic
                async with self._message_lock:
                    # Only change username if it's different from the last one
                    # This optimization skips username changes when same user sends multiple messages
                    if username != self._last_queued_username:
                        log_verbose(f"[QUEUE] Username change needed: {self._last_queued_username} → {username}")
                        success = await self._send_username_change(username)
                        if not success:
                            log_verbose(f"[QUEUE] Failed to change username, skipping message")
                            self._relay_queue.task_done()
                            continue
                        self._last_queued_username = username
                    else:
                        # Same user - skip username change but still add delay for server processing
                        log_verbose(f"[QUEUE] Username unchanged ({username}), skipping username change")
                        await asyncio.sleep(0.08)  # Small delay for server processing
                    
                    # Send the message with rate limit protection
                    # Courtroom has 1 message per second rate limit per user account
                    success = await self._send_message_internal(message_text, character_id, pose_id, enforce_rate_limit=True)
                
                if success:
                    log_verbose(f"[QUEUE] ✓ Sent: {username}: {message_text[:50]}...")
                else:
                    log_verbose(f"[QUEUE] ✗ Failed to send message from {username}")
                
                # Mark task as done
                self._relay_queue.task_done()
                
            except asyncio.CancelledError:
                print("📋 Queue processor cancelled")
                break
            except Exception as e:
                print(f"❌ Error in queue processor: {e}")
                # Don't break - continue processing
        
        print("📋 Message queue processor stopped")
    
    async def _process_discord_queue(self):
        """
        Process Courtroom->Discord messages in order.
        This ensures messages arrive in Discord in the same order they were sent from the courtroom,
        while not blocking the WebSocket message loop (which needs to respond to pings quickly).
        """
        print("📤 Discord message queue processor started")
        
        while self.connected:
            try:
                # Get the next item from the queue (blocks until available)
                queue_item = await self._discord_send_queue.get()
                
                # Check for shutdown signal
                if queue_item is None:
                    print("📤 Discord queue processor received shutdown signal")
                    break
                
                # Unpack the queue item
                send_type, args = queue_item
                
                try:
                    if send_type == "message" and self.discord_bot:
                        username, text, character_id, pose_id = args
                        await self.discord_bot.send_to_discord(username, text, character_id, pose_id)
                    elif send_type == "user_notification" and self.discord_bot:
                        username, action, user_list = args
                        await self.discord_bot.send_user_notification(username, action, user_list)
                    elif send_type == "username_change" and self.discord_bot:
                        old_username, new_username = args
                        await self.discord_bot.send_username_change_notification(old_username, new_username)
                except Exception as e:
                    print(f"❌ Error sending to Discord: {e}")
                
                # Mark task as done
                self._discord_send_queue.task_done()
                
            except asyncio.CancelledError:
                print("📤 Discord queue processor cancelled")
                break
            except Exception as e:
                print(f"❌ Error in Discord queue processor: {e}")
                # Don't break - continue processing
        
        print("📤 Discord message queue processor stopped")
    
    def queue_discord_message(self, username, text, character_id=None, pose_id=None):
        """Queue a message to be sent to Discord (preserves order)"""
        try:
            self._discord_send_queue.put_nowait(("message", (username, text, character_id, pose_id)))
        except Exception as e:
            print(f"❌ Failed to queue Discord message: {e}")
    
    def queue_discord_notification(self, username, action, user_list=None):
        """Queue a user notification to be sent to Discord (preserves order)"""
        try:
            self._discord_send_queue.put_nowait(("user_notification", (username, action, user_list)))
        except Exception as e:
            print(f"❌ Failed to queue Discord notification: {e}")
    
    def queue_discord_username_change(self, old_username, new_username):
        """Queue a username change notification to be sent to Discord (preserves order)"""
        try:
            self._discord_send_queue.put_nowait(("username_change", (old_username, new_username)))
        except Exception as e:
            print(f"❌ Failed to queue Discord username change: {e}")
    
    async def _send_username_change(self, new_username):
        """Internal method to change username (used by queue processor)"""
        # No lock needed - queue processor ensures sequential execution
        # Skip if username is already current
        if self._current_username == new_username:
            log_verbose(f"[DEBUG] Username already set to {new_username}, skipping change")
            return True
        
        # Check if WebSocket is still connected
        if not self.connected or not self.websocket or self.websocket.close_code is not None:
            log_verbose("❌ Cannot change username - not connected")
            return False
        
        try:
            # Send username change via WebSocket
            message_data = {"username": new_username}
            message = f'42["change_username",{json.dumps(message_data)}]'
            await self.websocket.send(message)
            
            # Username changes are also subject to the 1-second rate limit
            # Wait for both propagation AND rate limit
            await asyncio.sleep(1.0)
            
            # Update current username tracking
            self._current_username = new_username
            return True
        except Exception as e:
            log_verbose(f"❌ Username change failed: {e}")
            return False
    
    async def _send_message_internal(self, text, character_id=None, pose_id=None, enforce_rate_limit=False):
        """Internal method to send message (used by queue processor)"""
        # No lock needed - queue processor ensures sequential execution
        if not self.connected or not self.websocket or self.websocket.close_code is not None:
            return False
        
        # Use provided character/pose or fall back to config defaults
        char_id = character_id if character_id is not None else self.config.get('settings', 'character_id')
        p_id = pose_id if pose_id is not None else self.config.get('settings', 'pose_id')
        message_data = {
            "characterId": char_id,
            "poseId": p_id,
            "text": text
        }
        
        try:
            message = f'42["message",{json.dumps(message_data)}]'
            await self.websocket.send(message)
            
            # Courtroom enforces 1 message per second rate limit per user account
            # For queued Discord messages, we must respect this 1-second limit
            # For direct bot messages (pairing, etc), use minimal delay
            if enforce_rate_limit:
                await asyncio.sleep(1.0)  # 1 second rate limit for courtroom
            else:
                await asyncio.sleep(0.05)  # Minimal delay for direct messages
            return True
        except Exception as e:
            log_verbose(f"❌ Send failed: {e}")
            return False
    
    async def queue_message(self, username, message_text, character_id=None, pose_id=None):
        """
        Queue a message for high-performance relay.
        Messages are processed in order by the background queue processor.
        """
        try:
            await self._relay_queue.put((username, message_text, character_id, pose_id))
            log_verbose(f"[QUEUE] Queued message from {username} (queue size: {self._relay_queue.qsize()})")
            return True
        except Exception as e:
            print(f"❌ Failed to queue message: {e}")
            return False
    
    async def change_username_and_wait(self, new_username, timeout=2.0):
        """Change the bot's username using WebSocket with proper locking"""
        # Use lock to ensure username changes happen sequentially
        async with self._message_lock:
            log_verbose(f"[DEBUG] Requesting username change to: {new_username}")
            
            # Skip if username is already current
            if self._current_username == new_username:
                log_verbose(f"[DEBUG] Username already set to {new_username}, skipping change")
                return True
            
            # Check if WebSocket is still connected
            if not self.connected:
                log_verbose("❌ Cannot change username - Bot marked as disconnected")
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
                
                # Reduced delay for faster username propagation (was 0.15s)
                # This is still safe but improves message throughput
                await asyncio.sleep(0.08)
                
                # Update current username tracking
                self._current_username = new_username
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
    
    async def handle_radio_command(self, user_id, text):
        """Handle !radio command - start playing the radio in the courtroom"""
        username = self.user_names.get(user_id, f"User-{user_id[:8]}")
        
        print(f"[RADIO] {username} requested radio")
        
        # Set radio state to active
        self.radio_active = True
        
        # Try to get current track info from stored state first, then fallback to API
        title = self.radio_last_title
        artist = self.radio_last_artist
        
        if not title:
            # Fetch from radio API as fallback
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(self.radio_api_url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                        if response.status == 200:
                            data = await response.json()
                            title = data.get('title', 'Unknown')
                            artist = data.get('artist', '')
                            print(f"[RADIO] Fetched current track from API: {title} by {artist}")
                        else:
                            title = 'Unknown'
                            artist = ''
                            print(f"[RADIO] API returned status {response.status}, using defaults")
            except Exception as e:
                title = 'Unknown'
                artist = ''
                print(f"[RADIO] Failed to fetch from API: {e}")
        
        # Change to bot's default username for command responses
        original_username = self.config.get('objection', 'bot_username')
        await self.change_username_and_wait(original_username)
        self._last_queued_username = None  # Reset so next Discord message changes username
        
        # Send combined BGM + announcement as a single normal message (BGM tag must be in a normal message to work)
        if artist:
            radio_announcement = f"📻 Ruff 🎵 (This is CourtDog FM, you're listening to: {title} by {artist}) [{self.radio_bgm_id}]"
        else:
            radio_announcement = f"📻 Ruff 🎵 (This is CourtDog FM, you're listening to: {title}) [{self.radio_bgm_id}]"
        
        await self.send_message(radio_announcement)
        print(f"[RADIO] Sent radio announcement with BGM: {radio_announcement}")
    
    async def start_webhook_server(self):
        """Start HTTP webhook server for radio song change notifications"""
        webhook_port = int(os.getenv('WEBHOOK_PORT', '5050'))
        
        async def handle_now_playing(request):
            try:
                data = await request.json()
                title = data.get('title', 'Unknown')
                artist = data.get('artist', '')
                
                # Store last known track info for !radio command
                self.radio_last_title = title
                self.radio_last_artist = artist
                
                print(f"📻 Webhook received: {title}" + (f" by {artist}" if artist else ""))
                
                # Only send courtroom message if radio is active
                if self.radio_active and self.connected:
                    # Revert to bot username for radio announcements
                    original_username = self.config.get('objection', 'bot_username')
                    await self.change_username_and_wait(original_username)
                    self._last_queued_username = None  # Reset so next Discord message changes username
                    
                    # Format announcement
                    if artist:
                        announcement = f"Ruff 🎵 (Now Playing: {title} by {artist})"
                    else:
                        announcement = f"Ruff 🎵 (Now Playing: {title})"
                    
                    await self.send_plain_message(announcement)
                    print(f"📻 Sent radio announcement to courtroom (plain): {announcement}")
                else:
                    if not self.radio_active:
                        print(f"📻 Radio inactive, skipping courtroom announcement")
                    elif not self.connected:
                        print(f"📻 Not connected, skipping courtroom announcement")
                
                return web.Response(text="OK", status=200)
            except Exception as e:
                print(f"📻 Webhook error: {e}")
                return web.Response(text="Error", status=500)
        
        app = web.Application()
        app.router.add_post('/webhook/now-playing', handle_now_playing)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', webhook_port)
        await site.start()
        print(f"📻 Webhook server listening on port {webhook_port}")
        self._webhook_runner = runner
    
    async def graceful_disconnect(self):
        """Gracefully disconnect: clean up Discord, update room, disconnect socket."""
        print("🔄 Starting graceful disconnect...")
        
        # Clean up webhook server
        if hasattr(self, '_webhook_runner') and self._webhook_runner:
            print("🛑 Stopping webhook server...")
            await self._webhook_runner.cleanup()
            print("✅ Webhook server stopped")
        
        # Stop the queue processor first
        if self._queue_processor_task and not self._queue_processor_task.done():
            print("🛑 Stopping message queue processor...")
            await self._relay_queue.put(None)  # Send shutdown signal
            try:
                await asyncio.wait_for(self._queue_processor_task, timeout=5.0)
                print("✅ Queue processor stopped")
            except asyncio.TimeoutError:
                print("⚠️ Queue processor did not stop gracefully, cancelling...")
                self._queue_processor_task.cancel()
                try:
                    await self._queue_processor_task
                except asyncio.CancelledError:
                    pass
        
        # Stop the Discord queue processor
        if self._discord_queue_processor_task and not self._discord_queue_processor_task.done():
            print("🛑 Stopping Discord queue processor...")
            await self._discord_send_queue.put(None)  # Send shutdown signal
            try:
                await asyncio.wait_for(self._discord_queue_processor_task, timeout=5.0)
                print("✅ Discord queue processor stopped")
            except asyncio.TimeoutError:
                print("⚠️ Discord queue processor did not stop gracefully, cancelling...")
                self._discord_queue_processor_task.cancel()
                try:
                    await self._discord_queue_processor_task
                except asyncio.CancelledError:
                    pass
        
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
    
    async def send_message(self, text, character_id=None, pose_id=None):
        """Send a message to the chatroom with optional character/pose override"""
        # Use lock to ensure messages are sent sequentially
        async with self._message_lock:
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
                
            # Use provided character/pose or fall back to config defaults
            char_id = character_id if character_id is not None else self.config.get('settings', 'character_id')
            p_id = pose_id if pose_id is not None else self.config.get('settings', 'pose_id')
            message_data = {
                "characterId": char_id,
                "poseId": p_id,
                "text": text
            }
            
            try:
                message = f'42["message",{json.dumps(message_data)}]'
                await self.websocket.send(message)
                log_verbose(f"📤 Sent: {text}")
                # Reduced delay for faster message throughput (was 0.1s)
                # Still prevents rate limiting but improves responsiveness
                await asyncio.sleep(0.05)
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

    async def send_plain_message(self, text):
        """Send a plain message to the chatroom (no character/pose avatar)"""
        async with self._message_lock:
            if not self.connected:
                print("❌ Not connected - cannot send plain message")
                if self.auto_reconnect:
                    await self.start_auto_reconnect()
                return False
                
            if not self.websocket or self.websocket.close_code is not None:
                print("❌ WebSocket connection lost - cannot send plain message")
                self.connected = False
                if self.auto_reconnect:
                    await self.start_auto_reconnect()
                return False
                
            message_data = {"text": text}
            
            try:
                message = f'42["plain_message",{json.dumps(message_data)}]'
                await self.websocket.send(message)
                log_verbose(f"📤 Sent (plain): {text}")
                await asyncio.sleep(0.05)
                return True
            except Exception as e:
                print(f"❌ Plain send failed: {e}")
                if "closed" in str(e).lower() or "disconnected" in str(e).lower():
                    print("🔗 Send failure suggests connection loss - marking as disconnected")
                    self.connected = False
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

    async def update_room_aspect_ratio(self, aspect_ratio):
        """Update the room aspect ratio (admin only)"""
        if not self.is_admin:
            print("[ASPECT] Cannot update aspect ratio - bot is not admin")
            return False
        
        # Validate aspect ratio
        valid_ratios = ["3:2", "4:3", "16:9", "16:10"]
        if aspect_ratio not in valid_ratios:
            print(f"[ASPECT] Invalid aspect ratio: {aspect_ratio}. Valid options: {', '.join(valid_ratios)}")
            return False
        
        # Send update to server
        try:
            update_data = {"aspectRatio": aspect_ratio}
            message = f'42["update_room",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            print(f"[ASPECT] Updated room aspect ratio: {aspect_ratio}")
            return True
        except Exception as e:
            print(f"[ASPECT] Error updating aspect ratio: {e}")
            return False

    async def update_room_spectating(self, enable_spectating):
        """Enable or disable spectating in the room (admin only)"""
        if not self.is_admin:
            print("[SPECTATING] Cannot update spectating - bot is not admin")
            return False
        
        # Send update to server
        try:
            update_data = {"enableSpectating": enable_spectating}
            message = f'42["update_room",{json.dumps(update_data)}]'
            await self.websocket.send(message)
            status = "enabled" if enable_spectating else "disabled"
            print(f"[SPECTATING] {status.capitalize()} spectating in room")
            return True
        except Exception as e:
            print(f"[SPECTATING] Error updating spectating: {e}")
            return False

    async def refresh_room_data(self):
        """Refresh room data by sending get_room message"""
        if not self.connected or not self.websocket:
            print("[REFRESH] Cannot refresh - not connected")
            return False
        
        try:
            print("🔄 Refreshing room data...")
            await self.websocket.send('42["get_room"]')
            return True
        except Exception as e:
            print(f"[REFRESH] Error refreshing room data: {e}")
            return False

    async def transfer_ownership(self, target_user_id):
        """Transfer room ownership to another user"""
        if not self.connected or not self.websocket:
            print("[TRANSFER] Cannot transfer ownership - not connected")
            return False
        
        try:
            print(f"🔄 Transferring ownership to user: {target_user_id}")
            message = f'42["owner_transfer","{target_user_id}"]'
            await self.websocket.send(message)
            print(f"[TRANSFER] Ownership transfer initiated for user: {target_user_id}")
            return True
        except Exception as e:
            print(f"[TRANSFER] Error transferring ownership: {e}")
            return False

    def get_user_id_by_username(self, username):
        """Get user ID by username (case-insensitive search)"""
        username_lower = username.lower()
        for user_id, stored_username in self.user_names.items():
            if stored_username.lower() == username_lower:
                return user_id
        return None

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
            elif cmd_lower.startswith("transfer "):
                # Extract the username after "transfer "
                username = cmd[9:].strip()  # Remove "transfer " prefix (preserving original case)
                if username:
                    if objection_bot.connected:
                        # Find user ID by username
                        user_id = objection_bot.get_user_id_by_username(username)
                        if user_id:
                            print(f"🔄 Transferring ownership to '{username}' (ID: {user_id[:8]}...)")
                            success = await objection_bot.transfer_ownership(user_id)
                            if success:
                                print(f"✅ Ownership transfer initiated successfully!")
                                print(f"⚠️ Bot will no longer be admin after transfer completes.")
                            else:
                                print(f"❌ Failed to transfer ownership.")
                        else:
                            print(f"❌ User '{username}' not found in courtroom.")
                            print("Current users:")
                            for uid, uname in objection_bot.user_names.items():
                                print(f"   - {uname} (ID: {uid[:8]}...)")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a username after 'transfer'. Example: transfer JohnDoe")
            elif cmd_lower == "status":
                # Show detailed bot status
                print("🤖 Bot Status:")
                print(f"   Objection.lol: {'🟢 Connected' if objection_bot.connected else '🔴 Disconnected'}")
                print(f"   Discord: {'🟢 Connected' if not discord_bot.is_closed() else '🔴 Disconnected'}")
                print(f"   Admin Status: {'🛡️ Yes' if objection_bot.is_admin else '❌ No'}")
                print(f"   Room ID: {objection_bot.room_id}")
                print(f"   Bot Username: {objection_bot.username}")
                print(f"   Users in Room: {len(objection_bot.user_names)}")
                if objection_bot.current_mods:
                    mod_names = [objection_bot.user_names.get(mod_id, f"User-{mod_id[:8]}") for mod_id in objection_bot.current_mods]
                    print(f"   Moderators: {', '.join(mod_names)}")
                else:
                    print(f"   Moderators: None")
                print(f"   Reconnect Attempts: {objection_bot.reconnect_attempts}/{objection_bot.max_reconnect_attempts}")
            elif cmd_lower == "users":
                # List all users in the courtroom
                if objection_bot.user_names:
                    print(f"👥 Users in Courtroom ({len(objection_bot.user_names)}):")
                    for user_id, username in objection_bot.user_names.items():
                        status_indicators = []
                        if user_id == objection_bot.user_id:
                            status_indicators.append("🤖 Bot")
                        if user_id in objection_bot.current_mods:
                            status_indicators.append("🛡️ Mod")
                        status_text = f" ({', '.join(status_indicators)})" if status_indicators else ""
                        print(f"   - {username}{status_text} (ID: {user_id[:8]}...)")
                else:
                    print("👥 No users found in courtroom")
            elif cmd_lower == "refresh":
                # Refresh room data
                if objection_bot.connected:
                    print("🔄 Refreshing room data...")
                    success = await objection_bot.refresh_room_data()
                    if success:
                        await asyncio.sleep(1)  # Wait for response
                        print(f"✅ Room data refreshed. Found {len(objection_bot.user_names)} users.")
                    else:
                        print("❌ Failed to refresh room data.")
                else:
                    print("❌ Not connected to objection.lol. Use 'reconnect' first.")
            elif cmd_lower.startswith("title "):
                # Change room title
                title = cmd[6:].strip()  # Remove "title " prefix
                if title:
                    if objection_bot.connected:
                        if objection_bot.is_admin:
                            print(f"📝 Changing room title to: '{title}'")
                            success = await objection_bot.update_room_title(title)
                            if success:
                                print("✅ Room title updated successfully!")
                            else:
                                print("❌ Failed to update room title.")
                        else:
                            print("❌ Bot is not admin. Cannot change room title.")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a title after 'title'. Example: title My Awesome Courtroom")
            elif cmd_lower.startswith("slowmode "):
                # Set slow mode
                try:
                    seconds = int(cmd[9:].strip())  # Remove "slowmode " prefix
                    if 0 <= seconds <= 60:
                        if objection_bot.connected:
                            if objection_bot.is_admin:
                                if seconds == 0:
                                    print("⏱️ Disabling slow mode...")
                                else:
                                    print(f"⏱️ Setting slow mode to {seconds} seconds...")
                                success = await objection_bot.update_room_slowmode(seconds)
                                if success:
                                    print("✅ Slow mode updated successfully!")
                                else:
                                    print("❌ Failed to update slow mode.")
                            else:
                                print("❌ Bot is not admin. Cannot change slow mode.")
                        else:
                            print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                    else:
                        print("❌ Slow mode seconds must be between 0 and 60.")
                except ValueError:
                    print("❌ Please provide a valid number after 'slowmode'. Example: slowmode 5")
            elif cmd_lower.startswith("textbox "):
                # Change textbox style
                style = cmd[8:].strip()  # Remove "textbox " prefix
                if style:
                    if objection_bot.connected:
                        if objection_bot.is_admin:
                            print(f"🎨 Changing textbox style to: '{style}'")
                            success = await objection_bot.update_room_textbox(style)
                            if success:
                                print("✅ Textbox style updated successfully!")
                            else:
                                print("❌ Failed to update textbox style.")
                        else:
                            print("❌ Bot is not admin. Cannot change textbox style.")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a style after 'textbox'. Example: textbox aa-trilogy")
            elif cmd_lower.startswith("aspect "):
                # Change aspect ratio
                ratio = cmd[7:].strip()  # Remove "aspect " prefix
                if ratio:
                    valid_ratios = ["3:2", "4:3", "16:9", "16:10"]
                    if ratio in valid_ratios:
                        if objection_bot.connected:
                            if objection_bot.is_admin:
                                print(f"📐 Changing aspect ratio to: '{ratio}'")
                                success = await objection_bot.update_room_aspect_ratio(ratio)
                                if success:
                                    print("✅ Aspect ratio updated successfully!")
                                else:
                                    print("❌ Failed to update aspect ratio.")
                            else:
                                print("❌ Bot is not admin. Cannot change aspect ratio.")
                        else:
                            print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                    else:
                        print(f"❌ Invalid aspect ratio '{ratio}'. Valid options: {', '.join(valid_ratios)}")
                else:
                    print("❌ Please provide an aspect ratio after 'aspect'. Example: aspect 16:9")
            elif cmd_lower == "config":
                # Show current configuration
                print("⚙️ Current Configuration:")
                print(f"   Room ID: {objection_bot.config.get('objection', 'room_id')}")
                print(f"   Bot Username: {objection_bot.config.get('objection', 'bot_username')}")
                print(f"   Character ID: {objection_bot.config.get('settings', 'character_id')}")
                print(f"   Pose ID: {objection_bot.config.get('settings', 'pose_id')}")
                print(f"   Mode: {objection_bot.config.get('settings', 'mode')}")
                print(f"   Auto-reconnect: {objection_bot.auto_reconnect}")
                print(f"   Max reconnect attempts: {objection_bot.max_reconnect_attempts}")
                discord_config = objection_bot.config.get('discord')
                if discord_config:
                    print(f"   Discord Channel ID: {discord_config.get('channel_id')}")
                    print(f"   Discord Guild ID: {discord_config.get('guild_id')}")
            elif cmd_lower == "debug":
                # Show debug information
                print("🐛 Debug Information:")
                print(f"   WebSocket State: {objection_bot.websocket.state if objection_bot.websocket else 'None'}")
                print(f"   WebSocket Close Code: {objection_bot.websocket.close_code if objection_bot.websocket else 'None'}")
                print(f"   User ID: {objection_bot.user_id}")
                print(f"   Pending Username: {objection_bot._pending_username}")
                print(f"   Pending Pair Request: {bool(objection_bot._pending_pair_request)}")
                print(f"   Terminal Queue Size: {objection_bot.message_queue.qsize()}")
                print(f"   Relay Queue Size: {objection_bot._relay_queue.qsize()} (Discord→Courtroom)")
                print(f"   Last Queued Username: {objection_bot._last_queued_username}")
                print(f"   Queue Processor Running: {objection_bot._queue_processor_task and not objection_bot._queue_processor_task.done()}")
                print(f"   Discord Nicknames: {len(discord_bot.nicknames)} users")
                print(f"   Discord Colors: {len(discord_bot.colors)} users")
                if objection_bot.reconnect_task:
                    print(f"   Reconnect Task: {objection_bot.reconnect_task.done()}")
            elif cmd_lower == "clear":
                # Clear the terminal
                import os
                os.system('cls' if os.name == 'nt' else 'clear')
                print("🤖 CourtBot Terminal - Type 'help' for commands")
            elif cmd_lower.startswith("ws ") or cmd_lower.startswith("websocket "):
                # Send raw WebSocket message
                prefix_len = 3 if cmd_lower.startswith("ws ") else 10  # "ws " or "websocket "
                raw_message = cmd[prefix_len:].strip()
                if raw_message:
                    if objection_bot.connected:
                        try:
                            await objection_bot.websocket.send(raw_message)
                            print(f"📡 Sent raw WebSocket message: {raw_message}")
                        except Exception as e:
                            print(f"❌ Failed to send WebSocket message: {e}")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a WebSocket message. Examples:")
                    print("   ws 42[\"get_room\"]")
                    print("   ws 42[\"message\",{\"characterId\":1,\"poseId\":1,\"text\":\"Hello\"}]")
                    print("   ws 2  (ping)")
                    print("   ws 3  (pong)")
                    print("   ws 40  (handshake ack)")
            elif cmd_lower.startswith("autoban "):
                # Autoban pattern management commands
                autoban_cmd = cmd[8:].strip()  # Remove "autoban " prefix
                autoban_parts = autoban_cmd.split(" ", 1)
                autoban_action = autoban_parts[0].lower() if autoban_parts else ""
                autoban_arg = autoban_parts[1] if len(autoban_parts) > 1 else ""
                
                if autoban_action == "add" and autoban_arg:
                    # Add a new autoban pattern
                    pattern = autoban_arg
                    # Validate regex pattern
                    try:
                        re.compile(pattern)
                        if pattern not in objection_bot.autoban_patterns:
                            objection_bot.autoban_patterns.append(pattern)
                            save_autobans(objection_bot.autoban_patterns)
                            print(f"✅ Added autoban pattern: '{pattern}'")
                            print(f"   Total patterns: {len(objection_bot.autoban_patterns)}")
                        else:
                            print(f"⚠️ Pattern '{pattern}' already exists in autoban list")
                    except re.error as e:
                        print(f"❌ Invalid regex pattern: {e}")
                        print("   Tip: For exact username match, just type the username")
                        print("   Tip: For prefix match, use: ^prefix")
                        print("   Tip: For suffix match, use: suffix$")
                        print("   Tip: For contains match, just type the substring")
                
                elif autoban_action == "remove" and autoban_arg:
                    # Remove an autoban pattern
                    pattern = autoban_arg
                    if pattern in objection_bot.autoban_patterns:
                        objection_bot.autoban_patterns.remove(pattern)
                        save_autobans(objection_bot.autoban_patterns)
                        print(f"✅ Removed autoban pattern: '{pattern}'")
                        print(f"   Remaining patterns: {len(objection_bot.autoban_patterns)}")
                    else:
                        print(f"❌ Pattern '{pattern}' not found in autoban list")
                        if objection_bot.autoban_patterns:
                            print("   Current patterns:")
                            for i, p in enumerate(objection_bot.autoban_patterns, 1):
                                print(f"      {i}. {p}")
                
                elif autoban_action == "list":
                    # List all autoban patterns
                    if objection_bot.autoban_patterns:
                        print(f"🚫 Autoban Patterns ({len(objection_bot.autoban_patterns)}):")
                        for i, pattern in enumerate(objection_bot.autoban_patterns, 1):
                            print(f"   {i}. {pattern}")
                    else:
                        print("🚫 No autoban patterns configured")
                        print("   Use 'autoban add <pattern>' to add one")
                
                elif autoban_action == "clear":
                    # Clear all autoban patterns
                    if objection_bot.autoban_patterns:
                        count = len(objection_bot.autoban_patterns)
                        objection_bot.autoban_patterns = []
                        save_autobans(objection_bot.autoban_patterns)
                        print(f"✅ Cleared all {count} autoban pattern(s)")
                    else:
                        print("⚠️ No autoban patterns to clear")
                
                elif autoban_action == "test" and autoban_arg:
                    # Test if a username would be banned
                    test_username = autoban_arg
                    matched = objection_bot.check_autoban(test_username)
                    if matched:
                        print(f"🚫 Username '{test_username}' WOULD be banned")
                        print(f"   Matched pattern: '{matched}'")
                    else:
                        print(f"✅ Username '{test_username}' would NOT be banned")
                        print(f"   No patterns matched ({len(objection_bot.autoban_patterns)} patterns checked)")
                
                else:
                    print("🚫 Autoban Commands:")
                    print("  autoban add <pattern>    - Add a regex pattern to autoban list")
                    print("  autoban remove <pattern> - Remove a pattern from autoban list")
                    print("  autoban list             - List all autoban patterns")
                    print("  autoban clear            - Clear all autoban patterns")
                    print("  autoban test <username>  - Test if a username would be banned")
                    print("\n📝 Pattern Examples:")
                    print("  autoban add tesya        - Ban exact username 'tesya' (case-insensitive)")
                    print("  autoban add ^tes         - Ban usernames starting with 'tes'")
                    print("  autoban add bot$         - Ban usernames ending with 'bot'")
                    print("  autoban add spam         - Ban usernames containing 'spam'")
                    print("  autoban add ^test.*bot$  - Ban usernames starting with 'test' and ending with 'bot'")
                    if not objection_bot.is_admin:
                        print("\n⚠️ Note: Bot must be admin to execute bans")
            
            elif cmd_lower == "bans":
                # Show current ban list
                if objection_bot.connected:
                    # Refresh room data to get latest ban list
                    print("🔄 Refreshing ban list...")
                    await objection_bot.refresh_room_data()
                    await asyncio.sleep(0.5)  # Wait for response
                    
                    if objection_bot.banned_users:
                        print(f"🚫 Banned Users ({len(objection_bot.banned_users)}):")
                        for i, ban in enumerate(objection_bot.banned_users, 1):
                            username = ban.get('username', 'Unknown')
                            user_id = ban.get('id', 'Unknown')
                            print(f"   {i}. {username} (ID: {user_id[:8]}...)")
                    else:
                        if objection_bot.is_admin:
                            print("🚫 No users are currently banned from this courtroom.")
                        else:
                            print("🚫 No ban data available. Bot must be admin to view ban list.")
                    
                    if not objection_bot.is_admin:
                        print("⚠️ Note: Ban list may not be accurate - bot is not admin")
                else:
                    print("❌ Not connected to objection.lol. Use 'reconnect' first.")
            
            elif cmd_lower.startswith("ban "):
                # Ban a user by username
                username_to_ban = cmd[4:].strip()  # Remove "ban " prefix
                if username_to_ban:
                    if objection_bot.connected:
                        if objection_bot.is_admin:
                            # Find user ID by username
                            user_id = objection_bot.get_user_id_by_username(username_to_ban)
                            if user_id:
                                print(f"🚫 Banning user '{username_to_ban}' (ID: {user_id[:8]}...)")
                                success = await objection_bot.create_ban(user_id)
                                if success:
                                    print(f"✅ Successfully banned '{username_to_ban}'")
                                else:
                                    print(f"❌ Failed to ban '{username_to_ban}'")
                            else:
                                print(f"❌ User '{username_to_ban}' not found in courtroom.")
                                print("   Note: User must be in the room to ban them.")
                                print("   Current users:")
                                for uid, uname in objection_bot.user_names.items():
                                    print(f"      - {uname}")
                        else:
                            print("❌ Bot is not admin. Cannot ban users.")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a username after 'ban'. Example: ban TrollUser")
            
            elif cmd_lower.startswith("unban "):
                # Unban a user by username
                username_to_unban = cmd[6:].strip()  # Remove "unban " prefix
                if username_to_unban:
                    if objection_bot.connected:
                        if objection_bot.is_admin:
                            # Find the user in the ban list
                            ban_to_remove = None
                            for ban in objection_bot.banned_users:
                                if ban.get('username', '').lower() == username_to_unban.lower():
                                    ban_to_remove = ban
                                    break
                            
                            if ban_to_remove:
                                print(f"🔓 Unbanning user '{ban_to_remove.get('username')}' (ID: {ban_to_remove.get('id', '')[:8]}...)")
                                success = await objection_bot.remove_ban(ban_to_remove.get('id'))
                                if success:
                                    print(f"✅ Successfully unbanned '{ban_to_remove.get('username')}'")
                                else:
                                    print(f"❌ Failed to unban '{username_to_unban}'")
                            else:
                                print(f"❌ User '{username_to_unban}' not found in ban list.")
                                if objection_bot.banned_users:
                                    print("   Currently banned users:")
                                    for ban in objection_bot.banned_users:
                                        print(f"      - {ban.get('username', 'Unknown')}")
                                else:
                                    print("   No users are currently banned.")
                        else:
                            print("❌ Bot is not admin. Cannot unban users.")
                    else:
                        print("❌ Not connected to objection.lol. Use 'reconnect' first.")
                else:
                    print("❌ Please provide a username after 'unban'. Example: unban TrollUser")
            
            elif cmd_lower == "help":
                print("Available commands:")
                print("\n🔗 Connection:")
                print("  connect/reconnect - Reconnect to objection.lol")
                print("  disconnect        - Disconnect from objection.lol")
                print("  status           - Show detailed bot status")
                print("  refresh          - Refresh room data")
                print("\n💬 Communication:")
                print("  say <message>    - Send a message to the courtroom")
                print("\n👥 User Management:")
                print("  users            - List all users in courtroom")
                print("  transfer <user>  - Transfer ownership to user (admin only)")
                print("\n🛡️ Admin Commands:")
                print("  title <text>     - Change room title (admin only)")
                print("  slowmode <0-60>  - Set slow mode seconds (admin only)")
                print("  textbox <style>  - Change textbox style (admin only)")
                print("  aspect <ratio>   - Change aspect ratio (admin only)")
                print("\n🚫 Ban Management:")
                print("  bans             - Show banned users list")
                print("  ban <username>   - Ban a user (admin only)")
                print("  unban <username> - Unban a user (admin only)")
                print("\n🤖 Autoban Commands:")
                print("  autoban add <pattern>    - Add autoban pattern (regex)")
                print("  autoban remove <pattern> - Remove autoban pattern")
                print("  autoban list             - List all autoban patterns")
                print("  autoban clear            - Clear all patterns")
                print("  autoban test <username>  - Test if username would be banned")
                print("\n📡 Advanced:")
                print("  ws <message>     - Send raw WebSocket message")
                print("  websocket <msg>  - Send raw WebSocket message (alias)")
                print("\n🛠️ Utility:")
                print("  config           - Show current configuration")
                print("  debug            - Show debug information")
                print("  clear            - Clear terminal screen")
                print("  help             - Show this help message")
                print("  quit/exit/stop   - Shutdown and exit")
            else:
                print(f"Unknown command: {cmd_lower}. Type 'help' for available commands.")
        except (EOFError, KeyboardInterrupt):
            print("🛑 Terminal closed. Shutting down bots...")
            await shutdown(objection_bot, discord_bot)
async def main():
    global VERBOSE_MODE
    
    # Load configuration
    config = Config()
    
    # Set verbose mode from config
    VERBOSE_MODE = config.get('settings', 'verbose')
    if VERBOSE_MODE is None:
        VERBOSE_MODE = True  # Default to verbose if not set
    
    # Validate configuration
    errors = config.validate()
    if errors:
        print("❌ Configuration errors found:")
        for error in errors:
            print(f"   - {error}")
        print("\nPlease fix the configuration file and restart the bot.")
        return
    
    log_verbose("📋 Configuration loaded successfully!")
    log_verbose(f"🏠 Room: {config.get('objection', 'room_id')}")
    log_verbose(f"🤖 Username: {config.get('objection', 'bot_username')}")
    log_verbose(f"🎭 Mode: {config.get('settings', 'mode')}")
    
    if not VERBOSE_MODE:
        print("💬 Simple logging mode enabled (set VERBOSE=true for detailed logs)")
    else:
        print("📝 Verbose logging mode enabled")
    # Create bots
    objection_bot = ObjectionBot(config)
    discord_bot = DiscordCourtBot(objection_bot, config)
    # Link them together
    objection_bot.set_discord_bot(discord_bot)
    log_verbose("🔌 Attempting to connect to objection.lol...")
    objection_success = await objection_bot.connect_to_room()
    if objection_success:
        log_verbose("✅ Objection.lol connection successful!")
        # Start Discord bot in background
        log_verbose("🔌 Starting Discord bot...")
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