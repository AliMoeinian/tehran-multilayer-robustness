import unittest
import numpy as np
from research.src.build_connections import overlapping_segments,cut_positions,boarding_permissions


class ConnectionTests(unittest.TestCase):
    def test_exact_stop_at_boundary_does_not_depend_on_next_segment(self):
        self.assertEqual(overlapping_segments(np.array([0,10,30]),0,10),[0])

    def test_partial_segment_interval(self):
        self.assertEqual(overlapping_segments(np.array([0,10,30,40]),5,35),[0,1,2])

    def test_reversed_interval_rejected(self):
        with self.assertRaises(ValueError):overlapping_segments(np.array([0,10]),8,2)

    def test_two_connectors_preserve_original_length(self):
        cuts=cut_positions(0,100,[80,20,20,0,100])
        self.assertEqual(cuts,[0,20,80,100])
        self.assertEqual(sum(np.diff(cuts)),100)

    def test_restricted_boarding_and_alighting(self):
        self.assertEqual(boarding_permissions('stop_entry_only'),(True,False))
        self.assertEqual(boarding_permissions('platform_exit_only'),(False,True))
        self.assertEqual(boarding_permissions('stop'),(True,True))


if __name__=='__main__':unittest.main()
