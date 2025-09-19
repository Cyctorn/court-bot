#!/usr/bin/env python3
"""
Test script to explore objection.lol API endpoints for music data
"""

import asyncio
import aiohttp
import json
import sys

async def test_api_endpoint(session, url, description):
    """Test a single API endpoint and return the response"""
    print(f"\n{'='*60}")
    print(f"Testing: {description}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    try:
        async with session.get(url) as response:
            print(f"Status Code: {response.status}")
            print(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            
            if response.status == 200:
                try:
                    data = await response.json()
                    print(f"Response Type: {type(data)}")
                    
                    if isinstance(data, list):
                        print(f"Array Length: {len(data)}")
                        if len(data) > 0:
                            print(f"First Item: {json.dumps(data[0], indent=2)}")
                            if len(data) > 1:
                                print(f"Second Item: {json.dumps(data[1], indent=2)}")
                    elif isinstance(data, dict):
                        print(f"Object Keys: {list(data.keys())}")
                        print(f"Full Response: {json.dumps(data, indent=2)}")
                    else:
                        print(f"Response: {data}")
                        
                    return data
                except json.JSONDecodeError as e:
                    text_content = await response.text()
                    print(f"JSON Decode Error: {e}")
                    print(f"Raw Response: {text_content[:500]}...")
                    return None
            else:
                text_content = await response.text()
                print(f"Error Response: {text_content}")
                return None
                
    except Exception as e:
        print(f"Request Error: {e}")
        return None

async def test_specific_music_id(session, music_id):
    """Test fetching a specific music ID"""
    endpoints_to_try = [
        f"https://objection.lol/api/assets/music/{music_id}",
        f"https://objection.lol/api/music/{music_id}",
        f"https://objection.lol/api/assets/music/get/{music_id}",
        f"https://objection.lol/api/assets/music/getById/{music_id}"
    ]
    
    print(f"\n{'='*60}")
    print(f"Testing specific music ID: {music_id}")
    print(f"{'='*60}")
    
    for endpoint in endpoints_to_try:
        await test_api_endpoint(session, endpoint, f"Music ID {music_id}")

async def main():
    """Main function to test all API endpoints"""
    print("🎵 Testing objection.lol Music API Endpoints")
    print("=" * 60)
    
    # Test endpoints discovered from the website
    endpoints = [
        ("https://objection.lol/api/assets/sound/getMine", "Sound Assets (User's Sounds)"),
        ("https://objection.lol/api/assets/background/getAll", "Background Assets (All Backgrounds)"),
        ("https://objection.lol/api/assets/music/getAll", "Music Assets (All Music)"),
        ("https://objection.lol/api/assets/music/getMine", "Music Assets (User's Music)"),
    ]
    
    async with aiohttp.ClientSession() as session:
        # Test each endpoint
        music_data = None
        for url, description in endpoints:
            result = await test_api_endpoint(session, url, description)
            if "music" in url.lower() and result:
                music_data = result
        
        # If we got music data, try to test specific IDs
        if music_data and isinstance(music_data, list) and len(music_data) > 0:
            print(f"\n{'='*60}")
            print("Found music data! Testing specific music IDs...")
            
            # Extract some music IDs to test
            test_ids = []
            for item in music_data[:3]:  # Test first 3 items
                if isinstance(item, dict):
                    # Look for common ID field names
                    for id_field in ['id', '_id', 'musicId', 'uuid', 'assetId']:
                        if id_field in item:
                            test_ids.append(str(item[id_field]))
                            break
            
            # Test specific music IDs
            for music_id in test_ids:
                await test_specific_music_id(session, music_id)
        
        # Also test with a known BGM ID from the conversation (121893)
        await test_specific_music_id(session, "121893")

if __name__ == "__main__":
    # Handle Windows event loop policy if needed
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    asyncio.run(main())
