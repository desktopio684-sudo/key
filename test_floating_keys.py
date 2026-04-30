import unittest

from floating_keys import (
    _parse_xrandr_primary_bounds,
    build_xdotool_key_spec,
    calculate_spawn_layout,
    is_latching_modifier,
    key_needs_spawn_position,
)


def overlaps(rect_a, rect_b):
    ax, ay, aw, ah = rect_a
    bx, by, bw, bh = rect_b
    return ax < bx + bw and ax + aw > bx and ay < by + bh and ay + ah > by


class FloatingKeyLayoutTests(unittest.TestCase):
    def assert_inside_bounds(self, rects, bounds):
        left, top, screen_w, screen_h = bounds
        for x, y, width, height in rects:
            self.assertGreaterEqual(x, left)
            self.assertGreaterEqual(y, top)
            self.assertLessEqual(x + width, left + screen_w)
            self.assertLessEqual(y + height, top + screen_h)

    def assert_no_overlaps(self, rects):
        for i, rect_a in enumerate(rects):
            for rect_b in rects[i + 1:]:
                self.assertFalse(overlaps(rect_a, rect_b))

    def test_xrandr_parser_prefers_primary_monitor(self):
        output = "\n".join([
            "HDMI-1 connected 1920x1080+0+0",
            "DP-1 connected primary 2560x1440+1920+0",
        ])

        self.assertEqual(
            _parse_xrandr_primary_bounds(output),
            (1920, 0, 2560, 1440),
        )

    def test_xrandr_parser_falls_back_to_first_connected_monitor(self):
        output = "\n".join([
            "HDMI-1 connected 1920x1080+0+0",
            "DP-1 connected 2560x1440+1920+0",
        ])

        self.assertEqual(
            _parse_xrandr_primary_bounds(output),
            (0, 0, 1920, 1080),
        )

    def test_center_anchor_places_single_key_at_screen_center(self):
        rects = calculate_spawn_layout(
            sizes=[(48, 36)],
            bounds=(0, 0, 1920, 1080),
            anchor="center",
        )

        self.assertEqual(rects, [(936, 522, 48, 36)])

    def test_corner_anchors_start_from_requested_corner(self):
        bounds = (0, 0, 800, 600)
        size = [(48, 36)]

        self.assertEqual(
            calculate_spawn_layout(size, bounds, "top_left")[0],
            (28, 28, 48, 36),
        )
        self.assertEqual(
            calculate_spawn_layout(size, bounds, "top_right")[0],
            (724, 28, 48, 36),
        )
        self.assertEqual(
            calculate_spawn_layout(size, bounds, "bottom_left")[0],
            (28, 536, 48, 36),
        )
        self.assertEqual(
            calculate_spawn_layout(size, bounds, "bottom_right")[0],
            (724, 536, 48, 36),
        )

    def test_many_keys_stay_inside_screen_and_do_not_overlap(self):
        bounds = (0, 0, 800, 600)
        rects = calculate_spawn_layout(
            sizes=[(48, 36)] * 100,
            bounds=bounds,
            anchor="top_left",
        )

        self.assertEqual(len(rects), 100)
        self.assert_inside_bounds(rects, bounds)
        self.assert_no_overlaps(rects)

    def test_dense_layout_shrinks_cells_instead_of_overlapping(self):
        bounds = (0, 0, 320, 240)
        rects = calculate_spawn_layout(
            sizes=[(80, 50)] * 80,
            bounds=bounds,
            anchor="center",
        )

        self.assertEqual(len(rects), 80)
        self.assert_inside_bounds(rects, bounds)
        self.assert_no_overlaps(rects)
        self.assertTrue(any(width < 80 or height < 50 for _, _, width, height in rects))

    def test_saved_positions_are_not_repositioned_by_spawn_layout(self):
        saved = {"enter": (100, 200)}

        def lookup(key_id):
            return saved.get(key_id)

        self.assertFalse(key_needs_spawn_position("enter", lookup))
        self.assertTrue(key_needs_spawn_position("escape", lookup))

    def test_only_expected_modifiers_latch(self):
        for key_id in ("ctrl_l", "alt_l", "super_l", "shift_l"):
            self.assertTrue(is_latching_modifier(key_id))

        self.assertFalse(is_latching_modifier("caps_lock"))
        self.assertFalse(is_latching_modifier("enter"))

    def test_latched_modifiers_build_chorded_xdotool_key_spec(self):
        self.assertEqual(
            build_xdotool_key_spec("c", {"ctrl_l"}),
            "Control_L+c",
        )
        self.assertEqual(
            build_xdotool_key_spec("Delete", {"shift_l", "ctrl_l", "alt_l"}),
            "Control_L+Alt_L+Shift_L+Delete",
        )

    def test_no_latched_modifiers_keeps_plain_key_spec(self):
        self.assertEqual(build_xdotool_key_spec("a", set()), "a")

    def test_modifier_order_is_consistent_for_chorded_input(self):
        """Verify modifiers are always sent in MODIFIER_SEND_ORDER."""
        # Regardless of insertion order, output should follow MODIFIER_SEND_ORDER
        result1 = build_xdotool_key_spec("x", {"shift_l", "ctrl_l", "alt_l"})
        result2 = build_xdotool_key_spec("x", {"alt_l", "ctrl_l", "shift_l"})
        result3 = build_xdotool_key_spec("x", {"ctrl_l", "alt_l", "shift_l"})

        # All should produce the same result in correct order
        expected = "Control_L+Alt_L+Shift_L+x"
        self.assertEqual(result1, expected)
        self.assertEqual(result2, expected)
        self.assertEqual(result3, expected)

    def test_all_four_modifiers_chorded(self):
        """Test Ctrl+Alt+Super+Shift chord combination."""
        result = build_xdotool_key_spec(
            "z",
            {"ctrl_l", "alt_l", "super_l", "shift_l"}
        )
        self.assertEqual(
            result,
            "Control_L+Alt_L+Super_L+Shift_L+z"
        )


if __name__ == "__main__":
    unittest.main()
