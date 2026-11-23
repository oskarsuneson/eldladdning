import os
import random
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import eldledning as e  # noqa: E402


class TestBallistics(unittest.TestCase):
    def test_range_elevation_roundtrip(self):
        for v in e.CHARGES.values():
            for r in (1500, 3000, 4500):
                el = e.elev_for(v, r)
                if el is not None:
                    self.assertAlmostEqual(e.rng_for(v, el), r, delta=0.01)

    def test_unreachable_target(self):
        self.assertIsNone(e.elev_for(e.CHARGES[1], 5000))


class GameTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        e.SAVE = os.path.join(self.tmp, "save.json")
        random.seed(1)
        self.g = e.Game()

    def land(self, typ, x, y, tgt=0):
        g = self.g
        g.state = "flight"
        g.shot_type = typ
        g.shot_target = tgt
        g.pending = (x, y)
        g.impact()


class TestMissions(GameTestCase):
    def test_target_counts_and_positions(self):
        for n in range(1, 12):
            m = e.Mission(n, e.DEFAULT_PROFILE)
            self.assertTrue(1 <= len(m.targets) <= 4)
            self.assertLessEqual(len(m.targets), 1 + n // 2)
            for t in m.targets:
                self.assertTrue(0 <= t.x <= e.MAP_M and 0 <= t.y <= e.MAP_M)

    def test_tutorial_starts_open_then_remembered(self):
        self.assertEqual(self.g.tut, 0)
        for _ in range(len(e.TUTORIAL)):
            self.g.tut_next()
        self.assertIsNone(self.g.tut)
        self.assertTrue(e.load_profile()["tutorial_done"])
        self.assertIsNone(e.Game().tut)

    def test_destroying_all_targets_wins(self):
        g = self.g
        g.m.friend = None
        t = g.m.targets[0]
        t.hard = "mjuk"
        for other in g.m.targets[1:]:
            other.hp = 0
        before = g.points
        self.land("HE", t.x, t.y)
        self.assertEqual(g.state, "end")
        self.assertGreater(g.points, before)
        self.assertEqual(g.p["won"], 1)

    def test_he_is_weak_against_bunker_aphe_strong(self):
        g = self.g
        g.m.friend = None
        g.m.targets = g.m.targets[:1]
        t = g.m.targets[0]
        t.hard, t.hp = "bunker", 100
        self.land("HE", t.x, t.y)
        self.assertEqual(t.hp, 85)
        self.land("APHE", t.x, t.y)
        self.assertEqual(t.hp, 25)

    def test_friendly_fire_costs_trust(self):
        g = self.g
        t = g.m.targets[0]
        g.m.friend = (t.x + 200, t.y)
        trust = g.trust
        self.land("HE", t.x + 200, t.y)
        self.assertEqual(g.trust, trust - 1)
        self.assertEqual(g.state, "end")


class TestShopAndSave(GameTestCase):
    def test_save_roundtrip(self):
        self.g.points = 777
        self.g.save()
        self.assertEqual(e.load_profile()["points"], 777)

    def test_corrupt_save_falls_back_to_defaults(self):
        with open(e.SAVE, "w", encoding="utf-8") as f:
            f.write("{inte json")
        self.assertEqual(e.load_profile()["points"], 0)

    def test_buy_spotter(self):
        g = self.g
        g.spotter = False
        g.points = 200
        g.buy(1)
        self.assertTrue(g.spotter)
        self.assertEqual(g.points, 50)

    def test_cannot_buy_without_points(self):
        g = self.g
        g.spotter = False
        g.points = 10
        g.buy(1)
        self.assertFalse(g.spotter)

    def test_no_korr_without_spotter(self):
        g = self.g
        g.spotter = False
        g.last = None
        g.korr()
        self.assertIn("INGEN SPEJARE", g.log[-1][0])


if __name__ == "__main__":
    unittest.main()
