"""
mesh_utils.py
=============
Mesh loading, validation, and slicing helpers built on COMPAS.

All public functions accept / return ``compas.datastructures.Mesh`` objects
unless stated otherwise.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np

from compas.datastructures import Mesh
from compas_cgal.skeletonization import mesh_skeleton
from compas_cgal.slicer import slice_mesh_planes
from compas.geometry import (
    Frame,
    Plane,
    Point,
    Polyline,
    Vector,
    bounding_box,
    centroid_points,
    oriented_bounding_box_numpy,
    Box,
    Transformation,
    Translation,
    Rotation,
)



# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def mesh_bounding_box(mesh):
    """Compute the axis-aligned bounding box of a mesh.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The input mesh.

    Returns
    -------
    list of Point
        The 8 corner points of the bounding box.
    """
    v, f = mesh.to_vertices_and_faces(triangulated=True)
    bbox = oriented_bounding_box_numpy(v)
    bbox = Box.from_bounding_box(bbox)
    return bbox


def principal_axes(mesh: Mesh) -> Tuple[np.ndarray, np.ndarray]:
    """Compute the three principal axes of a mesh via PCA.

    Returns
    -------
    (axes, eigenvalues)
        *axes*  : (3, 3) array – each **row** is a unit axis (sorted by
                  descending variance, so row 0 is the longest axis).
        *eigenvalues* : (3,) array
    """
    pts = np.array([mesh.vertex_coordinates(v) for v in mesh.vertices()])
    centroid = pts.mean(axis=0)
    centered = pts - centroid
    cov = np.cov(centered.T)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # sort descending
    idx = np.argsort(eigenvalues)[::-1]
    return eigenvectors.T[idx], eigenvalues[idx]


def mesh_bbox_to_world_xyz_transform(mesh: Mesh) -> Transformation:
    """Get a transform that aligns mesh principal bbox directions to world XYZ.

    The longest principal direction is forced to align with ``+Z``. The other
    two (shorter) directions are aligned with the world ``XY`` plane.

    Notes
    -----
    For highly symmetric meshes (for example cubes), principal directions can
    be non-unique, so equivalent valid alignments may exist.
    """
    axes, _ = principal_axes(mesh)

    # Principal axes are sorted by descending variance: 0=longest.
    z_axis = np.array(axes[0], dtype=float)
    x_axis = np.array(axes[1], dtype=float)
    ref_short = np.array(axes[2], dtype=float)

    z_axis /= np.linalg.norm(z_axis)
    if z_axis[2] < 0.0:
        z_axis *= -1.0

    # Re-orthogonalize x against z for numerical stability.
    x_axis = x_axis - np.dot(x_axis, z_axis) * z_axis
    x_norm = np.linalg.norm(x_axis)
    if x_norm < 1e-12:
        fallback = np.array([1.0, 0.0, 0.0])
        if abs(np.dot(fallback, z_axis)) > 0.9:
            fallback = np.array([0.0, 1.0, 0.0])
        x_axis = fallback - np.dot(fallback, z_axis) * z_axis
        x_norm = np.linalg.norm(x_axis)
    x_axis /= x_norm

    y_axis = np.cross(z_axis, x_axis)
    y_axis /= np.linalg.norm(y_axis)

    # Keep a deterministic orientation for the two short axes.
    if np.dot(y_axis, ref_short) < 0.0:
        x_axis *= -1.0
        y_axis *= -1.0

    centroid = centroid_points([mesh.vertex_coordinates(v) for v in mesh.vertices()])
    source = Frame(Point(*centroid), Vector(*x_axis), Vector(*y_axis))
    target = Frame.worldXY()
    return Transformation.from_frame_to_frame(source, target)


def skeletonize_mesh(mesh, graph=False):
    """Skeletonizes a mesh and returns a list of polylines representing the skeleton.

    Parameters
    ----------
    mesh : compas.datastructures.Mesh
        The input mesh to be skeletonized.

    Returns
    -------
    list of compas.geometry.Polyline
        A list of polylines representing the skeleton of the mesh.
    """
    v, f = mesh.to_vertices_and_faces(triangulated=True)

    # =============================================================================
    # Skeleton
    # =============================================================================

    skeleton_edges = mesh_skeleton((v, f))

    polylines = []
    for start_point, end_point in skeleton_edges:
        polyline = Polyline([start_point, end_point])
        polylines.append(polyline)

    if graph:
        from graph_utils import graph_from_polylines
        return graph_from_polylines(polylines)
    
    return polylines


def mesh_plane_contours(mesh: Mesh, planes: List[Plane]) -> List[Polyline]:
    """Intersect a mesh with multiple planes and stitch the results into contours.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        Input mesh to slice.
    planes : list of :class:`compas.geometry.Plane`
        Section planes.

    Returns
    -------
    list[:class:`compas.geometry.Polyline`]
        Section contours produced by compas_cgal slicer for the given planes.
    """
    result = slice_mesh_planes(mesh, planes)
    return [Polyline(points) for points in result if len(points) >= 2]


def flip_mesh_top_bottom(mesh):
    center = mesh.centroid()

    # translation to origin
    T1 = Translation.from_vector(Vector(*(-c for c in center)))

    # 3. rotation: 180 degrees around Y axis
    R = Rotation.from_axis_and_angle([0, 1, 0], 3.141592653589793, point=Point(0, 0, 0))

    # 4. translate back
    T2 = Translation.from_vector(Vector(*center))

    # 5. combined transform
    transform = T2 * R * T1

    # apply to mesh
    flipped_mesh = mesh.transformed(transform)

    return flipped_mesh 