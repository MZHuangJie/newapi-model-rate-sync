from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional

from ..models import ModelPricing
from .pricing import apply_pricing_to_option_maps, clone_pricing


def _model_map(models: Iterable[ModelPricing]) -> Dict[str, ModelPricing]:
    return {model.name: model for model in models}


def _pricing_equal(left: Optional[ModelPricing], right: Optional[ModelPricing]) -> bool:
    if left is None or right is None:
        return left is right
    left_data = left.to_dict()
    right_data = right.to_dict()
    left_data.pop("status", None)
    right_data.pop("status", None)
    return left_data == right_data


def _site_name(backend: Any, site_id: str) -> str:
    if hasattr(backend, "get_site_name"):
        return backend.get_site_name(site_id)
    return site_id


def _deletion_block_reason(source: ModelPricing, target: Optional[ModelPricing]) -> str:
    if target is None or target.billing_mode == "unset":
        return ""
    if source.billing_mode == "unset":
        return "源站价格为未设置，同步会删除目标站已有模型价格，已阻止。"
    if source.billing_mode != target.billing_mode:
        return (
            f"源站计费模式为 {source.billing_mode}，目标站计费模式为 {target.billing_mode}，"
            "切换模式需要删除旧价格键，已阻止。"
        )
    if source.billing_mode == "quota":
        if target.cache_read_price > 0 and source.cache_read_price <= 0:
            return "同步会清空目标站缓存读取价格，已阻止删除。"
        if target.cache_create_price > 0 and source.cache_create_price <= 0:
            return "同步会清空目标站缓存创建价格，已阻止删除。"
    return ""


class SyncService:
    def __init__(self, backend: Any):
        self.backend = backend

    def preview_sync(
        self,
        source_site_id: str,
        target_site_ids: List[str],
        model_names: List[str],
        pricing_payload: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        source_models = _model_map(self.backend.load_models(source_site_id))
        plan: List[Dict[str, Any]] = []

        for target_site_id in target_site_ids:
            target_models = _model_map(self.backend.load_models(target_site_id))
            for model_name in model_names:
                if pricing_payload is not None:
                    source_pricing = ModelPricing.from_dict({"name": model_name, **pricing_payload})
                else:
                    source_pricing = source_models.get(model_name)

                if source_pricing is None:
                    continue

                target_pricing = target_models.get(model_name)
                block_reason = _deletion_block_reason(source_pricing, target_pricing)
                if block_reason:
                    action = "BLOCKED"
                elif source_pricing.billing_mode == "unset":
                    action = "NO_CHANGE"
                elif target_pricing is None or target_pricing.billing_mode == "unset":
                    action = "CREATE"
                elif _pricing_equal(source_pricing, target_pricing):
                    action = "NO_CHANGE"
                else:
                    action = "UPDATE"

                plan.append(
                    {
                        "source_site_id": source_site_id,
                        "target_site_id": target_site_id,
                        "target_site_name": _site_name(self.backend, target_site_id),
                        "model_name": model_name,
                        "source_summary": source_pricing.get_summary(),
                        "target_summary": target_pricing.get_summary()
                        if target_pricing
                        else "目标站未启用或未配置该模型",
                        "action": action,
                        "block_reason": block_reason,
                        "source_pricing": source_pricing.to_dict(),
                    }
                )

        return plan

    def execute_sync(self, sync_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
        blocked = [item for item in sync_plan if item.get("action") == "BLOCKED"]
        pending = [
            item for item in sync_plan
            if item.get("action") not in ("NO_CHANGE", "BLOCKED")
        ]
        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for item in pending:
            grouped[item["target_site_id"]].append(item)

        success_count = len(sync_plan) - len(pending) - len(blocked)
        fail_count = 0
        blocked_count = len(blocked)
        logs: List[str] = ["=== 开始执行价格同步 ==="]

        for item in blocked:
            logs.append(
                f"已阻止 {item['model_name']} 到 {item['target_site_name']}: "
                f"{item.get('block_reason', '该操作需要删除旧配置')}"
            )

        for target_site_id, items in grouped.items():
            try:
                option_maps = self.backend.get_option_maps(target_site_id)
                for item in items:
                    pricing = ModelPricing.from_dict(item["source_pricing"])
                    pricing.name = item["model_name"]
                    apply_pricing_to_option_maps(option_maps, pricing)

                self.backend.update_option_maps(target_site_id, option_maps)

                for item in items:
                    success_count += 1
                    logs.append(
                        f"成功同步 {item['model_name']} 到 {item['target_site_name']}: "
                        f"{item['target_summary']} -> {item['source_summary']}"
                    )
            except Exception as exc:
                fail_count += len(items)
                target_name = _site_name(self.backend, target_site_id)
                logs.append(f"同步到 {target_name} 失败: {exc}")

        logs.append(f"=== 同步结束 | 成功: {success_count}, 失败: {fail_count} ===")
        return {
            "success": fail_count == 0,
            "success_count": success_count,
            "fail_count": fail_count,
            "blocked_count": blocked_count,
            "logs": logs,
        }


def clone_models(models: Iterable[ModelPricing]) -> List[ModelPricing]:
    return [clone_pricing(model) for model in models]
