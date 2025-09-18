import os
print("🧹 CourtBot Command Cleaner")
print("Testing environment variables...")
print(f"DISCORD_TOKEN: {os.getenv('DISCORD_TOKEN')}")
print(f"DISCORD_GUILD_ID: {os.getenv('DISCORD_GUILD_ID')}")
print("Done.")
