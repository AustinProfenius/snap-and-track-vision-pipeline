"""
Streamlit UI for nutrition estimation evaluation.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import yaml
import json
import asyncio
from typing import Dict, Any, List
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.runner import EvaluationRunner
from src.core.store import ResultStore
from src.core.loader import NutritionVerseLoader


# Page config
st.set_page_config(
    page_title="NutritionVerse API Test Harness",
    page_icon="🍽️",
    layout="wide"
)

# Session state
if "running" not in st.session_state:
    st.session_state.running = False
if "run_id" not in st.session_state:
    st.session_state.run_id = None


def load_config():
    """Load configuration files."""
    config_dir = Path("configs")

    with open(config_dir / "apis.yaml") as f:
        apis_config = yaml.safe_load(f)

    with open(config_dir / "tasks.yaml") as f:
        tasks_config = yaml.safe_load(f)

    return apis_config, tasks_config


def get_available_runs() -> List[Path]:
    """Get list of available run results."""
    results_dir = Path("runs/results")
    if not results_dir.exists():
        return []

    return sorted(results_dir.glob("*_summary.json"), reverse=True)


def load_run_summary(summary_path: Path) -> Dict[str, Any]:
    """Load run summary."""
    with open(summary_path) as f:
        return json.load(f)


def load_run_results(run_id: str) -> pd.DataFrame:
    """Load run results as DataFrame."""
    store = ResultStore(Path("runs/results"))
    store.jsonl_path = Path(f"runs/results/{run_id}.jsonl")
    return store.to_dataframe()


def main():
    st.title("🍽️ NutritionVerse API Test Harness")
    st.markdown("Evaluate vision-language models on nutrition estimation tasks")

    # Sidebar - Configuration
    with st.sidebar:
        st.header("Configuration")

        # Load configs
        apis_config, tasks_config = load_config()

        # API selection
        enabled_apis = [
            name for name, config in apis_config["apis"].items()
            if config.get("enabled", False)
        ]

        api = st.selectbox("API", enabled_apis)

        # Task selection
        task = st.selectbox(
            "Task",
            list(tasks_config["tasks"].keys()),
            format_func=lambda x: f"{x}: {tasks_config['tasks'][x]['description']}"
        )

        st.divider()

        # Dataset slicing
        st.subheader("Dataset Range")

        # Load dataset to get size
        dataset_loaded = False
        dataset_size = 1000  # Default fallback

        try:
            loader = NutritionVerseLoader(
                Path("data/nvreal"),
                Path("configs/schema_map.yaml")
            )
            dataset_size = len(loader)

            if dataset_size > 0:
                dataset_loaded = True
                st.success(f"✓ Dataset loaded: {dataset_size} samples")
            else:
                st.warning("Dataset directory exists but contains no valid samples")
                dataset_size = 100  # Fallback for empty dataset

        except FileNotFoundError as e:
            st.warning("⚠️ Dataset not found. Please place NutritionVerse-Real data in `data/nvreal/`")
            st.info("Using default range for preview. Dataset is required to run evaluations.")
            dataset_size = 100  # Safe default
        except Exception as e:
            st.error(f"Error loading dataset: {e}")
            st.info("Using default range. Check that schema_map.yaml exists (run schema discovery first).")
            dataset_size = 100  # Safe default

        # Ensure dataset_size is at least 1 to avoid max_value errors
        dataset_size = max(dataset_size, 1)

        col1, col2 = st.columns(2)
        with col1:
            start_idx = st.number_input("Start index", min_value=0, max_value=dataset_size-1, value=0)
        with col2:
            end_idx = st.number_input("End index", min_value=start_idx+1, max_value=dataset_size, value=min(start_idx+20, dataset_size))

        limit = st.number_input("Max samples (0 = no limit)", min_value=0, value=0)

        st.divider()

        # Rate limiting
        st.subheader("Rate Limiting")
        rps = st.slider("Requests per second", min_value=0.1, max_value=10.0, value=0.5, step=0.1)

        budget = st.number_input("Budget cap ($)", min_value=0.0, value=5.0, step=0.5)

        st.divider()

        # Execution options
        st.subheader("Execution")
        resume = st.checkbox("Resume from checkpoint")
        dry_run = st.checkbox("Dry run (preview only)")

    # Main area - tabs
    tab1, tab2, tab3 = st.tabs(["▶️ Run Evaluation", "📊 Results", "📈 Analysis"])

    # Tab 1: Run evaluation
    with tab1:
        st.header("Run Evaluation")

        # Show setup guide if dataset not loaded
        if not dataset_loaded:
            st.info("📚 **First Time Setup Required**")
            with st.expander("Click here for setup instructions", expanded=True):
                st.markdown("""
                ### Quick Setup Guide

                1. **Place your dataset** in the `data/nvreal/` directory:
                   ```
                   data/nvreal/
                     ├── images/
                     │   ├── dish_001.jpg
                     │   └── ...
                     └── annotations/
                         ├── dish_001.json
                         └── ...
                   ```

                2. **Run schema discovery** (from terminal):
                   ```bash
                   python -m src.core.loader --data-dir data/nvreal --inspect
                   ```
                   This creates `configs/schema_map.yaml`

                3. **Verify setup** (optional):
                   ```bash
                   python scripts/verify_setup.py
                   ```

                4. **Refresh this page** after setup is complete

                See [QUICKSTART.md](QUICKSTART.md) for detailed instructions.
                """)

        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"""
            **Configuration Summary:**
            - API: {api}
            - Task: {task}
            - Range: {start_idx} to {end_idx} ({end_idx - start_idx} samples)
            - Rate limit: {rps} req/s
            - Budget: ${budget:.2f}
            - Dataset: {'✓ Loaded' if dataset_loaded else '⚠️ Not loaded'}
            """)

            if not dataset_loaded and not dry_run:
                st.warning("⚠️ Dataset not loaded. Only dry-run mode is available until you set up the dataset.")

        with col2:
            # Disable run button if dataset not loaded (unless dry run)
            run_disabled = st.session_state.running or (not dataset_loaded and not dry_run)

            if st.button("🚀 Start Run", type="primary", disabled=run_disabled):
                st.session_state.running = True

                # Run evaluation
                runner = EvaluationRunner(
                    config_dir=Path("configs"),
                    data_dir=Path("data/nvreal"),
                    run_dir=Path("runs")
                )

                with st.spinner("Running evaluation..."):
                    try:
                        summary = asyncio.run(runner.run_evaluation(
                            api=api,
                            task=task,
                            start=start_idx,
                            end=end_idx,
                            limit=limit if limit > 0 else None,
                            rps=rps,
                            max_cost=budget,
                            resume=resume,
                            dry_run=dry_run
                        ))

                        st.session_state.run_id = summary.get("run_id")
                        st.session_state.running = False

                        st.success(f"✅ Run completed! ID: {st.session_state.run_id}")
                        st.json(summary)

                    except Exception as e:
                        st.error(f"Error: {e}")
                        st.session_state.running = False

        # Live progress (if running)
        if st.session_state.running:
            st.info("⏳ Evaluation in progress...")
            progress_placeholder = st.empty()
            # In a real implementation, you'd poll the checkpoint file for progress

    # Tab 2: Results
    with tab2:
        st.header("Results Browser")

        # Load available runs
        available_runs = get_available_runs()

        if not available_runs:
            st.info("No results yet. Run an evaluation first!")
        else:
            # Run selector
            selected_run = st.selectbox(
                "Select run",
                available_runs,
                format_func=lambda x: x.stem.replace("_summary", "")
            )

            if selected_run:
                summary = load_run_summary(selected_run)
                run_id = summary["run_id"]

                # Summary metrics
                st.subheader("Summary")

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Samples", summary["total_samples"])
                with col2:
                    st.metric("Completed", summary["completed"])
                with col3:
                    st.metric("Errors", summary["errors"])
                with col4:
                    st.metric("Total Cost", f"${summary['total_cost']:.4f}")

                # Metrics
                if "metrics" in summary:
                    st.subheader("Aggregate Metrics")

                    metrics = summary["metrics"]

                    # Create metrics table
                    metrics_data = []

                    for field in ["calories", "protein", "carbs", "fat", "mass"]:
                        mae_key = f"{field}_mae"
                        mape_key = f"{field}_mape"

                        if mae_key in metrics:
                            metrics_data.append({
                                "Field": field.capitalize(),
                                "MAE (mean)": f"{metrics[mae_key]['mean']:.2f}",
                                "MAE (std)": f"{metrics[mae_key]['std']:.2f}",
                                "MAPE (mean)": f"{metrics.get(mape_key, {}).get('mean', 0):.1f}%"
                            })

                    if metrics_data:
                        st.dataframe(metrics_data, use_container_width=True)

                    # Name matching
                    if "name_jaccard" in metrics:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Name Jaccard (mean)", f"{metrics['name_jaccard']['mean']:.3f}")
                        with col2:
                            if "name_precision" in metrics:
                                st.metric("Name Precision", f"{metrics['name_precision']['mean']:.3f}")

                # Per-sample results
                st.subheader("Per-Sample Results")

                try:
                    df = load_run_results(run_id)

                    # Filters
                    col1, col2 = st.columns(2)
                    with col1:
                        show_errors_only = st.checkbox("Show errors only")
                    with col2:
                        if "eval_calories_mape" in df.columns:
                            mape_threshold = st.slider("MAPE threshold (%)", 0, 100, 50)
                        else:
                            mape_threshold = None

                    # Filter dataframe
                    filtered_df = df.copy()

                    if show_errors_only:
                        filtered_df = filtered_df[filtered_df["eval_error_message"].notna()]

                    if mape_threshold and "eval_calories_mape" in filtered_df.columns:
                        filtered_df = filtered_df[filtered_df["eval_calories_mape"] > mape_threshold]

                    # Display
                    st.dataframe(filtered_df, use_container_width=True)

                    # Download button
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        "📥 Download CSV",
                        csv,
                        f"{run_id}.csv",
                        "text/csv"
                    )

                except Exception as e:
                    st.error(f"Error loading results: {e}")

    # Tab 3: Analysis
    with tab3:
        st.header("Analysis & Visualization")

        # Load available runs
        available_runs = get_available_runs()

        if not available_runs:
            st.info("No results yet. Run an evaluation first!")
        else:
            # Run selector
            selected_run = st.selectbox(
                "Select run for analysis",
                available_runs,
                format_func=lambda x: x.stem.replace("_summary", ""),
                key="analysis_run_selector"
            )

            if selected_run:
                summary = load_run_summary(selected_run)
                run_id = summary["run_id"]

                try:
                    df = load_run_results(run_id)

                    # Plot selection
                    plot_type = st.selectbox(
                        "Plot type",
                        ["Calibration (Predicted vs Actual)", "Error Distribution", "MAPE Distribution"]
                    )

                    if plot_type == "Calibration (Predicted vs Actual)":
                        field = st.selectbox("Field", ["calories", "protein", "carbs", "fat"])

                        pred_col = f"pred_{field}"
                        true_col = f"true_{field}"

                        if pred_col in df.columns and true_col in df.columns:
                            plot_df = df[[pred_col, true_col]].dropna()

                            fig = px.scatter(
                                plot_df,
                                x=true_col,
                                y=pred_col,
                                labels={true_col: f"Actual {field}", pred_col: f"Predicted {field}"},
                                title=f"Calibration: {field.capitalize()}"
                            )

                            # Add y=x line
                            max_val = max(plot_df[true_col].max(), plot_df[pred_col].max())
                            fig.add_trace(go.Scatter(
                                x=[0, max_val],
                                y=[0, max_val],
                                mode="lines",
                                line=dict(dash="dash", color="gray"),
                                name="Perfect prediction"
                            ))

                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning(f"Columns not found: {pred_col}, {true_col}")

                    elif plot_type == "Error Distribution":
                        field = st.selectbox("Field", ["calories", "protein", "carbs", "fat"], key="error_field")

                        mae_col = f"eval_{field}_mae"

                        if mae_col in df.columns:
                            plot_df = df[mae_col].dropna()

                            fig = px.histogram(
                                plot_df,
                                x=mae_col,
                                nbins=30,
                                labels={mae_col: f"{field.capitalize()} MAE"},
                                title=f"Distribution of {field.capitalize()} MAE"
                            )

                            st.plotly_chart(fig, use_container_width=True)

                            # Statistics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Mean MAE", f"{plot_df.mean():.2f}")
                            with col2:
                                st.metric("Median MAE", f"{plot_df.median():.2f}")
                            with col3:
                                st.metric("Std MAE", f"{plot_df.std():.2f}")
                        else:
                            st.warning(f"Column not found: {mae_col}")

                    elif plot_type == "MAPE Distribution":
                        field = st.selectbox("Field", ["calories", "protein", "carbs", "fat"], key="mape_field")

                        mape_col = f"eval_{field}_mape"

                        if mape_col in df.columns:
                            plot_df = df[mape_col].dropna()

                            fig = px.histogram(
                                plot_df,
                                x=mape_col,
                                nbins=30,
                                labels={mape_col: f"{field.capitalize()} MAPE (%)"},
                                title=f"Distribution of {field.capitalize()} MAPE"
                            )

                            st.plotly_chart(fig, use_container_width=True)

                            # Statistics
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Mean MAPE", f"{plot_df.mean():.1f}%")
                            with col2:
                                st.metric("Median MAPE", f"{plot_df.median():.1f}%")
                            with col3:
                                st.metric("Std MAPE", f"{plot_df.std():.1f}%")
                        else:
                            st.warning(f"Column not found: {mape_col}")

                except Exception as e:
                    st.error(f"Error loading results: {e}")
                    import traceback
                    st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
