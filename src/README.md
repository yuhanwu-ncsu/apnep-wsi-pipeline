# Helper Function

The `/src` folder contains reusable function to serve the analysis pipeline

## Quick Start

To test if set up is correct, try to run this in the terminal
```
# Verify the internal modules are importable
pixi run -e processing python -c "from utils.spatial_utils import get_zip_raster_profile; print('✅ Pathing Correct!')"
```

If testing in the `notebooks/`, run a cell like something below here
```
from utils.spatial_utils import get_zip_raster_profile
```


## Directory

```
src/
└── utils/      # basic utils used for the analysis
```