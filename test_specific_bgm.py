#!/usr/bin/env python3
"""
Quick test of a few more BGM IDs to verify the API works consistently
"""

import asyncio
import aiohttp
import json
import sys

async def test_bgm_id(session, bgm_id):
    """Test a specific BGM ID"""
    api_url = f"https://objection.lol/api/assets/music/{bgm_id}"
    
    try:
        async with session.get(api_url) as response:
            if response.status == 200:
                data = await response.json()
                print(f"✅ BGM {bgm_id}: '{data.get('name', 'Unknown')}' -> {data.get('url', 'No URL')}")
                print(f"   Volume: {data.get('volume', 'Unknown')}%")
                return data
            else:
                print(f"❌ BGM {bgm_id}: Status {response.status}")
                return None
    except Exception as e:
        print(f"❌ BGM {bgm_id}: Error - {e}")
        return None

async def main():
    # Test a few different BGM IDs
    test_ids = ["121893", "100000", "1", "999999", "123456"]
    
    print("🎵 Testing multiple BGM IDs...")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        for bgm_id in test_ids:
            await test_bgm_id(session, bgm_id)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
