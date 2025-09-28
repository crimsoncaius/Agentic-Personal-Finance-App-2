#!/usr/bin/env python3
"""
Simple OpenAI SDK test script.
"""

import os
import sys
from dotenv import load_dotenv
from openai import OpenAI


def test_openai_sdk():
    """Test OpenAI API using the official SDK."""
    print("🔍 OpenAI SDK Test")
    print("-" * 20)

    # Load environment - try multiple locations for .env file
    # Script is at: backend/scripts/dev/simple_openai_demo.py
    # .env is at: project_root/.env
    script_dir = os.path.dirname(__file__)
    possible_env_paths = [
        os.path.join(script_dir, "..", "..", "..", ".env"),  # From backend/scripts/dev/
        os.path.join(script_dir, "..", "..", ".env"),  # From backend/scripts/
        os.path.join(script_dir, "..", ".env"),  # From backend/
        ".env",  # Current directory
    ]

    env_loaded = False
    for env_path in possible_env_paths:
        env_path = os.path.abspath(env_path)
        if os.path.exists(env_path):
            load_dotenv(env_path)
            env_loaded = True
            print(f"📁 Loaded .env from: {env_path}")
            break

    if not env_loaded:
        print("⚠️  No .env file found in expected locations")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in .env file")
        return False

    try:
        # Initialize OpenAI client
        print("🔄 Initializing OpenAI client...")
        client = OpenAI(api_key=api_key)

        # Test chat completion
        print("🔄 Testing chat completion...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say 'SDK test successful'"}],
            max_tokens=10,
            temperature=0,
        )

        message = response.choices[0].message.content.strip()
        print(f"✅ Success! Response: {message}")
        print("🎉 Your OpenAI SDK is working!")
        return True

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False


if __name__ == "__main__":
    success = test_openai_sdk()
    sys.exit(0 if success else 1)
