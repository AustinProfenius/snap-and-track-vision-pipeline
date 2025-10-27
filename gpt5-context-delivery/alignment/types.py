"""
Type definitions for nutrition conversion and alignment system.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class FdcEntry:
    """Foundation/Legacy/Branded FDC database entry."""
    fdc_id: int
    core_class: str              # Normalized food class (e.g., "rice_white", "beef_steak")
    name: str                    # Original FDC name
    source: str                  # "foundation", "sr_legacy", "branded"
    form: str                    # "raw", "cooked", "dried", etc.
    method: Optional[str] = None # Cooking method if cooked: "boiled", "grilled", etc.

    # Nutrition per 100g
    protein_100g: float = 0.0
    carbs_100g: float = 0.0
    fat_100g: float = 0.0
    kcal_100g: float = 0.0
    fiber_100g: float = 0.0

    # Data type from FDC
    data_type: str = ""          # "foundation_food", "sr_legacy_food", "branded_food"

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionFactors:
    """Conversion factors for raw→cooked transformation."""
    # Mass change
    hydration_factor: Optional[float] = None      # Grains/legumes (2.0-3.0×)
    shrinkage_fraction: Optional[float] = None    # Meats/vegetables (0.10-0.30)

    # Fat adjustments
    fat_render_fraction: Optional[float] = None   # Fat lost during cooking (0.15-0.35)
    oil_uptake_g_per_100g: Optional[float] = None # Added oil during cooking

    # Macro retention (after cooking losses)
    protein_retention: float = 1.0
    carbs_retention: float = 1.0
    fat_retention: float = 1.0

    # Metadata
    method: str = ""
    source_profile: str = ""  # Which profile was used


@dataclass
class ConvertedEntry:
    """FDC entry after raw→cooked conversion."""
    # Original entry
    original: FdcEntry

    # Converted nutrition per 100g
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    kcal_100g: float
    fiber_100g: float

    # Conversion metadata
    conversion_factors: ConversionFactors
    method: str
    form: str = "cooked"

    # Provenance tracking
    provenance: Dict[str, Any] = field(default_factory=dict)

    # Quality indicators
    atwater_ok: bool = True
    energy_clamped: bool = False
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "fdc_id": self.original.fdc_id,
            "name": self.original.name,
            "core_class": self.original.core_class,
            "source": self.original.source,
            "form": self.form,
            "method": self.method,
            "data_type": self.original.data_type,
            "nutrition_100g": {
                "protein_g": self.protein_100g,
                "carbs_g": self.carbs_100g,
                "fat_g": self.fat_100g,
                "kcal": self.kcal_100g,
                "fiber_g": self.fiber_100g
            },
            "conversion": {
                "hydration_factor": self.conversion_factors.hydration_factor,
                "shrinkage_fraction": self.conversion_factors.shrinkage_fraction,
                "fat_render_fraction": self.conversion_factors.fat_render_fraction,
                "oil_uptake_g_per_100g": self.conversion_factors.oil_uptake_g_per_100g,
                "method": self.conversion_factors.method,
                "source_profile": self.conversion_factors.source_profile
            },
            "provenance": self.provenance,
            "quality": {
                "atwater_ok": self.atwater_ok,
                "energy_clamped": self.energy_clamped,
                "confidence": self.confidence
            }
        }


@dataclass
class AlignmentResult:
    """Result of food alignment with conversion."""
    # Match info
    fdc_id: Optional[int]
    name: str
    source: str                  # "foundation", "sr_legacy", "branded", "none"

    # Nutrition per 100g
    protein_100g: float
    carbs_100g: float
    fat_100g: float
    kcal_100g: float

    # Alignment metadata
    match_score: float           # Semantic match score
    confidence: float            # Final confidence (0-1)
    alignment_stage: str         # "stage1_cooked_exact", "stage2_raw_convert", etc.
    method: str                  # Resolved cooking method
    method_reason: str           # How method was determined
    conversion_applied: bool     # Was raw→cooked conversion used?

    # Telemetry
    telemetry: Dict[str, Any] = field(default_factory=dict)
