"""
Prompt management system using Jinja2 templates
"""

from datetime import date
from pathlib import Path
from typing import List

from jinja2 import Environment, FileSystemLoader


class PromptManager:
    """Manages prompt templates using Jinja2"""

    def __init__(self, template_dir: str = "prompt_templates"):
        """Initialize the prompt manager with template directory"""
        # Get the backend directory path
        backend_dir = Path(__file__).parent.parent
        template_path = backend_dir / template_dir

        # Set up Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_path)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load v3 react agent system prompt template
        try:
            self.react_agent_system_prompt_template = self.env.get_template(
                "react_agent_system_prompt.j2"
            )
        except Exception:
            self.react_agent_system_prompt_template = None

    def generate_react_agent_system_prompt(
        self,
        current_date: date = None,
        categories: List[str] = None,
    ) -> str:
        """Generate system prompt for the ReAct agent (NLP Service V3).

        Args:
            current_date: Current date for date handling context
            categories: List of available category names

        Returns:
            Rendered system prompt string
        """
        if current_date is None:
            current_date = date.today()
        if categories is None:
            categories = []

        if getattr(self, "react_agent_system_prompt_template", None):
            return self.react_agent_system_prompt_template.render(
                current_date=current_date.isoformat(),
                categories=categories,
            )

        # Fallback: return a basic hardcoded prompt
        return f"""You are a helpful financial assistant helping users track their income and expenses.

**Current Date:** {current_date.isoformat()}

**Available Categories:**
{', '.join(categories)}

Use the available tools to fetch, create, and update financial entries."""
