from __future__ import annotations

from collections import deque
import math
from platform import node
from typing import List, Optional, Tuple

from networkx import nodes
import numpy as np
import statistics

from compas.datastructures import Graph
from compas.geometry import Line, Plane, distance_point_point, Point, Polyline


# ============================================================
# GRAPH CONSTRUCTION
# ============================================================

def graph_from_polylines(polylines):
    """
    Construct a graph from a list of polylines and repair connectivity.

    Parameters
    ----------
    polylines : list
        List of COMPAS polylines.

    Returns
    -------
    Graph
        Repaired COMPAS graph.
    """
    edges = [(tuple(line.start), tuple(line.end)) for line in polylines]
    graph = Graph.from_edges(edges)
    graph = repair_graph_by_tolerance(graph)
    return graph


# ============================================================
# GRAPH REPAIR
# ============================================================

def repair_graph_by_tolerance(graph, tol=1.0):
    """
    Connect nodes that are within a given Euclidean tolerance.
    """

    repaired = Graph()

    # copy nodes
    for node in graph.nodes():
        repaired.add_node(node)

    # copy edges
    for u, v in graph.edges():
        repaired.add_edge(u, v)

    nodes = list(graph.nodes())

    # spatial stitching
    for i, u in enumerate(nodes):
        pu = Point(*u)

        for j in range(i + 1, len(nodes)):
            v = nodes[j]

            if graph.has_edge((u, v)) or graph.has_edge((v, u)):
                continue

            pv = Point(*v)

            if distance_point_point(pu, pv) <= tol:
                repaired.add_edge(u, v)

    return repaired


def sort_graph_edges_by_z(graph):
    """
    Sort graph edges by their Z value in ascending order.

    Parameters
    ----------
    graph : Graph
        The input graph to sort.

    Returns
    -------
    graph : Graph
        A new graph with edges sorted by Z value.
    """
    edges = sorted(graph.edges(), key=lambda e: (e[0][2] + e[1][2]) / 2)    
    sorted_graph = Graph.from_edges(edges)
    return sorted_graph

# ============================================================
# BIFURCATION DETECTION
# ============================================================

def find_bifurcation_candidates(graph):
    return [node for node in graph.nodes() if graph.degree(node) == 3]


def get_next_edges(graph, current, prev):
    edges = graph.node_edges(current)
    result = []

    for edge in edges:
        u, v = edge
        nxt = v if u == current else u

        if nxt != prev:
            result.append((edge, nxt))

    return result


# ============================================================
# GEOMETRIC UTILITIES
# ============================================================

def edge_length(graph, u, v):
    return distance_point_point(Point(*u), Point(*v))


def edge_length_from_edge(graph, edge):
    u, v = edge
    return edge_length(graph, u, v)


def get_bifurcation_angle(graph):
    bif_node = get_bifurcation_node(graph)
    # get end points of axis 1 and axis 2
    nodes = graph.nodes_where({"axis":{1}})
    axis_1_end = [n for n in graph.nodes_where({"axis":{1}}) if graph.degree(n) == 1 and n != bif_node]
    axis_2_end = [n for n in graph.nodes_where({"axis":{2}}) if graph.degree(n) == 1 and n != bif_node]
    axis_1_endpt = Point(*axis_1_end[0])
    axis_2_endpt = Point(*axis_2_end[0])
    bif_pt = Point(*bif_node)
    v1 = axis_1_endpt - bif_pt
    v2 = axis_2_endpt - bif_pt
    angle = v1.angle(v2)
    return math.degrees(angle)


# ============================================================
# BRANCH WALKING
# ============================================================

def walk_branch(graph, start, first_edge):
    """
    Walk a branch and return longest valid path + length.
    """

    u, v = first_edge
    neighbor = v if u == start else u

    best_path = []
    best_length = 0.0

    stack = [
        (
            neighbor,
            start,
            [start, neighbor],
            edge_length_from_edge(graph, first_edge),
        )
    ]

    while stack:
        current, prev, path, length = stack.pop()
        degree = graph.degree(current)

        # leaf node
        if degree == 1:
            if length > best_length:
                best_path = path
                best_length = length
            continue

        next_edges = get_next_edges(graph, current, prev)

        # straight continuation
        if degree == 2 and len(next_edges) == 1:
            edge, nxt = next_edges[0]

            stack.append(
                (
                    nxt,
                    current,
                    path + [nxt],
                    length + edge_length_from_edge(graph, edge),
                )
            )

        # noisy branching
        else:
            for edge, nxt in next_edges:
                if nxt in path:
                    continue

                stack.append(
                    (
                        nxt,
                        current,
                        path + [nxt],
                        length + edge_length_from_edge(graph, edge),
                    )
                )

    return best_path, best_length


# ============================================================
# CANDIDATE EVALUATION
# ============================================================

def evaluate_candidate(graph, node):
    edges = graph.node_edges(node)

    paths = []
    total_length = 0.0

    for edge in edges:
        path, length = walk_branch(graph, node, edge)
        paths.append(path)
        total_length += length

    return paths, total_length


def find_best_bifurcation(graph):
    candidates = find_bifurcation_candidates(graph)

    best_node = None
    best_paths = None
    best_length = -1

    for node in candidates:
        paths, total_length = evaluate_candidate(graph, node)

        if total_length > best_length:
            best_node = node
            best_paths = paths
            best_length = total_length

    return best_node, best_paths, best_length


# ============================================================
# OUTPUT UTILITIES
# ============================================================

def _sort_paths_by_axis(paths):
    """Sort three paths so that axis indices are semantically consistent.

    Axis 0 — stem: path whose nodes have the lowest mean Z value.
    Axis 1 — left fork: of the two remaining paths, the one with the lower
              mean X value.
    Axis 2 — right fork: the remaining path with the higher mean X value.

    Parameters
    ----------
    paths : list[list[tuple]]
        Three paths as returned by ``find_best_bifurcation``.

    Returns
    -------
    list[list[tuple]]
        The same paths reordered as ``[stem, left, right]``.
    """
    if len(paths) != 3:
        return paths  # only defined for exactly three paths

    def mean_z(path):
        return sum(n[2] for n in path) / len(path) if path else 0.0

    def mean_x(path):
        return sum(n[0] for n in path) / len(path) if path else 0.0

    # Stem = path with lowest mean Z.
    stem_idx = min(range(3), key=lambda i: mean_z(paths[i]))
    forks = [paths[i] for i in range(3) if i != stem_idx]

    # Left = lower mean X, right = higher mean X.
    if mean_x(forks[0]) <= mean_x(forks[1]):
        left, right = forks[0], forks[1]
    else:
        left, right = forks[1], forks[0]

    return [paths[stem_idx], left, right]


def paths_to_graph(paths):
    paths = _sort_paths_by_axis(paths)

    g = Graph()

    for axis_idx, path in enumerate(paths):

        for i in range(len(path) - 1):
            u = path[i]
            v = path[i + 1]

            if not g.has_node(u):
                g.add_node(u)
                g.node_attribute(u, "axis", value=set())

            axes_u = g.node_attribute(u, "axis") or set()
            axes_u.add(axis_idx)
            g.node_attribute(u, "axis", value=axes_u)


            if not g.has_node(v):
                g.add_node(v)
                g.node_attribute(v, "axis", value=set())

            axes_v = g.node_attribute(v, "axis") or set()
            axes_v.add(axis_idx)
            g.node_attribute(v, "axis", value=axes_v)

            if not g.has_edge((u, v)):
                g.add_edge(u, v)
                g.edge_attribute((u, v), "axis", value=set())
            
            axes_edge = g.edge_attribute((u, v), "axis") or set()
            axes_edge.add(axis_idx)
            g.edge_attribute((u, v), "axis", value=axes_edge)

    return g


def get_average_z_from_end_points(graph):
    """Compute the average Z value of the end points (degree 1 nodes) in the graph.
    Parameters
    ----------
    graph : Graph
        The input graph.
    Returns
    -------
    float
        The average Z value of the end points.
    """
    return statistics.mean([n[2] for n in graph.nodes_where({"degree":1})])


def get_number_of_end_points_above_threshold(graph, threshold):
    """Count the number of end points (degree 1 nodes) in the graph that have a Z value above a given threshold.

    Parameters
    ----------
    graph : Graph
        The input graph.
    threshold : float
        The Z value threshold.

    Returns
    -------
    int
        The number of end points above the threshold.
    """
    return sum(1 for _, _, z in graph.nodes_where({"degree":1}) if z > threshold)


def _sample_path_point_and_tangent(path, distance):
    """Sample a point and local tangent at a distance along a graph path.
        Parameters
        ----------
        path : list of tuple
            A list of node coordinates representing a path in the graph.
        distance : float
            The distance along the path at which to sample the point and tangent.

        Returns
        -------
        tuple
            A tuple containing the sampled point and tangent.
    """
    if len(path) < 2:
        raise ValueError("Path must contain at least two nodes.")

    remaining = max(0.0, float(distance))
    for a, b in zip(path[:-1], path[1:]):
        a_xyz = np.asarray(a, dtype=float)
        b_xyz = np.asarray(b, dtype=float)
        segment = b_xyz - a_xyz
        seg_length = float(np.linalg.norm(segment))
        if seg_length <= 1e-12:
            continue

        if remaining <= seg_length:
            t = remaining / seg_length
            point = a_xyz + t * segment
            tangent = segment / seg_length
            return point.tolist(), tangent.tolist()

        remaining -= seg_length

    a_xyz = np.asarray(path[-2], dtype=float)
    b_xyz = np.asarray(path[-1], dtype=float)
    tangent = b_xyz - a_xyz
    tangent_length = float(np.linalg.norm(tangent))
    tangent = tangent / tangent_length if tangent_length > 1e-12 else np.array([0.0, 0.0, 1.0])
    return b_xyz.tolist(), tangent.tolist()


def clean_bifurcation_graph(graph):
    """Clean a bifurcation graph by removing short branches and small loops.

    Parameters
    ----------
    graph : Graph
        The input graph to clean.

    Returns
    -------
    Graph
        The cleaned graph.
    """
    node, best_paths, best_length = find_best_bifurcation(graph)
    best_graph = paths_to_graph(best_paths)
    return best_graph


def get_bifurcation_node(graph):
    return list(graph.nodes_where({"axis":{0,1,2}}))[0]


def get_axis_path(graph, axis_idx):
    """Return the ordered list of node keys from the bifurcation node to the
    leaf for a given axis index.

    The bifurcation node (axis {0,1,2}) is always the first element.
    Traversal follows only edges whose ``axis`` attribute contains
    ``axis_idx``.

    Parameters
    ----------
    graph : Graph
        The bifurcation graph produced by ``clean_bifurcation_graph``.
    axis_idx : int
        0 = stem, 1 = left fork, 2 = right fork.

    Returns
    -------
    list[tuple]
        Ordered node keys, or an empty list if the axis cannot be found.
    """
    bif_candidates = list(graph.nodes_where({"axis": {0, 1, 2}}))
    if not bif_candidates:
        return []

    bif_node = bif_candidates[0]
    path = [bif_node]
    current = bif_node
    prev = None

    while True:
        next_node = None
        for edge in graph.node_edges(current):
            u, v = edge
            nbr = v if u == current else u
            if nbr == prev:
                continue
            edge_axes = graph.edge_attribute(edge, "axis") or set()
            if axis_idx in edge_axes:
                next_node = nbr
                break

        if next_node is None:
            break

        path.append(next_node)
        prev, current = current, next_node

        if graph.degree(current) == 1:
            break

    return path


def get_trunk_axis(graph, geometry=False):
    axis_edges = list(graph.edges_where({"axis":{0}}))
    if geometry:
        return get_graph_polyline(axis_edges)
    else:
        return axis_edges
    
def get_bifurcating_axes(graph, geometry=False):
    axis_1_edges = list(graph.edges_where({"axis":{1}}))
    axis_2_edges = list(graph.edges_where({"axis":{2}}))
    if geometry:
        return get_graph_polyline(axis_1_edges), get_graph_polyline(axis_2_edges)
    else:
        return axis_1_edges, axis_2_edges


def get_graph_polyline(graph):
    pts = []
    # if graph is type graph, check if graph is type edges or type graph
    if hasattr(graph, 'edges'):
        for i, (u, v) in enumerate(graph.edges()):
            if i == 0:
                pts.append(Point(*u))
            pts.append(Point(*v))
    else:
        # if graph is type edges
        for i, (u, v) in enumerate(graph):
            if i == 0:
                pts.append(Point(*u))
            pts.append(Point(*v))

    return Polyline(pts)
