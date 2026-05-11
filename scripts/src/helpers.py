from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from compas.datastructures import Graph, Mesh
from compas.geometry import (
    oriented_bounding_box_numpy,
    Box,
    Translation,
    Vector,
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


def layout_meshes_in_grid(
    meshes: List[Mesh],
    columns: Optional[int] = None,
    padding: float = 1.0,
) -> List[Mesh]:
    """Translate a list of pre-processed meshes into an XY grid layout.

    Each mesh is placed at the centroid of a grid cell. Cell size is
    determined by the largest axis-aligned bounding box across all meshes,
    plus ``padding`` on each side.

    Parameters
    ----------
    meshes : list[:class:`compas.datastructures.Mesh`]
        Pre-processed meshes to lay out. Order is preserved left-to-right,
        top-to-bottom.
    columns : int, optional
        Number of columns in the grid. Defaults to ``ceil(sqrt(len(meshes)))``
        to produce a roughly square grid.
    padding : float, optional
        Extra space added around each mesh on every side. Default is 1.0.

    Returns
    -------
    list[:class:`compas.datastructures.Mesh`]
        New mesh objects translated to their grid positions. The originals
        are not modified.
    """
    if not meshes:
        return []

    # --- determine grid cell dimensions from the largest bounding box ---
    max_x = 0.0
    max_y = 0.0
    mesh_centers = []

    for mesh in meshes:
        pts = np.array([mesh.vertex_coordinates(v) for v in mesh.vertices()])
        lo = pts.min(axis=0)
        hi = pts.max(axis=0)
        max_x = max(max_x, float(hi[0] - lo[0]))
        max_y = max(max_y, float(hi[1] - lo[1]))
        mesh_centers.append((lo + hi) / 2.0)

    cell_w = max_x + 2.0 * padding
    cell_h = max_y + 2.0 * padding

    if columns is None:
        columns = math.ceil(math.sqrt(len(meshes)))
    columns = max(1, int(columns))

    # --- translate each mesh to its grid cell origin ---
    result: List[Mesh] = []
    for i, (mesh, center) in enumerate(zip(meshes, mesh_centers)):
        row = i // columns
        col = i % columns

        target_x = col * cell_w
        target_y = -row * cell_h   # rows grow in -Y so +Y stays up

        dx = target_x - center[0]
        dy = target_y - center[1]
        dz = -center[2]            # flatten to Z = 0

        T = Translation.from_vector(Vector(dx, dy, dz))
        result.append(mesh.transformed(T))

    return result

