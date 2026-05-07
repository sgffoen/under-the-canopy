from __future__ import annotations

import math
from typing import List, Optional, Tuple

from compas.datastructures import Graph
from compas.geometry import (
    oriented_bounding_box_numpy,
    Box,
)

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def curve_bounding_box(curve, sample=50) -> Box:
    """Compute the oriented bounding box of a set of points.

    Parameters
    ----------
    points : list of Point
        The input points.

    Returns
    -------
    :class:`compas.geometry.Box`
        The oriented bounding box.
    """
    t, pts = curve.divide_by_count(sample, return_points=True)
    bbox = oriented_bounding_box_numpy(pts)
    bbox = Box.from_bounding_box(bbox)
    return bbox

