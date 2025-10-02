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

    def __init__(self, template_dir: str = "templates"):
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

        # Load response templates
        self.read_response_template = self.env.get_template("read_response.j2")
        self.write_response_template = self.env.get_template("write_response.j2")
        self.unsure_response_template = self.env.get_template("unsure_response.j2")

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

    def generate_read_response_prompt(
        self,
        user_input: str,
        entries: List[Dict],
        query_params: Any,
        current_date: date = None,
    ) -> str:
        """Generate prompt for LLM to create user-friendly response for read operations"""
        if current_date is None:
            current_date = date.today()

        # Calculate totals and counts
        total_entries = len(entries)
        expense_entries = [e for e in entries if e.get("direction") == "expense"]
        income_entries = [e for e in entries if e.get("direction") == "income"]

        expense_count = len(expense_entries)
        income_count = len(income_entries)
        expense_total = sum(float(e.get("amount", 0)) for e in expense_entries)
        income_total = sum(float(e.get("amount", 0)) for e in income_entries)
        net_total = income_total - expense_total

        # Prepare query params for template
        params_dict = {
            "date_from": getattr(query_params, "date_from", None),
            "date_to": getattr(query_params, "date_to", None),
            "direction": getattr(query_params, "direction", None),
            "category_id": getattr(query_params, "category_id", None),
            "amount_min": getattr(query_params, "amount_min", None),
            "amount_max": getattr(query_params, "amount_max", None),
            "q": getattr(query_params, "q", None),
        }

        return self.read_response_template.render(
            user_input=user_input,
            query_params=params_dict,
            current_date=current_date.isoformat(),
            total_entries=total_entries,
            expense_count=expense_count,
            income_count=income_count,
            expense_total=f"{expense_total:.2f}",
            income_total=f"{income_total:.2f}",
            net_total=f"{net_total:.2f}",
            date_from=params_dict["date_from"],
            date_to=params_dict["date_to"],
        )

    def generate_write_response_prompt(
        self, user_input: str, entry: Dict, current_date: date = None
    ) -> str:
        """Generate prompt for LLM to create user-friendly response for write operations"""
        if current_date is None:
            current_date = date.today()

        amount = entry.get("amount", 0)
        direction = entry.get("direction", "")
        description = entry.get("description", "")
        category_name = entry.get("category", {}).get("name", "Unknown")
        entry_date = entry.get("entry_date", "")

        return self.write_response_template.render(
            user_input=user_input,
            current_date=current_date.isoformat(),
            amount=f"{float(amount):.2f}",
            direction=direction,
            description=description,
            category_name=category_name,
            entry_date=entry_date,
        )

    def generate_unsure_response_prompt(
        self, user_input: str, current_date: date = None
    ) -> str:
        """Generate prompt for LLM to create helpful response for unclear requests"""
        if current_date is None:
            current_date = date.today()

        return self.unsure_response_template.render(
            user_input=user_input,
            current_date=current_date.isoformat(),
        )
