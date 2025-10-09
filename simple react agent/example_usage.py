"""
Example usage of the ReAct agent showing different features.
Run this after setting up your .env file with OPENAI_API_KEY.
"""

from typing import TypedDict, Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import calculator, get_weather

# Load environment variables
load_dotenv()


# -------- 1) Define tools --------
# Tools are imported from tools.py: calculator and get_weather
tools = [calculator, get_weather]


# -------- 2) Custom state schema (Optional) --------
# create_react_agent already provides a default AgentState with `messages` and `remaining_steps`.
# If you need extra keys, you can define your own state schema:
class MyAgentState(TypedDict, total=False):
    messages: list
    remaining_steps: int


# -------- 3) Structured response schema (Optional) --------
# Define the structure you want the agent to return
class FinalAnswer(TypedDict):
    answer: str
    tool_calls_made: Optional[List[str]]
    confidence: Optional[str]


# -------- 4) Model --------
# You can pass a model id string or a ChatModel instance
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# -------- 5) Checkpointing / memory (Optional) --------
# Enables multi-turn conversations with memory
checkpointer = MemorySaver()  # Volatile in-memory checkpoints


# -------- 6) Create the agent graph --------
agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=(
        "You are a helpful assistant with access to calculator and weather tools. "
        "Use tools when needed to answer questions accurately. "
        "Think step-by-step, keep messages concise, and cite tool outputs in your answers."
    ),
    response_format=FinalAnswer,  # optional: structured output
    checkpointer=checkpointer,  # optional: conversation memory
    # You can also specify:
    # pre_model_hook=...,
    # post_model_hook=...,
    # state_schema=MyAgentState,
    # interrupt_before=[...],
    # interrupt_after=[...],
    # version="v2" (default)
)


# -------- 7) Run the agent --------
print("=" * 80)
print("EXAMPLE 1: Simple Query")
print("=" * 80)

initial_input = {
    "messages": [
        {"role": "user", "content": "What's the weather in Tokyo and what is 78 - 32?"}
    ]
}

# One-shot invoke
result_state = agent.invoke(initial_input)

# The compiled graph returns a state dict with `messages`
final_messages = result_state["messages"]
print("\n=== FINAL MESSAGE ===")
print(final_messages[-1].content)

# If `response_format` was given, you'll also have `structured_response`
if "structured_response" in result_state:
    print("\n=== STRUCTURED RESPONSE ===")
    print(result_state["structured_response"])


# -------- 8) Multi-turn conversation with memory --------
print("\n\n" + "=" * 80)
print("EXAMPLE 2: Multi-turn Conversation")
print("=" * 80)

# Use thread_id to maintain conversation context
config = {"configurable": {"thread_id": "conversation-1"}}

# First query
result1 = agent.invoke(
    {"messages": [{"role": "user", "content": "What's the weather in New York?"}]},
    config=config,
)
print("\nUser: What's the weather in New York?")
print(f"Agent: {result1['messages'][-1].content}")

# Follow-up query (agent remembers context)
result2 = agent.invoke(
    {"messages": [{"role": "user", "content": "What about London?"}]}, config=config
)
print("\nUser: What about London?")
print(f"Agent: {result2['messages'][-1].content}")


# -------- 9) Streaming mode --------
print("\n\n" + "=" * 80)
print("EXAMPLE 3: Streaming")
print("=" * 80)

streaming_input = {
    "messages": [
        {
            "role": "user",
            "content": "Calculate 25 * 4 and tell me if it's sunny in Dubai",
        }
    ]
}

print("\nUser: Calculate 25 * 4 and tell me if it's sunny in Dubai\n")
print("Agent (streaming):")

for event in agent.stream(streaming_input, stream_mode="updates"):
    # Each event shows updates to the graph state
    for node_name, node_output in event.items():
        print(f"\n--- Node: {node_name} ---")
        if "messages" in node_output:
            for msg in node_output["messages"]:
                print(
                    f"  {msg.__class__.__name__}: {msg.content if hasattr(msg, 'content') else msg}"
                )


# -------- 10) Test Queries --------
print("\n\n" + "=" * 80)
print("QUICK TEST QUERIES")
print("=" * 80)

test_queries = [
    "What is 144 / 12?",
    "What's the weather in Paris?",
    "Get the weather in Sydney and Moscow, then calculate the temperature difference",
]

for i, query in enumerate(test_queries, 1):
    print(f"\n[Test {i}] {query}")
    result = agent.invoke({"messages": [{"role": "user", "content": query}]})
    print(f"→ {result['messages'][-1].content}")

print("\n" + "=" * 80)
print("✅ All examples completed!")
print("=" * 80)
