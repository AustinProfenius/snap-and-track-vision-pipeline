"""
Main pipeline orchestrator - single source of truth for alignment.

This module provides run_once() which is called identically by both
web app and batch harness to ensure zero behavioral drift.
"""
import time
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import sys

# Add nutritionverse-tests to path
nutritionverse_path = Path(__file__).parent.parent / "nutritionverse-tests"
if str(nutritionverse_path) not in sys.path:
    sys.path.insert(0, str(nutritionverse_path))

from pipeline.schemas import (
    AlignmentRequest,
    AlignmentResult,
    FoodAlignment,
    Totals,
    TelemetryEvent,
    DetectedFood
)
from pipeline.config_loader import PipelineConfig
from pipeline.fdc_index import FDCIndex

# Import existing alignment engine
from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion
from src.adapters.alignment_adapter import AlignmentEngineAdapter


def run_once(
    request: AlignmentRequest,
    cfg: PipelineConfig,
    fdc_index: FDCIndex,
    *,
    allow_stage_z: bool = False,
    code_git_sha: str
) -> AlignmentResult:
    """
    Run complete alignment pipeline: normalize → align → convert → aggregate.

    This is the SINGLE SOURCE OF TRUTH called by both web app and batch harness.

    Args:
        request: AlignmentRequest with image_id and detected foods
        cfg: PipelineConfig with all externalized configs
        fdc_index: FDCIndex wrapper with versioned database
        allow_stage_z: Enable Stage-Z branded fallback (default False)
        code_git_sha: Git SHA for code version tracking

    Returns:
        AlignmentResult with aligned foods, totals, and version tracking

    Example:
        >>> from pipeline.run import run_once
        >>> from pipeline.config_loader import load_pipeline_config, get_code_git_sha
        >>> from pipeline.fdc_index import load_fdc_index
        >>> from pipeline.schemas import AlignmentRequest, DetectedFood
        >>>
        >>> cfg = load_pipeline_config()
        >>> fdc = load_fdc_index()
        >>> request = AlignmentRequest(
        ...     image_id="test_001",
        ...     foods=[DetectedFood(name="grape", form="raw", mass_g=100)],
        ...     config_version=cfg.config_version
        ... )
        >>> result = run_once(request, cfg, fdc, code_git_sha=get_code_git_sha())
        >>> print(result.foods[0].alignment_stage)
    """
    # Phase 3 COMPLETE: Pass external configs to FDCAlignmentWithConversion
    # Create alignment engine with external configs
    alignment_engine = FDCAlignmentWithConversion(
        class_thresholds=cfg.thresholds,
        negative_vocab=cfg.neg_vocab,
        feature_flags={**cfg.feature_flags, "stageZ_branded_fallback": allow_stage_z}
    )

    # Use adapter wrapper for compatibility with existing code
    adapter = AlignmentEngineAdapter(enable_conversion=True)
    # Inject our configured engine and database
    adapter.alignment_engine = alignment_engine
    adapter.fdc_db = fdc_index.adapter

    # Convert DetectedFood to dict format expected by adapter
    prediction = {
        "foods": [
            {
                "name": food.name,
                "form": food.form,
                "mass_g": food.mass_g,
                "confidence": food.confidence or 0.85,
                "modifiers": food.modifiers or [],
            }
            for food in request.foods
        ]
    }

    # Run alignment through existing adapter
    aligned_result = adapter.align_prediction_batch(prediction)

    # Extract aligned foods and build FoodAlignment objects
    aligned_foods = []
    telemetry_events = []

    for idx, food_result in enumerate(aligned_result.get("foods", [])):
        # Build FoodAlignment from result
        aligned_food = FoodAlignment(
            name=food_result.get("name", ""),
            form=food_result.get("form", ""),
            mass_g=food_result.get("mass_g", 0.0),
            alignment_stage=food_result.get("alignment_stage", "unknown"),
            fdc_id=food_result.get("fdc_id"),
            fdc_name=food_result.get("fdc_name"),
            conversion_applied=food_result.get("conversion_applied", False),
            match_score=food_result.get("match_score"),
            calories=food_result.get("calories"),
            protein_g=food_result.get("protein_g"),
            carbs_g=food_result.get("carbs_g"),
            fat_g=food_result.get("fat_g"),
            method=food_result.get("telemetry", {}).get("method"),
            method_reason=food_result.get("telemetry", {}).get("method_reason"),
            variant_chosen=food_result.get("telemetry", {}).get("variant_chosen"),
        )
        aligned_foods.append(aligned_food)

        # Build TelemetryEvent with all mandatory fields
        telemetry = food_result.get("telemetry", {})
        # Safe conversions for telemetry fields
        search_variants = telemetry.get("search_variants_tried", [])
        if not isinstance(search_variants, list):
            search_variants = []

        negative_blocks = telemetry.get("negative_vocab_blocks", [])
        if not isinstance(negative_blocks, list):
            negative_blocks = []

        sodium_gate = telemetry.get("sodium_gate_blocks")
        if sodium_gate is not None and not isinstance(sodium_gate, str):
            sodium_gate = None

        telemetry_event = TelemetryEvent(
            image_id=request.image_id,
            food_idx=idx,
            query=food_result.get("name", ""),
            alignment_stage=food_result.get("alignment_stage", "unknown"),
            fdc_id=food_result.get("fdc_id"),
            fdc_name=food_result.get("fdc_name"),
            candidate_pool_size=telemetry.get("candidate_pool_size", 0),
            foundation_pool_count=telemetry.get("candidate_pool_raw_foundation", 0),
            search_variants_tried=search_variants,
            variant_chosen=telemetry.get("variant_chosen"),
            stage1b_score=telemetry.get("stage1b_score"),
            match_score=food_result.get("match_score"),
            method=telemetry.get("method"),
            method_reason=telemetry.get("method_reason"),
            method_inferred=telemetry.get("method_inferred"),
            conversion_applied=food_result.get("conversion_applied", False),
            conversion_steps=telemetry.get("conversion_steps"),
            raw_fdc_id=telemetry.get("raw_fdc_id"),
            raw_fdc_name=telemetry.get("raw_fdc_name"),
            cook_method=telemetry.get("cook_method"),
            retention_factor=telemetry.get("retention_factor"),
            negative_vocab_blocks=negative_blocks,
            sodium_gate_blocks=sodium_gate,
            atwater_ok=telemetry.get("atwater_ok"),
            atwater_deviation_pct=telemetry.get("atwater_deviation_pct"),
            oil_uptake_g_per_100g=telemetry.get("oil_uptake_g_per_100g"),
            code_git_sha=code_git_sha,
            config_version=cfg.config_version,
            fdc_index_version=fdc_index.version,
            config_source=getattr(adapter.alignment_engine, 'config_source', 'fallback'),
        )
        telemetry_events.append(telemetry_event)

    # Build totals
    totals_data = aligned_result.get("totals", {})
    totals = Totals(
        mass_g=totals_data.get("mass_g", 0.0),
        calories=totals_data.get("calories"),
        protein_g=totals_data.get("protein_g"),
        carbs_g=totals_data.get("carbs_g"),
        fat_g=totals_data.get("fat_g"),
    )

    # Build telemetry summary
    stage_counts = {}
    for food in aligned_foods:
        stage = food.alignment_stage
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

    telemetry_summary = {
        "stage_counts": stage_counts,
        "total_items": len(aligned_foods),
        "conversion_rate": aligned_result.get("telemetry", {}).get("conversion_rate", 0.0),
        "stage5_proxy_count": aligned_result.get("telemetry", {}).get("stage5_proxy_count", 0),
    }

    # Build final result
    result = AlignmentResult(
        image_id=request.image_id,
        foods=aligned_foods,
        totals=totals,
        telemetry_summary=telemetry_summary,
        code_git_sha=code_git_sha,
        config_version=cfg.config_version,
        fdc_index_version=fdc_index.version,
    )

    # Persist artifacts to runs/
    _persist_run_artifacts(request.image_id, result, telemetry_events)

    return result


def _persist_run_artifacts(
    image_id: str,
    result: AlignmentResult,
    telemetry: List[TelemetryEvent]
) -> None:
    """
    Persist alignment results and telemetry to JSONL files.

    Artifacts written to: runs/<timestamp>/{results.jsonl, telemetry.jsonl}

    Args:
        image_id: Image identifier
        result: Complete alignment result
        telemetry: List of per-food telemetry events
    """
    # Create runs directory with timestamp
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    run_dir = Path("runs") / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    # Write result as single JSONL line
    results_file = run_dir / "results.jsonl"
    with open(results_file, "a") as f:
        f.write(result.model_dump_json() + "\n")

    # Write telemetry events as JSONL
    telemetry_file = run_dir / "telemetry.jsonl"
    with open(telemetry_file, "a") as f:
        for event in telemetry:
            f.write(event.model_dump_json() + "\n")

    print(f"[PIPELINE] Artifacts saved to: {run_dir}/")
