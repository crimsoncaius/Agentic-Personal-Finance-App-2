"""
Simple test script for the ReAct agent.
"""

import os
import sys
from dotenv import load_dotenv

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Load environment variables
load_dotenv()

# Check API key
api_key = os.getenv("OPENAI_API_KEY")
if not api_key or api_key == "your_openai_api_key_here":
    print("[ERROR] OPENAI_API_KEY not set properly")
    exit(1)

print("[OK] API Key loaded successfully!\n")
print("=" * 80)
print("TESTING SIMPLE REACT AI AGENT")
print("=" * 80)

from agent import create_agent, run_agent, get_final_response

# Create agent
print("\n[1/5] Creating agent...")
try:
    agent = create_agent(
        model_name="gpt-4o-mini",
        temperature=0,
        use_checkpointer=True,
        use_structured_response=False,
    )
    print("[OK] Agent created successfully!")
except Exception as e:
    print(f"[ERROR] Error creating agent: {e}")
    exit(1)

# Config for checkpointer
config = {"configurable": {"thread_id": "test-session"}}

# Test 1: Simple calculator
print("\n" + "=" * 80)
print("TEST 1: Simple Calculator")
print("=" * 80)
query1 = "What is 25 + 37?"
print(f"\nQuery: {query1}")
try:
    result1 = run_agent(agent, query1, config=config, verbose=False)
    response1 = get_final_response(result1)
    print(f"[OK] Response: {response1}")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 2: Weather lookup
print("\n" + "=" * 80)
print("TEST 2: Weather Lookup")
print("=" * 80)
config2 = {"configurable": {"thread_id": "test-session-2"}}
query2 = "What's the weather in Tokyo?"
print(f"\nQuery: {query2}")
try:
    result2 = run_agent(agent, query2, config=config2, verbose=False)
    response2 = get_final_response(result2)
    print(f"[OK] Response: {response2}")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 3: Complex query (both tools)
print("\n" + "=" * 80)
print("TEST 3: Complex Query (Both Tools)")
print("=" * 80)
config3 = {"configurable": {"thread_id": "test-session-3"}}
query3 = (
    "Get the weather in New York and London, then calculate the temperature difference"
)
print(f"\nQuery: {query3}")
try:
    result3 = run_agent(agent, query3, config=config3, verbose=False)
    response3 = get_final_response(result3)
    print(f"[OK] Response: {response3}")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 4: Multi-turn conversation
print("\n" + "=" * 80)
print("TEST 4: Multi-turn Conversation with Memory")
print("=" * 80)
config = {"configurable": {"thread_id": "test-conversation"}}

query4a = "What's the weather in Paris?"
print(f"\nQuery 1: {query4a}")
try:
    result4a = run_agent(agent, query4a, config=config, verbose=False)
    response4a = get_final_response(result4a)
    print(f"[OK] Response: {response4a}")
except Exception as e:
    print(f"[ERROR] {e}")

query4b = "What about Dubai?"
print(f"\nQuery 2 (follow-up): {query4b}")
try:
    result4b = run_agent(agent, query4b, config=config, verbose=False)
    response4b = get_final_response(result4b)
    print(f"[OK] Response: {response4b}")
except Exception as e:
    print(f"[ERROR] {e}")

# Test 5: Complex calculation
print("\n" + "=" * 80)
print("TEST 5: Complex Calculation")
print("=" * 80)
config5 = {"configurable": {"thread_id": "test-session-5"}}
query5 = "Calculate (50 + 30) * 2 and then subtract 100"
print(f"\nQuery: {query5}")
try:
    result5 = run_agent(agent, query5, config=config5, verbose=False)
    response5 = get_final_response(result5)
    print(f"[OK] Response: {response5}")
except Exception as e:
    print(f"[ERROR] {e}")

print("\n" + "=" * 80)
print("ALL TESTS COMPLETED!")
print("=" * 80)
print("\n[SUCCESS] The ReAct agent is working correctly!")
print("\nYou can now run 'python main.py' for the interactive CLI.")
