"""
Adapter to make FDCAlignmentWithConversion compatible with web app interface.

This adapter wraps the new Stage 5 alignment engine to work with the existing
web app that expects the FDCAlignmentEngineV2 interface.
"""

from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import os

from ..nutrition.alignment.align_convert import FDCAlignmentWithConversion
from .fdc_database import FDCDatabase
from .search_normalizer import normalize_query, generate_query_variants


class AlignmentEngineAdapter:
    """
    Adapter for FDCAlignmentWithConversion that provides V2 interface.

    This allows the web app to use the new Stage 5 alignment engine
    without changing the web app code.
    """

    def __init__(self, enable_conversion: bool = True, alignment_engine=None, fdc_db=None):
        """
        Initialize alignment engine adapter.

        Phase 7.3: Removed double-init - alignment_engine and fdc_db are injected
        by the pipeline (run.py) to avoid "hardcoded defaults" warning.

        For web app compatibility: If alignment_engine and fdc_db are not provided,
        they will be auto-initialized on first use.

        Args:
            enable_conversion: Enable raw→cooked conversion (always True for new engine)
            alignment_engine: Optional pre-initialized alignment engine
            fdc_db: Optional pre-initialized FDC database
        """
        load_dotenv(override=True)

        # Phase 7.3: Support both injection (pipeline) and auto-init (web app)
        self.alignment_engine = alignment_engine
        self.fdc_db = fdc_db
        self.db_available = False
        self._auto_init_attempted = False

    def _auto_initialize(self):
        """Auto-initialize engine and database if not provided (for web app compatibility)."""
        if self._auto_init_attempted:
            return

        self._auto_init_attempted = True

        try:
            print("[ADAPTER] Auto-initializing alignment engine and database...")

            # Check for database connection
            neon_url = os.getenv("NEON_CONNECTION_URL")
            if not neon_url:
                print("[ADAPTER] ERROR: NEON_CONNECTION_URL not found in environment")
                self.db_available = False
                return

            # Initialize FDC database
            self.fdc_db = FDCDatabase()
            print(f"[ADAPTER] FDC Database initialized")

            # Load configs from pipeline/configs (single source of truth)
            from pathlib import Path
            import sys

            # Find repo root (3 levels up from this file)
            repo_root = Path(__file__).parent.parent.parent.parent
            configs_path = repo_root / "configs"

            if not configs_path.exists():
                print(f"[ADAPTER] WARNING: Configs path not found: {configs_path}")
                print(f"[ADAPTER] Falling back to hardcoded defaults")
                # Initialize without configs (fallback to hardcoded)
                self.alignment_engine = FDCAlignmentWithConversion(fdc_db=self.fdc_db)
            else:
                # Add pipeline to path to import config_loader
                pipeline_path = str(repo_root / "pipeline")
                if pipeline_path not in sys.path:
                    sys.path.insert(0, pipeline_path)

                from config_loader import load_pipeline_config
                cfg = load_pipeline_config(root=str(configs_path))
                print(f"[ADAPTER] Loaded configs from {configs_path}")
                print(f"[ADAPTER] Config version: {cfg.config_version}")

                # Initialize alignment engine with individual config parameters
                self.alignment_engine = FDCAlignmentWithConversion(
                    fdc_db=self.fdc_db,
                    class_thresholds=cfg.thresholds,
                    negative_vocab=cfg.neg_vocab,
                    feature_flags=cfg.feature_flags,
                    variants=cfg.variants,
                    proxy_rules=cfg.proxy_rules,
                    category_allowlist=cfg.category_allowlist,
                    branded_fallbacks=cfg.branded_fallbacks,
                    unit_to_grams=cfg.unit_to_grams
                )
            print(f"[ADAPTER] Alignment engine initialized with configs")

            self.db_available = True

        except Exception as e:
            print(f"[ADAPTER] ERROR: Failed to auto-initialize: {e}")
            import traceback
            traceback.print_exc()
            self.db_available = False

    def align_prediction_batch(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """
        Align all foods in a prediction (V2 interface).

        Args:
            prediction: Prediction dict with "foods" list

        Returns:
            Dict with alignments and totals compatible with web app
        """
        # Phase 7.3: Check if engine and DB were injected by pipeline, or auto-initialize
        if self.alignment_engine is None or self.fdc_db is None:
            self._auto_initialize()

        print(f"[ADAPTER] ===== Starting batch alignment (Stage 5 Engine) =====")
        print(f"[ADAPTER] DB Available: {self.db_available}")

        if not self.db_available:
            print("[ADAPTER] Database not available")
            return {
                "available": False,
                "foods": [],
                "totals": {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}
            }

        foods = prediction.get("foods", [])
        print(f"[ADAPTER] Processing {len(foods)} foods")

        aligned_foods = []
        totals = {"mass_g": 0, "calories": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0}

        # Telemetry tracking
        telemetry = {
            "total_items": len(foods),
            "alignment_stages": {},
            "conversion_applied_count": 0,
            "stage5_proxy_count": 0,
            "unknown_stages": 0,
            "unknown_methods": 0
        }

        for food_idx, food in enumerate(foods):
            name = food.get("name", "")
            form = food.get("form", "")
            mass_g = food.get("mass_g", 0)
            predicted_kcal = food.get("calories_per_100g", 100)  # Default if missing
            confidence = food.get("confidence", 0.85)

            if not name:
                print(f"[ADAPTER] Skipping food {food_idx}: missing name")
                continue

            print(f"[ADAPTER] [{food_idx+1}/{len(foods)}] Aligning: {name} ({form})")

            # Generate query variants (singular, plural, FDC hints)
            query_variants = generate_query_variants(name)
            fdc_candidates = []
            used_query = name.lower()
            variants_tried = len(query_variants)

            # SURGICAL FIX: Score variants by Foundation count, total count, AND raw bias
            # Prefer variants with "raw" suffix for fruits/vegetables
            best_variant = None
            best_candidates = []
            best_score = (-1, -1, -1)  # (foundation_count, total_count, raw_bias)

            for variant in query_variants:
                try:
                    candidates = self.fdc_db.search_foods(variant, limit=50)
                    if not candidates:
                        continue

                    # Count Foundation/SR Legacy entries (preferred over branded)
                    foundation_count = sum(
                        1 for c in candidates
                        if str(c.get("source", c.get("data_type", ""))).lower()
                        in {"foundation_food", "foundation", "sr_legacy_food", "sr_legacy"}
                    )

                    # Prefer variants ending with " raw" (common for fruits/vegetables)
                    raw_bias = 1 if (" raw" in (" " + variant) or variant.endswith(" raw")) else 0

                    score_tuple = (foundation_count, len(candidates), raw_bias)

                    # Prefer variant with best score (Foundation count > total count > raw bias)
                    if score_tuple > best_score:
                        best_score = score_tuple
                        best_variant = variant
                        best_candidates = candidates

                except Exception as e:
                    print(f"[ADAPTER] Database search failed for variant '{variant}': {e}")
                    continue

            # Use best variant (or empty if all failed)
            if best_variant:
                used_query = best_variant
                fdc_candidates = best_candidates
                if best_variant != name.lower():
                    foundation_ct, total_ct, raw_bias = best_score
                    print(f"[ADAPTER]   Query variant matched: '{name}' → '{best_variant}' ({total_ct} candidates, {foundation_ct} Foundation/SR)")
            else:
                fdc_candidates = []

            # Phase 7.3 Fix: ALWAYS call align_food_item, even with empty candidates
            # This allows Stage 5B salad decomposition to run
            if not fdc_candidates:
                print(f"[ADAPTER]   No FDC candidates found (tried {variants_tried} variants), trying Stage 5B...")

            # Run alignment using new engine
            try:
                result = self.alignment_engine.align_food_item(
                    predicted_name=name,
                    predicted_form=form,
                    predicted_kcal_100g=predicted_kcal,
                    fdc_candidates=fdc_candidates,
                    confidence=confidence
                )

                # Add search variant telemetry (NEW: variant_chosen, foundation_pool_count)
                result.telemetry["variant_chosen"] = used_query
                result.telemetry["search_variants_tried"] = variants_tried
                result.telemetry["foundation_pool_count"] = sum(
                    1 for c in (fdc_candidates or [])
                    if str(c.get('source', c.get('data_type', ''))).lower()
                    in {"foundation_food", "foundation", "sr_legacy_food", "sr_legacy"}
                )

                # Phase 7.3: Handle Stage 5B salad decomposition (multiple components)
                expanded_foods = result.telemetry.get("expanded_foods", [])
                if expanded_foods and result.alignment_stage == "stage5b_salad_decomposition":
                    recipe_name = result.telemetry.get("decomposition_recipe", "unknown")
                    print(f"[ADAPTER]   ✓ Decomposed '{name}' via Stage 5B: {recipe_name} ({len(expanded_foods)} components)")

                    # Process each component separately
                    for comp_idx, comp in enumerate(expanded_foods):
                        comp_mass = mass_g * comp.get("decomposition_ratio", 0.0)
                        comp_name = comp.get("name", f"component_{comp_idx}")
                        comp_fdc_id = comp.get("fdc_id")
                        comp_fdc_name = comp.get("fdc_name", comp_name)
                        comp_stage = comp.get("alignment_stage", "stage5b_salad_component")

                        # Track stage
                        telemetry["alignment_stages"][comp_stage] = \
                            telemetry["alignment_stages"].get(comp_stage, 0) + 1

                        # Calculate nutrition (with None safety)
                        if comp_fdc_id:
                            kcal = comp.get("kcal_100g") or 0
                            protein = comp.get("protein_100g") or 0
                            carbs = comp.get("carbs_100g") or 0
                            fat = comp.get("fat_100g") or 0

                            calories = (kcal * comp_mass) / 100
                            protein_g = (protein * comp_mass) / 100
                            carbs_g = (carbs * comp_mass) / 100
                            fat_g = (fat * comp_mass) / 100

                            totals["mass_g"] += comp_mass
                            totals["calories"] += calories
                            totals["protein_g"] += protein_g
                            totals["carbs_g"] += carbs_g
                            totals["fat_g"] += fat_g

                            print(f"[ADAPTER]     [{comp_idx+1}/{len(expanded_foods)}] {comp_name} → {comp_fdc_name} ({comp_mass:.1f}g)")

                            # Add as separate food item
                            aligned_foods.append({
                                "name": f"{name} - {comp_name}",
                                "form": form,
                                "mass_g": comp_mass,
                                "calories": round(calories, 1),
                                "protein_g": round(protein_g, 1),
                                "carbs_g": round(carbs_g, 1),
                                "fat_g": round(fat_g, 1),
                                "fdc_id": comp_fdc_id,
                                "fdc_name": comp_fdc_name,
                                "confidence": confidence,
                                "match_score": 0.0,
                                "alignment_stage": comp_stage,
                                "conversion_applied": False
                            })
                        else:
                            print(f"[ADAPTER]     [{comp_idx+1}/{len(expanded_foods)}] {comp_name} → NO MATCH")

                    continue  # Skip normal processing for decomposed items

                # Extract telemetry (normal single-item processing)
                stage = result.telemetry.get("alignment_stage", "unknown")
                method = result.telemetry.get("method", "unknown")
                conversion_applied = result.telemetry.get("conversion_applied", False)
                proxy_used = result.telemetry.get("proxy_used", False)

                # Track telemetry
                telemetry["alignment_stages"][stage] = \
                    telemetry["alignment_stages"].get(stage, 0) + 1

                if conversion_applied:
                    telemetry["conversion_applied_count"] += 1

                if stage == "stage5_proxy_alignment":
                    telemetry["stage5_proxy_count"] += 1

                if stage == "unknown":
                    telemetry["unknown_stages"] += 1

                if method == "unknown":
                    telemetry["unknown_methods"] += 1

                # Calculate nutrition for this food item
                if result.fdc_id:
                    calories = (result.kcal_100g * mass_g) / 100
                    protein_g = (result.protein_100g * mass_g) / 100
                    carbs_g = (result.carbs_100g * mass_g) / 100
                    fat_g = (result.fat_100g * mass_g) / 100

                    # Add to totals
                    totals["mass_g"] += mass_g
                    totals["calories"] += calories
                    totals["protein_g"] += protein_g
                    totals["carbs_g"] += carbs_g
                    totals["fat_g"] += fat_g

                    print(f"[ADAPTER]   ✓ Matched: {result.name} (stage={stage}, conversion={conversion_applied})")
                    if proxy_used:
                        proxy_formula = result.telemetry.get("proxy_formula", "N/A")
                        print(f"[ADAPTER]     Stage 5 Proxy: {proxy_formula}")
                else:
                    calories = 0
                    protein_g = 0
                    carbs_g = 0
                    fat_g = 0
                    print(f"[ADAPTER]   ✗ No match")

                # Build aligned food entry
                aligned_food = {
                    "name": name,
                    "form": form,
                    "mass_g": mass_g,
                    "calories": round(calories, 1),
                    "protein_g": round(protein_g, 2),
                    "carbs_g": round(carbs_g, 2),
                    "fat_g": round(fat_g, 2),
                    "fdc_id": result.fdc_id,
                    "fdc_name": result.name,
                    "match_score": result.confidence,
                    "alignment_stage": stage,
                    "conversion_applied": conversion_applied,
                    "telemetry": result.telemetry  # Include full telemetry
                }

                aligned_foods.append(aligned_food)

            except Exception as e:
                print(f"[ADAPTER]   ❌ Alignment failed: {e}")
                import traceback
                traceback.print_exc()
                aligned_foods.append({
                    "name": name,
                    "form": form,
                    "mass_g": mass_g,
                    "calories": 0,
                    "protein_g": 0,
                    "carbs_g": 0,
                    "fat_g": 0,
                    "fdc_id": None,
                    "fdc_name": "ERROR",
                    "match_score": 0.0,
                    "alignment_stage": "error",
                    "conversion_applied": False,
                    "error": str(e)
                })

        # Calculate conversion rate
        if telemetry["total_items"] > 0:
            telemetry["conversion_rate"] = telemetry["conversion_applied_count"] / telemetry["total_items"]
        else:
            telemetry["conversion_rate"] = 0.0

        print(f"[ADAPTER] ===== Batch alignment complete =====")
        print(f"[ADAPTER] Conversion rate: {telemetry['conversion_rate']:.1%}")
        print(f"[ADAPTER] Stage 5 proxy count: {telemetry['stage5_proxy_count']}")
        print(f"[ADAPTER] Stage distribution: {telemetry['alignment_stages']}")

        return {
            "available": True,
            "foods": aligned_foods,
            "totals": totals,
            "telemetry": telemetry  # NEW: Include telemetry
        }
