"""
growth_center.py
================
Compute the growth center of a polygon, defined as the center of the maximum inscribed circle.

Algorithm overview
------------------
1. Compute the straight skeleton of the polygon to get candidate interior points.
2. For each skeleton point, compute the minimum distance to the polygon boundary.
3. The skeleton point with the maximum minimum distance is the center of the maximum inscribed circle.
4. The radius of the maximum inscribed circle is that maximum minimum distance.
5. The growth center is the center of the maximum inscribed circle.
"""

from typing import List, Tuple
import numpy as np
import math
from compas.geometry import (
    Circle,
    Frame,
    Vector,
    distance_point_point_xy,
    Rotation,
    Point,
    Translation,
    normal_polygon,
    Polygon,
    
)
from compas_cgal.straight_skeleton_2 import interior_straight_skeleton


def min_distance_points_to_poly(points, polygon):
    """Compute the minimum distance between point and polygon boundary from a set of points.

    Parameters
    ----------
    points : list of Point
        The input points.
    polygon : list of Point
        The input polygon vertices (in order).

    Returns
    -------
    list of float
        The minimum distances from the points to the polygon.
    """
    min_distances = []
    for pt in points:
        min_dist = float("inf")
        for j in polygon.points:
            dist = distance_point_point_xy(pt, j)
            if dist < min_dist:
                min_dist = dist
        min_distances.append(min_dist)
    return min_distances


def get_transform_polygon_to_origin(polygon):
    """Get a transform that moves the polygon centroid to the world origin
    """
    centroid = polygon.centroid
    translation = Vector.from_start_end(centroid, Point(0, 0, 0))
    return Translation.from_vector(translation)


def get_transform_polygon_to_xy_plane(polygon):
    normal = Vector(*normal_polygon(polygon.points, True))
    if normal.z == -1.0:
        # rotate 180 degrees around X axis
        return Rotation.from_axis_and_angle(Vector(1, 0, 0), math.pi, polygon.centroid)
    target = Vector(0, 0, 1)
    axis = normal.cross(target)
    angle = normal.angle(target)
    R = Rotation.from_axis_and_angle(axis, angle, polygon.centroid)
    return R


def maximum_inscribed_circle(polyline):
    """Compute the maximum inscribed circle of a polygon.

    Parameters
    ----------
    polyline : compas.geometry.Polyline
        The input polyline.

    Returns
    -------
    Circle
        The maximum inscribed circle.
    """
    polygon = Polygon(polyline.points)
    T = get_transform_polygon_to_origin(polygon)
    R = get_transform_polygon_to_xy_plane(polygon)
    # T * R: rotate around centroid first, then translate centroid to origin.
    # R * T would apply T first (centroid already at origin) then rotate around
    # the original centroid position, which is now the wrong pivot.
    combined = T * R
    polygon_transformed = polygon.transformed(combined)
    sk_points, indices, edges, edge_types = interior_straight_skeleton(polygon_transformed, as_graph=False)
    # sk_points are in transformed space, so measure against the transformed polygon
    min_distances = min_distance_points_to_poly(sk_points, polygon_transformed)
    max_index = np.argmax(min_distances)
    center = sk_points[max_index]
    radius = min_distances[max_index]
    circle = Circle(radius, Frame(center, Vector(1, 0, 0), Vector(0, 1, 0)))
    inverse = combined.inverse()
    circle.transform(inverse)
    return circle
