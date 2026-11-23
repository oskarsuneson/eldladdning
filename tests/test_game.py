import curses
import math
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

    def test_solver_lands_exactly_with_wind(self):
        for wind in [(0, 0), (5, -3), (-8, 6), (10, 10)]:
            for c in (1, 2, 3):
                for pt in [(2000, 1800), (3000, 2500), (1500, 1000), (800, 2400)]:
                    sol = e.solve_shot(pt[0], pt[1], e.CHARGES[c], wind)
                    if sol is None:
                        continue
                    az, el, T, _ = sol
                    px, py, _ = e.predict(az, el, e.CHARGES[c], wind)
                    self.assertLess(math.hypot(px - pt[0], py - pt[1]), 0.01)


def recent(g, n=4):
    return " ".join(x[0] for x in g.log[-n:])


class GameTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        e.SAVE = os.path.join(self.tmp, "save.json")
        random.seed(1)
        self.g = e.Game()
        self.g.close_tutorial()
        self._gauss = random.gauss

    def tearDown(self):
        random.gauss = self._gauss

    def no_spread(self):
        random.gauss = lambda a, b: 0.0

    def land(self, typ, x, y, tgt=0):
        g = self.g
        g.state = "flight"
        g.shot_type = typ
        g.shot_target = tgt
        g.pending = (x, y)
        g.impact()

    def one_target(self, hard="bunker"):
        g = self.g
        g.m.friend = None
        g.m.targets = [t for t in g.m.targets if not t.bonus][:1]
        t = g.m.targets[0]
        t.hard, t.hp = hard, 100
        g.sel = 0
        return t


class TestMissions(GameTestCase):
    def test_target_counts_and_positions(self):
        for n in range(1, 12):
            m = e.Mission(n, e.DEFAULT_PROFILE)
            main = m.main_targets()
            self.assertTrue(1 <= len(main) <= 4)
            self.assertLessEqual(len(main), 1 + n // 2)
            for t in m.targets:
                self.assertTrue(0 <= t.x <= e.MAP_M and 0 <= t.y <= e.MAP_M)
            for t in m.targets:
                if t.bonus:
                    self.assertTrue(t.hidden)

    def test_tutorial_shows_every_start_until_turned_off(self):
        g = e.Game()
        self.assertEqual(g.tut, 0)
        for _ in range(len(e.TUTORIAL)):
            g.tut_next()
        self.assertIsNone(g.tut)
        self.assertEqual(e.Game().tut, 0)          # visas igen vid nasta start
        g.run("TUTORIAL AV")
        self.assertIsNone(e.Game().tut)
        g.run("TUTORIAL PA")
        self.assertEqual(e.Game().tut, 0)

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
        t = self.one_target("bunker")
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


class TestAmmo(GameTestCase):
    def test_frag_huge_radius_but_useless_against_armor(self):
        t = self.one_target("pansar")
        self.land("FRAG", t.x + 140, t.y)          # inom 150 m
        self.assertEqual(t.hp, 97)

    def test_frag_hits_soft_target_at_long_range(self):
        t = self.one_target("mjuk")
        self.land("FRAG", t.x + 140, t.y)
        self.assertEqual(t.hp, 30)
        self.land("FRAG", t.x + 160, t.y)          # utanfor 150 m
        self.assertEqual(t.hp, 30)

    def test_heat_must_hit_exactly_and_kills_anything(self):
        for hard in ("mjuk", "pansar", "bunker"):
            t = self.one_target(hard)
            self.land("HEAT", t.x + 15, t.y)        # utanfor 10 m
            self.assertEqual(t.hp, 100)
            self.g.state = "aim"
            self.land("HEAT", t.x + 6, t.y)
            self.assertEqual(t.hp, 0)

    def test_light_reveals_hidden_contacts_and_does_no_damage(self):
        g = self.g
        t = self.one_target("mjuk")
        hidden = e.Target("B", "INFANTERI", "mjuk", t.x + 200, t.y, hidden=True, bonus=True)
        far = e.Target("C", "INFANTERI", "mjuk", t.x + 2000, t.y, hidden=True, bonus=True)
        g.m.targets += [hidden, far]
        self.land("LJUS", t.x, t.y)
        self.assertFalse(hidden.hidden)
        self.assertTrue(hidden.seen)
        self.assertTrue(far.hidden)                 # utanfor 700 m
        self.assertEqual((t.hp, hidden.hp), (100, 100))
        self.assertEqual(len(g.m.lit), 1)
        self.assertEqual(g.state, "aim")

    def test_light_shows_targets_on_map_without_spotter(self):
        g = self.g
        g.spotter = False
        t = self.one_target("mjuk")
        self.assertFalse(t.seen)
        self.land("LJUS", t.x, t.y)
        self.assertTrue(t.seen)

    def test_light_never_causes_friendly_fire(self):
        g = self.g
        t = self.one_target("mjuk")
        g.m.friend = (t.x + 10, t.y)
        trust = g.trust
        self.land("LJUS", t.x, t.y)
        self.assertEqual(g.trust, trust)
        self.assertTrue(g.m.friend_seen)

    def test_hidden_contact_destroyed_by_splash_gives_bonus(self):
        g = self.g
        t = self.one_target("bunker")
        hidden = e.Target("B", "INFANTERI", "mjuk", t.x + 40, t.y, hidden=True, bonus=True)
        g.m.targets.append(hidden)
        before = g.points
        self.land("HE", t.x, t.y)
        self.assertEqual(hidden.hp, 0)
        self.assertFalse(hidden.hidden)
        self.assertGreater(g.points, before)

    def test_light_does_not_count_as_damaging_ammo(self):
        g = self.g
        m = g.m
        for k in m.stock:
            m.stock[k] = 0
        m.stock["LJUS"] = 5
        self.assertEqual(m.dmg_ammo(), 0)

    def test_all_ammo_types_have_a_stock(self):
        m = e.Mission(1, e.DEFAULT_PROFILE)
        for name in e.AMMO_TYPES:
            self.assertGreater(m.stock[name], 0)


class TestFDC(GameTestCase):
    def test_punkt_sets_solution_that_lands_on_target(self):
        g = self.g
        self.no_spread()
        g.m.werr = (0.0, 0.0)
        t = self.one_target("mjuk")
        g.run("PUNKT A HE")
        self.assertIsNotNone(g.az)
        self.assertEqual(g.aim, (t.x, t.y))
        g.run("ELD")
        self.assertEqual(g.state, "flight")
        self.assertLess(math.hypot(g.pending[0] - t.x, g.pending[1] - t.y), 2.5)

    def test_punkt_with_offset_and_absolute(self):
        g = self.g
        self.one_target("mjuk")
        g.run("PUNKT 2000 1500")
        self.assertEqual(g.aim, (2000.0, 1500.0))
        t = g.cur
        g.run("PUNKT A 30 -10")
        self.assertAlmostEqual(g.aim[0], t.x + 30, places=6)
        self.assertAlmostEqual(g.aim[1], t.y - 10, places=6)

    def test_punkt_rejects_unreachable_and_outside_map(self):
        g = self.g
        g.run("LAD 1")
        g.run("PUNKT 5500 5500")
        self.assertIn("INGEN LOSNING", recent(g))
        g.run("PUNKT 9000 100")
        self.assertIn("UTANFOR KARTAN", recent(g))

    def test_auto_charge_is_rechosen_but_manual_charge_is_kept(self):
        g = self.g
        g.run("PUNKT 2000 1500")
        low = g.charge
        g.run("PUNKT 4500 4000")                  # kraver hogre laddning
        self.assertGreater(g.charge, low)
        g.run("LAD 3")
        g.run("PUNKT 2000 1500")
        self.assertEqual(g.charge, 3)             # manuellt val behalls

    def test_manual_input_clears_aim(self):
        g = self.g
        g.run("PUNKT A")
        self.assertIsNotNone(g.aim)
        g.run("AZ 10.5")
        self.assertIsNone(g.aim)

    def test_korr_removes_hidden_wind_error(self):
        g = self.g
        self.no_spread()
        t = self.one_target("bunker")
        g.m.werr = (2.5, -2.0)
        g.run("PUNKT A HE ELD")
        first = math.hypot(g.pending[0] - t.x, g.pending[1] - t.y)
        g.impact()
        self.assertGreater(first, 5.0)                 # vindfelet syns
        g.run("KORR")
        g.run("ELD")
        second = math.hypot(g.pending[0] - t.x, g.pending[1] - t.y)
        self.assertLess(second, 2.5)
        self.assertLess(second, first / 3)

    def test_more_registration_shots_average_out_the_noise(self):
        g = self.g
        t = self.one_target("bunker")
        g.m.werr = (1.0, -1.0)
        g.m.stock["LJUS"] = 9
        g.run("PUNKT A LJUS")
        for _ in range(3):
            g.state = "aim"
            g.run("ELD")
            g.impact()
            g.state = "aim"
            g.run("KORR")
        self.assertEqual(len(g.wsamples), 3)
        mean_x = sum(s[0] for s in g.wsamples) / 3
        self.assertAlmostEqual(g.wcorr[0], mean_x, places=9)

    def test_korr_carries_over_to_next_target(self):
        g = self.g
        self.no_spread()
        g.m.friend = None
        g.m.targets = [t for t in g.m.targets if not t.bonus]
        if len(g.m.targets) < 2:
            g.m.targets.append(e.Target("B", "BUNKER", "bunker",
                                        g.m.targets[0].x + 600, g.m.targets[0].y + 300))
        for t in g.m.targets:
            t.hard, t.hp = "bunker", 100
        g.m.werr = (-2.0, 2.0)
        g.run("PUNKT A HE ELD")
        g.impact()
        g.run("KORR")
        g.run("MAL B PUNKT B ELD")
        t = g.m.targets[1]
        self.assertLess(math.hypot(g.pending[0] - t.x, g.pending[1] - t.y), 3.5)

    def test_korr_needs_observation(self):
        g = self.g
        g.spotter = False
        self.one_target("bunker")
        g.run("PUNKT A HE ELD")
        g.impact()
        g.run("KORR")
        self.assertIn("INGEN OBSERVERAD", recent(g))

    def test_korr_works_without_spotter_after_light(self):
        g = self.g
        self.no_spread()
        g.spotter = False
        t = self.one_target("bunker")
        g.m.werr = (2.0, 1.0)
        g.run("PUNKT A LJUS ELD")
        g.impact()
        g.run("KORR")
        g.run("HEAT ELD")
        self.assertLess(math.hypot(g.pending[0] - t.x, g.pending[1] - t.y), 2.5)

    def test_heat_with_spread_hits_after_registration(self):
        g = self.g
        self.one_target("bunker")
        hits = 0
        for seed in range(40):
            random.seed(seed)
            g.state = "aim"
            g.m.stock["HEAT"] = 5
            t = g.m.targets[0]
            t.hp = 100
            g.wcorr = (0.0, 0.0)
            g.m.werr = (1.0, -1.0)
            g.run("PUNKT A LJUS ELD")
            g.impact()
            g.state = "aim"
            g.run("KORR")
            g.run("HEAT ELD")
            if math.hypot(g.pending[0] - t.x, g.pending[1] - t.y) <= 10:
                hits += 1
        self.assertGreaterEqual(hits, 30)


class TestBrowsing(GameTestCase):
    def setUp(self):
        super().setUp()
        self.g.m = e.Mission(8, e.DEFAULT_PROFILE)
        self.g.sel = 0

    def test_tab_cycles_through_visible_targets_only(self):
        g = self.g
        for t in g.m.targets:
            t.hidden = False
        g.m.targets[-1].hidden = True
        vis = g.vis()
        self.assertGreaterEqual(len(vis), 2)
        seen = []
        for _ in range(len(vis)):
            g.key(9)
            seen.append(g.sel)
        self.assertEqual(sorted(seen), sorted(vis))
        self.assertNotIn(len(g.m.targets) - 1, seen)

    def test_shift_tab_goes_back_and_arrows_work_on_empty_line(self):
        g = self.g
        for t in g.m.targets:
            t.hidden = False
        start = g.sel
        g.key(9)
        g.key(getattr(curses, "KEY_BTAB", 353))
        self.assertEqual(g.sel, start)
        g.key(curses.KEY_RIGHT)
        self.assertNotEqual(g.sel, start)
        g.key(curses.KEY_LEFT)
        self.assertEqual(g.sel, start)

    def test_arrows_do_not_switch_target_while_typing(self):
        g = self.g
        for t in g.m.targets:
            t.hidden = False
        g.buf = "AZ"
        s = g.sel
        g.key(curses.KEY_RIGHT)
        self.assertEqual(g.sel, s)

    def test_commands_nasta_forra_and_hidden_not_selectable(self):
        g = self.g
        hid = [i for i, t in enumerate(g.m.targets) if t.hidden]
        for t in g.m.targets:
            if not t.bonus:
                t.hidden = False
        g.run("NASTA")
        self.assertNotIn(g.sel, hid)
        g.run("FORRA")
        for i in hid:
            g.run(f"MAL {g.m.targets[i].letter}")
            self.assertIn("OGILTIGT", recent(g))

    def test_switching_target_clears_aim(self):
        g = self.g
        for t in g.m.targets:
            t.hidden = False
        g.run("PUNKT A")
        self.assertIsNotNone(g.aim)
        g.run("NASTA")
        self.assertIsNone(g.aim)


class TestShopAndSave(GameTestCase):
    def test_save_roundtrip(self):
        self.g.points = 777
        self.g.save()
        self.assertEqual(e.load_profile()["points"], 777)

    def test_corrupt_save_falls_back_to_defaults(self):
        with open(e.SAVE, "w", encoding="utf-8") as f:
            f.write("{inte json")
        self.assertEqual(e.load_profile()["points"], 0)

    def test_old_save_without_new_keys_loads(self):
        with open(e.SAVE, "w", encoding="utf-8") as f:
            f.write('{"points": 50, "he_extra": 2}')
        p = e.load_profile()
        self.assertEqual((p["points"], p["he_extra"], p["heat_extra"]), (50, 2, 0))

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

    def test_buy_new_ammo_adds_stock_immediately_and_saves(self):
        g = self.g
        g.points = 5000
        for n, name in ((7, "FRAG"), (8, "HEAT"), (9, "LJUS")):
            before = g.m.stock[name]
            g.buy(n)
            self.assertEqual(g.m.stock[name], before + 1)
        self.assertEqual(e.load_profile()["heat_extra"], 1)
        g2 = e.Game()
        self.assertEqual(g2.m.stock["HEAT"], e.AMMO_TYPES["HEAT"]["stock"] + 1)

    def test_extra_ammo_has_a_cap(self):
        g = self.g
        g.points = 10 ** 6
        for _ in range(10):
            g.buy(8)
        self.assertEqual(g.p["heat_extra"], 2)

    def test_no_korr_without_observation(self):
        g = self.g
        g.spotter = False
        g.korr()
        self.assertIn("INGEN OBSERVERAD", recent(g))


if __name__ == "__main__":
    unittest.main()
