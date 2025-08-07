# Environment Variables Configuration

CourtBot supports configuration through environment variables, which override the values in `config.json`. This is particularly useful for Docker deployments and keeping sensitive information secure.

## Supported Environment Variables

### Discord Configuration
- `DISCORD_TOKEN` - Your Discord bot token
- `DISCORD_CHANNEL_ID` - Discord channel ID for the bridge
- `DISCORD_GUILD_ID` - Discord guild (server) ID

### Objection.lol Configuration
- `OBJECTION_ROOM_ID` - Room ID on objection.lol
- `OBJECTION_BOT_USERNAME` - Username for the bot in objection.lol

### Character Settings
- `OBJECTION_CHARACTER_ID` - Character ID for objection.lol
- `OBJECTION_POSE_ID` - Pose ID for objection.lol

### Bot Settings
- `MAX_MESSAGES` - Maximum number of messages to keep in Discord (default: 50)
- `DELETE_COMMANDS` - Whether to delete command messages (true/false)
- `SHOW_JOIN_LEAVE` - Whether to show join/leave notifications (true/false)

## Usage

### Option 1: .env file (Recommended)
1. Copy `.env.example` to `.env`
2. Edit `.env` with your values
3. Run with Docker Compose: `docker-compose up -d`

### Option 2: Direct environment variables
Set environment variables directly in your shell or Docker Compose file.

### Option 3: Hybrid approach
Use `config.json` for default values and environment variables for sensitive or deployment-specific settings.

## Priority Order
1. Environment variables (highest priority)
2. config.json file
3. Default values (if config.json doesn't exist)

## Example .env file
```
DISCORD_TOKEN=your_discord_bot_token_here
DISCORD_CHANNEL_ID=1234567890123456789
DISCORD_GUILD_ID=1234567890123456789
OBJECTION_ROOM_ID=your_room_id
OBJECTION_BOT_USERNAME=CourtBot
```

## Security Notes
- Never commit `.env` files to version control
- Use different `.env` files for different environments (development, production)
- Keep your Discord token secure and rotate it if compromised
