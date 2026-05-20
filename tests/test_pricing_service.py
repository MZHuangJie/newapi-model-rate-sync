import unittest

from app.models import ModelPricing
from app.core.pricing import (
    PricingError,
    apply_pricing_to_option_maps,
    model_from_newapi_options,
    pricing_to_newapi_payload,
)


class PricingServiceTests(unittest.TestCase):
    def test_quota_prices_convert_to_newapi_ratios(self):
        pricing = ModelPricing(
            name="gpt-test",
            billing_mode="quota",
            input_price=0.25,
            output_price=2.0,
            cache_read_price=0.025,
            cache_create_price=0.375,
        )

        payload = pricing_to_newapi_payload(pricing)

        self.assertEqual(payload["mode"], "quota")
        self.assertAlmostEqual(payload["ModelRatio"], 0.125)
        self.assertAlmostEqual(payload["CompletionRatio"], 8.0)
        self.assertAlmostEqual(payload["CacheRatio"], 0.1)
        self.assertAlmostEqual(payload["CreateCacheRatio"], 1.5)

    def test_newapi_ratios_convert_to_real_prices(self):
        options = {
            "ModelRatio": {"gpt-test": 0.125},
            "CompletionRatio": {"gpt-test": 8},
            "CacheRatio": {"gpt-test": 0.1},
            "CreateCacheRatio": {"gpt-test": 1.5},
            "ModelPrice": {},
            "billing_setting.billing_mode": {},
            "billing_setting.billing_expr": {},
        }

        pricing = model_from_newapi_options("gpt-test", options)

        self.assertEqual(pricing.billing_mode, "quota")
        self.assertAlmostEqual(pricing.input_price, 0.25)
        self.assertAlmostEqual(pricing.output_price, 2.0)
        self.assertAlmostEqual(pricing.cache_read_price, 0.025)
        self.assertAlmostEqual(pricing.cache_create_price, 0.375)

    def test_times_pricing_refuses_cross_mode_change_that_requires_deletion(self):
        maps = {
            "ModelRatio": {"model-a": 1},
            "CompletionRatio": {"model-a": 2},
            "CacheRatio": {"model-a": 0.5},
            "CreateCacheRatio": {"model-a": 1.25},
            "ModelPrice": {},
            "billing_setting.billing_mode": {"model-a": "tiered_expr"},
            "billing_setting.billing_expr": {"model-a": "tier('old', p * 1)"},
        }
        pricing = ModelPricing(
            name="model-a",
            billing_mode="times",
            times_price=0.5,
        )

        with self.assertRaises(PricingError):
            apply_pricing_to_option_maps(maps, pricing)

        self.assertEqual(maps["ModelRatio"]["model-a"], 1)
        self.assertEqual(maps["billing_setting.billing_expr"]["model-a"], "tier('old', p * 1)")
        self.assertNotIn("model-a", maps["ModelPrice"])

    def test_expr_pricing_generates_tiered_expr_mode(self):
        maps = {
            "ModelRatio": {},
            "CompletionRatio": {},
            "CacheRatio": {},
            "CreateCacheRatio": {},
            "ModelPrice": {},
            "billing_setting.billing_mode": {},
            "billing_setting.billing_expr": {},
        }
        pricing = ModelPricing(
            name="model-a",
            billing_mode="expr",
            expression='tier("base", p * 1.5 + c * 7.5)',
        )

        apply_pricing_to_option_maps(maps, pricing)

        self.assertEqual(maps["billing_setting.billing_mode"]["model-a"], "tiered_expr")
        self.assertEqual(
            maps["billing_setting.billing_expr"]["model-a"],
            'tier("base", p * 1.5 + c * 7.5)',
        )

    def test_unset_pricing_is_rejected_because_it_would_delete_price(self):
        pricing = ModelPricing(name="model-a", billing_mode="unset")

        with self.assertRaises(PricingError):
            pricing_to_newapi_payload(pricing)


if __name__ == "__main__":
    unittest.main()
