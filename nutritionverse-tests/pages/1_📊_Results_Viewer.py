"""
Results Viewer Page - Mass Estimation & DB Alignment Analytics Dashboard

REDESIGNED FOR NEW WORKFLOW:
- Vision model predicts: name, form, mass_g, count, confidence
- DB alignment provides: matched FDC entry + all nutrition data
- Ground truth has: actual mass_g + nutrition

KEY METRICS:
1. Mass Accuracy (predicted mass vs ground truth mass)
2. Food Identification Accuracy (correct food + form detection)
3. DB Alignment Quality (match score, confidence, stage)
4. Total Mass Error (system-wide mass estimation)
"""
import streamlit as st
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from collections import defaultdict, Counter
from PIL import Image
import os
from decimal import Decimal


# Custom JSON encoder to handle Decimal types
class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)

st.set_page_config(
    page_title="Mass & Alignment Analytics",
    page_icon="📊",
    layout="wide"
)

# Custom CSS for mass-focused analytics
st.markdown("""
<style>
    [data-testid="stMetric"] {
        padding: 8px 12px;
        margin: 0;
    }

    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 600;
    }

    [data-testid="stMetricValue"] {
        font-size: 1.2rem;
    }

    .compact-table {
        font-size: 0.85rem;
    }

    .compact-table td, .compact-table th {
        padding: 6px 10px !important;
    }

    /* Mass error color coding */
    .mass-excellent { background-color: #d4edda; color: #155724; }
    .mass-good { background-color: #cfe2ff; color: #084298; }
    .mass-fair { background-color: #fff3cd; color: #856404; }
    .mass-poor { background-color: #f8d7da; color: #721c24; }

    /* Confidence indicators */
    .conf-high { border-left: 4px solid #28a745; }
    .conf-medium { border-left: 4px solid #ffc107; }
    .conf-low { border-left: 4px solid #dc3545; }

    /* DB alignment badges */
    .stage-foundation { background: #28a745; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
    .stage-legacy { background: #17a2b8; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }
    .stage-branded { background: #ffc107; color: black; padding: 2px 8px; border-radius: 12px; font-size: 0.75rem; }

    hr {
        margin: 0.5rem 0 !important;
    }

    .streamlit-expanderHeader {
        font-size: 0.9rem;
        padding: 8px 12px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Mass Estimation & DB Alignment Analytics")
st.caption("Vision → Database → Nutrition pipeline evaluation")

# Find all result files
results_dir = Path("results")
if not results_dir.exists():
    st.error("Results directory not found")
    st.stop()

result_files = sorted(results_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)

if not result_files:
    st.warning("No result files found in results/")
    st.stop()

# Sidebar: File selection + filters
with st.sidebar:
    st.header("📁 File Selection")

    # Create display names with metadata
    file_options = {}
    for f in result_files:
        try:
            with open(f, 'r') as file:
                preview = json.load(file)
                display_name = f"{f.stem} | {preview.get('model', 'unknown')} | {preview.get('total_images', 0)} imgs"
                file_options[display_name] = f
        except:
            file_options[f.stem] = f

    selected_display = st.selectbox(
        "Choose result file",
        options=list(file_options.keys())
    )
    selected_file = file_options[selected_display]

# Load selected file
def load_results(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)

# Function to save modified data back to JSON
def save_results(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2, cls=DecimalEncoder)
    st.session_state.data_modified = False

# Initialize session state for tracking changes
if 'current_file' not in st.session_state or st.session_state.current_file != selected_file:
    st.session_state.current_file = selected_file
    st.session_state.data_modified = False

data = load_results(selected_file)

# Initialize 'considered' field for all results if not present
for result in data.get("results", []):
    if "considered" not in result:
        result["considered"] = True

# Continue sidebar after loading data
with st.sidebar:
    st.divider()

    # View options
    st.subheader("🎛️ View Options")
    show_db_aligned = st.checkbox("Show DB-Aligned Data", value=True)
    show_insights = st.checkbox("Show Insights Panel", value=True)
    show_charts = st.checkbox("Show Visualizations", value=False)

    st.divider()

    # Filter controls
    st.subheader("🔍 Filters")
    min_confidence = st.slider("Min Confidence", 0.0, 1.0, 0.0, 0.05)
    max_mass_error = st.slider("Max Mass Error %", 0, 200, 200, 10)

    show_errors_only = st.checkbox("Show Failed Only", value=False)

    st.divider()

    # Save button for persisting changes
    st.subheader("💾 Save Changes")
    if st.session_state.get('data_modified', False):
        st.info("📝 You have unsaved changes to the 'considered' flags")
        if st.button("💾 Save to JSON File", type="primary", use_container_width=True):
            save_results(selected_file, data)
            st.success("✅ Changes saved successfully!")
            st.rerun()
    else:
        st.caption("No unsaved changes")

# ========== DATA PROCESSING ==========
results_list = data.get("results", [])
# Filter by 'considered' flag - only include results marked as considered for statistics
considered_results = [r for r in results_list if r.get("considered", True)]
excluded_count = len(results_list) - len(considered_results)

successful_results = [r for r in considered_results if r.get("error") is None]
failed_results = [r for r in considered_results if r.get("error") is not None]

# Check if we have DB alignment data (handle None values)
has_db_aligned = any(
    (r.get("database_aligned") or {}).get("available", False)
    for r in successful_results
)

# Calculate mass accuracy metrics
mass_errors = []
mass_ratios = []
food_detection_scores = []
db_alignment_stages = Counter()
avg_confidence_scores = []

for result in successful_results:
    pred = result.get("prediction", {})
    gt = result.get("ground_truth", {})
    # Handle None case for database_aligned
    db = result.get("database_aligned") or {}

    # Total mass comparison
    pred_total_mass = sum(f.get("mass_g", 0) for f in pred.get("foods", []))
    gt_total_mass = gt.get("total_mass_g", 0)

    if gt_total_mass > 0 and pred_total_mass > 0:
        mass_error_pct = abs(pred_total_mass - gt_total_mass) / gt_total_mass * 100
        mass_errors.append(mass_error_pct)
        mass_ratios.append(pred_total_mass / gt_total_mass)

    # Average confidence across foods
    confidences = [f.get("confidence", 0) for f in pred.get("foods", [])]
    if confidences:
        avg_confidence_scores.append(np.mean(confidences))

    # DB alignment stage tracking (only if db is dict)
    if has_db_aligned and isinstance(db, dict) and db.get("available"):
        telemetry = db.get("telemetry", {})
        stages = telemetry.get("alignment_stages", {})
        for stage, count in stages.items():
            db_alignment_stages[stage] += count

# ========== SUMMARY BANNER ==========
st.markdown("## 📋 Batch Summary")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Model", data.get("model", "Unknown"))
    st.metric("Timestamp", data.get("timestamp", "N/A"))
    if excluded_count > 0:
        st.warning(f"⚠️ {excluded_count} dish(es) excluded from stats")

with col2:
    st.metric("Total Images", data.get("total_images", 0))
    st.metric("Success Rate", f"{len(successful_results)}/{len(considered_results)} ({len(successful_results)/len(considered_results)*100:.1f}%)" if considered_results else "0/0 (0.0%)")
    if avg_confidence_scores:
        avg_conf = np.mean(avg_confidence_scores)
        st.metric("Avg Vision Confidence", f"{avg_conf:.1%}")

with col3:
    if mass_errors:
        avg_mass_error = np.mean(mass_errors)
        median_mass_error = np.median(mass_errors)
        st.metric("Avg Mass Error", f"{avg_mass_error:.1f}%", delta=f"Median: {median_mass_error:.1f}%")

        # Mass estimation quality badge
        if avg_mass_error < 10:
            st.success("🎯 Excellent mass estimation")
        elif avg_mass_error < 20:
            st.info("✅ Good mass estimation")
        elif avg_mass_error < 35:
            st.warning("⚠️ Fair mass estimation")
        else:
            st.error("❌ Poor mass estimation")
    else:
        st.metric("Mass Accuracy", "No data")

# ========== MASS DISTRIBUTION SPARKLINES ==========
if mass_errors and show_charts:
    st.markdown("### 📊 Mass Error Distribution")

    fig = go.Figure()
    fig.add_trace(go.Histogram(
        x=mass_errors,
        nbinsx=20,
        marker_color='rgb(31, 119, 180)',
        opacity=0.7,
        name="Mass Error %"
    ))
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_title="Mass Error %",
        yaxis_title="Count",
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)

# ========== AUTOMATED INSIGHTS ==========
if show_insights and successful_results:
    st.markdown("### 🔍 Automated Insights")

    insights_col1, insights_col2 = st.columns(2)

    with insights_col1:
        st.markdown("**Mass Estimation Patterns:**")

        if mass_ratios:
            over_estimated = sum(1 for r in mass_ratios if r > 1.15)
            under_estimated = sum(1 for r in mass_ratios if r < 0.85)

            if over_estimated > len(mass_ratios) * 0.5:
                st.warning(f"⬆️ System over-estimates mass in {over_estimated}/{len(mass_ratios)} dishes (>15%)")
            elif under_estimated > len(mass_ratios) * 0.5:
                st.warning(f"⬇️ System under-estimates mass in {under_estimated}/{len(mass_ratios)} dishes (>15%)")
            else:
                st.success(f"✅ Balanced estimation: {len(mass_ratios) - over_estimated - under_estimated}/{len(mass_ratios)} within ±15%")

        # Confidence analysis
        if avg_confidence_scores:
            low_conf_count = sum(1 for c in avg_confidence_scores if c < 0.65)
            if low_conf_count > len(avg_confidence_scores) * 0.3:
                st.warning(f"⚠️ {low_conf_count}/{len(avg_confidence_scores)} dishes have low confidence (<65%)")

    with insights_col2:
        st.markdown("**DB Alignment Quality:**")

        if db_alignment_stages:
            total_alignments = sum(db_alignment_stages.values())

            # Show stage distribution
            for stage, count in db_alignment_stages.most_common(3):
                pct = count / total_alignments * 100
                badge_class = "stage-foundation" if "foundation" in stage else \
                             "stage-legacy" if "legacy" in stage else "stage-branded"
                st.markdown(f"<span class='{badge_class}'>{stage}</span> {count} ({pct:.0f}%)", unsafe_allow_html=True)

            # Check for concerning patterns
            branded_count = sum(count for stage, count in db_alignment_stages.items() if "branded" in stage)
            if branded_count / total_alignments > 0.3:
                st.warning(f"⚠️ High branded usage: {branded_count}/{total_alignments} ({branded_count/total_alignments:.0%})")

# ========== DISH RESULTS TABLE ==========
st.markdown("### 📋 Dish Results - Mass Accuracy View")

if has_db_aligned and show_db_aligned:
    table_tabs = st.tabs(["🎯 Mass Estimation", "🗄️ DB Alignment Quality"])
else:
    table_tabs = [st.container()]

# Tab 1: Mass Estimation Focus
with table_tabs[0]:
    st.caption("Vision model mass predictions vs ground truth")

    table_data = []
    for idx, result in enumerate(successful_results):
        pred = result.get("prediction", {})
        gt = result.get("ground_truth", {})

        pred_foods = pred.get("foods", [])
        pred_total_mass = sum(f.get("mass_g", 0) for f in pred_foods)
        gt_total_mass = gt.get("total_mass_g", 0)

        mass_error = 0
        if gt_total_mass > 0:
            mass_error = abs(pred_total_mass - gt_total_mass) / gt_total_mass * 100

        # Average confidence
        avg_conf = np.mean([f.get("confidence", 0) for f in pred_foods]) if pred_foods else 0

        # Food count comparison
        pred_food_count = len(pred_foods)
        gt_food_count = len(gt.get("foods", []))

        table_data.append({
            "Dish": result.get("dish_id", "unknown"),
            "Pred Mass (g)": f"{pred_total_mass:.0f}",
            "GT Mass (g)": f"{gt_total_mass:.0f}",
            "Mass Error %": f"{mass_error:.1f}",
            "Foods": f"{pred_food_count} (GT: {gt_food_count})",
            "Avg Conf": f"{avg_conf:.0%}",
            "Status": "✅" if mass_error < 20 else "⚠️" if mass_error < 40 else "❌"
        })

    if table_data:
        df_mass = pd.DataFrame(table_data)
        st.dataframe(df_mass, use_container_width=True, hide_index=True)

# Tab 2: DB Alignment Quality
if has_db_aligned and show_db_aligned:
    with table_tabs[1]:
        st.caption("Database alignment match quality and confidence")

        alignment_data = []
        for idx, result in enumerate(successful_results):
            # Handle None case for database_aligned
            db = result.get("database_aligned") or {}
            if not isinstance(db, dict) or not db.get("available"):
                continue

            foods = db.get("foods", [])
            if not foods:
                continue

            avg_score = np.mean([f.get("score", 0) for f in foods])
            avg_conf = np.mean([f.get("confidence", 0) for f in foods])

            # Stage distribution
            telemetry = db.get("telemetry", {})
            stages = telemetry.get("alignment_stages", {})
            primary_stage = max(stages.keys(), key=lambda k: stages[k]) if stages else "unknown"

            alignment_data.append({
                "Dish": result.get("dish_id", "unknown"),
                "Items": len(foods),
                "Avg Match Score": f"{avg_score:.1f}",
                "Avg DB Conf": f"{avg_conf:.0%}",
                "Primary Stage": primary_stage,
                "Status": "🟢" if avg_score > 2.5 else "🟡" if avg_score > 1.5 else "🔴"
            })

        if alignment_data:
            df_align = pd.DataFrame(alignment_data)
            st.dataframe(df_align, use_container_width=True, hide_index=True)

# ========== DETAILED INDIVIDUAL RESULTS ==========
st.markdown("### 🔍 Detailed Individual Results")
st.caption("Click to expand each dish for full analysis")

for idx, result in enumerate(results_list):
    dish_id = result.get("dish_id", "Unknown")
    error = result.get("error")
    considered = result.get("considered", True)

    # Status badge
    if error:
        status = "❌ Failed"
        status_color = "🔴"
    elif not considered:
        status = "⏸️ Excluded"
        status_color = "⚪"
    else:
        status = "✅ Success"
        status_color = "🟢"

    with st.expander(f"#{idx + 1}: {dish_id} - {status}", expanded=False):
        # Display dish image
        image_path = result.get("image_path")
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                st.image(img, caption=f"Dish {dish_id}", width=400)
            except Exception as e:
                st.caption(f"⚠️ Could not load image: {e}")

        # Add checkbox to include/exclude from statistics
        considered_key = f"considered_{idx}"
        current_considered = result.get("considered", True)

        new_considered = st.checkbox(
            "✅ Include in overall statistics",
            value=current_considered,
            key=considered_key,
            help="Uncheck to exclude this dish from accuracy calculations (e.g., if image is bad or contains mislabeled foods)"
        )

        # Update the result if checkbox changed
        if new_considered != current_considered:
            result["considered"] = new_considered
            st.session_state.data_modified = True
            st.rerun()

        st.divider()

        # Handle None case - some results may have database_aligned: null
        db_aligned = result.get("database_aligned") or {}
        has_db = db_aligned.get("available", False) if isinstance(db_aligned, dict) else False

        # Show error if present
        if error:
            st.error(f"**Error:** {error}")
            continue

        # Layout: Prediction | Ground Truth | DB Alignment
        detail_cols = st.columns(3) if has_db and show_db_aligned else st.columns(2)

        # Column 1: Vision Prediction
        with detail_cols[0]:
            st.markdown("**🎯 Vision Prediction**")
            pred = result.get("prediction", {})
            pred_foods = pred.get("foods", [])

            if pred_foods:
                pred_total_mass = sum(f.get("mass_g", 0) for f in pred_foods)
                st.caption(f"Total Mass: {pred_total_mass:.0f}g | {len(pred_foods)} items")

                for food in pred_foods:
                    name = food.get("name", "unknown")
                    form = food.get("form", "unknown")
                    mass = food.get("mass_g", 0)
                    count = food.get("count", 1)
                    conf = food.get("confidence", 0)

                    # Confidence badge
                    conf_class = "conf-high" if conf > 0.7 else "conf-medium" if conf > 0.5 else "conf-low"

                    st.markdown(f"""
                    <div class='{conf_class}' style='padding: 8px; margin: 4px 0; border-radius: 4px; background: #fffff;'>
                        <strong>{name}</strong> ({form})<br>
                        Mass: {mass:.0f}g | Count: {count} | Conf: {conf:.0%}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No foods predicted")

        # Column 2: Ground Truth
        with detail_cols[1]:
            st.markdown("**✅ Ground Truth**")
            gt = result.get("ground_truth", {})
            gt_foods = gt.get("foods", [])
            gt_total_mass = gt.get("total_mass_g", 0)
            gt_total_cals = gt.get("total_calories", 0)

            st.caption(f"Total: {gt_total_mass:.0f}g | {gt_total_cals:.0f} kcal")

            if gt_foods:
                for food in gt_foods:
                    name = food.get("name", "unknown")
                    mass = food.get("mass_g", 0)
                    cals = food.get("calories", 0)

                    st.markdown(f"""
                    <div style='padding: 8px; margin: 4px 0; border-radius: 4px; background: #fffff;'>
                        <strong>{name}</strong><br>
                        Mass: {mass:.0f}g | Cals: {cals:.0f}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.caption("No ground truth data")

        # Column 3: DB Alignment (if available)
        if has_db and show_db_aligned and isinstance(db_aligned, dict):
            with detail_cols[2]:
                st.markdown("**🗄️ DB Alignment**")
                db_foods = db_aligned.get("foods", []) if db_aligned else []
                db_totals = db_aligned.get("totals", {}) if db_aligned else {}

                if db_totals:
                    st.caption(f"Total: {db_totals.get('mass_g', 0):.0f}g | {db_totals.get('calories', 0):.0f} kcal")

                if db_foods:
                    for food in db_foods:
                        pred_name = food.get("name", "unknown")
                        matched_name = food.get("fdc_name", "unknown")
                        score = food.get("match_score", 0)
                        conf = food.get("confidence", 0)
                        data_type = food.get("data_type", "unknown")

                        # Stage badge
                        badge_class = "stage-foundation" if "foundation" in data_type else \
                                     "stage-legacy" if "legacy" in data_type else "stage-branded"

                        telemetry = food.get("telemetry", {})
                        mass = food.get("mass_g", 0)
                        cals = food.get("calories", 0)
                        raw_source = telemetry.get("raw_source", "N/A")
                        raw_name = telemetry.get("raw_name", "N/A")

                        st.markdown(f"""
                        <div style='padding: 8px; margin: 4px 0; border-radius: 4px; background: #fffff;'>
                            {pred_name}<br>
                            → <strong>{matched_name}</strong><br>
                            <span class='{badge_class}'>{data_type}</span><br>
                            Score: {score:.1f} | Conf: {conf:.0%}<br>
                            {mass:.0f}g | {cals:.0f} kcal<br>
                            Food Type: {raw_source:s} <br>
                             Raw Name: {raw_name:s}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.caption("No DB alignment data")

        # Mass accuracy metrics
        if pred_foods and gt_total_mass > 0:
            st.divider()
            st.markdown("#### 📊 Mass Accuracy")

            pred_total_mass = sum(f.get("mass_g", 0) for f in pred_foods)
            mass_error_pct = abs(pred_total_mass - gt_total_mass) / gt_total_mass * 100
            mass_ratio = pred_total_mass / gt_total_mass

            acc_col1, acc_col2, acc_col3 = st.columns(3)

            with acc_col1:
                st.metric("Mass Error", f"{mass_error_pct:.1f}%")

            with acc_col2:
                direction = "Over" if mass_ratio > 1 else "Under"
                st.metric("Estimation Ratio", f"{mass_ratio:.2f}x", delta=f"{direction}-estimated")

            with acc_col3:
                if mass_error_pct < 10:
                    st.success("🎯 Excellent")
                elif mass_error_pct < 20:
                    st.info("✅ Good")
                elif mass_error_pct < 35:
                    st.warning("⚠️ Fair")
                else:
                    st.error("❌ Poor")

st.markdown("---")
st.caption(f"Results loaded from: {selected_file.name}")
