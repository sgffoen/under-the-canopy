from compas.geometry import Polyline, pca_numpy
from compas.datastructures import Mesh
import math
import numpy as np

from mesh_utils import principal_axes
from compas_cgal.polylines import simplify_polyline


def branch_direction(mesh):
    """Computes the principal direction of a branch mesh.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        Input mesh representing a single branch (tubular or irregular).

    Returns
    -------
    Vector
        The principal direction vector of the branch.
    """
    axes, _ = principal_axes(mesh)
    main_axis = axes[0]  # longest variance direction
    return main_axis


def simplify_centerline(centerline, threshold=1.0):
    """Simplify a centerline polyline using the Ramer-Douglas-Peucker algorithm.

    Parameters
    ----------
    centerline : Polyline
        The input centerline as a polyline.
    threshold : float, optional
        The distance threshold for simplification (default is 1.0).

    Returns
    -------
    Polyline
        The simplified centerline.
    """
    simplified_points = simplify_polyline(centerline.points, threshold)
    return Polyline(simplified_points)