import json
import unittest
from pathlib import Path

from channel_ops.economics import campaign_unit_economics, example_campaign_inputs
from channel_ops.economics import example_saas_inputs, saas_unit_economics


class EconomicsTests(unittest.TestCase):
    def test_default_saas(self):
        report = saas_unit_economics(example_saas_inputs())
        self.assertEqual(report["basis"]["status"], "assumptions_only")
        self.assertEqual(report["variable_cost_usd"], 9.07)
        self.assertEqual(report["monthly_contribution_usd"], 9.36)
        self.assertEqual(report["simple_payback_months"], 3.74)
        self.assertEqual(report["steady_break_even_active_channels"], 40)

    def test_sensitivity(self):
        report = saas_unit_economics(dict(example_saas_inputs(), monthly_price_usd=29))
        self.assertEqual(report["steady_break_even_active_channels"], 18)
        report = saas_unit_economics(dict(example_saas_inputs(), support_minutes=30))
        self.assertEqual(report["monthly_contribution_usd"], -0.64)
        self.assertIsNone(report["simple_payback_months"])
        self.assertIsNone(report["steady_break_even_active_channels"])

    def test_no_acquisitions_and_no_churn(self):
        inputs = dict(example_saas_inputs(), new_paying_channels=0)
        self.assertIsNone(saas_unit_economics(inputs)["steady_break_even_active_channels"])
        inputs["monthly_churn_percent"] = 0
        report = saas_unit_economics(inputs)
        self.assertIsNone(report["cac_usd"])
        self.assertIsNone(report["modeled_lifetime_contribution_usd"])
        self.assertEqual(report["monthly_replacement_acquisition_usd"], 0)
        self.assertEqual(report["steady_break_even_active_channels"], 33)

    def test_evidence_and_inputs(self):
        inputs = dict(example_saas_inputs(), measured_fields=["support_minutes"],
                      evidence_refs={"support_minutes": "ledger/week-2"})
        self.assertEqual(saas_unit_economics(inputs)["basis"]["status"], "mixed")
        inputs["evidence_refs"] = {}
        with self.assertRaises(ValueError):
            saas_unit_economics(inputs)
        for field, bad in [("new_paying_channels", 1.5), ("support_minutes", True),
                           ("monthly_price_usd", -1), ("monthly_price_usd", float("inf")),
                           ("monthly_price_usd", float("nan")), ("monthly_churn_percent", 101)]:
            with self.subTest(field=field, bad=bad), self.assertRaises(ValueError):
                saas_unit_economics(dict(example_saas_inputs(), **{field: bad}))

    def test_campaign_repeat_sale(self):
        report = campaign_unit_economics(example_campaign_inputs())
        self.assertEqual(report["blended_cac_usd"], 125)
        self.assertEqual(report["campaign_contribution_usd"], 25)
        self.assertEqual(report["payback_week_through_observed_window"], 2)
        self.assertEqual(report["modeled_break_even_orders"], 2)

    def test_campaign_refund_breaks_payback(self):
        inputs = example_campaign_inputs()
        refund_week = {k: 0 for k in inputs["weeks"][0]}
        refund_week["refunds_usd"] = 30
        inputs["weeks"].append(refund_week)
        self.assertIsNone(campaign_unit_economics(inputs)["payback_week_through_observed_window"])

    def test_no_orders(self):
        inputs = example_campaign_inputs()
        inputs["weeks"] = [{k: 0 for k in inputs["weeks"][0]}]
        report = campaign_unit_economics(inputs)
        self.assertEqual(report["campaign_contribution_usd"], -125)
        self.assertIsNone(report["blended_cac_usd"])
        self.assertIsNone(report["modeled_break_even_orders"])
        inputs["weeks"][0]["other_net_income_usd"] = 125
        self.assertEqual(campaign_unit_economics(inputs)["modeled_break_even_orders"], 0)

    def test_new_customers_cannot_exceed_order_count(self):
        inputs = example_campaign_inputs()
        inputs["weeks"][0]["confirmed_new_customers"] = 2
        with self.assertRaises(ValueError):
            campaign_unit_economics(inputs)

    def test_worked_examples_match_distributed_json(self):
        path = Path(__file__).resolve().parents[1] / "examples"
        for name, expected in [("saas", example_saas_inputs()), ("campaign", example_campaign_inputs())]:
            self.assertEqual(json.loads((path / f"{name}-inputs.json").read_text()), expected)


if __name__ == "__main__":
    unittest.main()
