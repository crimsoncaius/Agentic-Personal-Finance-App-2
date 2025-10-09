# Simple ReAct AI Agent

A command-line ReAct (Reasoning + Acting) agent built with LangGraph and OpenAI, featuring calculator and weather lookup capabilities.

## Features

- **Calculator Tool**: Perform mathematical calculations
- **Weather Tool**: Get current weather information for cities
- **ReAct Pattern**: The agent reasons about which tools to use and how to combine them
- **Interactive CLI**: Easy-to-use command-line interface

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

1. Get your OpenAI API key from [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Open the `.env` file
3. Replace `your_openai_api_key_here` with your actual API key:

```
OPENAI_API_KEY=sk-proj-...your-actual-key...
```

### 3. Run the Agent

```bash
python main.py
```

## Usage

### Interactive CLI

Run the main application:

```bash
python main.py
```

You'll be prompted to select a mode:

- **[1] Standard mode**: Normal operation (default)
- **[2] Verbose mode**: Shows full execution trace with all messages
- **[3] Streaming mode**: Shows step-by-step execution events
- **[4] Structured response mode**: Returns structured output with answer, tools used, and confidence

Once running, simply type your questions and press Enter. The agent will automatically determine which tools to use.

**Special commands:**

- `quit` or `exit` - Stop the agent
- `verbose` - Toggle verbose mode on/off
- `stream` - Toggle streaming mode on/off

### Programmatic Usage

See `example_usage.py` for comprehensive examples:

```bash
python example_usage.py
```

This demonstrates:

- Simple one-shot queries
- Multi-turn conversations with memory
- Streaming mode
- Structured responses
- Batch testing

## Test Queries

Here's a comprehensive list of test queries to explore the agent's capabilities:

### Calculator Tool Tests

**Basic Arithmetic:**

```
What is 25 + 37?
Calculate 144 divided by 12
What's 15 times 8?
Subtract 99 from 200
```

**Complex Expressions:**

```
Calculate (50 + 30) * 2
What is 100 / 4 + 25?
Evaluate 2 * 3 + 4 * 5
What's the result of 1000 - 250 - 150?
```

**Advanced Math:**

```
What is 2 to the power of 10?
Calculate the square root equivalent: what number times itself equals 144?
What's the absolute value of -42?
```

### Weather Tool Tests

**Simple Weather Queries:**

```
What's the weather in New York?
Tell me the weather in London
How's the weather in Tokyo today?
What's the current weather in Paris?
```

**Various Cities:**

```
What's the weather like in Sydney?
Check the weather in Dubai
Get me the weather for Moscow
What's the temperature in Singapore?
```

**Unknown Cities (Random Weather):**

```
What's the weather in Seattle?
Tell me the weather in Berlin
How's the weather in Mumbai?
```

### Multi-Step Reasoning (Combining Both Tools)

**Calculation + Weather:**

```
What's the weather in New York and London? Calculate the temperature difference.
If the temperature in Tokyo is 78°F, what is that minus 32?
Get the weather for Paris and Dubai, then calculate the average temperature.
```

**Complex Reasoning:**

```
I'm planning a trip. Check the weather in New York and Tokyo. If the temperature difference is more than 10 degrees, calculate exactly how much warmer one is than the other.
```

**Conditional Logic:**

```
What's 50 + 25? Also, is it sunny in Sydney today?
Calculate 100 / 5. Then tell me if the weather in London is rainy.
```

### Conversational Queries

**Natural Language:**

```
I need to know if I should bring an umbrella to London tomorrow
How warm is it in Dubai compared to room temperature (72 degrees)?
If I have 15 apples and give away 7, how many do I have left?
```

**Multi-Part Questions:**

```
What's 25 times 4, and also what's the weather like in Paris?
Can you tell me the weather in Singapore and also calculate 88 - 32?
```

### Edge Cases & Error Handling

**Invalid Math:**

```
Calculate 10 divided by 0
What is the square root of -16?
Evaluate this expression: 5 + + 3
```

**Ambiguous Requests:**

```
What's the weather?
Calculate something for me
Tell me about New York
```

**No Tool Needed:**

```
Hello, how are you?
What can you help me with?
Tell me a joke
```

## Architecture

### Files

- `main.py` - Interactive CLI application entry point
- `agent.py` - ReAct agent creation and execution logic
- `tools.py` - Calculator and weather tool implementations
- `example_usage.py` - Comprehensive usage examples (simple queries, multi-turn, streaming)
- `requirements.txt` - Python dependencies
- `.env` - Environment configuration (API keys)

### How It Works

1. **User Query**: You type a question
2. **Agent Reasoning**: The LLM analyzes your query and decides which tool(s) to use
3. **Tool Execution**: The agent calls the appropriate tools with the right parameters
4. **Response Generation**: The agent combines tool outputs into a natural language response

### Key Features

- **Checkpointing**: Maintains conversation context across multiple turns using `MemorySaver`
- **Structured Responses**: Optional structured output format with `FinalAnswer` schema
- **Streaming**: Stream agent execution step-by-step to see the reasoning process
- **Verbose Mode**: Toggle execution trace to see all intermediate messages and tool calls
- **Custom Prompts**: Customize the system prompt to change agent behavior

## Customization

### Change the Model

Edit `main.py` or `agent.py` to use a different OpenAI model:

```python
agent = create_agent(model_name="gpt-4o", temperature=0)
```

Available models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`, `gpt-3.5-turbo`

### Add More Tools

Create new tools in `tools.py` using the `@tool` decorator:

```python
from langchain_core.tools import tool

@tool
def your_custom_tool(param: str) -> str:
    """
    Description of what your tool does.

    Args:
        param: Description of the parameter

    Returns:
        Description of the return value
    """
    # Your implementation here
    return "result"
```

Then add it to the tools list in `agent.py`:

```python
from tools import calculator, get_weather, your_custom_tool

tools = [calculator, get_weather, your_custom_tool]
```

### Customize the Agent Prompt

Pass a custom prompt when creating the agent:

```python
agent = create_agent(
    model_name="gpt-4o-mini",
    custom_prompt="You are a specialized assistant focused on mathematical and meteorological queries."
)
```

### Enable Features

The `create_agent` function supports multiple configuration options:

```python
agent = create_agent(
    model_name="gpt-4o-mini",
    temperature=0,
    use_checkpointer=True,        # Enable conversation memory
    use_structured_response=True,  # Enable structured output
    custom_prompt="Your custom prompt here"
)
```

### Advanced: Hooks and Interrupts

You can add hooks and interrupts in `agent.py`:

```python
agent = create_react_agent(
    model=model,
    tools=tools,
    prompt=prompt,
    pre_model_hook=your_pre_hook,   # Run before model call
    post_model_hook=your_post_hook, # Run after model call
    interrupt_before=["tools"],     # Interrupt before tool execution
    interrupt_after=["agent"],      # Interrupt after agent reasoning
)
```

## Troubleshooting

**Error: OPENAI_API_KEY not found**

- Make sure you've added your API key to the `.env` file
- Ensure the key starts with `sk-`

**Import errors**

- Run `pip install -r requirements.txt` to install all dependencies

**Rate limit errors**

- You may be hitting OpenAI's rate limits
- Wait a moment and try again
- Consider upgrading your OpenAI plan

## License

MIT License - feel free to use and modify as needed!

## Learn More

- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangChain Documentation](https://python.langchain.com/)
- [OpenAI API Documentation](https://platform.openai.com/docs/)
