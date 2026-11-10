#!/usr/bin/env python3
"""Experimental inverse Collatz tree; finite exploration is not a proof."""
import argparse
import json
from collections import deque
from pathlib import Path
from xml.sax.saxutils import escape

def inverse_tree(depth: int, max_nodes: int):
    if depth < 0 or max_nodes < 1:
        raise ValueError("depth must be >= 0 and max_nodes >= 1")
    nodes = [{"value": 1, "depth": 0, "parent": None}]
    seen = {1}
    queue = deque([0])
    while queue and len(nodes) < max_nodes:
        idx = queue.popleft()
        parent = nodes[idx]
        if parent["depth"] >= depth:
            continue
        n = parent["value"]
        candidates = [n * 2]
        if n > 4 and (n - 1) % 3 == 0:
            odd = (n - 1) // 3
            if odd > 1 and odd % 2 == 1:
                candidates.append(odd)
        for child in candidates:
            if child in seen:
                continue
            seen.add(child)
            nodes.append({"value": child, "depth": parent["depth"] + 1, "parent": idx})
            queue.append(len(nodes) - 1)
            if len(nodes) >= max_nodes:
                break
    return nodes

def svg_tree(nodes):
    levels = {}
    for idx, node in enumerate(nodes):
        levels.setdefault(node["depth"], []).append(idx)
    width = 1200
    height = 130 + 115 * len(levels)
    coords = {}
    for level, indices in levels.items():
        for pos, idx in enumerate(indices):
            coords[idx] = (width * (pos + 1) / (len(indices) + 1), 85 + 115 * level)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="#091329"/>',
             '<text x="30" y="36" fill="#f0f5ff" font-size="23" font-family="sans-serif">Inverse Collatz tree · experimental</text>']
    for idx, node in enumerate(nodes):
        x, y = coords[idx]
        if node["parent"] is not None:
            px, py = coords[node["parent"]]
            parts.append(f'<path d="M{px:.1f},{py:.1f} L{x:.1f},{y:.1f}" stroke="#4e85b3" stroke-width="1.5"/>')
    for idx, node in enumerate(nodes):
        x, y = coords[idx]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="17" fill="#1a79a7" stroke="#75dfff"/>')
        parts.append(f'<text x="{x:.1f}" y="{y+5:.1f}" text-anchor="middle" font-family="sans-serif" font-size="11" fill="white">{escape(str(node["value"]))}</text>')
    parts.append('</svg>')
    return '\n'.join(parts)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--depth", type=int, default=12)
    parser.add_argument("--max-nodes", type=int, default=300)
    parser.add_argument("--output", default="inverse-tree.svg")
    parser.add_argument("--json", dest="json_path")
    args = parser.parse_args()
    nodes = inverse_tree(args.depth, args.max_nodes)
    Path(args.output).write_text(svg_tree(nodes), encoding="utf-8")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(nodes, indent=2), encoding="utf-8")
    print(f"Generated {len(nodes)} inverse-tree nodes; no universal convergence claim.")

if __name__ == "__main__":
    main()