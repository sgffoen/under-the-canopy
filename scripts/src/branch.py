from __future__ import annotations

from typing import Tuple

import numpy as np
import math

from compas.datastructures import Mesh
from mesh_utils import mesh_bounding_box, principal_axes, skeletonize_mesh, mesh_bbox_to_world_xyz_transform, flip_mesh_top_bottom, mesh_plane_contours
from graph_utils import (
get_bifurcating_axes,
get_bifurcation_node,
get_number_of_end_points_above_threshold, 
get_average_z_from_end_points,
clean_bifurcation_graph,
get_trunk_axis,
get_axis_path,
_sample_path_point_and_tangent,
get_bifurcation_angle,
paths_to_graph,
sort_graph_edges_by_z,
)
from growth_center import maximum_inscribed_circle
from compas.geometry import Line, Plane, Point, Polyline, distance_point_point, centroid_points, Polygon


class Branch:
    """A single branch mesh.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the branch.
    """

    def __init__(self, mesh: Mesh):
        self.mesh = mesh
        self._skeleton_graph = None  # cached on first call to skeleton()
        self._is_bifurcation = None  # cached on first call to is_bifurcation()
        self._centerline = None
        self._mesh_triangulated = None  # cached triangulated mesh data for use in multiple CGAL calls
        self._skeleton_bifurcation_graph = None  # cached cleaned skeleton graph for bifurcation branches
        self._true_bifurcation_graph = None  # cached graph rebuilt from computed bifurcation node
        self._tubular_skeleton_graph = None  # cached skeleton graph for tubular branches

    def bounding_box(self):
        """Compute the oriented bounding box of the branch.

        Returns
        -------
        :class:`compas.geometry.Box`
        """
        return mesh_bounding_box(self.mesh)
    
    def height(self):
        """Compute the height of the branch, defined as the Z dimension of the bounding box.

        Returns
        -------
        float
            The height of the branch in mm.
        """
        pts = self.bounding_box().points
        z_values = [pt.z for pt in pts]
        return max(z_values) - min(z_values)
    
    def triangulated_mesh(self):
        """Get the triangulated mesh data as vertices and faces.

        Returns
        -------
        (vertices, faces)
            *vertices* : list of :class:`compas.geometry.Point`
            *faces* : list of lists of int (vertex indices)
        """
        if self._mesh_triangulated is None:
            self._mesh_triangulated = self.mesh.to_vertices_and_faces(triangulated=True)
        return self._mesh_triangulated

    def pca(self) -> Tuple[np.ndarray, np.ndarray]:
        """Compute the principal axes of the branch via PCA.

        Returns
        -------
        (axes, eigenvalues)
            *axes* : (3, 3) array – each row is a unit axis sorted by
            descending variance (row 0 is the longest direction).
            *eigenvalues* : (3,) array
        """
        return principal_axes(self.mesh)

    def skeleton_graph(self):
        """Compute and cache the skeleton of the branch.

        The result is computed once and stored on ``self._skeleton``.
        Subsequent calls return the cached result immediately.

        Parameters
        ----------

        Returns
        -------
        list of :class:`compas.geometry.Polyline` or graph
        """
        if self._skeleton_graph is None:
            self._skeleton_graph = skeletonize_mesh(self.mesh, graph=True)
        return self._skeleton_graph
    
    def number_of_end_points(self):
        """Count the number of end points (degree 1 nodes) in the skeleton graph.

        Returns
        -------
        int
            The number of end points in the skeleton graph.
        """
        graph = self.skeleton_graph()
        return len(list(graph.nodes_where({"degree": 1})))
    
    def skeleton_bifurcation_graph(self):
        """Get the graph of a bifurcation branch.

        Returns
        -------
        Graph
            The cleaned skeleton graph of the bifurcation branch.
        """
        if self._skeleton_bifurcation_graph is None:
            self._skeleton_bifurcation_graph = clean_bifurcation_graph(self.skeleton_graph())
        return self._skeleton_bifurcation_graph

    def skeleton_bifurcation_node(self):
        """Get the bifurcation node of a bifurcation branch.

        Returns
        -------
        Node
            The node in the bifurcation graph where the bifurcation occurs.
        """
        return get_bifurcation_node(self.skeleton_bifurcation_graph())
    
    def tubular_skeleton_graph(self):
        """Get the skeleton graph of a tubular branch.

        Returns
        -------
        Graph
            The skeleton graph of a tubular branch.
        """
        if self._tubular_skeleton_graph is None:
            graph = self.skeleton_graph()
            self._tubular_skeleton_graph = sort_graph_edges_by_z(graph)
        return self._tubular_skeleton_graph

    def true_bifurcation_graph(self):
        """Get the graph rebuilt around the computed bifurcation node.

        The graph is constructed by trimming the three axis paths from the
        skeleton bifurcation graph at the step where the lockstep branch angle
        best matches the original bifurcation angle. The skipped nodes above
        the new bifurcation are removed, and ``paths_to_graph`` restores the
        same ``axis`` attributes on nodes and edges.

        Returns
        -------
        Graph
            The trimmed bifurcation graph.
        """
        if self._true_bifurcation_graph is None:
            graph = self.skeleton_bifurcation_graph()
            step = self._compute_bifurcation_step(tolerance=5.0)

            trunk_path = get_axis_path(graph, 0)
            axis_1_path = get_axis_path(graph, 1)
            axis_2_path = get_axis_path(graph, 2)

            if step <= 0:
                self._true_bifurcation_graph = graph
            else:
                new_bif_node = trunk_path[step]
                trimmed_paths = [
                    trunk_path[step:],
                    [new_bif_node] + axis_1_path[step:],
                    [new_bif_node] + axis_2_path[step:],
                ]
                self._true_bifurcation_graph = paths_to_graph(trimmed_paths)

        return self._true_bifurcation_graph

    def true_bifurcation_graph_lines(self):
        """Get the lines representing the edges of the true bifurcation graph.

        Returns
        -------
        list of :class:`compas.geometry.Line`
            The lines representing the edges of the true bifurcation graph.
        """
        graph = self.true_bifurcation_graph()
        lines = []
        for u, v in graph.edges():
            lines.append(Line(Point(*u), Point(*v)))
        return lines

    def bifurcation_point(self):
        """Get the point at the bifurcation node.

        Returns
        -------
        :class:`compas.geometry.Point`
            The point at the bifurcation node.
        """
        graph = self.skeleton_bifurcation_graph()
        node = get_bifurcation_node(graph)
        return Point(*node)
    
    def skeleton_trunk_axis(self):
        graph = self.skeleton_bifurcation_graph()
        return get_trunk_axis(graph, geometry=False)

    def skeleton_trunk_lines(self):
        graph = self.skeleton_bifurcation_graph()
        return get_trunk_axis(graph, geometry=True)
    
    def skeleton_branching_axes(self):
        graph = self.skeleton_bifurcation_graph()
        return get_bifurcating_axes(graph, geometry=False)

    def skeleton_branching_lines(self):
        """Get the lines representing the branching axes in a bifurcation. Returns a list with first item corresponding to the first branch and second item corresponding to the second branch.

        Returns
        -------
        tuple of lists of :class:`compas.geometry.Line`
            The lines representing the branching axes.
        """
        graph = self.skeleton_bifurcation_graph()
        return get_bifurcating_axes(graph, geometry=True)

    @property
    def is_bifurcation(self):
        if self._is_bifurcation is None:
            end_points = list(self.skeleton_graph().nodes_where({"degree": 1}))
            self._is_bifurcation = len(end_points) > 2
        return self._is_bifurcation
    
    def update_skeleton_graph(self):
        """Clear the cached skeleton graph so it will be recomputed on next call to skeleton_graph()
        """
        self._skeleton_graph = None
        self._skeleton_bifurcation_graph = None
        self._true_bifurcation_graph = None
        self._is_bifurcation = None
        self._centerline = None

    def preprocess(self):
        """Align the branch to world XYZ and flip it if bifurcations point down.

        The mesh is first transformed so its bounding-box principal directions
        align with world axes. The transformed skeleton graph is then inspected:
        if at most one end point lies above ``threshold`` in Z, the branch is
        flipped top-to-bottom.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The preprocessed mesh.
        """
        transform = mesh_bbox_to_world_xyz_transform(self.mesh)
        self.mesh = self.mesh.transformed(transform)

        graph = self.skeleton_graph()
        end_points_above_threshold = get_number_of_end_points_above_threshold(
            graph,
            get_average_z_from_end_points(graph)
        )

        if self.is_bifurcation:
            # only bifurcations have a top and bottom, regular branch has no top or bottom
            if end_points_above_threshold <= 1:
                # fork is upside down, flip it
                self.mesh = flip_mesh_top_bottom(self.mesh)
                self.update_skeleton_graph()

    def geometric_centerline(self, resolution=30.0):
        """Compute the centerline of the branch.

        Parameters
        ----------
        resolution : float
             Desired distance in mm between points on the centerline.

        Returns
        -------
        list of :class:`compas.geometry.Polyline`
            The centerline polylines of the branch.
        """
        if self.is_bifurcation:
            centerline, sections = self._bifurcation_geometric_centerline(resolution=resolution)
            return centerline, sections
        else:
            centerline, sections = self._tubular_geometric_centerline(resolution=resolution)
            return centerline, sections

    def growth_centerline(self, resolution=30.0):
        """Compute the centerline of the branch.

        Parameters
        ----------
        resolution : float
             Desired distance in mm between points on the centerline.

        Returns
        -------
        list of :class:`compas.geometry.Polyline`
            The centerline polylines of the branch.
        """
        if self.is_bifurcation:
            centerline, circles = self._bifurcation_growth_centerline(resolution=resolution)
            return centerline, circles
        else:
            centerline, circles = self._tubular_growth_centerline(resolution=resolution)
            return centerline, circles

    def bifurcation_centerline_stubs(self, resolution=30.0, method="growth"):
        """Return only the bifurcation stubs of a bifurcation centerline.

        A stub is the segment from the computed bifurcation point to the first
        sampled contour center on each axis.

        Parameters
        ----------
        resolution : float
            Desired distance in mm between slicing planes used for centerline
            extraction.
        method : str
            Centerline method to use: ``"growth"`` or ``"geometric"``.

        Returns
        -------
        list[:class:`compas.geometry.Polyline`]
            One 2-point polyline per available axis stub.
        """
        if not self.is_bifurcation:
            return []

        if method == "growth":
            centerlines, _ = self._bifurcation_growth_centerline(resolution=resolution)
        elif method == "geometric":
            centerlines, _ = self._bifurcation_geometric_centerline(resolution=resolution)
        else:
            raise ValueError("method must be 'growth' or 'geometric'")

        stubs = []
        for polyline in centerlines:
            points = list(polyline.points)
            if len(points) >= 2:
                stubs.append(Polyline([points[0], points[1]]))

        return stubs

    def _bifurcation_geometric_centerline(self, resolution):
        """Compute the centerline of a bifurcation branch.

        Returns
        -------
        list of :class:`compas.geometry.Polyline`
            The centerline polylines of the branch.
        """
        contours = self._contours(self.true_bifurcation_graph(), resolution=resolution)

        bif_pt = self.compute_bifurcation_point()
        centerlines = []
        sections = []

        for axis_idx in range(3):
            axis_points = [bif_pt]
            axis_sections = []
            for contour in contours.get(axis_idx, []):
                try:
                    polygon = Polygon(contour.points)
                    cnt_pt = polygon.centroid
                    axis_sections.append(contour)
                except Exception:
                    continue
                axis_points.append(cnt_pt)

            if len(axis_points) >= 2:
                centerline = Polyline(axis_points)
                centerlines.append(centerline)

            sections.append(axis_sections)

        return centerlines, sections
        
    def _bifurcation_growth_centerline(self, resolution):
        """Compute the centerline of a bifurcation branch.

        Returns
        -------
        list of :class:`compas.geometry.Polyline`
            The centerline polylines of the branch.
        """
        contours = self._contours(self.true_bifurcation_graph(), resolution=resolution)

        bif_pt = self.compute_bifurcation_point()
        centerlines = []
        circular_sections = []

        for axis_idx in range(3):
            axis_points = [bif_pt]
            circles = []
            for contour in contours.get(axis_idx, []):
                try:
                    circle = maximum_inscribed_circle(contour)
                    circles.append(circle)
                except Exception:
                    continue
                axis_points.append(circle.center)

            if len(axis_points) >= 2:
                centerline = Polyline(axis_points)
                centerlines.append(centerline)
            circular_sections.append(circles)

        return centerlines, circular_sections
       
    def _tubular_geometric_centerline(self, resolution=30.0):
        """Compute the centerline of a tubular branch by slicing it with planes perpendicular to the longest axis and connecting the centroids of the resulting contours.
        """
        contours = self._contours_tubular(self.tubular_skeleton_graph(), resolution=resolution)
        centerline_points = []
        for contour in contours:
            try:
                polygon = Polygon(contour.points)
                cnt_pt = polygon.centroid
                centerline_points.append(cnt_pt)
            except Exception:
                continue
        
        return Polyline(centerline_points), contours
    
    def _tubular_growth_centerline(self, resolution=30.0):
        """Compute the centerline of a tubular branch by slicing it with planes perpendicular to the axis and connecting the centers of the maximum inscribed circles of the resulting contours.
        """
        contours = self._contours_tubular(self.tubular_skeleton_graph(), resolution=resolution)
        centerline_points = []
        circular_sections = []
        for contour in contours:
            try:
                circle = maximum_inscribed_circle(contour)
                centerline_points.append(circle.center)
                circular_sections.append(circle)
            except Exception:
                continue
        
        return Polyline(centerline_points), circular_sections


    def _compare_contour_centroid_to_axis(self, contour, plane_point, max_distance=20.0):
        """Check if a contour centroid is close to the current slicing point.

        Parameters
        ----------
        contour : :class:`compas.geometry.Polyline`
            Candidate contour for a single slice.
        plane_point : sequence[float] or :class:`compas.geometry.Point`
            Origin point of the slicing plane (located on the target axis).
        max_distance : float
            Maximum allowed centroid-to-plane-point distance in mm.

        Returns
        -------
        bool
            ``True`` if the contour is close enough, else ``False``.
        """
        if contour is None:
            return False

        c = centroid_points(contour)
        centroid = c if isinstance(c, Point) else Point(*c)
        origin = plane_point if isinstance(plane_point, Point) else Point(*plane_point)
        dist = distance_point_point(centroid, origin)
        return dist <= float(max_distance)
    
    def _contours_tubular(self, graph, resolution=30.0):
        """compute the contours for a graph with one axis (tubular branch)
        the contours are perpendicular to the input graph path
        
        Parameters        
        ----------
        graph : Graph
        resolution : float
            Target spacing in mm between consecutive slicing planes.
        Returns
        -------
        list[:class:`compas.geometry.Polyline`]
            Section contours produced by compas_cgal slicer for the given planes.
        """
        mesh_data = self.triangulated_mesh()

        path = list(graph.nodes())
        path_length = sum(
            distance_point_point(Point(*path[i]), Point(*path[i + 1]))
            for i in range(len(path) - 1)
        )
        num_planes = max(1, int(path_length // resolution))
        distances = np.linspace(0.0, path_length, num_planes + 2)

        contours = []
        for dist in distances:
            pt, tangent = _sample_path_point_and_tangent(path, dist)
            plane = Plane(pt, tangent)
            slice_contours = mesh_plane_contours(mesh_data, [plane])

            if not slice_contours:
                continue

            contours.append(slice_contours[0])

        return contours
        

    def _contours(self, graph, resolution=30.0):
        """Compute cross-section contours perpendicular to each axis of the bifurcation.

        Slicing planes are distributed along each axis path (stem, left fork,
        right fork) at the requested spacing.  Because a plane cutting through
        one fork may also intersect the other fork, every slice is run
        independently and — when more than one contour is returned — only the
        contour whose centroid is closest to the plane origin (which lies on
        the target axis) is kept.

        Parameters
        ----------
        graph : Graph
            The graph to slice along.
        resolution : float
            Target spacing in mm between consecutive slicing planes.

        Returns
        -------
        dict[int, list[:class:`compas.geometry.Polyline`]]
            ``{0: [stem contours], 1: [left contours], 2: [right contours]}``
        """
        mesh_data = self.triangulated_mesh()

        result = {}

        for axis_idx in range(3):
            path = get_axis_path(graph, axis_idx)

            if len(path) < 2:
                result[axis_idx] = []
                continue

            path_length = sum(
                distance_point_point(Point(*path[i]), Point(*path[i + 1]))
                for i in range(len(path) - 1)
            )

            if path_length <= 1e-12:
                result[axis_idx] = []
                continue

            num_planes = max(1, int(path_length // resolution))
            # Exclude the very start (bifurcation node) and end (leaf) to
            # avoid degenerate contours at the tips.
            distances = np.linspace(0.0, path_length, num_planes + 2)[1:]

            axis_contours = []
            max_centroid_distance = max(10.0, 0.5 * float(resolution))
            for dist in distances:
                pt, tangent = _sample_path_point_and_tangent(path, dist)
                plane = Plane(pt, tangent)
                candidates = mesh_plane_contours(mesh_data, [plane])

                if not candidates:
                    continue

                if len(candidates) == 1:
                    selected = candidates[0]
                else:
                    # Multiple contours: keep the one whose centroid is
                    # closest to the plane origin (on the target axis).
                    origin = Point(*pt)
                    selected = min(
                        candidates,
                        key=lambda c: distance_point_point(origin, centroid_points(c)),
                    )

                if self._compare_contour_centroid_to_axis(
                    selected,
                    pt,
                    max_distance=max_centroid_distance,
                ):
                    axis_contours.append(selected)

            result[axis_idx] = axis_contours

        return result

    def skeleton_polylines(self):
        """Get the skeleton as a list of polylines.

        Returns
        -------
        list of :class:`compas.geometry.Polyline`
            The skeleton polylines of the branch.
        """
        graph = skeletonize_mesh(self.mesh, graph=True)
        polylines = []
        for e in graph.edges():
             polylines.append(Line(*e))

        return polylines

    def skeleton_bifurcation_angle(self):
        """Compute the bifurcation angle between two end points and the bifurcation node.

        Returns
        -------
        float
            The bifurcation angle in degrees.
        """
        graph = self.skeleton_bifurcation_graph()
        return get_bifurcation_angle(graph)

    def compute_bifurcation_point(self, tolerance=5.0):
        """Compute the bifurcation point by walking from the bifurcation node toward the end nodes node by node of each axis simultaneously and calculate the angle until it matches with the bifurcation angle.
        
        Returns
        -------
        :class:`compas.geometry.Point`
            The computed bifurcation point.
        
        
        """
        graph = self.skeleton_bifurcation_graph()
        trunk_path = get_axis_path(graph, 0)
        step = self._compute_bifurcation_step(tolerance=tolerance)
        return Point(*trunk_path[step])

    def _compute_bifurcation_step(self, tolerance):
        """Return the trunk-path index of the computed bifurcation node."""
        graph = self.skeleton_bifurcation_graph()
        trunk_path = get_axis_path(graph, 0)
        axis_1_path = get_axis_path(graph, 1)
        axis_2_path = get_axis_path(graph, 2)
        bifurcation_angle = get_bifurcation_angle(graph)

        max_step = min(len(trunk_path), len(axis_1_path), len(axis_2_path)) - 1
        if max_step < 1:
            return 0

        best_step = 0
        best_delta = float("inf")

        for step in range(1, max_step + 1):
            trunk_pt = Point(*trunk_path[step])
            axis_1_pt = Point(*axis_1_path[step])
            axis_2_pt = Point(*axis_2_path[step])

            v1 = axis_1_pt - trunk_pt
            v2 = axis_2_pt - trunk_pt

            angle = math.degrees(v1.angle(v2))
            delta = abs(angle - bifurcation_angle)

            if delta < best_delta:
                best_delta = delta
                best_step = step

            if delta <= tolerance:
                return step

        return best_step





