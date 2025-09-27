"""
Prompt management system using Jinja2 templates
"""

import os
from datetime import date
from pathlib import Path
from typing import List, Dict, Any

from jinja2 import Environment, FileSystemLoader, Template


class PromptManager:
    """Manages prompt templates using Jinja2"""

    def __init__(self, template_dir: str = "prompt templates"):
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

        # Load templates
        self.router_template = self.env.get_template("router_prompt.j2")
        self.read_template = self.env.get_template("read_prompt.j2")
        self.write_template = self.env.get_template("write_prompt.j2")

    def _get_date_examples(self, current_date: date) -> List[Dict[str, Any]]:
        """Generate date examples for relative date parsing"""
        # Calculate relative dates
        yesterday = (
            current_date.replace(day=current_date.day - 1)
            if current_date.day > 1
            else (
                current_date.replace(month=current_date.month - 1, day=28)
                if current_date.month > 1
                else current_date.replace(year=current_date.year - 1, month=12, day=28)
            )
        )

        last_week = (
            current_date.replace(day=current_date.day - 7)
            if current_date.day > 7
            else (
                current_date.replace(
                    month=current_date.month - 1, day=current_date.day + 21
                )
                if current_date.month > 1
                else current_date.replace(
                    year=current_date.year - 1, month=12, day=current_date.day + 21
                )
            )
        )

        this_month = current_date.replace(day=1)

        return [
            {"name": "yesterday", "value": yesterday.isoformat()},
            {"name": "last week", "value": f"date_from: {last_week.isoformat()}"},
            {"name": "this month", "value": f"date_from: {this_month.isoformat()}"},
            {"name": "today", "value": current_date.isoformat()},
        ]

    def generate_router_prompt(self, user_input: str) -> str:
        """Generate router prompt"""
        return self.router_template.render(user_input=user_input)

    def generate_read_prompt(
        self, user_input: str, current_date: date = None, categories: List[str] = None
    ) -> str:
        """Generate read prompt with date examples and categories"""
        if current_date is None:
            current_date = date.today()

        date_examples = self._get_date_examples(current_date)

        return self.read_template.render(
            user_input=user_input,
            current_date=current_date.isoformat(),
            date_examples=date_examples,
            categories=categories or [],
        )

    def generate_write_prompt(
        self, user_input: str, categories: List[str], current_date: date = None
    ) -> str:
        """Generate write prompt with categories and date examples"""
        if current_date is None:
            current_date = date.today()

        date_examples = self._get_date_examples(current_date)
        category_list = ", ".join(categories)

        return self.write_template.render(
            user_input=user_input,
            current_date=current_date.isoformat(),
            categories=category_list,
            date_examples=date_examples,
        )
