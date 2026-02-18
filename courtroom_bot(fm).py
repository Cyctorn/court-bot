import asyncio
import json
import random
import websockets
import requests
import os
import re
import time
from typing import Dict, List, Optional
import config
from emotion_classifier import EmotionClassifier
from popular_thread_fetcher import PopularThreadFetcher

class CourtroomBot:
    def __init__(self, courtroom_id: str, shapes_api_key: str, shape_username: str = None):
        self.courtroom_id = courtroom_id
        self.websocket = None
        self.shapes_api_key = shapes_api_key
        self.shapes_base_url = config.API_URL.replace('/chat/completions', '')  # Remove endpoint to get base URL
        self.shape_username = shape_username or config.SHAPESINC_SHAPE_USERNAME
        self.users = {}  # Store user info for name mentions
        self.message_count = 0
        self.response_threshold = config.RESPONSE_THRESHOLD
        self.connected = False
        self.ping_interval = config.PING_INTERVAL
        self.ping_timeout = config.PING_TIMEOUT
        self.last_ping_time = 0
        self.my_user_id = None  # Track bot's own user ID
        self.recent_messages = []  # Store recent messages for context
        self.max_context_messages = 15  # Number of recent messages to keep for idle analysis
        self.max_ai_context_messages = 5  # Number of messages to send to AI for responses
        self.emotion_classifier = EmotionClassifier()  # Initialize emotion classifier
        
        # Pairing system
        self.current_pair_id = None  # Current pair ID if paired
        self.paired_with_user_id = None  # User ID of current pair partner
        self.pair_status = "solo"  # "solo", "paired", "pending"
        
        # Smart conversation system
        self.last_message_time = None  # Track when last message was sent by anyone
        self.last_user_message_time = None  # Track when last user message was sent (not bot)
        self.conversation_participants = set()  # Track active conversation participants
        self.current_topic_keywords = []  # Track current conversation topic
        self.bot_mentioned_recently = False  # Track if bot was mentioned recently
        self.last_idle_message_time = None  # Track when we last sent an idle message
        self.idle_message_count = 0  # Track how many idle messages we've sent in current silence
        self.idle_task = None  # Task for scheduling idle messages
        
        # Join/Leave reaction system
        self.recent_departures = {}  # Track recent user departures {user_id: timestamp}
        self.last_join_leave_reaction = None  # Track when we last reacted to join/leave
        
        # BGM roulette system
        self.last_bgm_command = None  # Track when BGM command was last used
        
        # Popular thread fetcher system
        self.thread_fetcher = PopularThreadFetcher()
        self.last_popular_command = None  # Track when !popular command was last used
        self.last_random_command = None  # Track when !random command was last used
        
        # Busy mode system (for high-activity periods)
        self.message_timestamps = []  # Track recent message times
        self.active_users_in_window = set()  # Track active users in current time window
        self.is_busy_mode = False  # Whether we're currently in busy mode
        self.busy_mode_start_time = None  # When busy mode started
        self.last_busy_check = None  # Last time we checked if we should be in busy mode
        
        # Conversation detection system
        self.recent_exchanges = []  # Track recent user-to-user exchanges
        self.max_exchange_tracking = 10  # Number of recent exchanges to track
        
    async def connect(self):
        """Connect to the courtroom WebSocket"""
        # Use the correct WebSocket URL with required parameters
        uri = f"{config.WEBSOCKET_BASE_URL}?roomId={self.courtroom_id}&username={config.BOT_USERNAME}&password=&{config.WEBSOCKET_PARAMS}"
        try:
            self.websocket = await websockets.connect(uri)
            print(f"WebSocket connection established")
            
            # Wait for initial handshake message
            print("Waiting for server handshake...")
            initial_message = await self.websocket.recv()
            if config.SHOW_RAW_MESSAGES:
                print(f"Received: {initial_message}")
            
            if initial_message.startswith('0'):
                # Parse ping interval and timeout
                try:
                    handshake_data = json.loads(initial_message[1:])
                    self.ping_interval = handshake_data.get('pingInterval', config.PING_INTERVAL)
                    self.ping_timeout = handshake_data.get('pingTimeout', config.PING_TIMEOUT)
                    print(f"Ping interval: {self.ping_interval}ms, Timeout: {self.ping_timeout}ms")
                except:
                    print("Could not parse handshake data, using defaults")
                
                # Send handshake acknowledgment
                print("Sending handshake acknowledgment...")
                await self.websocket.send("40")
                
                # Wait for server response
                response = await self.websocket.recv()
                if config.SHOW_RAW_MESSAGES:
                    print(f"Server response: {response}")
                
                if response.startswith('40'):
                    print("Handshake completed successfully")
                    
                    # Send "me" message to get user info
                    print("Sending 'me' message...")
                    await self.websocket.send('42["me"]')
                    
                    # Send "get_room" message to join/get room info
                    print("Sending 'get_room' message...")
                    await self.websocket.send('42["get_room"]')
                    
                    return True
                else:
                    print(f"Unexpected response after handshake: {response}")
                    return False
            else:
                print(f"Unexpected initial message: {initial_message}")
                return False
            
        except Exception as e:
            print(f"Failed to connect: {e}")
            return False
    
    async def send_message(self, text: str, character_id: int = None, pose_id: int = None, auto_emotion: bool = True):
        """Send a message to the courtroom with automatic emotion detection"""
        if not self.websocket or not self.connected:
            return
            
        # Use config defaults if not specified
        character_id = character_id or config.DEFAULT_CHARACTER_ID
        
        # Automatically determine pose_id based on message emotion if not specified
        emotion_result = None
        if pose_id is None and auto_emotion and config.ENABLE_AUTO_EMOTION:
            emotion_result = self.emotion_classifier.classify_emotion(text)
            pose_id = emotion_result.pose_id
            
            if config.EMOTION_DEBUG:
                print(f"Auto-detected emotion: {emotion_result.emotion} (confidence: {emotion_result.score:.2f})")
        elif pose_id is None:
            pose_id = config.DEFAULT_POSE_ID
        
        # ALWAYS check for angry emotion to apply red color, regardless of pose settings
        if not emotion_result:  # Only classify if we haven't already
            emotion_result = self.emotion_classifier.classify_emotion(text)
        
        # Add red color for angry messages (regardless of auto_emotion or pose_id settings)
        if emotion_result and emotion_result.emotion == "angry":
            text = self.add_angry_color(text)
            if config.EMOTION_DEBUG:
                print(f"Added red color for angry message: {text}")
        
        # Add fast typing speed command at the beginning
        if not text.startswith("[#ts"):
            text = f"[#ts5]{text}"
        
        # Truncate message if too long
        if len(text) > config.MAX_MESSAGE_LENGTH:
            text = text[:config.MAX_MESSAGE_LENGTH-3] + "..."
            
        message_data = {
            "characterId": character_id,
            "poseId": pose_id,
            "text": text
        }
        
        message = f'42["message",{json.dumps(message_data)}]'
        await self.websocket.send(message)
        print(f"Sent: {text} [Pose ID: {pose_id}]")
        
        # Update last message time when bot sends a message
        self.last_message_time = time.time()
    
    async def send_ping(self):
        """Send ping message to keep connection alive"""
        if self.websocket and self.connected:
            await self.websocket.send("2")
            self.last_ping_time = asyncio.get_event_loop().time()
            print("Sent ping")
    
    async def get_ai_response(self, message: str, username: str = None, include_context: bool = False) -> Optional[str]:
        """Get response from Shapes API using direct HTTP request"""
        try:
            # Build context for the AI using config values
            context = config.AI_CONTEXT_PREFIX.format(bot_name=config.BOT_NAME)
            
            # Add recent conversation context for non-name-mentioned responses
            if include_context and username:
                # Determine if this is a name-mentioned response
                is_name_mentioned = (config.ALWAYS_RESPOND_TO_NAME and 
                                   config.BOT_NAME.lower() in message.lower())
                recent_context = self.get_context_messages(username, message, is_name_mentioned)
                if recent_context:
                    context += recent_context
                
                # Add conversation analysis context for smart interjections
                if config.ENABLE_SMART_INTERJECTION and username in self.conversation_participants:
                    context_score = self.analyze_conversation_context(message, username)
                    if context_score >= config.CONVERSATION_ANALYSIS_THRESHOLD:
                        context += "You are naturally joining this ongoing conversation. "
            
            if username:
                context += f"A user named '{username}' just said: \"{message}\""
            else:
                context += f"Someone said: {message}"
            
            context += config.AI_CONTEXT_SUFFIX
            
            # Add specific anti-summarizing instruction for random responses
            if include_context and not (config.ALWAYS_RESPOND_TO_NAME and 
                                      config.BOT_NAME.lower() in message.lower()):
                context += " Do not comment on or summarize the conversation. Just respond directly to what was said."
            
            # Prepare the request payload
            payload = {
                "model": f"shapesinc/{self.shape_username}",
                "messages": [
                    {"role": "user", "content": context}
                ]
            }
            
            headers = {
                "Authorization": f"Bearer {self.shapes_api_key}",
                "Content-Type": "application/json"
            }
            
            print(f"Calling Shapes API with model: shapesinc/{self.shape_username}")
            print(f"API Key (first 10 chars): {self.shapes_api_key[:10]}...")
            print(f"API URL: {config.API_URL}")
            
            # Make the HTTP request to Shapes API
            response = requests.post(
                config.API_URL,
                json=payload,
                headers=headers,
                timeout=config.CONNECTION_TIMEOUT
            )
            
            if response.status_code == 200:
                response_data = response.json()
                ai_response = response_data["choices"][0]["message"]["content"].strip()
                
                # Remove emojis if configured
                if config.REMOVE_EMOJIS:
                    ai_response = self.remove_emojis(ai_response)
                
                # Truncate if too long
                if len(ai_response) > config.MAX_AI_RESPONSE_LENGTH:
                    ai_response = ai_response[:config.MAX_AI_RESPONSE_LENGTH-3] + "..."
                    
                return ai_response
            else:
                print(f"Shapes API error: {response.status_code}")
                print(f"Error details: {response.text}")
                
                if response.status_code == 401:
                    print("❌ INVALID API KEY!")
                    print("Please check your API key at: https://shapes.inc/developer")
                    print("Make sure you're using the correct key for the 'maclunky' shape")
                    print("Also check that your API key is set in config.py")
                elif response.status_code == 404:
                    print("❌ SHAPE NOT FOUND!")
                    print(f"Shape 'maclunky' not found. Check if the username is correct")
                elif response.status_code == 429:
                    print("❌ RATE LIMITED!")
                    print("You've hit the API rate limit. Wait a bit and try again")
                else:
                    print(f"❌ UNKNOWN ERROR: {response.status_code}")
                
                return None
                
        except Exception as e:
            print(f"Error getting AI response: {e}")
            return None
    
    def remove_emojis(self, text: str) -> str:
        """Remove emojis and other Unicode symbols from text"""
        # Pattern to match emojis and other Unicode symbols
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"  # Enclosed characters
            "]+", 
            flags=re.UNICODE
        )
        
        # Remove emojis
        cleaned_text = emoji_pattern.sub('', text)
        
        # Clean up any double spaces or trailing spaces
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        
        return cleaned_text
    
    def strip_color_codes(self, text: str) -> str:
        """Remove objection.lol color codes from text"""
        # Remove color codes like [#ts15], [#/r], [#/c123456], [/#]
        # Pattern matches: [#...], [#/...], [/#]
        color_pattern = re.compile(r'\[#[^]]*\]|\[/#\]')
        cleaned_text = color_pattern.sub('', text)
        # Clean up any multiple spaces left by color code removal
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
        return cleaned_text
    
    def add_angry_color(self, text: str) -> str:
        """Add red color formatting for angry messages"""
        return f"[#/r]{text}[/#]"
    
    def update_busy_mode_status(self, username: str = None):
        """Update busy mode status based on recent chat activity"""
        if not config.ENABLE_BUSY_MODE:
            return
        
        current_time = time.time()
        
        # Add current message timestamp
        self.message_timestamps.append(current_time)
        if username:
            self.active_users_in_window.add(username)
        
        # Remove old timestamps outside the time window
        cutoff_time = current_time - config.BUSY_MODE_TIME_WINDOW
        self.message_timestamps = [ts for ts in self.message_timestamps if ts > cutoff_time]
        
        # Clean up active users set periodically
        if not self.last_busy_check or current_time - self.last_busy_check > 30:
            self.active_users_in_window.clear()
            self.last_busy_check = current_time
        
        # Calculate messages per minute
        messages_in_window = len(self.message_timestamps)
        messages_per_minute = (messages_in_window / config.BUSY_MODE_TIME_WINDOW) * 60
        
        # Count active users (only those who sent messages recently)
        active_user_count = len(self.active_users_in_window)
        
        # Determine if we should be in busy mode
        should_be_busy = (
            messages_per_minute >= config.BUSY_MODE_MESSAGE_THRESHOLD and
            active_user_count >= config.BUSY_MODE_MIN_USERS
        )
        
        # Update busy mode status
        if should_be_busy and not self.is_busy_mode:
            self.is_busy_mode = True
            self.busy_mode_start_time = current_time
            print(f"🚦 BUSY MODE ACTIVATED - {messages_per_minute:.1f} msgs/min, {active_user_count} active users")
        elif not should_be_busy and self.is_busy_mode:
            # Check if we should exit busy mode (with cooldown)
            time_in_busy_mode = current_time - (self.busy_mode_start_time or current_time)
            if time_in_busy_mode >= config.BUSY_MODE_COOLDOWN:
                self.is_busy_mode = False
                self.busy_mode_start_time = None
                print(f"🚦 BUSY MODE DEACTIVATED - {messages_per_minute:.1f} msgs/min, {active_user_count} active users")
        
        # Debug info
        if config.EMOTION_DEBUG and username:
            status = "BUSY" if self.is_busy_mode else "NORMAL"
            print(f"[{status}] Messages/min: {messages_per_minute:.1f}, Active users: {active_user_count}")
    
    def analyze_conversation_context(self, message: str, username: str) -> float:
        """Analyze message context to determine if bot should interject"""
        if not config.ENABLE_SMART_INTERJECTION:
            return 0.0
        
        score = 0.0
        message_lower = message.lower()
        
        # Check for conversational cues that suggest talking to the bot
        conversational_cues = [
            r'\bwhat do you think\b', r'\bdo you\b', r'\bhave you\b', r'\bcan you\b',
            r'\bwould you\b', r'\bdid you\b', r'\byour\b', r'\byou\b',
            r'\bagree\b', r'\bopinion\b', r'\bthoughts\b'
        ]
        
        for cue in conversational_cues:
            if re.search(cue, message_lower):
                score += config.CONVERSATIONAL_KEYWORDS_WEIGHT
                break
        
        # Check for questions (higher weight)
        if re.search(r'\?', message) or re.search(r'\b(what|how|why|when|where|who)\b', message_lower):
            score += config.QUESTION_DETECTION_WEIGHT
        
        # Check if this continues a topic the bot was involved in
        if self.bot_mentioned_recently and len(self.recent_messages) > 0:
            # Look for topic continuation
            last_messages = self.recent_messages[-3:]  # Last 3 messages
            topic_words = set()
            for msg in last_messages:
                topic_words.update(msg['message'].lower().split())
            
            current_words = set(message_lower.split())
            overlap = len(topic_words.intersection(current_words))
            if overlap > 0:
                score += config.TOPIC_CONTINUATION_WEIGHT * min(overlap / 5, 1.0)
        
        # Check if user was recently talking to bot
        if username in self.conversation_participants:
            score += 0.3
        
        # Boost score if multiple people are in conversation
        if len(self.conversation_participants) >= 2:
            score += 0.2
        
        return min(score, 1.0)
    
    def detect_private_conversation(self, message: str, username: str) -> bool:
        """Detect if users are having a private conversation that bot shouldn't interrupt"""
        if not config.ENABLE_PRIVATE_CONVERSATION_DETECTION:
            return False
        
        # Get list of usernames in the room
        usernames = list(self.users.values())
        usernames = [name.lower() for name in usernames if name != config.BOT_USERNAME and name != config.BOT_NAME]
        
        # Check if message directly addresses someone by name
        message_lower = message.lower()
        directly_addressed = False
        addressed_user = None
        
        for user in usernames:
            if user in message_lower:
                # Check if it's a direct address (name at start, or after common address patterns)
                patterns = [
                    f"^{re.escape(user)}[,:!?]",  # "username:" or "username,"
                    f"@{re.escape(user)}",  # "@username"
                    f"hey {re.escape(user)}",  # "hey username"
                    f"hi {re.escape(user)}",   # "hi username"
                    f"{re.escape(user)} what",  # "username what..."
                    f"{re.escape(user)} how",   # "username how..."
                    f"{re.escape(user)} did",   # "username did..."
                    f"{re.escape(user)} can",   # "username can..."
                ]
                
                for pattern in patterns:
                    if re.search(pattern, message_lower):
                        directly_addressed = True
                        addressed_user = user
                        break
                        
                if directly_addressed:
                    break
        
        if directly_addressed:
            print(f"  → Detected direct address to {addressed_user}")
            return True
        
        # Check for ongoing conversation patterns between specific users
        private_conversation_score = self.analyze_conversation_patterns(username, message)
        
        if private_conversation_score >= config.PRIVATE_CONVERSATION_THRESHOLD:
            print(f"  → Detected private conversation pattern (score: {private_conversation_score:.2f})")
            return True
        
        return False
    
    def analyze_conversation_patterns(self, current_username: str, current_message: str) -> float:
        """Analyze recent message patterns to detect private conversations"""
        if len(self.recent_messages) < 3:  # Need at least 3 messages to detect patterns
            return 0.0
        
        current_time = time.time()
        recent_window_messages = []
        
        # Get messages from the recent conversation window
        for msg in reversed(self.recent_messages):
            if current_time - msg.get('timestamp', 0) <= config.RECENT_CONVERSATION_WINDOW:
                recent_window_messages.insert(0, msg)
            else:
                break
        
        if len(recent_window_messages) < 3:
            return 0.0
        
        # Analyze conversation patterns
        score = 0.0
        
        # Check for back-and-forth between just 2 users
        participants = set()
        for msg in recent_window_messages[-5:]:  # Last 5 messages
            participants.add(msg['username'])
        
        if len(participants) == 2 and current_username in participants:
            # Only 2 people talking recently
            score += 0.4
            print(f"    → Two-person conversation detected: {participants}")
        
        # Check for rapid back-and-forth (alternating speakers)
        if len(recent_window_messages) >= 4:
            alternating_count = 0
            for i in range(len(recent_window_messages) - 1):
                if (recent_window_messages[i]['username'] != recent_window_messages[i + 1]['username']):
                    alternating_count += 1
            
            alternating_ratio = alternating_count / (len(recent_window_messages) - 1)
            if alternating_ratio > 0.7:  # High alternation
                score += 0.3
                print(f"    → High alternation pattern detected ({alternating_ratio:.2f})")
        
        # Check for quick responses (messages within 30 seconds of each other)
        quick_responses = 0
        for i in range(1, len(recent_window_messages)):
            time_diff = recent_window_messages[i].get('timestamp', 0) - recent_window_messages[i-1].get('timestamp', 0)
            if time_diff <= 30:  # Within 30 seconds
                quick_responses += 1
        
        if quick_responses >= 2:
            score += 0.2
            print(f"    → Quick response pattern detected ({quick_responses} quick replies)")
        
        # Check for conversation continuity (related topics/responses)
        if self.has_conversational_continuity(recent_window_messages[-3:]):
            score += 0.3
            print(f"    → Conversational continuity detected")
        
        return min(score, 1.0)
    
    def has_conversational_continuity(self, messages) -> bool:
        """Check if messages show conversational continuity (responses, questions, etc.)"""
        if len(messages) < 2:
            return False
        
        continuity_indicators = [
            # Response indicators
            r'\byeah\b', r'\byes\b', r'\bno\b', r'\btrue\b', r'\bfalse\b',
            r'\bagreed?\b', r'\bexactly\b', r'\bright\b', r'\bwrong\b',
            
            # Question/answer patterns
            r'\?', r'\bwhat\b', r'\bhow\b', r'\bwhy\b', r'\bwhen\b', r'\bwhere\b',
            
            # Continuation words
            r'\balso\b', r'\bbut\b', r'\bhowever\b', r'\bthough\b', r'\bstill\b',
            r'\banyway\b', r'\bbesides\b', r'\bmoreover\b',
            
            # Direct references
            r'\bthat\b', r'\bthis\b', r'\bit\b', r'\bthey\b', r'\byou\b'
        ]
        
        for i in range(1, len(messages)):
            current_msg = messages[i]['message'].lower()
            for indicator in continuity_indicators:
                if re.search(indicator, current_msg):
                    return True
        
        return False
    
    def is_private_conversation_ongoing(self) -> bool:
        """Check if there's currently a private conversation happening that we shouldn't interrupt"""
        if not config.ENABLE_PRIVATE_CONVERSATION_DETECTION or len(self.recent_messages) < 3:
            return False
        
        current_time = time.time()
        recent_messages = []
        
        # Get messages from the last minute
        for msg in reversed(self.recent_messages):
            if current_time - msg.get('timestamp', 0) <= 60:  # Last minute
                recent_messages.insert(0, msg)
            else:
                break
        
        if len(recent_messages) < 3:
            return False
        
        # Check for two-person conversation pattern
        participants = set()
        for msg in recent_messages[-5:]:  # Last 5 messages
            participants.add(msg['username'])
        
        # If only 2 people have been talking recently, it might be private
        if len(participants) == 2:
            # Check for alternating pattern or quick responses
            alternating_count = 0
            quick_responses = 0
            
            for i in range(1, len(recent_messages)):
                # Check alternation
                if recent_messages[i]['username'] != recent_messages[i-1]['username']:
                    alternating_count += 1
                
                # Check response time
                time_diff = recent_messages[i].get('timestamp', 0) - recent_messages[i-1].get('timestamp', 0)
                if time_diff <= 30:  # Quick response
                    quick_responses += 1
            
            alternating_ratio = alternating_count / (len(recent_messages) - 1) if len(recent_messages) > 1 else 0
            
            # Private conversation indicators
            if alternating_ratio > 0.6 and quick_responses >= 2:
                return True
        
        return False
    
    def should_respond(self, message: str, username: str = None) -> bool:
        """Determine if bot should respond to this message"""
        # Always respond if bot name is mentioned (case insensitive)
        if config.ALWAYS_RESPOND_TO_NAME and config.BOT_NAME.lower() in message.lower():
            print(f"Name '{config.BOT_NAME}' mentioned! Responding 100% of the time.")
            self.bot_mentioned_recently = True
            self._last_mention_time = time.time()
            if username:
                self.conversation_participants.add(username)
            return True
        
        # Always respond if username is mentioned
        if config.ALWAYS_RESPOND_TO_USERNAME and username and username.lower() in message.lower():
            print(f"Username '{username}' mentioned! Responding 100% of the time.")
            self.bot_mentioned_recently = True
            self._last_mention_time = time.time()
            if username:
                self.conversation_participants.add(username)
            return True
        
        # Check if this appears to be a private conversation we shouldn't interrupt
        if username and self.detect_private_conversation(message, username):
            print(f"Detected private conversation - not responding to avoid interruption")
            return False
        
        # In busy mode, be much more selective about responding
        if self.is_busy_mode:
            # Only respond to high-context conversations in busy mode
            if username and config.ENABLE_SMART_INTERJECTION:
                context_score = self.analyze_conversation_context(message, username)
                # Require higher context score in busy mode
                if context_score >= (config.CONVERSATION_ANALYSIS_THRESHOLD + 0.2):
                    print(f"Busy mode: High-context interjection! Score: {context_score:.2f}")
                    self.conversation_participants.add(username)
                    return True
            
            # Much lower random response rate in busy mode
            busy_threshold = self.response_threshold * config.BUSY_MODE_RESPONSE_RATE
            should_respond = random.random() < busy_threshold
            if should_respond:
                print(f"Busy mode: Random response ({busy_threshold*100:.1f}% chance)")
            return should_respond
        
        # Normal mode behavior
        # Smart contextual analysis
        if username and config.ENABLE_SMART_INTERJECTION:
            context_score = self.analyze_conversation_context(message, username)
            if context_score >= config.CONVERSATION_ANALYSIS_THRESHOLD:
                print(f"Smart interjection triggered! Context score: {context_score:.2f}")
                self.conversation_participants.add(username)
                return True
        
        # Random chance to respond to other messages
        should_respond = random.random() < self.response_threshold
        if should_respond:
            print(f"Random response triggered ({self.response_threshold*100:.0f}% chance)")
        return should_respond
    
    async def handle_command(self, text: str, username: str, user_id: str) -> bool:
        """Handle special commands like !pair and !bgm. Returns True if command was processed."""
        if not text.startswith("!"):
            return False
            
        command = text.lower().strip()
        
        if command == "!pair" and config.ENABLE_PAIRING_COMMANDS:
            # Instead of trying to create a pair (which causes Bad Request),
            # just tell the user how pairing works
            if self.pair_status == "solo":
                await self.send_message(f"Send me a pair request from the courtroom interface and I'll accept it!")
            elif self.pair_status == "paired":
                paired_username = self.get_username(self.paired_with_user_id)
                await self.send_message(f"I'm already paired with {paired_username}.")
            elif self.pair_status == "pending":
                await self.send_message("I'm processing a pair request.")
            return True
            
        elif command == "!bgm" and config.ENABLE_BGM_ROULETTE:
            await self.handle_bgm_roulette(username)
            return True
            
        elif command == "!popular":
            await self.handle_popular_thread(username)
            return True
            
        elif command == "!random":
            await self.handle_random_thread(username)
            return True
            
        return False
    
    async def handle_message(self, data: Dict):
        """Handle incoming messages"""
        try:
            # Check if this is a nested message structure
            if "message" in data and isinstance(data["message"], dict):
                # Nested structure: {"userId":"...", "message":{"characterId":1,"poseId":1,"text":"..."}}
                message_data = data["message"]
                text = message_data.get("text", "")
                character_id = message_data.get("characterId", config.DEFAULT_CHARACTER_ID)
                
                # Get username from userId if available
                username = None
                user_id = None
                if "userId" in data:
                    user_id = data["userId"]
                    username = self.get_username(user_id)
                    
                    # If we don't have this user, refresh room data
                    if user_id not in self.users:
                        print(f"Unknown user ID {user_id}, refreshing room data...")
                        await self.refresh_room_data()
                        username = self.get_username(user_id)
                
                print(f"Message from {username or f'Character {character_id}'}: {text}")
                
                # Don't respond to own messages
                if user_id == self.my_user_id:
                    print("Ignoring own message")
                    return
                
                # Check for commands first (strip color codes before processing)
                clean_text = self.strip_color_codes(text)
                if username and user_id and await self.handle_command(clean_text, username, user_id):
                    print(f"Processed command: {clean_text} (original: {text})")
                    return
                
                # Add message to history for context (if we have a username)
                if username:
                    self.add_message_to_history(username, text)
                
                # Check if we should respond
                if self.should_respond(text, username):
                    print("Getting AI response...")
                    
                    # Determine if this is a name-mentioned response or random response
                    is_name_mentioned = (config.ALWAYS_RESPOND_TO_NAME and 
                                       config.BOT_NAME.lower() in text.lower())
                    include_context = not is_name_mentioned  # Include context for non-name responses
                    
                    ai_response = await self.get_ai_response(text, username, include_context)
                    
                    if ai_response:
                        # Add a small delay to make responses feel more natural
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                        await self.send_message(ai_response)
                    else:
                        print("No AI response received - not sending anything")
                        
            elif "text" in data and "characterId" in data:
                # Direct structure: {"characterId":1,"poseId":1,"text":"..."}
                text = data["text"]
                character_id = data["characterId"]
                
                # Get username if available
                username = None
                if "username" in data:
                    username = data["username"]
                
                print(f"Message from {username or f'Character {character_id}'}: {text}")
                
                # Add message to history for context (if we have a username)
                if username:
                    self.add_message_to_history(username, text)
                
                # Check if we should respond
                if self.should_respond(text, username):
                    print("Getting AI response...")
                    
                    # Determine if this is a name-mentioned response or random response
                    is_name_mentioned = (config.ALWAYS_RESPOND_TO_NAME and 
                                       config.BOT_NAME.lower() in text.lower())
                    include_context = not is_name_mentioned  # Include context for non-name responses
                    
                    ai_response = await self.get_ai_response(text, username, include_context)
                    
                    if ai_response:
                        # Add a small delay to make responses feel more natural
                        await asyncio.sleep(random.uniform(1.0, 2.5))
                        await self.send_message(ai_response)
                    else:
                        print("No AI response received - not sending anything")
                
        except Exception as e:
            print(f"Error handling message: {e}")
            print(f"Message data: {data}")
    
    async def handle_room_update(self, data: Dict):
        """Handle room updates to get user information"""
        try:
            if "users" in data:
                print(f"Updating user list from room update...")
                for user in data["users"]:
                    if "id" in user and "username" in user:
                        user_id = user["id"]
                        username = user["username"]
                        # Update our user mapping
                        old_username = self.users.get(user_id)
                        self.users[user_id] = username
                        
                        if old_username != username:
                            if old_username:
                                print(f"User updated: {old_username} -> {username}")
                            else:
                                print(f"User joined: {username}")
                
                print(f"Total users in room: {len(self.users)}")
                # Don't list all users to avoid AI confusion
            
            if "title" in data:
                print(f"Room title: {data['title']}")
                
        except Exception as e:
            print(f"Error handling room update: {e}")
    
    async def handle_user_joined(self, data: Dict):
        """Handle user_joined events for real-time updates"""
        try:
            if isinstance(data, dict):
                user_id = data.get('id')
                username = data.get('username')
                if user_id and username:
                    # Don't react to our own join
                    if user_id == self.my_user_id:
                        return
                    
                    self.users[user_id] = username
                    print(f"User joined: {username}")
                    
                    # Check for quick rejoin
                    is_quick_rejoin = False
                    if config.IGNORE_QUICK_REJOIN and user_id in self.recent_departures:
                        time_since_leave = time.time() - self.recent_departures[user_id]
                        if time_since_leave < 30:  # 30 seconds
                            is_quick_rejoin = True
                            print(f"  Quick rejoin detected ({time_since_leave:.1f}s ago) - not reacting")
                        del self.recent_departures[user_id]
                    
                    # React to user joining
                    if config.ENABLE_JOIN_LEAVE_REACTIONS and not is_quick_rejoin:
                        await self.react_to_user_join(username)
                        
        except Exception as e:
            print(f"Error handling user joined: {e}")
    
    async def handle_user_left(self, data: Dict):
        """Handle user_left events"""
        try:
            # Handle both dict format {"id": "..."} and direct user_id string
            user_id = None
            if isinstance(data, dict):
                user_id = data.get('id')
            elif isinstance(data, str):
                user_id = data
            
                if user_id and user_id in self.users:
                    username = self.users[user_id]
                
                # Don't react to our own departure
                if user_id == self.my_user_id:
                    return
                
                # Track departure time for quick rejoin detection
                self.recent_departures[user_id] = time.time()
                
                # If our pair partner left, automatically unpair
                if user_id == self.paired_with_user_id:
                    print(f"Pair partner {username} left the room - unpairing")
                    self.current_pair_id = None
                    self.paired_with_user_id = None
                    self.pair_status = "solo"
                
                # Remove from conversation participants
                self.conversation_participants.discard(username)
                
                del self.users[user_id]
                print(f"User left: {username}")
                
                # React to user leaving
                if config.ENABLE_JOIN_LEAVE_REACTIONS:
                    await self.react_to_user_leave(username)
                    
        except Exception as e:
            print(f"Error handling user left: {e}")
    

    
    async def handle_update_user(self, user_id: str, user_data: Dict):
        """Handle user updates (username changes)"""
        try:
            if isinstance(user_data, dict) and user_id:
                new_username = user_data.get('username')
                if new_username:
                    old_username = self.users.get(user_id)
                    self.users[user_id] = new_username
                    if old_username and old_username != new_username:
                        print(f"User renamed: {old_username} -> {new_username}")
        except Exception as e:
            print(f"Error handling user update: {e}")
    
    async def handle_incoming_pair_request(self, data: Dict):
        """Handle incoming pair requests and automatically accept them"""
        try:
            if isinstance(data, dict) and "pairs" in data:
                pair_id = data.get("id")
                pairs = data.get("pairs", [])
                
                print(f"Received pair request with ID: {pair_id}")
                
                # Check if this pair request involves us
                bot_pair = None
                requester_pair = None
                
                for pair in pairs:
                    if pair.get("userId") == self.my_user_id:
                        bot_pair = pair
                    else:
                        requester_pair = pair
                
                # If we found both pairs and we're marked as pending, accept it
                if (bot_pair and requester_pair and 
                    bot_pair.get("status") == "pending" and 
                    self.pair_status == "solo"):
                    
                    requester_id = requester_pair.get("userId")
                    requester_username = self.get_username(requester_id)
                    
                    print(f"Auto-accepting pair request from {requester_username}")
                    
                    # Send acceptance response
                    success = await self.respond_to_pair(pair_id, "accepted")
                    
                    if success:
                        # Update our state
                        self.current_pair_id = pair_id
                        self.paired_with_user_id = requester_id
                        self.pair_status = "paired"
                        
                        # Announce acceptance
                        await self.send_message(f"Accepted pair request from {requester_username}!")
                        print(f"Successfully paired with {requester_username}")
                    else:
                        print("Failed to send pair acceptance")
                else:
                    print("Pair request doesn't involve us or we're not available")
                    
        except Exception as e:
            print(f"Error handling incoming pair request: {e}")
            print(f"Pair data: {data}")
    
    def get_username(self, user_id: str) -> str:
        """Get username for a user ID, with fallback"""
        if user_id in self.users:
            return self.users[user_id]
        else:
            # Fallback for unknown users
            return f"User-{user_id[:8]}"
    
    async def refresh_room_data(self):
        """Manually refresh room data if usernames are missing"""
        if self.websocket and self.connected:
            print("Refreshing room data to get latest user list...")
            await self.websocket.send('42["get_room"]')
    
    def list_users(self):
        """List all known users for debugging"""
        print(f"\n=== Known Users ({len(self.users)}) ===")
        for user_id, username in self.users.items():
            marker = " (ME)" if user_id == self.my_user_id else ""
            pair_marker = " (PAIRED)" if user_id == self.paired_with_user_id else ""
            print(f"  {username} (ID: {user_id}){marker}{pair_marker}")
        print("===========================\n")
    
    async def create_pair_request(self, target_user_id: str):
        """Send a pair request to another user"""
        if not self.websocket or not self.connected:
            print("Cannot send pair request - not connected")
            return False
            
        if self.pair_status != "solo":
            print(f"Cannot create pair - current status: {self.pair_status}")
            return False
        
        # Check if target user is valid
        if target_user_id not in self.users:
            print(f"Target user {target_user_id} not found in room")
            return False
            
        import uuid
        pair_id = str(uuid.uuid4())
        
        # Exactly match the structure from your working example
        pair_data = {
            "id": pair_id,
            "pairs": [
                {
                    "userId": self.my_user_id,
                    "status": "accepted",
                    "offsetX": -10,
                    "offsetY": 0,
                    "front": 0,
                    "flipped": False,
                    "target": 2
                },
                {
                    "userId": target_user_id,
                    "status": "pending",
                    "offsetX": 10,
                    "offsetY": 0,
                    "front": 1,
                    "flipped": False,
                    "target": 4
                }
            ],
            "backgroundUserId": self.my_user_id
        }
        
        message = f'42["create_pair",{json.dumps(pair_data)}]'
        
        try:
            await self.websocket.send(message)
            print(f"Attempting to send pair request...")
            print(f"Pair data: {json.dumps(pair_data, indent=2)}")
            
            self.current_pair_id = pair_id
            self.paired_with_user_id = target_user_id
            self.pair_status = "pending"
            
            username = self.get_username(target_user_id)
            print(f"Sent pair request to {username} (ID: {target_user_id})")
            return True
            
        except Exception as e:
            print(f"Error sending pair request: {e}")
            return False
    
    async def respond_to_pair(self, pair_id: str, status: str = "accepted"):
        """Respond to a pair request"""
        if not self.websocket or not self.connected:
            return False
            
        response_data = {
            "pairId": pair_id,
            "status": status
        }
        
        message = f'42["respond_to_pair",{json.dumps(response_data)}]'
        try:
            await self.websocket.send(message)
            print(f"Sent pair response: {message}")
        except Exception as e:
            print(f"Error sending pair response: {e}")
            return False
        
        if status == "accepted":
            self.current_pair_id = pair_id
            self.pair_status = "paired"
            print(f"Accepted pair request: {pair_id}")
        else:
            print(f"Declined pair request: {pair_id}")
            
        return True
    
    def add_message_to_history(self, username: str, message: str):
        """Add a message to the recent message history"""
        # Don't store our own messages
        if username == config.BOT_NAME or username == config.BOT_USERNAME:
            return
            
        message_entry = {"username": username, "message": message, "timestamp": time.time()}
        self.recent_messages.append(message_entry)
        
        # Keep only the most recent messages
        if len(self.recent_messages) > self.max_context_messages:
            self.recent_messages.pop(0)
        
        # Update busy mode status based on this message
        self.update_busy_mode_status(username)
        
        # Update conversation tracking
        current_time = time.time()
        
        # Clear old participants if it's been a while since last message
        if self.last_message_time and current_time - self.last_message_time > 120:  # 2 minutes
            self.conversation_participants.clear()
            self.bot_mentioned_recently = False
        
        self.last_message_time = current_time
        
        self.conversation_participants.add(username)
        
        # Reset idle message tracking since we got a new user message
        self.reset_idle_message_tracking()
        
        # Reset bot mentioned flag after some time
        if hasattr(self, '_last_mention_time'):
            if time.time() - self._last_mention_time > 180:  # 3 minutes
                self.bot_mentioned_recently = False
    
    async def schedule_next_idle_message(self):
        """Schedule the next idle message with progressive delay"""
        if not config.ENABLE_IDLE_MESSAGES or not self.connected:
            return
        
        # Cancel existing idle task
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        
        # Calculate delay: base_delay * multiplier^count
        delay = config.IDLE_MESSAGE_BASE_DELAY * (config.IDLE_MESSAGE_MULTIPLIER ** self.idle_message_count)
        print(f"Scheduling idle message #{self.idle_message_count + 1} in {delay} seconds")
        
        # Schedule the idle message
        self.idle_task = asyncio.create_task(self._wait_and_send_idle_message(delay))
    
    async def _wait_and_send_idle_message(self, delay: float):
        """Wait for the specified delay then send an idle message"""
        try:
            await asyncio.sleep(delay)
            
            # Double-check we should still send an idle message
            if not config.ENABLE_IDLE_MESSAGES or not self.connected:
                return
            
            current_time = time.time()
            
            # Only send if no new user messages have arrived since we scheduled this
            if (self.last_user_message_time and 
                current_time - self.last_user_message_time >= delay):
                
                # Check if there's an ongoing direct conversation we shouldn't interrupt
                if self.recent_messages and len(self.recent_messages) >= 2:
                    last_two = self.recent_messages[-2:]
                    if (len(set(msg["username"] for msg in last_two)) == 2 and
                        current_time - last_two[-1].get("timestamp", 0) < 120):  # Within last 2 minutes
                        print(f"  → Skipping idle message - detected ongoing conversation between users")
                        # Reschedule for later
                        await self.schedule_next_idle_message()
                        return
                
                print(f"Sending idle message #{self.idle_message_count + 1}...")
                
                # Get intelligent idle message based on chat history
                ai_response = await self.get_intelligent_idle_message()
                
                if ai_response:
                    await self.send_message(ai_response)
                    self.last_idle_message_time = current_time
                    self.idle_message_count += 1
                    
                    # Schedule the next idle message
                    await self.schedule_next_idle_message()
                else:
                    print("Failed to get AI response for idle message")
            else:
                print("New user message arrived, cancelling idle message")
                
        except asyncio.CancelledError:
            print("Idle message task was cancelled")
        except Exception as e:
            print(f"Error in idle message task: {e}")
    
    def reset_idle_message_tracking(self):
        """Reset idle message tracking when new user messages arrive"""
        # Cancel any pending idle message
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
        
        # Reset the counter
        self.idle_message_count = 0
        
        # Update the last user message time
        self.last_user_message_time = time.time()
        
        # Schedule the first idle message
        asyncio.create_task(self.schedule_next_idle_message())
    
    async def get_intelligent_idle_message(self) -> Optional[str]:
        """Generate intelligent idle messages based on chat history analysis"""
        if not self.recent_messages:
            # No chat history, use random conversation starter
            return await self.get_ai_response(
                "Start an interesting conversation topic in a chatroom. Be natural and engaging.", 
                None, 
                False
            )
        
        # 50/50 chance: contextual continuation vs random topic
        use_context = random.random() < 0.5
        
        if use_context:
            print("  → Generating contextual idle message based on recent chat")
            return await self.get_contextual_idle_message()
        else:
            print("  → Generating random conversation starter")
            return await self.get_random_idle_message()
    
    async def get_contextual_idle_message(self) -> Optional[str]:
        """Generate idle message that continues or relates to recent conversation"""
        if not self.recent_messages:
            return None
        
        # Check if there's an ongoing private conversation we shouldn't interrupt
        if self.is_private_conversation_ongoing():
            print("    → Private conversation ongoing, falling back to random message")
            return await self.get_random_idle_message()
        
        # Analyze recent conversation (last 10 messages or 5 minutes, whichever is smaller)
        current_time = time.time()
        recent_context = []
        
        for msg in reversed(self.recent_messages):
            # Only include messages from last 5 minutes
            if current_time - msg.get('timestamp', 0) > 300:  # 5 minutes
                break
            recent_context.insert(0, f"{msg['username']}: {msg['message']}")
            
            # Limit to 10 messages max for context
            if len(recent_context) >= 10:
                break
        
        if not recent_context:
            print("    → No recent context found, falling back to random message")
            return await self.get_random_idle_message()
        
        print(f"    → Using {len(recent_context)} recent messages for context")
        
        # Create context for AI analysis
        chat_history = "\n".join(recent_context)
        
        context_prompt = (
            f"Here's the recent chat history from a courtroom chatroom:\n\n{chat_history}\n\n"
            f"The conversation has been quiet for a while. Based on this chat history, "
            f"either continue a topic that was being discussed, ask a follow-up question about something mentioned, "
            f"or bring up something related to what people were talking about. "
            f"Be natural and conversational - don't summarize what happened, just join in naturally. "
            f"Keep it short and engaging."
        )
        
        return await self.get_ai_response(context_prompt, None, False)
    
    async def get_random_idle_message(self) -> Optional[str]:
        """Generate random conversation starter"""
        # Mix of different types of conversation starters
        starter_types = [
            "Ask an interesting question about games, technology, or general topics that might spark discussion.",
            "Share a random interesting thought or observation that could start a conversation.",
            "Bring up something about current events, gaming, or internet culture that people might want to discuss.",
            "Start a casual topic about daily life, entertainment, or hobbies that people can relate to.",
            "Ask for opinions on something interesting or controversial (but not too serious)."
        ]
        
        selected_type = random.choice(starter_types)
        
        context_prompt = (
            f"{selected_type} "
            f"Be natural and conversational for a chatroom setting. "
            f"Keep it short and engaging. Don't be too formal."
        )
        
        return await self.get_ai_response(context_prompt, None, False)
    
    def get_idle_message_context(self) -> str:
        """Generate context for idle messages (legacy method, keeping for compatibility)"""
        if not self.recent_messages:
            return "Start a casual conversation. "
        
        # Analyze recent topic
        recent_words = []
        for msg in self.recent_messages[-2:]:
            recent_words.extend(msg['message'].lower().split())
        
        if recent_words:
            # Find common themes
            word_freq = {}
            for word in recent_words:
                if len(word) > 3:  # Skip short words
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            if word_freq:
                common_word = max(word_freq, key=word_freq.get)
                return f"Continue the conversation about {common_word} or bring up something related. "
        
        return "Start a natural conversation or comment on something interesting. "
    
    def detect_name_mentions(self, message: str) -> List[str]:
        """Detect if a message mentions any user names in the room"""
        mentioned_users = []
        message_lower = message.lower()
        
        # Check for direct mentions of usernames
        for user_id, username in self.users.items():
            if user_id == self.my_user_id:  # Skip bot's own name
                continue
            
            username_lower = username.lower()
            # Look for the username as a separate word (not part of another word)
            pattern = r'\b' + re.escape(username_lower) + r'\b'
            if re.search(pattern, message_lower):
                mentioned_users.append(username)
        
        return mentioned_users
    
    def is_direct_conversation(self, current_username: str, current_message: str) -> bool:
        """Detect if this appears to be a direct conversation between specific users"""
        # Check if the current message mentions specific users
        mentioned_users = self.detect_name_mentions(current_message)
        if mentioned_users:
            print(f"  → Direct mention detected: {current_username} mentioned {mentioned_users}")
            return True
        
        # Check for recent back-and-forth pattern (last 4 messages)
        if len(self.recent_messages) >= 3:
            recent_msgs = self.recent_messages[-4:]  # Last 4 messages including current
            recent_msgs.append({"username": current_username, "message": current_message})
            
            # Look for alternating pattern between two users
            if len(recent_msgs) >= 3:
                user_sequence = [msg["username"] for msg in recent_msgs[-3:]]
                unique_users = list(set(user_sequence))
                
                # If only 2 unique users in last 3 messages, it's likely a direct conversation
                if len(unique_users) == 2 and self.my_user_id not in [self.get_user_id(u) for u in unique_users]:
                    print(f"  → Back-and-forth detected between: {unique_users}")
                    return True
        
        # Check for conversational indicators suggesting direct response
        response_indicators = [
            r'\b(yes|yeah|yep|no|nope|sure|okay|ok)\b',
            r'\b(what do you|why do you|how do you|did you|will you|can you|are you)\b',
            r'\b(i think|i agree|i disagree|i know|i see)\b',
            r'\b(that\'s|thats|you\'re|youre|your)\b'
        ]
        
        message_lower = current_message.lower()
        for pattern in response_indicators:
            if re.search(pattern, message_lower):
                # If we see response indicators and there was a recent message from someone else
                if (self.recent_messages and 
                    self.recent_messages[-1]["username"] != current_username):
                    print(f"  → Response pattern detected: '{current_message[:30]}...'")
                    return True
        
        return False
    
    def get_user_id(self, username: str) -> Optional[str]:
        """Get user ID from username"""
        for user_id, stored_username in self.users.items():
            if stored_username == username:
                return user_id
        return None
    
    def should_avoid_interrupting(self, current_username: str, current_message: str) -> bool:
        """Determine if bot should avoid interrupting this conversation"""
        # Always allow responses to direct mentions of the bot
        if (config.ALWAYS_RESPOND_TO_NAME and config.BOT_NAME.lower() in current_message.lower()) or \
           (config.ALWAYS_RESPOND_TO_USERNAME and config.BOT_USERNAME.lower() in current_message.lower()):
            return False
        
        # Check if this is a direct conversation
        if self.is_direct_conversation(current_username, current_message):
            print("  → Avoiding interruption of direct conversation")
            return True
        
        return False
    
    async def react_to_user_join(self, username: str):
        """React to a user joining the courtroom"""
        try:
            # Check reaction cooldown
            current_time = time.time()
            if (self.last_join_leave_reaction and 
                current_time - self.last_join_leave_reaction < config.REACTION_COOLDOWN):
                print(f"Join/leave reaction on cooldown, not reacting to {username} joining")
                return
            
            # Check probability
            if random.random() > config.JOIN_REACTION_CHANCE:
                print(f"Join reaction probability not met for {username}")
                return
            
            print(f"Reacting to {username} joining...")
            
            # Add delay before reacting
            delay = random.uniform(*config.JOIN_LEAVE_REACTION_DELAY)
            await asyncio.sleep(delay)
            
            # Generate AI-powered contextual greeting
            room_size = len(self.users)
            context_info = f"A user named '{username}' just joined the courtroom. "
            
            if room_size <= 3:
                context_info += "It's a small group, so be more personal and welcoming. "
            else:
                context_info += "It's a bigger room with several people, so be casual but friendly. "
            
            # Add conversation context if available
            if self.recent_messages:
                recent_topics = []
                for msg in self.recent_messages[-2:]:
                    recent_topics.append(msg['message'])
                if recent_topics:
                    context_info += f"Recent conversation topics: {' | '.join(recent_topics)}. "
            
            context_info += "Greet them naturally as if you know them from the courtroom community."
            
            # Get AI-generated greeting
            ai_greeting = await self.get_ai_response(context_info, username, True)
            
            if ai_greeting:
                await self.send_message(ai_greeting)
            else:
                # Fallback to simple greeting if AI fails
                await self.send_message(f"Hey {username}! Welcome!")
            self.last_join_leave_reaction = current_time
            
        except Exception as e:
            print(f"Error reacting to user join: {e}")
    
    async def react_to_user_leave(self, username: str):
        """React to a user leaving the courtroom"""
        try:
            # Check reaction cooldown
            current_time = time.time()
            if (self.last_join_leave_reaction and 
                current_time - self.last_join_leave_reaction < config.REACTION_COOLDOWN):
                print(f"Join/leave reaction on cooldown, not reacting to {username} leaving")
                return
            
            # Check probability
            if random.random() > config.LEAVE_REACTION_CHANCE:
                print(f"Leave reaction probability not met for {username}")
                return
            
            print(f"Reacting to {username} leaving...")
            
            # Add delay before reacting
            delay = random.uniform(*config.JOIN_LEAVE_REACTION_DELAY)
            await asyncio.sleep(delay)
            
            # Generate AI-powered contextual farewell
            was_active = username in self.conversation_participants
            context_info = f"A user named '{username}' just left the courtroom. "
            
            if was_active:
                context_info += f"{username} was actively chatting with everyone. "
                context_info += "Say goodbye in a personal way since you were talking with them. "
            else:
                context_info += f"{username} was in the room but not very active in conversation. "
                context_info += "Say goodbye in a friendly but more casual way. "
            
            # Add conversation context if they were involved
            if was_active and self.recent_messages:
                recent_with_user = []
                for msg in self.recent_messages[-3:]:
                    if msg['username'] == username:
                        recent_with_user.append(msg['message'])
                if recent_with_user:
                    context_info += f"They recently said: '{recent_with_user[-1]}'. "
            
            context_info += "Send them off naturally as a courtroom community member would."
            
            # Get AI-generated farewell
            ai_farewell = await self.get_ai_response(context_info, username, True)
            
            if ai_farewell:
                await self.send_message(ai_farewell)
            else:
                # Fallback to simple farewell if AI fails
                await self.send_message(f"See you later, {username}!")
            self.last_join_leave_reaction = current_time
            
        except Exception as e:
            print(f"Error reacting to user leave: {e}")
    
    async def handle_bgm_roulette(self, username: str):
        """Handle !bgm command - generates random BGM code"""
        try:
            # Check cooldown
            current_time = time.time()
            if (self.last_bgm_command and 
                current_time - self.last_bgm_command < config.BGM_COOLDOWN):
                remaining = config.BGM_COOLDOWN - (current_time - self.last_bgm_command)
                print(f"BGM command on cooldown for {remaining:.1f} more seconds")
                await self.send_message(f"BGM roulette is on cooldown for {remaining:.0f} more seconds!")
                return
            
            # Generate random BGM ID (above 15k as requested)
            bgm_id = random.randint(config.BGM_MIN_ID, config.BGM_MAX_ID)
            
            # Format as BGM code
            bgm_code = f"[#bgm{bgm_id}]"
            
            # Create announcement message
            announcement = f"here's BGM{bgm_id} {bgm_code}"
            
            print(f"Generated BGM {bgm_id} for {username}")
            
            # Send the announcement with BGM code and special pose
            await self.send_message(announcement, pose_id=config.BGM_POSE_ID, auto_emotion=False)
            
            # Update cooldown
            self.last_bgm_command = current_time
            
        except Exception as e:
            print(f"Error handling BGM roulette: {e}")
    
    async def handle_popular_thread(self, username: str):
        """Handle !popular command - fetches and shares popular /v/ thread"""
        try:
            # Check cooldown (30 seconds to avoid spam)
            current_time = time.time()
            cooldown_time = 30  # 30 seconds cooldown
            if (self.last_popular_command and 
                current_time - self.last_popular_command < cooldown_time):
                remaining = cooldown_time - (current_time - self.last_popular_command)
                print(f"Popular command on cooldown for {remaining:.1f} more seconds")
                await self.send_message(f"!popular is on cooldown for {remaining:.0f} more seconds!")
                return
            
            print(f"Fetching popular /v/ thread for {username}...")
            
            # Fetch popular thread from /v/ only
            thread_url, thread_summary = await self.thread_fetcher.get_popular_thread_info('v')
            
            if thread_url and thread_summary:
                # Send the thread link directly
                await self.send_message(thread_url)
                
                # Small delay before AI reaction
                await asyncio.sleep(random.uniform(1.5, 3.0))
                
                # Get AI reaction to the thread
                ai_context = (
                    f"A user asked for a popular /v/ thread. I found this thread: {thread_url}. "
                    f"Here's what it's about: {thread_summary}. "
                    f"React to this thread content naturally, as if you just read it yourself. "
                    f"Keep your reaction short and conversational. Don't summarize what I just told you."
                )
                
                ai_reaction = await self.get_ai_response(ai_context, username, False)
                
                if ai_reaction:
                    await self.send_message(ai_reaction)
                else:
                    # Fallback reaction if AI fails
                    await self.send_message("That's an interesting thread!")
                
                print(f"Successfully shared thread: {thread_url}")
            else:
                await self.send_message("Couldn't find any hot /v/ threads right now, try again later!")
                print("Failed to fetch thread data")
            
            # Update cooldown
            self.last_popular_command = current_time
            
        except Exception as e:
            print(f"Error handling popular thread command: {e}")
            await self.send_message("Something went wrong while fetching threads!")
    
    async def handle_random_thread(self, username: str):
        """Handle !random command - fetches random thread from /v/, /g/, or /a/ avoiding generals"""
        try:
            # Check cooldown (30 seconds to avoid spam)
            current_time = time.time()
            cooldown_time = 30  # 30 seconds cooldown
            if (self.last_random_command and 
                current_time - self.last_random_command < cooldown_time):
                remaining = cooldown_time - (current_time - self.last_random_command)
                print(f"Random command on cooldown for {remaining:.1f} more seconds")
                await self.send_message(f"!random is on cooldown for {remaining:.0f} more seconds!")
                return
            
            print(f"Fetching random thread for {username}...")
            
            # Fetch random thread from /v/, /g/, or /a/ (avoiding generals)
            thread_url, thread_summary = await self.thread_fetcher.get_random_thread_info(['v', 'g', 'a'])
            
            if thread_url and thread_summary:
                # Send the thread link directly
                await self.send_message(thread_url)
                
                # Small delay before AI reaction
                await asyncio.sleep(random.uniform(1.5, 3.0))
                
                # Get AI reaction to the thread
                ai_context = (
                    f"A user asked for a random thread. I found this thread: {thread_url}. "
                    f"Here's what it's about: {thread_summary}. "
                    f"React to this thread content naturally, as if you just read it yourself. "
                    f"Keep your reaction short and conversational. Don't summarize what I just told you."
                )
                
                ai_reaction = await self.get_ai_response(ai_context, username, False)
                
                if ai_reaction:
                    await self.send_message(ai_reaction)
                else:
                    # Fallback reaction if AI fails
                    await self.send_message("That's an interesting thread!")
                
                print(f"Successfully shared random thread: {thread_url}")
            else:
                await self.send_message("Couldn't find any good threads right now, try again later!")
                print("Failed to fetch random thread data")
            
            # Update cooldown
            self.last_random_command = current_time
            
        except Exception as e:
            print(f"Error handling random thread command: {e}")
            await self.send_message("Something went wrong while fetching threads!")
    
    def get_context_messages(self, current_username: str, current_message: str, is_name_mentioned: bool = False) -> str:
        """Get recent message context for AI, excluding the current message"""
        if not self.recent_messages:
            return ""
        
        # Use different context lengths based on response type
        max_messages = self.max_ai_context_messages
        if not is_name_mentioned and config.REDUCE_CONTEXT_FOR_RANDOM_RESPONSES:
            max_messages = config.MAX_CONTEXT_MESSAGES_RANDOM
        
        context_lines = []
        recent_subset = self.recent_messages[-max_messages:] if len(self.recent_messages) > max_messages else self.recent_messages
        
        for msg in recent_subset:
            if msg["username"] != current_username or msg["message"] != current_message:
                context_lines.append(f"{msg['username']}: {msg['message']}")
        
        if context_lines:
            # Keep context simple to avoid triggering summary behavior
            return " | ".join(context_lines) + " | "
        return ""
    
    async def handle_me_message(self, data: Dict):
        """Handle 'me' messages to get current user info"""
        try:
            if "user" in data and "username" in data["user"]:
                username = data["user"]["username"]
                # Capture bot's own user ID
                if "id" in data["user"]:
                    self.my_user_id = data["user"]["id"]
                    print(f"Current user: {username} (ID: {self.my_user_id})")
                else:
                    print(f"Current user: {username}")
                
        except Exception as e:
            print(f"Error handling me message: {e}")
    
    async def process_message(self, message: str):
        """Process incoming WebSocket messages"""
        try:
            # Handle different message types
            if message.startswith('42["message"'):
                # Extract message data - handle extra data after JSON
                start = message.find('[')
                if start > 0:
                    # Find the end of the JSON array, ignoring extra data
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                await self.handle_message(data[1])
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            
            elif message.startswith('42["update_room"'):
                # Extract room update data - handle extra data after JSON
                start = message.find('[')
                if start > 0:
                    # Find the end of the JSON array, ignoring extra data
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                await self.handle_room_update(data[1])
                                # Set connected when we get room info
                                if not self.connected:
                                    print("Successfully connected to room!")
                                    self.connected = True
                                    # Initialize idle message tracking when we connect
                                    if config.ENABLE_IDLE_MESSAGES:
                                        self.last_user_message_time = time.time()
                                        asyncio.create_task(self.schedule_next_idle_message())
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            
            elif message.startswith('42["me"'):
                # Extract me message data - handle extra data after JSON
                start = message.find('[')
                if start > 0:
                    # Find the end of the JSON array, ignoring extra data
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                await self.handle_me_message(data[1])
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            
            elif message.startswith('40'):
                print("Connected to Socket.IO")
                # Don't set connected yet, wait for room info
            elif message.startswith('42["joined_room"'):
                print("Successfully joined the room!")
                self.connected = True
                # Initialize idle message tracking when we connect
                if config.ENABLE_IDLE_MESSAGES:
                    self.last_user_message_time = time.time()
                    asyncio.create_task(self.schedule_next_idle_message())
            elif message.startswith('42["user_joined"'):
                # Handle user joined events
                start = message.find('[')
                if start > 0:
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                await self.handle_user_joined(data[1])
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            elif message.startswith('42["user_left"'):
                # Handle user left events - format: 42["user_left","user-id","session-id"]
                start = message.find('[')
                if start > 0:
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                # user_left sends user_id as string in data[1]
                                user_id = data[1]
                                await self.handle_user_left(user_id)
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            elif message.startswith('42["update_user"'):
                # Handle user update events
                start = message.find('[')
                if start > 0:
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 2:
                                user_id = data[1]
                                user_data = data[2]
                                await self.handle_update_user(user_id, user_data)
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            elif message.startswith('42["create_pair"'):
                # Handle incoming pair requests
                start = message.find('[')
                if start > 0:
                    bracket_count = 0
                    end = start
                    for i, char in enumerate(message[start:], start):
                        if char == '[':
                            bracket_count += 1
                        elif char == ']':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    if end > start:
                        json_str = message[start:end]
                        try:
                            data = json.loads(json_str)
                            if len(data) > 1:
                                await self.handle_incoming_pair_request(data[1])
                        except json.JSONDecodeError as e:
                            print(f"JSON decode error: {e} for string: {json_str}")
            elif message.startswith('42["respond_to_pair"') or message.startswith('42["leave_pair"'):
                # Log other pairing events
                print(f"Pairing event received: {message[:50]}...")
            elif message.startswith('42["error"'):
                print(f"Error from server: {message}")
            elif message.startswith('2'):
                # Ping message, respond with pong
                await self.websocket.send("3")
                print("Received ping, sent pong")
            elif message.startswith('3'):
                # Pong message
                print("Received pong")
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    async def ping_loop(self):
        """Send periodic ping messages to keep connection alive"""
        while self.connected and self.websocket:
            await asyncio.sleep(self.ping_interval / 1000)  # Convert ms to seconds
            if self.connected and self.websocket:
                await self.send_ping()
    
    async def run(self):
        """Main bot loop"""
        if not await self.connect():
            return
        
        try:
            # Start ping loop
            ping_task = asyncio.create_task(self.ping_loop())
            
            # Main message loop
            async for message in self.websocket:
                if config.SHOW_RAW_MESSAGES:
                    print(f"Raw message: {message}")
                await self.process_message(message)
                
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            self.connected = False
            # Cancel any pending idle message tasks
            if self.idle_task and not self.idle_task.done():
                self.idle_task.cancel()
            if self.websocket:
                await self.websocket.close()

async def main():
    # Get configuration from config.py or environment variables
    courtroom_id = os.getenv("COURTROOM_ID", config.DEFAULT_COURTROOM_ID)
    shapes_api_key = os.getenv("SHAPESINC_API_KEY", config.SHAPESINC_API_KEY)
    shape_username = os.getenv("SHAPESINC_SHAPE_USERNAME", config.SHAPESINC_SHAPE_USERNAME)
    
    # If no API key in config.py, prompt user
    if not shapes_api_key:
        print("❌ SHAPES API KEY NOT SET!")
        print("Please set your API key in config.py:")
        print("1. Open config.py")
        print("2. Set SHAPESINC_API_KEY = 'your_actual_api_key_here'")
        print("3. Save the file and run again")
        print("\nOr set the SHAPESINC_API_KEY environment variable")
        return
    
    print(f"Starting bot for courtroom: {courtroom_id}")
    print(f"Using shape: {shape_username}")
    print(f"API URL: {config.API_URL}")
    print(f"Response threshold: {config.RESPONSE_THRESHOLD*100:.0f}%")
    
    bot = CourtroomBot(courtroom_id, shapes_api_key, shape_username)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
