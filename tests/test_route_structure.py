import unittest
from research.src.route_structure import merge_intervals,shared_length


class RouteIntervalTests(unittest.TestCase):
    def test_repeated_traversals_do_not_duplicate_physical_overlap(self):
        first=merge_intervals([(0,2),(1,4),(0,2),(7,8)])
        self.assertEqual(first,[(0,4),(7,8)])
        self.assertEqual(shared_length(first,[(2,7.5)]),2.5)
        self.assertEqual(shared_length(first,[(4,7)]),0)
