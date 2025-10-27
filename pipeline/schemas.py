"""
Pydantic schemas for the unified alignment pipeline.

Ensures type safety and schema validation across web app and batch harness.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class DetectedFood(BaseModel):
    """Food detected by vision model."""
    name: str
    form: str
    mass_g: float
    modifiers: List[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    count: Optional[int] = None


class AlignmentRequest(BaseModel):
    """Request to align detected foods with FDC database."""
    image_id: str
    foods: List[DetectedFood]
    mode: Dict[str, Any] = Field(default_factory=dict)  # e.g., {"mass_only": True}
    config_version: str


class FoodAlignment(BaseModel):
    """Aligned food with FDC match and telemetry."""
    name: str
    form: str
    mass_g: float

    # Alignment results
    alignment_stage: str
    fdc_id: Optional[int] = None
    fdc_name: Optional[str] = None
    conversion_applied: bool = False
    match_score: Optional[float] = None

    # Nutrition (per 100g from FDC, scaled by mass_g)
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None

    # Telemetry summary (subset for display)
    method: Optional[str] = None
    method_reason: Optional[str] = None
    variant_chosen: Optional[str] = None


class Totals(BaseModel):
    """Aggregated nutrition totals for all foods in image."""
    mass_g: float
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fat_g: Optional[float] = None


class AlignmentResult(BaseModel):
    """Complete alignment result with version tracking."""
    image_id: str
    foods: List[FoodAlignment]
    totals: Totals
    telemetry_summary: Dict[str, Any] = Field(default_factory=dict)

    # Version tracking (mandatory)
    code_git_sha: str
    config_version: str
    fdc_index_version: str


class TelemetryEvent(BaseModel):
    """
    Per-food telemetry event with mandatory fields for drift detection.

    Schema enforced by tests - build fails if any field missing.
    """
    # Identity
    image_id: str
    food_idx: int
    query: str

    # Alignment outcome
    alignment_stage: str
    fdc_id: Optional[int] = None
    fdc_name: Optional[str] = None

    # Candidate search
    candidate_pool_size: int
    foundation_pool_count: int = 0
    search_variants_tried: List[str] = Field(default_factory=list)
    variant_chosen: Optional[str] = None

    # Scoring
    stage1b_score: Optional[float] = None
    match_score: Optional[float] = None

    # Method resolution
    method: Optional[str] = None
    method_reason: Optional[str] = None
    method_inferred: Optional[bool] = None

    # Conversion (Stage 2)
    conversion_applied: bool = False
    conversion_steps: Optional[List[str]] = None
    raw_fdc_id: Optional[int] = None
    raw_fdc_name: Optional[str] = None
    cook_method: Optional[str] = None
    retention_factor: Optional[float] = None

    # Guards and filters
    negative_vocab_blocks: List[str] = Field(default_factory=list)
    sodium_gate_blocks: Optional[str] = None
    atwater_ok: Optional[bool] = None
    atwater_deviation_pct: Optional[float] = None
    oil_uptake_g_per_100g: Optional[float] = None

    # Version tracking (mandatory)
    code_git_sha: str
    config_version: str
    fdc_index_version: str
    config_source: str = "external"  # "external" or "fallback"
