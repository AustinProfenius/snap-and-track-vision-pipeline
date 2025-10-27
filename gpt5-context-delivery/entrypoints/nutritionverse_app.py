"""
Streamlit app optimized for NutritionVerse dataset evaluation.
Zero-setup, direct CSV loading, comprehensive results display.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import asyncio
import sys
from PIL import Image
from dotenv import load_dotenv
import os
import json
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Add repo root to path for pipeline imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root))

# Import pipeline components
from pipeline.run import run_once
from pipeline.config_loader import load_pipeline_config, get_code_git_sha
from pipeline.fdc_index import load_fdc_index
from pipeline.schemas import AlignmentRequest, DetectedFood

from src.core.food_nutrients_loader import FoodNutrientsDataset, DishData
from src.core.nutritionverse_prompts import (
    SYSTEM_MESSAGE,
    get_macro_only_prompt,
    get_micro_macro_prompt,
    parse_json_response,
    validate_response_schema
)
from src.adapters.openai_ import OpenAIAdapter
from src.adapters.fdc_alignment_v2 import FDCAlignmentEngineV2  # Legacy engine (kept for compatibility)
from src.nutrition.alignment.align_convert import FDCAlignmentWithConversion, print_alignment_banner  # NEW: Stage 5 proxy alignment
from src.adapters.fdc_database import FDCDatabase
from src.adapters.alignment_adapter import AlignmentEngineAdapter  # NEW: Stage 5 adapter for web app
from src.core.prediction_rails import PredictionRails
from src.core.calibration import FoodCalibrator
from src.config.feature_flags import FLAGS

# Import telemetry validation utilities
import importlib.util
spec = importlib.util.spec_from_file_location("eval_aggregator", Path(__file__).parent / "tools" / "eval_aggregator.py")
eval_aggregator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_aggregator)
validate_telemetry_schema = eval_aggregator.validate_telemetry_schema
compute_telemetry_stats = eval_aggregator.compute_telemetry_stats


# Page config
st.set_page_config(
    page_title="Food Nutrients Evaluator",
    page_icon="🍽️",
    layout="wide"
)

# Custom CSS for better selectbox display
st.markdown("""
<style>
    /* Make selectbox dropdown larger and denser */
    [data-baseweb="select"] {
        font-family: 'Monaco', 'Menlo', 'Courier New', monospace;
        font-size: 0.85rem;
    }

    /* Increase max height of dropdown menu */
    [role="listbox"] {
        max-height: 600px !important;
    }

    /* Make dropdown items more compact */
    [role="option"] {
        padding: 4px 12px !important;
        min-height: 28px !important;
        line-height: 1.3 !important;
    }

    /* Improve sidebar width for better filter controls */
    section[data-testid="stSidebar"] {
        width: 380px !important;
    }

    section[data-testid="stSidebar"] > div {
        width: 380px !important;
    }
</style>
""", unsafe_allow_html=True)

# Load pipeline components (cached for Streamlit)
@st.cache_resource
def load_pipeline_components():
    """Load pipeline config and FDC index once (cached across reruns)."""
    configs_path = repo_root / "configs"
    config = load_pipeline_config(root=str(configs_path))
    fdc_index = load_fdc_index()
    code_sha = get_code_git_sha()
    return config, fdc_index, code_sha

# Initialize session state
if "dataset" not in st.session_state:
    st.session_state.dataset = None
if "current_dish_idx" not in st.session_state:
    st.session_state.current_dish_idx = 0
if "prediction" not in st.session_state:
    st.session_state.prediction = None
if "database_aligned" not in st.session_state:
    st.session_state.database_aligned = None
if "last_result_entry" not in st.session_state:
    st.session_state.last_result_entry = None
if "running" not in st.session_state:
    st.session_state.running = False
if "batch_results" not in st.session_state:
    st.session_state.batch_results = []
if "test_mode" not in st.session_state:
    st.session_state.test_mode = "Single Image"


@st.cache_resource
def load_dataset():
    """Load Food Nutrients dataset (cached)."""
    dataset_path = Path("/Users/austinprofenius/snapandtrack-model-testing/food-nutrients")
    try:
        dataset = FoodNutrientsDataset(dataset_path)
        return dataset, None
    except Exception as e:
        return None, str(e)


@st.cache_resource
def load_prediction_rails():
    """Load prediction rails engine (cached)."""
    try:
        rails = PredictionRails()
        return rails
    except Exception as e:
        print(f"[WARNING] Failed to load prediction rails: {e}")
        return None


@st.cache_resource
def load_calibrator():
    """Load calibration coefficients if available (cached)."""
    calibration_file = Path("calibration_coefficients.json")
    if calibration_file.exists():
        try:
            calibrator = FoodCalibrator.load(calibration_file)
            return calibrator
        except Exception as e:
            print(f"[WARNING] Failed to load calibration: {e}")
            return None
    return None


def calculate_percentage_diff(predicted: float, actual: float) -> float:
    """Calculate percentage difference."""
    if actual == 0:
        return 0 if predicted == 0 else 100
    return ((predicted - actual) / actual) * 100


def calculate_total_accuracy(pred: dict, actual: DishData, include_micros: bool) -> float:
    """
    Calculate overall accuracy across all metrics.

    Returns average absolute percentage error across all measured fields.

    Note: In mass-only mode, prediction may not have "totals" (only individual foods with mass).
    In this case, we can't calculate accuracy from vision alone - need to wait for FDC alignment.
    """
    # Check if prediction has totals (legacy macro mode)
    if "totals" not in pred:
        # Mass-only mode: no totals from vision, can't calculate accuracy yet
        # Caller should use database_aligned totals instead
        return None

    errors = []

    # Macros + calories + mass
    fields = [
        ("mass_g", actual.total_mass_g),
        ("calories", actual.total_calories),
        ("fat_g", actual.total_fat_g),
        ("carbs_g", actual.total_carbs_g),
        ("protein_g", actual.total_protein_g),
    ]

    if include_micros:
        fields.extend([
            ("calcium_mg", actual.total_calcium_mg),
            ("iron_mg", actual.total_iron_mg),
            ("magnesium_mg", actual.total_magnesium_mg),
            ("potassium_mg", actual.total_potassium_mg),
            ("sodium_mg", actual.total_sodium_mg),
            ("vitamin_d_ug", actual.total_vitamin_d_ug),
            ("vitamin_b12_ug", actual.total_vitamin_b12_ug),
        ])

    for field, actual_val in fields:
        pred_val = pred["totals"].get(field, 0)
        if actual_val > 0:
            error = abs((pred_val - actual_val) / actual_val) * 100
            errors.append(error)

    return sum(errors) / len(errors) if errors else 0


async def run_prediction(dish: DishData, model: str, include_micros: bool):
    """Run prediction on a single dish."""
    try:
        from src.config.feature_flags import FLAGS
        from src.core.nutritionverse_prompts import validate_mass_only_response

        # Check if mass-only mode is enabled
        use_mass_only = FLAGS.vision_mass_only

        # Initialize adapter (reads feature flag if use_mass_only not specified)
        adapter = OpenAIAdapter(
            model=model,
            temperature=0.1,
            max_tokens=900,
            use_mass_only=use_mass_only
        )

        if use_mass_only:
            # Mass-only mode: vision returns {name, form, mass_g, count?, confidence}
            # Adapter handles prompts internally - no need to pass prompt
            print(f"[VISION] Using MASS-ONLY mode (no calorie estimation from vision)")

            result = await adapter.infer(
                image_path=dish.image_path,
                prompt=""  # Ignored in mass-only mode
            )

            # Validate mass-only schema (adapter already validated, but double-check)
            try:
                validate_mass_only_response(result)
                print(f"[VISION] ✅ Mass-only validation passed: {len(result['foods'])} foods")
            except ValueError as e:
                print(f"[VISION] ❌ Mass-only validation failed: {e}")
                return {"error": f"Mass-only validation failed: {e}"}

        else:
            # Legacy macro-only mode (for backward compatibility)
            print(f"[VISION] Using LEGACY macro mode (vision estimates calories)")

            prompt = get_micro_macro_prompt() if include_micros else get_macro_only_prompt()

            result = await adapter.infer(
                image_path=dish.image_path,
                prompt=prompt,
                system_message=SYSTEM_MESSAGE
            )

            # Validate legacy schema
            if not validate_response_schema(result, include_micros):
                return {"error": "Invalid response schema"}

        # Apply prediction rails (skip in mass-only - no macros from vision to validate)
        rails = load_prediction_rails()
        if rails and not use_mass_only:
            print(f"[RAILS] Applying prediction rails to dish {dish.dish_id}")
            result = rails.apply_all_rails(result)
        elif not use_mass_only:
            print(f"[WARNING] Prediction rails not available, skipping validation")

        # Apply calibration (skip in mass-only - no vision calories to calibrate)
        if not use_mass_only:
            calibrator = load_calibrator()
            if calibrator and calibrator.fitted:
                print(f"[CALIBRATION] Applying per-class calibration to dish {dish.dish_id}")
                result = calibrator.calibrate(result)
            else:
                print(f"[INFO] No calibration available (run scripts/fit_calibration.py to create)")

        return result

    except Exception as e:
        return {"error": str(e)}


async def run_single_dish_with_result(dish: DishData, model: str, include_micros: bool):
    """Run prediction on a single dish and format result."""
    prediction = await run_prediction(dish, model, include_micros)

    # Calculate accuracy for this dish
    accuracy = None
    if "error" not in prediction:
        total_acc = calculate_total_accuracy(prediction, dish, include_micros)
        # calculate_total_accuracy returns None in mass-only mode (no totals yet)
        if total_acc is not None:
            accuracy = 100 - total_acc

    # Align predicted foods to FDC database using pipeline
    print(f"\n[APP] Running alignment through unified pipeline for dish {dish.dish_id}")
    database_aligned = None
    if "error" not in prediction:
        print(f"[APP] Loading pipeline components...")
        CONFIG, FDC, CODE_SHA = load_pipeline_components()
        print(f"  Config: {CONFIG.config_version}, FDC: {FDC.version}, Code: {CODE_SHA}")

        # Convert prediction to AlignmentRequest
        detected_foods = [
            DetectedFood(
                name=food["name"],
                form=food.get("form", "raw"),
                mass_g=food.get("grams", 0.0),
                confidence=food.get("confidence", 0.85)
            )
            for food in prediction.get("foods", [])
        ]

        request = AlignmentRequest(
            image_id=dish.dish_id,
            foods=detected_foods,
            config_version=CONFIG.config_version
        )

        print(f"[APP] Running pipeline alignment...")
        pipeline_result = run_once(
            request=request,
            cfg=CONFIG,
            fdc_index=FDC,
            allow_stage_z=True,  # Web app: allow branded fallback for graceful UX
            code_git_sha=CODE_SHA
        )

        # Convert pipeline result back to legacy format for UI compatibility
        database_aligned = {
            "foods": [
                {
                    "name": f.name,
                    "form": f.form,
                    "mass_g": f.mass_g,
                    "fdc_id": f.fdc_id,
                    "fdc_name": f.fdc_name,
                    "alignment_stage": f.alignment_stage,
                    "conversion_applied": f.conversion_applied,
                    "match_score": f.match_score,
                    "calories": f.calories,
                    "protein_g": f.protein_g,
                    "carbs_g": f.carbs_g,
                    "fat_g": f.fat_g,
                    "telemetry": {
                        "method": f.method,
                        "method_reason": f.method_reason,
                        "variant_chosen": f.variant_chosen
                    }
                }
                for f in pipeline_result.foods
            ],
            "totals": {
                "mass_g": pipeline_result.totals.mass_g,
                "calories": pipeline_result.totals.calories,
                "protein_g": pipeline_result.totals.protein_g,
                "carbs_g": pipeline_result.totals.carbs_g,
                "fat_g": pipeline_result.totals.fat_g
            },
            "telemetry_summary": pipeline_result.telemetry_summary
        }
        print(f"[APP] Alignment result: available={database_aligned.get('available', False)}, foods={len(database_aligned.get('foods', []))}")

    result_entry = {
        "dish_id": dish.dish_id,
        "image_filename": dish.image_filename,
        "image_path": str(dish.image_path),
        "prediction": prediction,
        "database_aligned": database_aligned,
        "ground_truth": {
            "dish_id": dish.dish_id,
            "image_filename": dish.image_filename,
            "image_path": str(dish.image_path),
            "total_mass_g": dish.total_mass_g,
            "total_calories": dish.total_calories,
            "total_fat_g": dish.total_fat_g,
            "total_carbs_g": dish.total_carbs_g,
            "total_protein_g": dish.total_protein_g,
            "foods": [{"name": f.name, "mass_g": f.mass_g, "calories": f.calories} for f in dish.foods]
        },
        "accuracy": accuracy,
        "error": prediction.get("error") if "error" in prediction else None
    }

    if include_micros and "error" not in prediction:
        result_entry["ground_truth"].update({
            "total_calcium_mg": dish.total_calcium_mg,
            "total_iron_mg": dish.total_iron_mg,
            "total_magnesium_mg": dish.total_magnesium_mg,
            "total_potassium_mg": dish.total_potassium_mg,
            "total_sodium_mg": dish.total_sodium_mg,
            "total_vitamin_d_ug": dish.total_vitamin_d_ug,
            "total_vitamin_b12_ug": dish.total_vitamin_b12_ug,
        })

    return result_entry


async def run_batch_predictions(dishes: list, model: str, include_micros: bool, progress_callback=None, max_concurrent: int = 5):
    """Run predictions on a batch of dishes with concurrent requests."""
    import asyncio

    results = []
    completed = 0

    # Process in batches with concurrency limit
    for i in range(0, len(dishes), max_concurrent):
        batch = dishes[i:i + max_concurrent]

        # Run batch concurrently
        batch_tasks = [run_single_dish_with_result(dish, model, include_micros) for dish in batch]
        batch_results = await asyncio.gather(*batch_tasks)

        results.extend(batch_results)

        # Update progress
        completed += len(batch)
        if progress_callback and completed <= len(dishes):
            # Report progress for last dish in batch
            progress_callback(completed - 1, len(dishes), batch[-1])

    return results


def save_batch_results(results: list, model: str, include_micros: bool, test_mode: str):
    """
    Save batch results to JSON file with timestamp.

    Phase 7: Also writes pipeline artifacts to runs/{timestamp}/ for consistency
    with batch harness format (results.jsonl, telemetry.jsonl, summary.md).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    # Create summary statistics
    successful_results = [r for r in results if r["error"] is None]
    failed_results = [r for r in results if r["error"] is not None]

    accuracies = [r["accuracy"] for r in successful_results if r["accuracy"] is not None]
    avg_accuracy = sum(accuracies) / len(accuracies) if accuracies else 0

    summary = {
        "timestamp": timestamp,
        "model": model,
        "include_micros": include_micros,
        "test_mode": test_mode,
        "total_images": len(results),
        "successful": len(successful_results),
        "failed": len(failed_results),
        "average_accuracy": avg_accuracy,
        "results": results
    }

    # Save to file with model name and image count (legacy format)
    model_name = model.replace('/', '_').replace('-', '_')
    filename = results_dir / f"{model_name}_{len(results)}images_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(summary, f, indent=2)

    # Phase 7: Write pipeline artifacts to runs/{timestamp}/ (for consistency with batch harness)
    _write_pipeline_artifacts(results, timestamp)

    return filename, summary


def _write_pipeline_artifacts(results: list, timestamp: str):
    """
    Phase 7: Write pipeline artifacts in batch harness format.

    Creates runs/{timestamp}/ with:
    - results.jsonl: One line per image (pipeline AlignmentResult format)
    - telemetry.jsonl: One line per food (telemetry events)
    - summary.md: Human-readable summary

    Args:
        results: List of result dictionaries from run_single_dish_with_result
        timestamp: Timestamp string (YYYYMMDD_HHMMSS)
    """
    run_dir = Path("runs") / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    results_file = run_dir / "results.jsonl"
    telemetry_file = run_dir / "telemetry.jsonl"
    summary_file = run_dir / "summary.md"

    # Extract pipeline results and write JSONL
    with open(results_file, "w") as rf, open(telemetry_file, "w") as tf:
        for result in results:
            if result.get("error") is None and result.get("database_aligned"):
                # Write result as JSONL (simplified format)
                result_entry = {
                    "image_id": result["dish_id"],
                    "foods": result["database_aligned"]["foods"],
                    "totals": result["database_aligned"]["totals"],
                    "telemetry_summary": result["database_aligned"].get("telemetry_summary", {})
                }
                rf.write(json.dumps(result_entry) + "\n")

                # Write telemetry events (one per food)
                for idx, food in enumerate(result["database_aligned"]["foods"]):
                    telemetry_event = {
                        "image_id": result["dish_id"],
                        "food_idx": idx,
                        "query": food["name"],
                        "alignment_stage": food.get("alignment_stage"),
                        "fdc_id": food.get("fdc_id"),
                        "fdc_name": food.get("fdc_name"),
                        "match_score": food.get("match_score"),
                        "conversion_applied": food.get("conversion_applied", False),
                        "method": food.get("telemetry", {}).get("method"),
                        "method_reason": food.get("telemetry", {}).get("method_reason"),
                        "variant_chosen": food.get("telemetry", {}).get("variant_chosen")
                    }
                    tf.write(json.dumps(telemetry_event) + "\n")

    # Write summary markdown
    successful = [r for r in results if r.get("error") is None]
    failed = [r for r in results if r.get("error") is not None]

    # Collect stage distribution
    stage_counts = {}
    for result in successful:
        if result.get("database_aligned"):
            for food in result["database_aligned"]["foods"]:
                stage = food.get("alignment_stage", "unknown")
                stage_counts[stage] = stage_counts.get(stage, 0) + 1

    with open(summary_file, "w") as f:
        f.write(f"# Web App Batch Run - {timestamp}\n\n")
        f.write(f"**Total Images**: {len(results)}\n")
        f.write(f"**Successful**: {len(successful)}\n")
        f.write(f"**Failed**: {len(failed)}\n\n")
        f.write(f"## Alignment Stage Distribution\n\n")
        for stage, count in sorted(stage_counts.items(), key=lambda x: -x[1]):
            f.write(f"- **{stage}**: {count}\n")
        f.write(f"\n**Artifacts**: results.jsonl, telemetry.jsonl\n")

    print(f"[APP] Pipeline artifacts written to: {run_dir}/")



def save_single_result(result_entry: dict, model: str, include_micros: bool):
    """Save single image result to JSON file with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)

    # Calculate accuracy
    accuracy = result_entry.get("accuracy")

    summary = {
        "timestamp": timestamp,
        "model": model,
        "include_micros": include_micros,
        "test_mode": "Single Image",
        "total_images": 1,
        "successful": 1 if result_entry.get("error") is None else 0,
        "failed": 0 if result_entry.get("error") is None else 1,
        "average_accuracy": accuracy if accuracy is not None else 0,
        "results": [result_entry]
    }

    # Save to file with model name and dish ID
    model_name = model.replace('/', '_').replace('-', '_')
    dish_id = result_entry.get("dish_id", "unknown")
    filename = results_dir / f"{model_name}_single_{dish_id}_{timestamp}.json"
    with open(filename, "w") as f:
        json.dump(summary, f, indent=2)

    return filename, summary


def display_comparison_table(pred: dict, actual: DishData, include_micros: bool):
    """Display comprehensive comparison table."""
    st.subheader("📊 Results Comparison")

    # Check if prediction has totals (mass-only mode won't have totals)
    if "totals" not in pred:
        st.warning("⚠️ Vision prediction in mass-only mode - no nutrition totals from vision model. See database alignment results below.")
        return

    # Prepare data
    rows = []

    # Totals comparison
    fields = [
        ("Total Mass", "mass_g", actual.total_mass_g, "g"),
        ("Total Calories", "calories", actual.total_calories, "kcal"),
        ("Total Fat", "fat_g", actual.total_fat_g, "g"),
        ("Total Carbs", "carbs_g", actual.total_carbs_g, "g"),
        ("Total Protein", "protein_g", actual.total_protein_g, "g"),
    ]

    if include_micros:
        fields.extend([
            ("Total Calcium", "calcium_mg", actual.total_calcium_mg, "mg"),
            ("Total Iron", "iron_mg", actual.total_iron_mg, "mg"),
            ("Total Magnesium", "magnesium_mg", actual.total_magnesium_mg, "mg"),
            ("Total Potassium", "potassium_mg", actual.total_potassium_mg, "mg"),
            ("Total Sodium", "sodium_mg", actual.total_sodium_mg, "mg"),
            ("Total Vitamin D", "vitamin_d_ug", actual.total_vitamin_d_ug, "µg"),
            ("Total Vitamin B12", "vitamin_b12_ug", actual.total_vitamin_b12_ug, "µg"),
        ])

    for label, field, actual_val, unit in fields:
        pred_val = pred["totals"].get(field, 0)
        diff = pred_val - actual_val
        pct_diff = calculate_percentage_diff(pred_val, actual_val)

        rows.append({
            "Metric": label,
            "Predicted": f"{pred_val:.2f} {unit}",
            "Actual": f"{actual_val:.2f} {unit}",
            "Difference": f"{diff:+.2f} {unit}",
            "Error %": f"{pct_diff:+.1f}%"
        })

    df = pd.DataFrame(rows)

    # Color code error column
    def color_error(val):
        pct = float(val.strip('%'))
        if abs(pct) < 10:
            return 'background-color: #d4edda'  # green
        elif abs(pct) < 25:
            return 'background-color: #fff3cd'  # yellow
        else:
            return 'background-color: #f8d7da'  # red

    styled_df = df.style.applymap(color_error, subset=['Error %'])
    st.dataframe(styled_df, use_container_width=True, height=400)

    # Overall accuracy
    total_acc = calculate_total_accuracy(pred, actual, include_micros)
    if total_acc is not None:
        total_accuracy = 100 - total_acc
        st.metric("**Overall Accuracy**", f"{total_accuracy:.1f}%",
                  help="Average accuracy across all measured statistics")
    else:
        st.info("Overall accuracy not available (mass-only mode - use database alignment metrics)")


def display_per_food_comparison(pred: dict, actual: DishData, include_micros: bool, database_aligned: dict = None):
    """Display per-food item breakdown."""
    st.subheader("🍴 Per-Food Breakdown")

    # Check if database alignment is available
    has_db_aligned = database_aligned and database_aligned.get("available", False)

    # Create columns: predicted vs actual vs database-aligned (if available)
    if has_db_aligned:
        col1, col2, col3 = st.columns(3)
    else:
        col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Predicted Foods")
        for i, food in enumerate(pred["foods"]):
            with st.expander(f"**{food['name']}** ({food.get('mass_g', 0):.0f}g)"):
                st.write(f"**Calories:** {food.get('calories', 0):.1f} kcal")
                st.write(f"**Protein:** {food.get('protein_g', 0):.1f}g")
                st.write(f"**Carbs:** {food.get('carbs_g', 0):.1f}g")
                st.write(f"**Fat:** {food.get('fat_g', 0):.1f}g")

                if include_micros:
                    st.divider()
                    st.write(f"**Calcium:** {food.get('calcium_mg', 0):.2f}mg")
                    st.write(f"**Iron:** {food.get('iron_mg', 0):.4f}mg")
                    st.write(f"**Magnesium:** {food.get('magnesium_mg', 0):.2f}mg")
                    st.write(f"**Potassium:** {food.get('potassium_mg', 0):.2f}mg")
                    st.write(f"**Sodium:** {food.get('sodium_mg', 0):.3f}mg")
                    st.write(f"**Vitamin D:** {food.get('vitamin_d_ug', 0):.4f}µg")
                    st.write(f"**Vitamin B12:** {food.get('vitamin_b12_ug', 0):.6f}µg")

    with col2:
        st.markdown("### Actual Foods (Ground Truth)")
        for food in actual.foods:
            with st.expander(f"**{food.name}** ({food.mass_g:.0f}g)"):
                st.write(f"**Calories:** {food.calories:.1f} kcal")
                st.write(f"**Protein:** {food.protein_g:.1f}g")
                st.write(f"**Carbs:** {food.carbs_g:.1f}g")
                st.write(f"**Fat:** {food.fat_g:.1f}g")

                if include_micros:
                    st.divider()
                    st.write(f"**Calcium:** {food.calcium_mg:.2f}mg")
                    st.write(f"**Iron:** {food.iron_mg:.4f}mg")
                    st.write(f"**Magnesium:** {food.magnesium_mg:.2f}mg")
                    st.write(f"**Potassium:** {food.potassium_mg:.2f}mg")
                    st.write(f"**Sodium:** {food.sodium_mg:.3f}mg")
                    st.write(f"**Vitamin D:** {food.vitamin_d_ug:.4f}µg")
                    st.write(f"**Vitamin B12:** {food.vitamin_b12_ug:.6f}µg")

    # Database-aligned column (if available)
    if has_db_aligned:
        with col3:
            st.markdown("### Database-Aligned Foods")
            db_foods = database_aligned.get("foods", [])

            if not db_foods:
                st.info("No foods aligned from database")
            else:
                for food in db_foods:
                    matched_name = food.get("matched_name", "Unknown")
                    nutrition = food.get("nutrition", {})

                    with st.expander(f"**{matched_name[:40]}...** ({nutrition.get('mass_g', 0):.0f}g)"):
                        st.caption(f"Predicted: {food.get('predicted_name', 'N/A')}")
                        st.caption(f"FDC ID: {food.get('fdc_id', 'N/A')} | {food.get('data_type', 'N/A')}")
                        st.divider()
                        st.write(f"**Calories:** {nutrition.get('calories', 0):.1f} kcal")
                        st.write(f"**Protein:** {nutrition.get('protein_g', 0):.1f}g")
                        st.write(f"**Carbs:** {nutrition.get('carbs_g', 0):.1f}g")
                        st.write(f"**Fat:** {nutrition.get('fat_g', 0):.1f}g")


def main():
    st.title("🍽️ Food Nutrients Evaluator")
    st.markdown("Evaluate OpenAI vision models on Google Research's Nutrition5k dataset with detailed comparisons")

    # Load dataset
    if st.session_state.dataset is None:
        with st.spinner("Loading Food Nutrients dataset..."):
            dataset, error = load_dataset()
            if error:
                st.error(f"❌ Failed to load dataset: {error}")
                st.stop()
            st.session_state.dataset = dataset
            st.success(f"✅ Loaded {len(dataset)} dishes")

    dataset = st.session_state.dataset

    # Print alignment banner to console on first run
    if "banner_printed" not in st.session_state:
        print_alignment_banner()
        st.session_state.banner_printed = True

    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Feature Flags Controls
        with st.expander("🚩 Feature Flags (Alignment Engine)", expanded=False):
            st.caption("⚠️ Changes apply to NEW alignments only")

            # Key Phase 1 flags
            prefer_raw = st.checkbox(
                "Prefer Raw Foundation + Conversion",
                value=FLAGS.prefer_raw_foundation_convert,
                help="Hard-gate Stage 1 (cooked SR/Legacy) when raw Foundation exists. Forces Stage 2 (raw + convert) path.",
                key="flag_prefer_raw"
            )
            FLAGS.prefer_raw_foundation_convert = prefer_raw

            enable_stage5 = st.checkbox(
                "Enable Stage 5 Proxy Alignment",
                value=FLAGS.enable_proxy_alignment,
                help="Use vetted proxies for classes lacking Foundation/Legacy entries (leafy_mixed_salad, squash_summer_yellow, tofu_plain_raw)",
                key="flag_stage5"
            )
            FLAGS.enable_proxy_alignment = enable_stage5

            strict_gate = st.checkbox(
                "Strict Cooked Exact Gate",
                value=FLAGS.strict_cooked_exact_gate,
                help="Require method compatibility AND energy within ±20% for Stage 1 admission",
                key="flag_strict_gate"
            )
            FLAGS.strict_cooked_exact_gate = strict_gate

            # Show current status
            st.divider()
            st.caption("**Current Status:**")
            st.caption(f"✓ Stage 5: {'Active' if enable_stage5 else 'Disabled'}")
            st.caption(f"✓ Conversion: {'Preferred' if prefer_raw else 'Standard'}")
            st.caption(f"✓ Stage 1 Gate: {'Strict' if strict_gate else 'Relaxed'}")

        st.divider()

        # Model selection - GPT-5 only
        model_options = [
            "gpt-5-mini",
            "gpt-5",
            "gpt-5-turbo",
            "gpt-5-turbo-mini",
            "gpt-5-vision",
            "gpt-5-vision-mini",
            "gpt-5-vision-turbo",
            "gpt-5-vision-turbo-mini",
        ]

        model = st.selectbox(
            "OpenAI Model (GPT-5 Only)",
            model_options,
            index=1,  # default to gpt-5
            help="Select which GPT-5 vision model to use. GPT-5 models map to gpt-4o in the OpenAI API."
        )

        # Micronutrient mode
        include_micros = st.checkbox(
            "Include Micronutrients",
            value=False,
            help="Enable to include vitamins and minerals in estimation"
        )

        st.divider()

        # Concurrency settings for batch tests
        st.subheader("⚡ Batch Performance")
        max_concurrent = st.slider(
            "Concurrent Requests",
            min_value=1,
            max_value=10,
            value=5,
            help="Number of simultaneous API requests. Higher = faster but may hit rate limits. Recommended: 5"
        )

        st.divider()

        # Dataset navigation - Enhanced
        st.subheader("📋 Dataset Navigation & Filtering")

        # Split filter (food-nutrients only has 'test' split)
        split_filter = st.selectbox(
            "Filter by split",
            ["All", "test"]
        )

        if split_filter == "All":
            base_dishes = dataset.dishes
        else:
            base_dishes = dataset.get_by_split(split_filter.lower())

        # Advanced filtering
        with st.expander("🔍 Advanced Filters", expanded=True):
            # Filter by number of items
            col1, col2 = st.columns(2)
            with col1:
                min_items = st.number_input("Min items", min_value=1, max_value=20, value=1)
            with col2:
                max_items = st.number_input("Max items", min_value=1, max_value=20, value=20)

            # Filter by calories
            col1, col2 = st.columns(2)
            with col1:
                min_calories = st.number_input("Min calories", min_value=0, max_value=5000, value=0, step=50)
            with col2:
                max_calories = st.number_input("Max calories", min_value=0, max_value=5000, value=5000, step=50)

            # Filter by mass
            col1, col2 = st.columns(2)
            with col1:
                min_mass = st.number_input("Min mass (g)", min_value=0, max_value=2000, value=0, step=50)
            with col2:
                max_mass = st.number_input("Max mass (g)", min_value=0, max_value=2000, value=2000, step=50)

        # Apply filters
        filtered_dishes = [
            dish for dish in base_dishes
            if (min_items <= len(dish.foods) <= max_items and
                min_calories <= dish.total_calories <= max_calories and
                min_mass <= dish.total_mass <= max_mass)
        ]

        # Sorting
        sort_by = st.selectbox(
            "Sort by",
            ["Dish ID", "Number of Items (Low→High)", "Number of Items (High→Low)",
             "Calories (Low→High)", "Calories (High→Low)",
             "Mass (Low→High)", "Mass (High→Low)"],
            index=0
        )

        # Apply sorting
        if sort_by == "Dish ID":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: d.dish_id)
        elif sort_by == "Number of Items (Low→High)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: len(d.foods))
        elif sort_by == "Number of Items (High→Low)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: len(d.foods), reverse=True)
        elif sort_by == "Calories (Low→High)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: d.total_calories)
        elif sort_by == "Calories (High→Low)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: d.total_calories, reverse=True)
        elif sort_by == "Mass (Low→High)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: d.total_mass)
        elif sort_by == "Mass (High→Low)":
            sorted_dishes = sorted(filtered_dishes, key=lambda d: d.total_mass, reverse=True)
        else:
            sorted_dishes = filtered_dishes

        # Update filtered dishes to sorted version
        filtered_dishes = sorted_dishes

        # Show filter results
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Filtered Dishes", len(filtered_dishes))
        with col2:
            if len(filtered_dishes) > 0:
                avg_items = sum(len(d.foods) for d in filtered_dishes) / len(filtered_dishes)
                st.metric("Avg Items", f"{avg_items:.1f}")

        # Dish selector with enhanced display - larger and denser
        if len(filtered_dishes) > 0:
            dish_idx = st.selectbox(
                "Select dish",
                range(len(filtered_dishes)),
                format_func=lambda i: (
                    f"#{i} | Dish {filtered_dishes[i].dish_id} | "
                    f"{len(filtered_dishes[i].foods)} items | "
                    f"{filtered_dishes[i].total_calories:.0f} kcal | "
                    f"{filtered_dishes[i].total_mass:.0f}g | "
                    f"{filtered_dishes[i].image_filename[:25]}"
                ),
                key="dish_selector"
            )
            st.session_state.current_dish_idx = dish_idx
        else:
            st.warning("No dishes match the current filters")
            dish_idx = 0
            st.session_state.current_dish_idx = 0

        st.divider()

        # Testing mode
        st.subheader("🧪 Testing Mode")
        test_mode = st.radio(
            "Select mode",
            ["Single Image", "Batch Test", "Full Filtered Dataset"],
            help="Single: Test one image at a time\nBatch: Test a range from filtered/sorted list\nFull Filtered Dataset: Test all images in current filter"
        )

        batch_start = 0
        batch_end = 0

        if test_mode == "Batch Test":
            st.info(f"📊 Batch from **{len(filtered_dishes)}** filtered & sorted dishes")

            # Quick batch selectors
            st.markdown("**Quick Batch Selection:**")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("First 10", use_container_width=True):
                    st.session_state.batch_start = 0
                    st.session_state.batch_end = min(9, len(filtered_dishes) - 1)
            with col2:
                if st.button("First 50", use_container_width=True):
                    st.session_state.batch_start = 0
                    st.session_state.batch_end = min(49, len(filtered_dishes) - 1)
            with col3:
                if st.button("First 100", use_container_width=True):
                    st.session_state.batch_start = 0
                    st.session_state.batch_end = min(99, len(filtered_dishes) - 1)

            col1, col2 = st.columns(2)
            with col1:
                if st.button("All Filtered", use_container_width=True):
                    st.session_state.batch_start = 0
                    st.session_state.batch_end = len(filtered_dishes) - 1
            with col2:
                if st.button("Current → End", use_container_width=True):
                    st.session_state.batch_start = dish_idx
                    st.session_state.batch_end = len(filtered_dishes) - 1

            st.markdown("**Custom Range:**")
            col_start, col_end = st.columns(2)
            with col_start:
                batch_start = st.number_input(
                    "Start index",
                    min_value=0,
                    max_value=max(0, len(filtered_dishes) - 1),
                    value=st.session_state.get("batch_start", 0),
                    key="batch_start_input"
                )
                st.session_state.batch_start = batch_start
            with col_end:
                batch_end = st.number_input(
                    "End index",
                    min_value=0,
                    max_value=max(0, len(filtered_dishes) - 1),
                    value=st.session_state.get("batch_end", min(9, len(filtered_dishes) - 1)),
                    key="batch_end_input"
                )
                st.session_state.batch_end = batch_end

            # Batch preview
            batch_size = batch_end - batch_start + 1
            st.success(f"✅ Will test **{batch_size}** images (indices {batch_start} → {batch_end})")

            if batch_size > 0 and batch_size <= 5:
                st.markdown("**Preview:**")
                for i in range(batch_start, min(batch_end + 1, batch_start + 5)):
                    dish = filtered_dishes[i]
                    st.caption(
                        f"  {i}: Dish {dish.dish_id} | "
                        f"{len(dish.foods)} items | "
                        f"{dish.total_calories:.0f} kcal"
                    )

        st.divider()

        # Dataset stats
        with st.expander("📊 Dataset Statistics"):
            stats = dataset.get_statistics()
            st.json(stats)

    # Main area
    current_dish = filtered_dishes[dish_idx]

    # Display image
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader(f"🖼️ Dish {current_dish.dish_id}")
        st.info(f"**Image File:** `{current_dish.image_filename}`")
        st.caption(f"**Full Path:** `{current_dish.image_path}`")
        img = Image.open(current_dish.image_path)
        st.image(img, use_container_width=True)

        st.caption(f"**Split:** {current_dish.split} | **Foods:** {len(current_dish.foods)}")

    with col2:
        st.subheader("🎯 Ground Truth")
        st.caption(f"**Dish ID:** {current_dish.dish_id}")
        st.metric("Total Calories", f"{current_dish.total_calories:.1f} kcal")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("Protein", f"{current_dish.total_protein_g:.1f}g")
        with col_b:
            st.metric("Carbs", f"{current_dish.total_carbs_g:.1f}g")
        with col_c:
            st.metric("Fat", f"{current_dish.total_fat_g:.1f}g")

        st.metric("Total Mass", f"{current_dish.total_mass_g:.1f}g")

        if include_micros:
            st.divider()
            st.markdown("**Micronutrients:**")
            micro_col1, micro_col2 = st.columns(2)
            with micro_col1:
                st.write(f"Calcium: {current_dish.total_calcium_mg:.2f}mg")
                st.write(f"Iron: {current_dish.total_iron_mg:.4f}mg")
                st.write(f"Magnesium: {current_dish.total_magnesium_mg:.2f}mg")
            with micro_col2:
                st.write(f"Potassium: {current_dish.total_potassium_mg:.2f}mg")
                st.write(f"Sodium: {current_dish.total_sodium_mg:.3f}mg")
                st.write(f"Vitamin D: {current_dish.total_vitamin_d_ug:.4f}µg")
                st.write(f"Vitamin B12: {current_dish.total_vitamin_b12_ug:.6f}µg")

    # Run prediction button
    st.divider()

    # Determine button label and action based on test mode
    if test_mode == "Single Image":
        button_label = "🚀 Run Prediction"
        button_help = "Test current image"
    elif test_mode == "Batch Test":
        button_label = f"🚀 Run Batch Test ({batch_end - batch_start + 1} images)"
        button_help = f"Test images from index {batch_start} to {batch_end}"
    else:  # Full Filtered Dataset
        button_label = f"🚀 Run Full Filtered Dataset Test ({len(filtered_dishes)} images)"
        button_help = "Test all images matching current filters and sort order"

    if st.button(button_label, type="primary", disabled=st.session_state.running, use_container_width=True, help=button_help):
        st.session_state.running = True

        if test_mode == "Single Image":
            # Single image test
            st.info(f"📤 Sending to API: `{current_dish.image_filename}` (Dish ID: {current_dish.dish_id})")

            with st.spinner(f"Running {model} prediction..."):
                prediction = asyncio.run(run_prediction(current_dish, model, include_micros))

                st.session_state.prediction = prediction

                # Align to database if prediction succeeded (using pipeline)
                if "error" not in prediction:
                    print(f"\n[APP] Running database alignment through pipeline for single image...")
                    CONFIG, FDC, CODE_SHA = load_pipeline_components()

                    # Convert to pipeline format
                    detected_foods = [
                        DetectedFood(
                            name=food["name"],
                            form=food.get("form", "raw"),
                            mass_g=food.get("grams", 0.0),
                            confidence=food.get("confidence", 0.85)
                        )
                        for food in prediction.get("foods", [])
                    ]

                    request = AlignmentRequest(
                        image_id=current_dish.dish_id,
                        foods=detected_foods,
                        config_version=CONFIG.config_version
                    )

                    pipeline_result = run_once(
                        request=request,
                        cfg=CONFIG,
                        fdc_index=FDC,
                        allow_stage_z=True,  # Web app: allow branded fallback
                        code_git_sha=CODE_SHA
                    )

                    # Convert to legacy format for UI
                    st.session_state.database_aligned = {
                        "foods": [
                            {
                                "name": f.name,
                                "form": f.form,
                                "mass_g": f.mass_g,
                                "fdc_id": f.fdc_id,
                                "fdc_name": f.fdc_name,
                                "alignment_stage": f.alignment_stage,
                                "conversion_applied": f.conversion_applied,
                                "match_score": f.match_score,
                                "calories": f.calories,
                                "protein_g": f.protein_g,
                                "carbs_g": f.carbs_g,
                                "fat_g": f.fat_g,
                                "telemetry": {
                                    "method": f.method,
                                    "method_reason": f.method_reason,
                                    "variant_chosen": f.variant_chosen
                                }
                            }
                            for f in pipeline_result.foods
                        ],
                        "totals": {
                            "mass_g": pipeline_result.totals.mass_g,
                            "calories": pipeline_result.totals.calories,
                            "protein_g": pipeline_result.totals.protein_g,
                            "carbs_g": pipeline_result.totals.carbs_g,
                            "fat_g": pipeline_result.totals.fat_g
                        },
                        "telemetry_summary": pipeline_result.telemetry_summary
                    }
                else:
                    st.session_state.database_aligned = None

                # Create result entry for saving
                accuracy = None
                if "error" not in prediction:
                    total_acc = calculate_total_accuracy(prediction, current_dish, include_micros)
                    # calculate_total_accuracy returns None in mass-only mode (no totals yet)
                    if total_acc is not None:
                        accuracy = 100 - total_acc

                st.session_state.last_result_entry = {
                    "dish_id": current_dish.dish_id,
                    "image_filename": current_dish.image_filename,
                    "image_path": str(current_dish.image_path),
                    "prediction": prediction,
                    "database_aligned": st.session_state.database_aligned,
                    "ground_truth": {
                        "dish_id": current_dish.dish_id,
                        "image_filename": current_dish.image_filename,
                        "image_path": str(current_dish.image_path),
                        "total_mass_g": current_dish.total_mass_g,
                        "total_calories": current_dish.total_calories,
                        "total_fat_g": current_dish.total_fat_g,
                        "total_carbs_g": current_dish.total_carbs_g,
                        "total_protein_g": current_dish.total_protein_g,
                        "foods": [{"name": f.name, "mass_g": f.mass_g, "calories": f.calories} for f in current_dish.foods]
                    },
                    "accuracy": accuracy,
                    "error": prediction.get("error") if "error" in prediction else None
                }

                st.session_state.running = False

                if "error" in prediction:
                    st.error(f"❌ Error: {prediction['error']}")
                else:
                    st.success("✅ Prediction complete!")
                    st.rerun()

        else:
            # Batch or full dataset test
            if test_mode == "Batch Test":
                test_dishes = filtered_dishes[batch_start:batch_end + 1]
            else:
                test_dishes = filtered_dishes

            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()

            def update_progress(idx, total, dish):
                progress = (idx + 1) / total
                progress_bar.progress(progress)
                status_text.text(f"Testing {idx + 1}/{total}: Dish {dish.dish_id} - {dish.image_filename[:40]}...")

            # Run batch predictions
            with st.spinner(f"Running batch test on {len(test_dishes)} images..."):
                results = asyncio.run(run_batch_predictions(
                    test_dishes,
                    model,
                    include_micros,
                    progress_callback=update_progress,
                    max_concurrent=max_concurrent
                ))

                # Save results
                filename, summary = save_batch_results(results, model, include_micros, test_mode)

                st.session_state.batch_results = results
                st.session_state.running = False

                progress_bar.empty()
                status_text.empty()

                st.success(f"✅ Batch test complete! Results saved to `{filename}`")
                st.json(summary)
                st.rerun()

    # Display results
    if test_mode == "Single Image":
        # Single image results
        if st.session_state.prediction and "error" not in st.session_state.prediction:
            st.divider()

            # Comparison table
            display_comparison_table(st.session_state.prediction, current_dish, include_micros)

            st.divider()

            # Per-food breakdown
            display_per_food_comparison(
                st.session_state.prediction,
                current_dish,
                include_micros,
                database_aligned=st.session_state.database_aligned
            )

            # Raw JSON (expandable)
            with st.expander("🔍 View Raw Prediction JSON"):
                st.json(st.session_state.prediction)

            # Database alignment info
            if st.session_state.database_aligned and st.session_state.database_aligned.get("available"):
                with st.expander("🗄️ View Database Alignment Details"):
                    st.json(st.session_state.database_aligned)

            # Save button
            st.divider()
            if st.button("💾 Save Result to Results Viewer", use_container_width=True, help="Save this single image result to view later in Results Viewer"):
                if st.session_state.last_result_entry:
                    filename, summary = save_single_result(
                        st.session_state.last_result_entry,
                        model,
                        include_micros
                    )
                    st.success(f"✅ Result saved to `{filename}`")
                    st.info("Navigate to **Results Viewer** page to view saved results")
                else:
                    st.error("No result to save. Run a prediction first.")

    else:
        # Batch results summary
        if st.session_state.batch_results:
            st.divider()
            st.header("📊 Batch Test Results")

            # Create summary dataframe
            results_data = []
            for result in st.session_state.batch_results:
                results_data.append({
                    "Dish ID": result["dish_id"],
                    "Image": result["image_filename"][:40] + "...",
                    "Accuracy (%)": f"{result['accuracy']:.1f}" if result['accuracy'] is not None else "Error",
                    "Status": "✅ Success" if result["error"] is None else f"❌ {result['error'][:30]}..."
                })

            results_df = pd.DataFrame(results_data)
            st.dataframe(results_df, use_container_width=True, height=400)

            # Summary statistics
            st.subheader("📈 Summary Statistics")
            col1, col2, col3, col4 = st.columns(4)

            successful = [r for r in st.session_state.batch_results if r["error"] is None]
            failed = [r for r in st.session_state.batch_results if r["error"] is not None]
            accuracies = [r["accuracy"] for r in successful if r["accuracy"] is not None]

            with col1:
                st.metric("Total Images", len(st.session_state.batch_results))
            with col2:
                st.metric("Successful", len(successful))
            with col3:
                st.metric("Failed", len(failed))
            with col4:
                avg_acc = sum(accuracies) / len(accuracies) if accuracies else 0
                st.metric("Avg Accuracy", f"{avg_acc:.1f}%")

            # Phase 1 Validation Report Card
            st.divider()
            st.subheader("🎯 Phase 1 Alignment Validation")

            # Extract telemetry from database_aligned results
            telemetry_items = []
            for result in successful:
                db_aligned = result.get("database_aligned", {})
                if db_aligned and db_aligned.get("available"):
                    foods = db_aligned.get("foods", [])
                    for food in foods:
                        telemetry_items.append({
                            "dish_id": result.get("dish_id"),
                            "predicted_name": food.get("name"),
                            "telemetry": food.get("telemetry", {}),
                            "provenance": food.get("provenance", {})
                        })

            if telemetry_items:
                try:
                    # Validate telemetry schema
                    validate_telemetry_schema(telemetry_items)
                    schema_valid = True
                    schema_msg = "✅ PASS: All items have valid telemetry"
                except ValueError as e:
                    schema_valid = False
                    schema_msg = f"❌ FAIL: {str(e)[:100]}..."

                # Compute telemetry stats
                try:
                    telemetry_stats = compute_telemetry_stats(telemetry_items)

                    # Phase 1 Criteria
                    total_items = telemetry_stats.get("total_items", 0)
                    eligible_count = telemetry_stats.get("conversion_eligible_count", 0)
                    conversion_count = telemetry_stats.get("conversion_applied_count", 0)
                    eligible_rate = (conversion_count / eligible_count * 100) if eligible_count > 0 else 0
                    overall_rate = (conversion_count / total_items * 100) if total_items > 0 else 0
                    stage5_count = telemetry_stats.get("stage5_count", 0)
                    stage5_violations = telemetry_stats.get("stage5_whitelist_violations", [])

                    # Display validation criteria
                    col1, col2 = st.columns(2)

                    with col1:
                        st.markdown("**1. Schema Validation**")
                        st.markdown(schema_msg)

                        st.markdown("**2. Conversion Rates**")
                        if eligible_rate >= 50.0:
                            st.markdown(f"✅ PASS: Eligible rate {eligible_rate:.1f}% ≥50%")
                        else:
                            st.markdown(f"❌ FAIL: Eligible rate {eligible_rate:.1f}% <50%")
                        st.caption(f"Overall: {overall_rate:.1f}% ({conversion_count}/{total_items})")
                        st.caption(f"Eligible: {eligible_rate:.1f}% ({conversion_count}/{eligible_count})")

                    with col2:
                        st.markdown("**3. Stage 5 Whitelist**")
                        if len(stage5_violations) == 0:
                            st.markdown(f"✅ PASS: No whitelist violations ({stage5_count} Stage 5 items)")
                        else:
                            st.markdown(f"❌ FAIL: {len(stage5_violations)} violations")

                        st.markdown("**4. Stage Distribution**")
                        stage_dist = telemetry_stats.get("alignment_stages", {})
                        for stage, count in sorted(stage_dist.items(), key=lambda x: -x[1])[:5]:
                            pct = (count / total_items * 100) if total_items > 0 else 0
                            st.caption(f"{stage}: {count} ({pct:.1f}%)")

                    # Detailed telemetry stats (expandable)
                    with st.expander("🔍 Detailed Telemetry Stats"):
                        st.json(telemetry_stats)

                except Exception as e:
                    st.error(f"Failed to compute telemetry stats: {e}")
            else:
                st.info("No telemetry data available (all items failed or no database alignment)")

            # Download results button
            st.divider()
            results_json = json.dumps(st.session_state.batch_results, indent=2)
            st.download_button(
                label="📥 Download Full Results (JSON)",
                data=results_json,
                file_name=f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True
            )


if __name__ == "__main__":
    main()
