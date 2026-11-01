import unittest

from research.src.resolve_route_exclusions import direction_limit


class RouteDirectionTests(unittest.TestCase):
    def test_bus_override_precedes_generic_oneway(self):
        self.assertEqual(direction_limit({'oneway':'yes','oneway:bus':'no'})[0],0)

    def test_negative_oneway(self):
        self.assertEqual(direction_limit({'oneway':'-1'})[0],-1)

    def test_roundabout_default(self):
        self.assertEqual(direction_limit({'junction':'roundabout'})[0],1)

    def test_conditional_direction_is_not_certified(self):
        self.assertIsNone(direction_limit({'oneway':'yes','oneway:conditional':'no @ (Mo-Fr)'})[0])

    def test_contraflow_lane_is_not_silently_ignored(self):
        self.assertIsNone(direction_limit({'oneway':'yes','busway':'opposite_lane'})[0])

    def test_directional_bus_access_is_not_silently_ignored(self):
        self.assertIsNone(direction_limit({'oneway':'yes','bus:backward':'yes'})[0])


if __name__=='__main__':unittest.main()
