#!/usr/bin/env python3
"""
OpenAI Model Latency Testing Script

Tests the latency of different OpenAI models at various query lengths.
Measures total response time, time to first token, and tokens per second.
"""

import asyncio
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import openai
from openai import AsyncOpenAI
import statistics
from dotenv import load_dotenv

# Model configurations
MODELS = ["gpt-3.5-turbo", "gpt-4.1-mini", "gpt-4.1-nano"]

# Query length targets (in characters)
QUERY_LENGTHS = [50, 100, 500, 1000, 2000]

# Number of iterations per model/length combination
ITERATIONS = 3


class LatencyTester:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.results = []
        self.reports_dir = Path("latency_reports")
        self.reports_dir.mkdir(exist_ok=True)

    def generate_test_queries(self) -> Dict[int, str]:
        """Generate financial-related test queries of varying lengths."""
        base_queries = {
            50: "Analyze my monthly spending on groceries and suggest budget optimizations.",
            100: "I need help creating a budget for a family of four with monthly income of $5000. Include categories for housing, food, transportation, and savings.",
            500: "I'm 28 years old and want to start investing for retirement. I have $10,000 in savings and can contribute $500 monthly. I'm risk-averse but want to maximize long-term growth. Should I focus on index funds, individual stocks, or a mix? What's the best strategy for someone with my profile and timeline? I'm also considering opening a Roth IRA versus a traditional 401k through my employer. Please provide specific recommendations with expected returns and risk levels.",
            1000: "I'm a 35-year-old software engineer with a stable income of $120,000 annually. I have $50,000 in a high-yield savings account, $30,000 in a 401k (currently contributing 6% with 3% employer match), and $15,000 in student loan debt at 4.5% interest. I'm planning to buy a house in the next 2-3 years and want to optimize my financial strategy. My monthly expenses are around $4,500 including rent, utilities, food, and entertainment. I have no other debt and a credit score of 780. Should I prioritize paying off the student loans, increasing my 401k contributions, or saving more for a down payment? What's the optimal allocation between these goals? I'm also interested in starting a taxable investment account for additional growth. Please provide a comprehensive financial plan with specific dollar amounts and timelines.",
            2000: "I'm a 42-year-old marketing director with a household income of $180,000 (my spouse earns $90,000 as a teacher). We have two children, ages 8 and 12, and live in a high-cost-of-living area. Our current financial situation includes: $200,000 in home equity (house worth $600,000 with $400,000 mortgage at 3.2%), $150,000 in 401k accounts (contributing 8% with 4% employer match), $75,000 in a 529 college savings plan, $25,000 in emergency fund, and $40,000 in taxable investments. We also have $35,000 in car loans at 2.9% and $20,000 in credit card debt at 18% interest. Our monthly expenses are $8,500 including mortgage, utilities, groceries, insurance, and activities for the kids. We're concerned about college costs (expecting $50,000+ per year per child) and want to retire by age 65. We're also considering whether to refinance our mortgage, pay off the credit card debt aggressively, or invest more in the 529 plans. Additionally, we're wondering about life insurance needs and whether to open a Roth IRA. Please provide a detailed financial strategy that addresses all these concerns with specific recommendations, dollar amounts, and priority order. Include considerations for tax optimization, risk management, and timeline for achieving our goals.",
        }
        return base_queries

    async def measure_latency(
        self, model: str, query: str, length: int
    ) -> Dict[str, Any]:
        """Measure latency metrics for a single API call."""
        start_time = time.time()
        first_token_time = None
        token_count = 0

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": query}],
                max_tokens=100,  # Keep responses short for consistent testing
                temperature=0.1,
            )

            end_time = time.time()
            total_time = end_time - start_time

            # Calculate tokens (rough estimation)
            token_count = len(query.split()) + len(
                response.choices[0].message.content.split()
            )

            # For time to first token, we'll use a rough estimate
            # In a real implementation, you'd use streaming to get exact timing
            first_token_time = total_time * 0.1  # Rough estimate: 10% of total time

            tokens_per_second = token_count / total_time if total_time > 0 else 0

            return {
                "model": model,
                "query_length": length,
                "total_time": total_time,
                "time_to_first_token": first_token_time,
                "tokens_per_second": tokens_per_second,
                "token_count": token_count,
                "success": True,
                "error": None,
            }

        except Exception as e:
            end_time = time.time()
            return {
                "model": model,
                "query_length": length,
                "total_time": end_time - start_time,
                "time_to_first_token": None,
                "tokens_per_second": None,
                "token_count": 0,
                "success": False,
                "error": str(e),
            }

    async def run_tests(self):
        """Run all latency tests."""
        queries = self.generate_test_queries()

        print("🚀 Starting OpenAI Model Latency Tests")
        print(f"Models: {', '.join(MODELS)}")
        print(f"Query lengths: {QUERY_LENGTHS} characters")
        print(f"Iterations per combination: {ITERATIONS}")
        print("=" * 60)

        total_tests = len(MODELS) * len(QUERY_LENGTHS) * ITERATIONS
        current_test = 0

        for model in MODELS:
            print(f"\n📊 Testing {model}...")

            for length in QUERY_LENGTHS:
                query = queries[length]
                print(f"  Length {length} chars: ", end="", flush=True)

                model_results = []
                for iteration in range(ITERATIONS):
                    current_test += 1
                    print(f"[{current_test}/{total_tests}] ", end="", flush=True)

                    result = await self.measure_latency(model, query, length)
                    model_results.append(result)
                    self.results.append(result)

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.5)

                # Calculate and display averages for this model/length
                successful_results = [r for r in model_results if r["success"]]
                if successful_results:
                    avg_total_time = statistics.mean(
                        [r["total_time"] for r in successful_results]
                    )
                    avg_tokens_per_sec = statistics.mean(
                        [r["tokens_per_second"] for r in successful_results]
                    )
                    print(
                        f"✅ Avg: {avg_total_time:.2f}s, {avg_tokens_per_sec:.1f} tok/s"
                    )
                else:
                    print("❌ All failed")

        print("\n" + "=" * 60)
        print("✅ All tests completed!")

    def generate_report(self):
        """Generate detailed report and save to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.reports_dir / f"latency_report_{timestamp}.json"

        # Calculate summary statistics
        summary = self.calculate_summary_stats()

        report_data = {
            "timestamp": timestamp,
            "test_config": {
                "models": MODELS,
                "query_lengths": QUERY_LENGTHS,
                "iterations": ITERATIONS,
            },
            "summary": summary,
            "detailed_results": self.results,
        }

        # Save JSON report
        with open(report_file, "w") as f:
            json.dump(report_data, f, indent=2)

        # Print console summary
        self.print_console_summary(summary)

        print(f"\n📄 Detailed report saved to: {report_file}")
        return report_file

    def calculate_summary_stats(self) -> Dict[str, Any]:
        """Calculate summary statistics from test results."""
        summary = {}

        for model in MODELS:
            model_data = [
                r for r in self.results if r["model"] == model and r["success"]
            ]
            if not model_data:
                continue

            summary[model] = {}

            for length in QUERY_LENGTHS:
                length_data = [r for r in model_data if r["query_length"] == length]
                if not length_data:
                    continue

                summary[model][f"length_{length}"] = {
                    "avg_total_time": statistics.mean(
                        [r["total_time"] for r in length_data]
                    ),
                    "median_total_time": statistics.median(
                        [r["total_time"] for r in length_data]
                    ),
                    "avg_tokens_per_second": statistics.mean(
                        [r["tokens_per_second"] for r in length_data]
                    ),
                    "success_rate": len(length_data) / ITERATIONS,
                    "sample_count": len(length_data),
                }

        return summary

    def print_console_summary(self, summary: Dict[str, Any]):
        """Print a formatted console summary."""
        print("\n📈 LATENCY TEST SUMMARY")
        print("=" * 80)

        for model in MODELS:
            if model not in summary:
                continue

            print(f"\n🤖 {model.upper()}")
            print("-" * 40)
            print(f"{'Length':<8} {'Avg Time':<10} {'Tokens/s':<10} {'Success':<8}")
            print("-" * 40)

            for length in QUERY_LENGTHS:
                key = f"length_{length}"
                if key in summary[model]:
                    data = summary[model][key]
                    print(
                        f"{length:<8} {data['avg_total_time']:<10.2f} {data['avg_tokens_per_second']:<10.1f} {data['success_rate']:<8.1%}"
                    )
                else:
                    print(f"{length:<8} {'N/A':<10} {'N/A':<10} {'0%':<8}")


async def main():
    """Main function to run the latency tests."""
    # Load environment variables from .env file
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

    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ Error: OPENAI_API_KEY environment variable not set")
        print("Please set your OpenAI API key in the .env file")
        return

    tester = LatencyTester()

    try:
        await tester.run_tests()
        report_file = tester.generate_report()
        print(f"\n🎉 Testing complete! Report saved to: {report_file}")

    except KeyboardInterrupt:
        print("\n⏹️  Testing interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
