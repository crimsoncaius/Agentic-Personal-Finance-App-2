"""
Main entry point for the Simple ReAct AI Agent CLI application.
"""

import os
import sys
from dotenv import load_dotenv
from agent import create_agent, run_agent, stream_agent, get_final_response


def main():
    """Main function to run the ReAct agent CLI."""
    # Load environment variables
    load_dotenv()

    # Check for OpenAI API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_api_key_here":
        print("❌ Error: OPENAI_API_KEY not found or not set in .env file")
        print("\nPlease:")
        print("1. Get your API key from: https://platform.openai.com/api-keys")
        print("2. Add it to the .env file")
        print("3. Replace 'your_openai_api_key_here' with your actual API key")
        sys.exit(1)

    print("🤖 Simple ReAct AI Agent")
    print("=" * 60)
    print("This agent can help you with:")
    print("  • Calculator operations (math expressions)")
    print("  • Weather lookups (current weather for cities)")
    print("=" * 60)

    # Configuration options
    print("\nConfiguration:")
    print("  [1] Standard mode (default)")
    print("  [2] Verbose mode (show execution trace)")
    print("  [3] Streaming mode (show step-by-step)")
    print("  [4] Structured response mode")

    mode_choice = input("\nSelect mode (1-4, default=1): ").strip() or "1"

    verbose = mode_choice == "2"
    streaming = mode_choice == "3"
    structured = mode_choice == "4"

    print("\nInitializing agent...")

    try:
        # Create the agent with configuration
        agent = create_agent(
            model_name="gpt-4o-mini",
            temperature=0,
            use_checkpointer=True,  # Enable conversation memory
            use_structured_response=structured,
        )
        print("✅ Agent initialized successfully!\n")
    except Exception as e:
        print(f"❌ Error initializing agent: {e}")
        sys.exit(1)

    print("Type your questions below (or 'quit'/'exit' to stop)")
    print("Type 'verbose' to toggle verbose mode")
    print("Type 'stream' to toggle streaming mode")
    print("-" * 60 + "\n")

    # Configuration for checkpointing (maintains conversation context)
    thread_id = "main-conversation"
    config = {"configurable": {"thread_id": thread_id}}

    # Main interaction loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            # Check for exit commands
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            # Toggle verbose mode
            if user_input.lower() == "verbose":
                verbose = not verbose
                print(f"ℹ️  Verbose mode: {'ON' if verbose else 'OFF'}\n")
                continue

            # Toggle streaming mode
            if user_input.lower() == "stream":
                streaming = not streaming
                print(f"ℹ️  Streaming mode: {'ON' if streaming else 'OFF'}\n")
                continue

            # Skip empty input
            if not user_input:
                continue

            # Run the agent
            if streaming:
                print("\n🤔 Agent thinking (streaming)...\n")
                for event in stream_agent(agent, user_input, config=config):
                    print(f"📊 Event: {event}")
                print()
            else:
                print("\n🤔 Agent thinking...\n")
                result_state = run_agent(
                    agent, user_input, config=config, verbose=verbose
                )

                # Display structured response if available
                if "structured_response" in result_state:
                    structured_resp = result_state["structured_response"]
                    print("📋 Structured Response:")
                    print(f"   Answer: {structured_resp.get('answer', 'N/A')}")
                    print(
                        f"   Tools Used: {structured_resp.get('tool_calls_made', 'N/A')}"
                    )
                    print(f"   Confidence: {structured_resp.get('confidence', 'N/A')}")
                    print()

                # Display final response
                response = get_final_response(result_state)
                print(f"🤖 Agent: {response}\n")

            print("-" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}\n")
            print("-" * 60 + "\n")


if __name__ == "__main__":
    main()
