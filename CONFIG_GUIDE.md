# Config Guide

## Quick Setup for Windows Users

### Prerequisites
1. Download this project: Click the green "Code" button on GitHub → "Download ZIP" → Extract to a folder

### Normal Setup

#### 1. Create your environment file
- In the extracted folder, find `.env.example`
- Change it to '.env'
- Edit it with your text editor of choice
- Replace `your_discord_bot_token_here` with your actual Discord bot token
- Replace the channel and guild IDs with your actual Discord IDs
- Save and close

#### 2. Create your configuration file
- In the same folder, find `config.example.json`
- Change to `config.json`
- Edit the objection.lol room settings (see "Configuration Values" section below)
- Save and close

#### 3. Run the bot
- Follow the deployment method of your choice (see sections below for Docker or Python setup)

#### 4. Check if it's working
- Your Discord channel should show the bot came online & it should also join the courtroom

### Configuration Values You Need to Change

#### In `.env` file:
```env
DISCORD_TOKEN=your_actual_discord_bot_token_here
DISCORD_CHANNEL_ID=1234567890123456789  ← Change to your Discord channel ID
DISCORD_GUILD_ID=1234567890123456789    ← Change to your Discord server ID
```

#### In `config.json` file:
```json
{
  "objection": {
    "room_id": "your_room_id_here",     ← Change this to your objection.lol room
    "bot_username": "YourBotName"       ← Change this to what you want the bot called
  }
}
```

### How to Get the IDs You Need

#### Discord Channel and Server IDs:
1. In Discord, go to **User Settings** (gear icon) → **Advanced** → Turn on **"Developer Mode"**
2. **Right-click your server name** → **"Copy Server ID"** (this is your guild_id)
3. **Right-click your channel name** → **"Copy Channel ID"** (this is your channel_id)

#### Discord Bot Token:
1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a **"New Application"** → Give it a name
3. Go to **"Bot"** section → **"Add Bot"**
4. Under **"Token"**, click **"Copy"** (this goes in your `.env` file as DISCORD_TOKEN)
5. Invite the bot to your server using the **"OAuth2"** section

## Configuration Files

### 1. `config.json` - Non-sensitive Configuration
Contains all non-sensitive settings that can be safely committed to version control:
- Objection.lol room settings
- Character and pose IDs
- Bot behavior settings

### 2. `.env` - Sensitive and Deployment-specific Data
Contains sensitive information and deployment-specific settings:
- Discord bot token (sensitive)
- Discord channel and guild IDs (deployment-specific)

## Running the Bot

### Option 1: With Docker (Recommended)
1. **Install Docker Desktop**: Download from [docker.com](https://www.docker.com/products/docker-desktop/) and install
2. **Restart your computer** after Docker installation
3. **Right-click** in the folder while holding **Shift** → **"Open PowerShell window here"**
4. Type: `docker-compose up -d`
5. Check logs with: `docker logs courtbot`

### Option 2: With Python
1. **Install Python**: Download from [python.org](https://www.python.org/downloads/) (make sure to check "Add to PATH")
2. **Right-click** in the folder while holding **Shift** → **"Open PowerShell window here"**
3. Type: `pip install -r requirements.txt`
4. Type: `python courtbot.py`

## For Advanced Users

### For Development:
1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your Discord bot token:
   ```
   DISCORD_TOKEN=your_actual_bot_token_here
   DISCORD_CHANNEL_ID=1234567890123456789
   DISCORD_GUILD_ID=1234567890123456789
   ```
3. Copy `config.example.json` to `config.json`:
   ```bash
   cp config.example.json config.json
   ```
4. Edit `config.json` with your specific settings:
   - Objection.lol room ID
   - Character and pose IDs
   - Other bot settings
5. Run: `docker-compose up -d`

### For Production:
Set the `DISCORD_TOKEN`, `DISCORD_CHANNEL_ID`, and `DISCORD_GUILD_ID` environment variables in your deployment system and ensure `config.json` contains your production settings.

## Configuration Priority
1. **Environment Variables** (Discord token, channel ID, guild ID)
2. **config.json** file (all other settings)
3. **Default values** (if config.json doesn't exist)

## What Goes Where?

### In `.env` (Sensitive & Deployment-specific):
- `DISCORD_TOKEN` - Your Discord bot token
- `DISCORD_CHANNEL_ID` - Discord channel ID for the bridge
- `DISCORD_GUILD_ID` - Discord server (guild) ID

### In `config.json` (Non-sensitive):
- Objection.lol room ID and bot username
- Character and pose IDs
- Message limits and behavior settings

This approach follows security best practices by keeping only truly sensitive data in environment variables while maintaining ease of configuration management for everything else.
