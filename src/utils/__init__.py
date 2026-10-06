"""Public API for utils package."""

from utils.io import load_zipped_raster, get_raster_profile, get_zip_raster_profile, save_raster
from utils.grid import is_nodata, valid_mask, finite_mask, grid_signature, grids_match, align_continuous_to_grid, align_categorical_to_grid
from utils.ops import (
    combine_binary_union,
    validate_inputs,
    recode_binary,
    build_exclusion_mask,
    weighted_sum,
    apply_mask,
    classify_quarter_step,
    highsuit_threshold,
    distribution_summary,
)
from utils.compare import validate_raster_identity, cast_to_reference, hist_l1_diff, raster_stats, compare_rasters
