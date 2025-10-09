"""
ReAct Agent implementation using LangGraph's create_react_agent.
"""

from typing import TypedDict, Optional, List
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver
from tools import calculator, get_weather

# Fix Pydantic compatibility issue
try:
    ChatOpenAI.model_rebuild()
except Exception:
    pass


# -------- Custom State Schema (Optional) --------
class AgentState(TypedDict, total=False):
    """Custom agent state schema."""

    messages: list
    remaining_steps: int


# -------- Structured Response Schema --------
class FinalAnswer(TypedDict):
    """Schema for the final structured response from the agent."""

    answer: str
    tool_calls_made: Optional[List[str]]
    confidence: Optional[str]


def create_agent(
    model_name: str = "gpt-4o-mini",
    temperature: float = 0,
    use_checkpointer: bool = True,
    use_structured_response: bool = False,
    custom_prompt: Optional[str] = None,
):
    """
    Create a ReAct agent with calculator and weather tools.

    Args:
        model_name: The OpenAI model to use (default: "gpt-4o-mini")
        temperature: The temperature for the model (default: 0 for deterministic responses)
        use_checkpointer: Whether to use memory checkpointing for multi-turn conversations (default: True)
        use_structured_response: Whether to use structured response format (default: False)
        custom_prompt: Custom system prompt for the agent (default: None)

    Returns:
        A compiled LangGraph agent ready to use.
    """
    # Initialize the language model
    model = ChatOpenAI(model=model_name, temperature=temperature)

    # Create the list of tools
    tools = [calculator, get_weather]

    # Default prompt
    default_prompt = (
        "You are a helpful assistant with access to calculator and weather tools. "
        "Use tools when needed to answer questions accurately. "
        "Think step-by-step, keep messages concise, and cite tool outputs in your answers."
    )

    prompt = custom_prompt if custom_prompt else default_prompt

    # Optional checkpointer for conversation memory
    checkpointer = MemorySaver() if use_checkpointer else None

    # Optional structured response format
    response_format = FinalAnswer if use_structured_response else None

    # Create the ReAct agent with enhanced configuration
    agent = create_react_agent(
        model=model,
        tools=tools,
        prompt=prompt,
        response_format=response_format,
        checkpointer=checkpointer,
        # You can also add:
        # pre_model_hook=...,
        # post_model_hook=...,
        # state_schema=AgentState,
        # interrupt_before=[...],
        # interrupt_after=[...],
    )

    return agent


def run_agent(agent, query: str, config: Optional[dict] = None, verbose: bool = True):
    """
    Run the agent with a given query.

    Args:
        agent: The compiled agent graph
        query: The user's question or request
        config: Optional configuration dict (e.g., for thread_id with checkpointing)
        verbose: Whether to print intermediate steps (default: True)

    Returns:
        The complete result state from the agent.
    """
    # Prepare input
    initial_input = {"messages": [{"role": "user", "content": query}]}

    # Invoke the agent with optional config
    result_state = agent.invoke(initial_input, config=config)

    # Extract messages
    messages = result_state["messages"]

    if verbose:
        print("\n" + "=" * 80)
        print("AGENT EXECUTION TRACE")
        print("=" * 80)
        for i, msg in enumerate(messages, 1):
            print(f"\n--- Message {i} ({msg.__class__.__name__}) ---")
            if hasattr(msg, "content") and msg.content:
                print(f"Content: {msg.content}")
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                print(f"Tool Calls: {msg.tool_calls}")
            if hasattr(msg, "name") and msg.name:
                print(f"Tool Name: {msg.name}")
        print("\n" + "=" * 80 + "\n")

    return result_state


def stream_agent(agent, query: str, config: Optional[dict] = None):
    """
    Stream the agent execution step-by-step.

    Args:
        agent: The compiled agent graph
        query: The user's question or request
        config: Optional configuration dict (e.g., for thread_id with checkpointing)

    Yields:
        Events from the agent execution.
    """
    # Prepare input
    initial_input = {"messages": [{"role": "user", "content": query}]}

    # Stream events
    for event in agent.stream(initial_input, config=config, stream_mode="updates"):
        yield event


def get_final_response(result_state: dict) -> str:
    """
    Extract the final response from the agent result state.

    Args:
        result_state: The result state from agent.invoke()

    Returns:
        The final response as a string.
    """
    messages = result_state.get("messages", [])

    # Check for structured response first
    if "structured_response" in result_state:
        structured = result_state["structured_response"]
        return structured.get("answer", "No answer provided.")

    # Otherwise get the last AI message
    for msg in reversed(messages):
        if (
            hasattr(msg, "content")
            and msg.__class__.__name__ == "AIMessage"
            and msg.content
        ):
            return msg.content

    return "No response generated."
