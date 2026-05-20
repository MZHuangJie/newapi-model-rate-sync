import unittest

from app.core.sync import SyncService
from app.models import ModelPricing


class FakeClient:
    def __init__(self):
        self.models = {
            "source": [
                ModelPricing("gpt-test", "quota", input_price=0.25, output_price=2.0),
            ],
            "target": [
                ModelPricing("gpt-test", "unset"),
            ],
            "target_times": [
                ModelPricing("gpt-test", "times", times_price=0.5),
            ],
        }
        self.option_maps = {
            "target": {
                "ModelRatio": {},
                "CompletionRatio": {},
                "CacheRatio": {},
                "CreateCacheRatio": {},
                "ModelPrice": {},
                "billing_setting.billing_mode": {},
                "billing_setting.billing_expr": {},
            },
            "target_times": {
                "ModelRatio": {},
                "CompletionRatio": {},
                "CacheRatio": {},
                "CreateCacheRatio": {},
                "ModelPrice": {"gpt-test": 0.5},
                "billing_setting.billing_mode": {},
                "billing_setting.billing_expr": {},
            }
        }
        self.writes = []

    def load_models(self, site_id):
        return list(self.models[site_id])

    def get_option_maps(self, site_id):
        return {k: dict(v) for k, v in self.option_maps[site_id].items()}

    def update_option_maps(self, site_id, option_maps):
        self.writes.append((site_id, option_maps))


class SyncServiceTests(unittest.TestCase):
    def test_preview_sync_includes_source_pricing_payload(self):
        client = FakeClient()
        service = SyncService(client)

        plan = service.preview_sync("source", ["target"], ["gpt-test"])

        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["action"], "CREATE")
        self.assertEqual(plan[0]["source_pricing"]["billing_mode"], "quota")
        self.assertIn("输入", plan[0]["source_summary"])

    def test_preview_blocks_cross_mode_sync_that_would_require_deletion(self):
        client = FakeClient()
        service = SyncService(client)

        plan = service.preview_sync("source", ["target_times"], ["gpt-test"])

        self.assertEqual(plan[0]["action"], "BLOCKED")
        self.assertIn("删除", plan[0]["block_reason"])

    def test_execute_sync_merges_selected_model_into_target_options(self):
        client = FakeClient()
        service = SyncService(client)
        plan = service.preview_sync("source", ["target"], ["gpt-test"])

        result = service.execute_sync(plan)

        self.assertTrue(result["success"])
        self.assertEqual(len(client.writes), 1)
        _, written = client.writes[0]
        self.assertEqual(written["ModelRatio"]["gpt-test"], 0.125)
        self.assertEqual(written["CompletionRatio"]["gpt-test"], 8.0)
        self.assertNotIn("gpt-test", written["ModelPrice"])

    def test_execute_sync_skips_blocked_items_without_writing(self):
        client = FakeClient()
        service = SyncService(client)
        plan = service.preview_sync("source", ["target_times"], ["gpt-test"])

        result = service.execute_sync(plan)

        self.assertTrue(result["success"])
        self.assertEqual(result["blocked_count"], 1)
        self.assertEqual(client.writes, [])


if __name__ == "__main__":
    unittest.main()
