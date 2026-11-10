import unittest
from inverse_tree import inverse_tree, svg_tree
from visualize3d import trajectory

class VisualizationTests(unittest.TestCase):
    def test_trajectory(self):
        self.assertEqual(trajectory(3, 20), [3, 10, 5, 16, 8, 4, 2, 1])
        self.assertEqual(trajectory(1, 10), [1])
        self.assertEqual(trajectory(27, 1), [27, 82])

    def test_inverse_edges(self):
        nodes = inverse_tree(15, 1000)
        values = [n["value"] for n in nodes]
        self.assertEqual(len(values), len(set(values)))
        self.assertIn(3, values)
        for node in nodes[1:]:
            parent = nodes[node["parent"]]["value"]
            child = node["value"]
            self.assertEqual(child // 2 if child % 2 == 0 else 3 * child + 1, parent)
        self.assertIn("<svg", svg_tree(nodes))

if __name__ == "__main__":
    unittest.main()