import unittest

from app.services.panel_aware_reading_order import assign_regions, order_panels, panel_aware_order, topological_order


def panel(name, bbox):
    return {"panel_id": name, "bbox": bbox}


class PanelAwareReadingOrderTests(unittest.TestCase):
    def test_two_by_two_is_row_major_rtl(self):
        panels = [panel("tl", [0, 0, 40, 40]), panel("tr", [60, 0, 100, 40]),
                  panel("bl", [0, 60, 40, 100]), panel("br", [60, 60, 100, 100])]
        self.assertEqual(order_panels(panels)["order"], ["tr", "tl", "br", "bl"])

    def test_spanning_top_and_bottom(self):
        top = [panel("top", [0, 0, 100, 30]), panel("left", [0, 40, 40, 100]), panel("right", [60, 40, 100, 100])]
        self.assertEqual(order_panels(top)["order"], ["top", "right", "left"])
        bottom = [panel("left", [0, 0, 40, 60]), panel("right", [60, 0, 100, 60]), panel("bottom", [0, 70, 100, 100])]
        self.assertEqual(order_panels(bottom)["order"], ["right", "left", "bottom"])

    def test_tall_side_panels(self):
        tall_right = [panel("right", [60, 0, 100, 100]), panel("lt", [0, 0, 40, 40]), panel("lb", [0, 60, 40, 100])]
        self.assertEqual(order_panels(tall_right)["order"], ["right", "lt", "lb"])
        tall_left = [panel("left", [0, 0, 40, 100]), panel("rt", [60, 0, 100, 40]), panel("rb", [60, 60, 100, 100])]
        self.assertEqual(order_panels(tall_left)["order"], ["rt", "rb", "left"])

    def test_assignment_ambiguity_and_unassigned_fail_closed(self):
        panels = [panel("a", [0, 0, 60, 100]), panel("b", [40, 0, 100, 100])]
        result = assign_regions([{"id": "overlap", "bbox": [45, 20, 55, 40]}, {"id": "out", "bbox": [120, 0, 130, 10]}], panels)
        self.assertEqual(len(result["ambiguous"]), 1)
        self.assertEqual(len(result["unassigned"]), 1)
        self.assertEqual(panel_aware_order([{"id": "out", "bbox": [120, 0, 130, 10]}], panels)["sequence"], [])

    def test_overlap_without_strict_cut_is_unresolved(self):
        result = order_panels([panel("a", [0, 0, 70, 70]), panel("b", [30, 30, 100, 100])])
        self.assertFalse(result["resolved"])

    def test_cycle_and_multiple_topological_orders_fail_closed(self):
        cycle = topological_order(["a", "b"], [{"before": "a", "after": "b"}, {"before": "b", "after": "a"}])
        self.assertFalse(cycle["resolved"])
        multiple = topological_order(["a", "b"], [])
        self.assertFalse(multiple["resolved"])

    def test_panel_input_permutation_is_invariant(self):
        panels = [panel("left", [0, 0, 40, 100]), panel("right", [60, 0, 100, 100])]
        self.assertEqual(order_panels(panels)["order"], order_panels(list(reversed(panels)))["order"])


if __name__ == "__main__":
    unittest.main()
