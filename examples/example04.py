"""
Author: L. Saetta
Date Modified: 2026-05-12
License: MIT
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
from datetime import date

from dotenv import load_dotenv

from examples.common import build_provider_from_environment, configure_logging
from services.assistant_api.nutrition.analysis import (
    NutritionAnalysisSettings,
    NutritionAnalysisSubAgent,
)
from services.assistant_api.nutrition.diary import NutritionDiaryService
from services.assistant_api.nutrition.plan import NutritionPlanService
from services.assistant_api.orchestration.training_data import LocalTrainingDataClient
from services.shared.llm import get_inference_client


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the nutrition analysis subagent."""
    parser = argparse.ArgumentParser(
        description=(
            "Analyze food diary adherence against the current nutrition plan "
            "and Garmin workouts for an inclusive date range."
        )
    )
    parser.add_argument("begin_date", help="Inclusive start date in YYYY-MM-DD format.")
    parser.add_argument("end_date", help="Inclusive end date in YYYY-MM-DD format.")
    parser.add_argument(
        "--database-path",
        default=None,
        help=(
            "SQLite nutrition database path. Defaults to NUTRITION_DB_PATH or "
            "./data/garmin_ai_coach.db."
        ),
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="OCI hosted model id. Defaults to OCI_MODEL_ID or openai.gpt-5.4.",
    )
    return parser.parse_args()


async def run_analysis(args: argparse.Namespace) -> None:
    """Create the nutrition subagent and print the generated report."""
    load_dotenv()
    database_path = (
        args.database_path
        or os.getenv("NUTRITION_DB_PATH")
        or "./data/garmin_ai_coach.db"
    )
    model_id = args.model_id or os.getenv("OCI_MODEL_ID", "openai.gpt-5.4")

    subagent = NutritionAnalysisSubAgent.create(
        plan_service=NutritionPlanService(database_path),
        diary_service=NutritionDiaryService(database_path),
        training_client=LocalTrainingDataClient(build_provider_from_environment()),
        inference_client=get_inference_client(),
        settings=NutritionAnalysisSettings(model_id=model_id),
    )
    result = await subagent.analyze(
        begin_date=date.fromisoformat(args.begin_date),
        end_date=date.fromisoformat(args.end_date),
    )

    print(result.report)
    print()
    print("---")
    print(f"Plan: {result.plan_filename}")
    print(f"Diary entries: {result.diary_entry_count}")
    print(f"Training days: {result.training_day_count}")
    if result.missing_diary_dates:
        missing_days = ", ".join(
            item.isoformat() for item in result.missing_diary_dates
        )
        print(f"Missing diary days: {missing_days}")
    if result.token_usage is not None:
        print(f"Input tokens: {result.token_usage.input_tokens}")
        print(f"Output tokens: {result.token_usage.output_tokens}")
        print(f"Total tokens: {result.token_usage.total_tokens}")


def main() -> None:
    """Run the command-line nutrition analysis example."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    configure_logging()
    asyncio.run(run_analysis(parse_args()))


if __name__ == "__main__":
    main()
