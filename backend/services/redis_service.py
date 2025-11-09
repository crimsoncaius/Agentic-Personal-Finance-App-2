"""
Redis service for conversation memory management
Stores and retrieves chat history for contextual NLP processing
"""

import json
import time
from typing import List, Optional, Dict
from uuid import uuid4

import redis
from redis.exceptions import RedisError

# Import configuration
from config.settings import settings


class ChatMessage:
    """Simple chat message model for Redis storage"""

    def __init__(self, role: str, content: str, timestamp: float = None):
        self.role = role  # "user" or "assistant"
        self.content = content
        self.timestamp = timestamp or time.time()

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ChatMessage":
        """Create from dictionary"""
        return cls(
            role=data["role"], content=data["content"], timestamp=data["timestamp"]
        )

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "ChatMessage":
        """Create from JSON string"""
        return cls.from_dict(json.loads(json_str))


class ToolObservation:
    """Structured representation of a tool call output stored privately."""

    def __init__(
        self,
        tool_name: str,
        payload: Dict,
        timestamp: float = None,
        message_id: Optional[str] = None,
    ):
        self.tool_name = tool_name
        self.payload = payload
        self.timestamp = timestamp or time.time()
        # message_id can be used to correlate with message ordering
        self.message_id = message_id or str(uuid4())

    def to_dict(self) -> Dict:
        return {
            "tool_name": self.tool_name,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "message_id": self.message_id,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "ToolObservation":
        return cls(
            tool_name=data["tool_name"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
            message_id=data.get("message_id"),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> "ToolObservation":
        return cls.from_dict(json.loads(json_str))


class RedisService:
    """Service for managing conversation history in Redis"""

    def __init__(self):
        """Initialize Redis connection"""
        self.redis_url = settings.redis_url
        self.ttl = settings.conversation_ttl
        self.history_limit = settings.conversation_history_limit

        # Initialize Redis client
        if self.redis_url:
            try:
                self.client = redis.from_url(
                    self.redis_url,
                    db=settings.redis_db,
                    max_connections=settings.redis_max_connections,
                    decode_responses=True,  # Automatically decode bytes to strings
                    socket_connect_timeout=5,
                    socket_timeout=5,
                )
                # Test connection
                self.client.ping()
                self._enabled = True
            except (RedisError, Exception) as e:
                print(f"Redis connection failed: {str(e)}")
                print("Conversation memory will be disabled.")
                self.client = None
                self._enabled = False
        else:
            print("Redis URL not configured. Conversation memory will be disabled.")
            self.client = None
            self._enabled = False

    @property
    def enabled(self) -> bool:
        """Check if Redis is available"""
        return self._enabled and self.client is not None

    def _get_key(self, chat_id: str) -> str:
        """Generate Redis key for chat conversation"""
        return f"chat:{chat_id}:messages"

    def _get_tool_key(self, chat_id: str) -> str:
        """Generate Redis key for stored tool observations"""
        return f"chat:{chat_id}:tools"

    async def store_message(
        self, chat_id: str, role: str, content: str, ttl: Optional[int] = None
    ) -> bool:
        """
        Store a message in the conversation history

        Args:
            chat_id: Unique chat identifier
            role: Message role ("user" or "assistant")
            content: Message content
            ttl: Time to live in seconds (default from settings)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            message = ChatMessage(role=role, content=content)
            key = self._get_key(chat_id)

            # Add message to sorted set with timestamp as score
            self.client.zadd(
                key, {message.to_json(): message.timestamp}, nx=False  # Allow updates
            )

            # Set TTL on the key
            expire_time = ttl or self.ttl
            self.client.expire(key, expire_time)

            return True

        except (RedisError, Exception) as e:
            print(f"Failed to store message in Redis: {str(e)}")
            return False

    async def store_tool_observation(
        self,
        chat_id: str,
        observation: ToolObservation,
        ttl: Optional[int] = None,
    ) -> bool:
        """
        Store a private tool observation for the conversation.

        Args:
            chat_id: Unique chat identifier
            observation: ToolObservation payload to store
            ttl: Time to live in seconds (default from settings)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            key = self._get_tool_key(chat_id)
            self.client.zadd(
                key, {observation.to_json(): observation.timestamp}, nx=False
            )
            expire_time = ttl or self.ttl
            self.client.expire(key, expire_time)
            return True
        except (RedisError, Exception) as e:
            print(f"Failed to store tool observation in Redis: {str(e)}")
            return False

    async def get_conversation_history(
        self, chat_id: str, limit: Optional[int] = None
    ) -> List[ChatMessage]:
        """
        Retrieve conversation history for a chat

        Args:
            chat_id: Unique chat identifier
            limit: Maximum number of messages to retrieve (default from settings)

        Returns:
            List of ChatMessage objects, ordered from oldest to newest
        """
        if not self.enabled:
            return []

        try:
            key = self._get_key(chat_id)
            message_limit = limit or self.history_limit

            # Get last N messages from sorted set (oldest to newest)
            # Use ZRANGE with negative indices to get last N items
            messages_json = self.client.zrange(
                key, -message_limit, -1  # Last N messages  # Up to end
            )

            # Parse JSON messages
            messages = [ChatMessage.from_json(msg_json) for msg_json in messages_json]

            return messages

        except (RedisError, Exception) as e:
            print(f"Failed to retrieve conversation history from Redis: {str(e)}")
            return []

    async def get_tool_observations(
        self, chat_id: str, limit: Optional[int] = None
    ) -> List[ToolObservation]:
        """
        Retrieve stored tool observations for a conversation.

        Args:
            chat_id: Unique chat identifier
            limit: Maximum number of observations to return

        Returns:
            List of ToolObservation objects ordered from oldest to newest.
        """
        if not self.enabled:
            return []

        try:
            key = self._get_tool_key(chat_id)
            observation_limit = limit or self.history_limit
            observations_json = self.client.zrange(key, -observation_limit, -1)

            observations = [
                ToolObservation.from_json(obs_json) for obs_json in observations_json
            ]

            return observations
        except (RedisError, Exception) as e:
            print(f"Failed to retrieve tool observations from Redis: {str(e)}")
            return []

    async def clear_conversation(self, chat_id: str) -> bool:
        """
        Clear all messages for a conversation

        Args:
            chat_id: Unique chat identifier

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            key = self._get_key(chat_id)
            tool_key = self._get_tool_key(chat_id)
            self.client.delete(key)
            self.client.delete(tool_key)
            return True

        except (RedisError, Exception) as e:
            print(f"Failed to clear conversation in Redis: {str(e)}")
            return False

    async def extend_ttl(self, chat_id: str, ttl: Optional[int] = None) -> bool:
        """
        Extend the TTL for a conversation

        Args:
            chat_id: Unique chat identifier
            ttl: New TTL in seconds (default from settings)

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            key = self._get_key(chat_id)
            tool_key = self._get_tool_key(chat_id)
            expire_time = ttl or self.ttl

            # Only extend if key exists
            if self.client.exists(key):
                self.client.expire(key, expire_time)
            if self.client.exists(tool_key):
                self.client.expire(tool_key, expire_time)

            return bool(self.client.exists(key) or self.client.exists(tool_key))

        except (RedisError, Exception) as e:
            print(f"Failed to extend TTL in Redis: {str(e)}")
            return False

    async def conversation_exists(self, chat_id: str) -> bool:
        """
        Check if a conversation exists

        Args:
            chat_id: Unique chat identifier

        Returns:
            True if conversation exists, False otherwise
        """
        if not self.enabled:
            return False

        try:
            key = self._get_key(chat_id)
            tool_key = self._get_tool_key(chat_id)
            return bool(self.client.exists(key) or self.client.exists(tool_key))

        except (RedisError, Exception) as e:
            print(f"Failed to check conversation existence in Redis: {str(e)}")
            return False


# Global Redis service instance
redis_service = RedisService()
