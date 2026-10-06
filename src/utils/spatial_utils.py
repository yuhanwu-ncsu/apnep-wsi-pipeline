"""Backwards-compatible shim — re-exports from the new modules.

Existing imports like `from utils.spatial_utils import load_zipped_raster` continue to work.
"""

from utils.io import load_zipped_raster, get_raster_profile, get_zip_raster_profile
from utils.grid import is_nodata, valid_mask, finite_mask, grid_signature, grids_match, align_continuous_to_grid
from utils.ops import combine_binary_union
from utils.compare import validate_raster_identity, cast_to_reference, hist_l1_diff, raster_stats, compare_rasters

# Keep old name as alias for backwards compat
combine_suitability_binary = combine_binary_union
