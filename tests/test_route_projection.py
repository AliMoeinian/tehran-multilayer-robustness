import unittest
from research.src.extract_routes import project_stop, ordered, order_status


class ProjectionTests(unittest.TestCase):
    def test_known_segment_distance_and_progress(self):
        distance, progress, ambiguous = project_stop((30, 10), [(0, 0), (100, 0)])
        self.assertAlmostEqual(distance, 10)
        self.assertAlmostEqual(progress, 30)
        self.assertFalse(ambiguous)

    def test_adjacent_segments_at_same_vertex_are_not_ambiguous(self):
        self.assertFalse(project_stop((100, 0), [(0, 0), (100, 0), (100, 100)])[2])

    def test_repeated_trace_location_is_ambiguous(self):
        self.assertTrue(project_stop((20, 0), [(0, 0), (100, 0), (0, 0)])[2])

    def test_zero_length_segment(self):
        self.assertAlmostEqual(project_stop((30, 0), [(0, 0), (0, 0), (100, 0)])[1], 30)

    def test_recorded_order_is_not_automatically_reversed(self):
        self.assertTrue(ordered([0, 20, 100]))
        self.assertFalse(ordered([100, 20, 0]))

    def test_reverse_and_mixed_order_are_distinct(self):
        self.assertEqual(order_status([100, 20, 0]), "opposes_trace")
        self.assertEqual(order_status([0, 100, 20]), "mixed")


if __name__ == "__main__":
    unittest.main()
