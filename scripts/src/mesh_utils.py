"""
mesh_utils.py
=============
Mesh loading, validation, and slicing helpers built on COMPAS.

All public functions accept / return ``compas.datastructures.Mesh`` objects
unless stated otherwise.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
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


def load_branch_meshes(
    index: Optional[int] = None,
    precision=None,
    load_bf: bool = True,
    load_gb: bool = True,
) -> Tuple[List[Mesh], List[str]]:
    """Load branch meshes from data/branches as COMPAS meshes.

    Parameters
    ----------
    index : int, optional
        Optional branch index. If provided, only one mesh is loaded.
        The function first tries to match branch naming by id (for example
        ``index=3`` -> ``b-003`` or ``t-003`` from the filename). If that does
        not exist, it falls back to 1-based positional selection in the sorted
        file list.
    precision : str, optional
        Optional precision passed to :meth:`compas.datastructures.Mesh.from_obj`.
    load_bf : bool, optional
        If ``True``, include files prefixed with ``bf-``. Default is ``True``.
    load_gb : bool, optional
        If ``True``, include files prefixed with ``gb-``. Default is ``True``.

    Returns
    -------
    tuple[list[:class:`compas.datastructures.Mesh`], list[str]]
        Loaded meshes and their branch ids. If ``index`` is provided, both
        lists contain one item.
    """
    root = Path(__file__).resolve().parents[2]
    branches_dir = root / "data" / "branches"

    if not branches_dir.exists():
        raise FileNotFoundError("Branches folder not found: {}".format(branches_dir))

    mesh_files = sorted(
        [
            path
            for path in branches_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".obj", ".stl"}
        ],
        key=lambda p: _mesh_file_sort_key(p.name),
    )

    if not load_bf:
        mesh_files = [path for path in mesh_files if not path.stem.lower().startswith("bf-")]
    if not load_gb:
        mesh_files = [path for path in mesh_files if not path.stem.lower().startswith("gb-")]

    if not mesh_files:
        return [], []

    selected: List[Path]
    if index is None:
        selected = mesh_files
    else:
        try:
            idx = int(index)
        except (TypeError, ValueError):
            raise ValueError("index must be an integer.")

        if idx < 1:
            raise ValueError("index must be >= 1.")

        b_name = f"b-{idx:03d}"
        t_name = f"t-{idx:03d}"
        name_match = next(
            (
                p
                for p in mesh_files
                if _extract_branch_id_from_filename(p.name).lower() in {b_name, t_name}
            ),
            None,
        )

        if name_match is not None:
            selected = [name_match]
        else:
            position = idx - 1
            if position >= len(mesh_files):
                raise IndexError(
                    "index {} out of range for {} mesh files in {}".format(
                        idx,
                        len(mesh_files),
                        branches_dir,
                    )
                )
            selected = [mesh_files[position]]

    meshes: List[Mesh] = []
    branch_ids: List[str] = []
    for path in selected:
        suffix = path.suffix.lower()
        if suffix == ".stl":
            try:
                mesh = Mesh.from_stl(str(path), precision=precision)
            except TypeError:
                mesh = Mesh.from_stl(str(path))
        else:
            mesh = Mesh.from_obj(str(path), precision=precision)
        meshes.append(mesh)
        branch_ids.append(_extract_branch_id_from_filename(path.name))

    return meshes, branch_ids


def load_scan_mesh(
    precision=None,
) -> Tuple[Mesh, str]:
    """Load the most recent 3D scan mesh from data/3d_scan as a COMPAS mesh.

    Parameters
    ----------
    precision : str, optional
        Optional precision passed to :meth:`compas.datastructures.Mesh.from_obj`.

    Returns
    -------
    tuple[:class:`compas.datastructures.Mesh`, str]
        Loaded mesh and its filename stem.

    Raises
    ------
    FileNotFoundError
        If the 3d_scan folder does not exist or contains no .obj files.
    """
    root = Path(__file__).resolve().parents[2]
    scan_dir = root / "data" / "3d_scan"

    if not scan_dir.exists():
        raise FileNotFoundError("3D scan folder not found: {}".format(scan_dir))

    mesh_files = sorted(
        [
            path
            for path in scan_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".obj"
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not mesh_files:
        raise FileNotFoundError("No .obj files found in {}".format(scan_dir))

    path = mesh_files[0]
    mesh = Mesh.from_obj(str(path), precision=precision)

    return mesh, path.stem


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


def _mesh_file_sort_key(filename: str):
    branch_id = _extract_branch_id_from_filename(filename).lower()
    id_match = re.match(r"^(b|t)-(\d+)$", branch_id)
    if id_match:
        prefix, number = id_match.groups()
        prefix_rank = 0 if prefix == "b" else 1
        return (0, prefix_rank, int(number), branch_id)

    stem = Path(filename).stem
    match = re.search(r"(\d+)$", stem)
    if match:
        return (0, int(match.group(1)), stem.lower())
    return (1, stem.lower())


def _extract_branch_id_from_filename(filename: str) -> str:
    """Extract normalized branch id from a mesh filename.

    Examples
    --------
    - ``b-001.obj`` -> ``b-001``
    - ``gb-t-001.obj`` -> ``t-001``
    - ``bf-t-102.stl`` -> ``t-102``
    """
    stem = Path(filename).stem
    match = re.search(r"(?:^|[-_])([bt]-\d+)$", stem, flags=re.IGNORECASE)
    if match:
        return match.group(1).lower()
    return stem.lower()