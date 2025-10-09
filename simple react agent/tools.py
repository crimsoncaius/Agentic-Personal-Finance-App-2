"""
Custom tools for the ReAct agent.
"""
from langchain_core.tools import tool
import random


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a mathematical expression and return the result.
    
    Args:
        expression: A mathematical expression to evaluate (e.g., "2 + 2", "10 * 5", "100 / 4")
    
    Returns:
        The result of the calculation as a string.
    
    Examples:
        - "2 + 2" -> "4"
        - "10 * 5" -> "50"
        - "100 / 4" -> "25.0"
    """
    try:
        # Use eval with limited scope for safety (only allow basic math operations)
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "pow": pow,
        }
        result = eval(expression, {"__builtins__": {}}, allowed_names)
        return str(result)
    except Exception as e:
        return f"Error calculating '{expression}': {str(e)}"


@tool
def get_weather(city: str) -> str:
    """
    Get the current weather for a specified city.
    
    Args:
        city: The name of the city to get weather for (e.g., "New York", "London", "Tokyo")
    
    Returns:
        A description of the current weather conditions in the city.
    
    Examples:
        - "New York" -> Returns weather information for New York
        - "London" -> Returns weather information for London
    """
    # Mock weather data for demonstration
    weather_conditions = ["sunny", "cloudy", "rainy", "partly cloudy", "windy", "foggy"]
    
    # Predefined weather for some cities for consistency in demos
    city_weather_map = {
        "new york": {"temp": 72, "condition": "partly cloudy"},
        "london": {"temp": 61, "condition": "rainy"},
        "tokyo": {"temp": 78, "condition": "sunny"},
        "paris": {"temp": 68, "condition": "cloudy"},
        "sydney": {"temp": 75, "condition": "sunny"},
        "moscow": {"temp": 45, "condition": "cloudy"},
        "dubai": {"temp": 95, "condition": "sunny"},
        "singapore": {"temp": 88, "condition": "partly cloudy"},
    }
    
    city_lower = city.lower().strip()
    
    if city_lower in city_weather_map:
        weather = city_weather_map[city_lower]
        temp = weather["temp"]
        condition = weather["condition"]
    else:
        # Generate random weather for unknown cities
        temp = random.randint(50, 90)
        condition = random.choice(weather_conditions)
    
    return f"The weather in {city} is currently {condition} with a temperature of {temp}°F."

