#!/usr/bin/env python3
"""
Simple command cleaner for CourtBot Discord slash commands.
"""
print("🧹 Starting CourtBot Command Cleaner")

import asyncio
print("✓ Asyncio imported")

try:
    import discord
    from discord import app_commands
    print("✓ Discord.py imported")
except ImportError as e:
    print(f"❌ Failed to import discord.py: {e}")
    exit(1)

import os
import json
print("✓ Standard libraries imported")

class CommandCleaner(discord.Client):
    def __init__(self, guild_id):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.guild_id = guild_id
        self.tree = app_commands.CommandTree(self)
        print(f"✓ Bot initialized for guild: {guild_id}")
    
    async def setup_hook(self):
        """Called when the bot is starting up"""
        print("🔗 Bot connected, starting command cleanup...")
        
        # Clear guild commands
        guild = discord.Object(id=self.guild_id)
        self.tree.clear_commands(guild=guild)
        await self.tree.sync(guild=guild)
        print("✅ Guild commands cleared!")
        
        # Clear global commands
        self.tree.clear_commands(guild=None)
        await self.tree.sync(guild=None)
        print("✅ Global commands cleared!")
        
        print("🎉 All slash commands have been cleared!")
        await self.close()

async def main():
    print("📋 Loading configuration...")
    
    # Get values from environment
    token = os.getenv('DISCORD_TOKEN')
    guild_id = os.getenv('DISCORD_GUILD_ID')
    
    if not token:
        print("❌ DISCORD_TOKEN not found in environment")
        return
    
    if not guild_id:
        print("❌ DISCORD_GUILD_ID not found in environment")
        return
    
    try:
        guild_id = int(guild_id)
    except ValueError:
        print("❌ DISCORD_GUILD_ID must be a number")
        return
    
    print(f"🎯 Target guild: {guild_id}")
    print(f"🔐 Token: {token[:20]}...")
    
    # Create and run the cleaner bot
    cleaner = CommandCleaner(guild_id)
    
    try:
        print("🚀 Starting bot...")
        await cleaner.start(token)
    except discord.LoginFailure:
        print("❌ Failed to log in with the provided token")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("▶️ Starting script...")
    try:
        asyncio.run(main())
        print("✅ Script completed!")
    except Exception as e:
        print(f"❌ Script failed: {e}")
        import traceback
        traceback.print_exc()
