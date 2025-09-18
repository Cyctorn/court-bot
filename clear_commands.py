#!/usr/bin/env python3
"""
Command cleaner script for CourtBot Discord slash commands.
This script will clear all registered slash commands from Discord.
"""

import asyncio
import discord
from discord import app_commands
import os
import json

class Config:
    def __init__(self, config_file='config.json'):
        self.config_file = config_file
        self.load_config()
    
    def load_config(self):
        """Load configuration from JSON file and override with environment variables"""
        if not os.path.exists(self.config_file):
            print(f"❌ Config file {self.config_file} not found!")
            return
        try:
            with open(self.config_file, 'r') as f:
                self.data = json.load(f)
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            return
        
        # Override with environment variables if they exist
        self.apply_env_overrides()
    
    def apply_env_overrides(self):
        """Apply environment variable overrides to configuration"""
        # Initialize discord section if it doesn't exist
        if 'discord' not in self.data:
            self.data['discord'] = {}
        
        # Discord settings
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
    
    def get(self, section, key=None):
        """Get configuration value"""
        if key is None:
            return self.data.get(section, {})
        return self.data.get(section, {}).get(key)

class CommandCleaner(discord.Client):
    def __init__(self, guild_id):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Clear all commands by syncing an empty tree
        guild = discord.Object(id=self.guild_id)
        
        print(f"🧹 Clearing guild commands for guild {self.guild_id}...")
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        print("✅ Guild commands cleared!")
        
        print("🧹 Clearing global commands...")
        self.tree.clear_commands(guild=None)
        await self.tree.sync(guild=None)
        print("✅ Global commands cleared!")
        
        print("🎉 All slash commands have been cleared!")
        await self.close()

async def main():
    print("🧹 CourtBot Command Cleaner")
    print("This will remove all registered Discord slash commands.")
    
    # Load configuration
    config = Config()
    
    # Check if we have required Discord settings
    token = config.get('discord', 'token')
    guild_id = config.get('discord', 'guild_id')
    
    if not token:
        print("❌ Discord token not found in config or environment variables")
        print("Please set DISCORD_TOKEN environment variable or add it to config.json")
        return
    
    if not guild_id:
        print("❌ Discord guild ID not found in config or environment variables")
        print("Please set DISCORD_GUILD_ID environment variable or add it to config.json")
        return
    
    print(f"🎯 Target guild: {guild_id}")
    
    # Create and run the cleaner bot
    cleaner = CommandCleaner(guild_id)
    
    try:
        await cleaner.start(token)
    except discord.LoginFailure:
        print("❌ Failed to log in with the provided token")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
