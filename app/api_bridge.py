from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .core.client import NewApiClient
from .core.store import CredentialStore
from .core.sync import SyncService, clone_models
from .models import ModelPricing, Site


_STORE = CredentialStore()
_MODEL_CACHE: Dict[str, List[ModelPricing]] = {}
_LOGS: List[str] = []


def _log(message: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _LOGS.append(f"{timestamp} {message}")


def _get_site(site_id: str) -> Site:
    return _STORE.get_site(site_id)


def _client_for(site_id: str) -> NewApiClient:
    return NewApiClient(_get_site(site_id))


class BridgeBackend:
    def get_site_name(self, site_id: str) -> str:
        try:
            return _get_site(site_id).name
        except KeyError:
            return site_id

    def load_models(self, site_id: str) -> List[ModelPricing]:
        if site_id not in _MODEL_CACHE:
            _MODEL_CACHE[site_id] = _client_for(site_id).load_models()
        return clone_models(_MODEL_CACHE[site_id])

    def get_option_maps(self, site_id: str) -> Dict[str, Dict[str, Any]]:
        return _client_for(site_id).get_option_maps()

    def update_option_maps(self, site_id: str, option_maps: Dict[str, Dict[str, Any]]) -> None:
        _client_for(site_id).update_option_maps(option_maps)


def list_sites() -> List[Site]:
    return _STORE.load_sites()


def add_site(site_data: Dict[str, Any]) -> Site:
    site = _STORE.upsert_site(site_data)
    _log(f"[INFO] 添加站点: {site.name}")
    return site


def edit_site(site_id: str, site_data: Dict[str, Any]) -> bool:
    site = _STORE.upsert_site(site_data, site_id=site_id)
    _MODEL_CACHE.pop(site_id, None)
    _log(f"[INFO] 修改站点: {site.name}")
    return True


def delete_site(site_id: str) -> bool:
    _log(f"[WARN] 已阻止删除站点: {site_id}")
    return False


def test_site(site_id: str) -> Dict[str, Any]:
    site = _get_site(site_id)
    try:
        client = NewApiClient(site)
        result = client.test_connection()
        site.status = "connected"
        if client.site.user_id:
            site.user_id = client.site.user_id
        _STORE.upsert_site(site.to_dict(), site_id=site_id)
        _log(f"[SUCCESS] 站点连接成功: {site.name}")
        return result
    except Exception as exc:
        site.status = "failed"
        _STORE.upsert_site(site.to_dict(), site_id=site_id)
        _log(f"[ERROR] 站点连接失败: {site.name} - {exc}")
        return {"success": False, "status": "failed", "message": str(exc)}


def load_site_models(site_id: str) -> List[ModelPricing]:
    if site_id in _MODEL_CACHE:
        return clone_models(_MODEL_CACHE[site_id])

    site = _get_site(site_id)
    client = NewApiClient(site)
    models = client.load_models()
    if client.site.user_id:
        site.user_id = client.site.user_id
    site.status = "connected"
    _STORE.upsert_site(site.to_dict(), site_id=site_id)
    _MODEL_CACHE[site_id] = models
    _log(f"[INFO] 加载模型价格: {site.name}, {len(models)} 个模型")
    return clone_models(models)


def get_unpriced_models(site_id: str) -> List[str]:
    return [model.name for model in load_site_models(site_id) if model.billing_mode == "unset"]


def update_model_pricing_local(site_id: str, model_name: str, pricing_data: Dict[str, Any]) -> bool:
    if pricing_data.get("billing_mode") == "unset":
        _log(f"[WARN] 已阻止清空模型价格: {model_name}")
        return False

    if site_id not in _MODEL_CACHE:
        _MODEL_CACHE[site_id] = load_site_models(site_id)

    models = _MODEL_CACHE[site_id]
    target = next((model for model in models if model.name == model_name), None)
    if target is None:
        target = ModelPricing(name=model_name, status="new")
        models.append(target)

    updated = ModelPricing.from_dict({"name": model_name, **pricing_data})
    updated.status = "modified"
    target.billing_mode = updated.billing_mode
    target.input_price = updated.input_price
    target.output_price = updated.output_price
    target.cache_read_price = updated.cache_read_price
    target.cache_create_price = updated.cache_create_price
    target.times_price = updated.times_price
    target.expression = updated.expression
    target.tiers = [dict(tier) for tier in updated.tiers]
    target.status = updated.status
    _log(f"[INFO] 本地修改价格: {model_name} -> {target.get_summary()}")
    return True


def preview_sync(
    source_site_id: str,
    target_site_ids: List[str],
    model_names: List[str],
    pricing_payload: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    service = SyncService(BridgeBackend())
    plan = service.preview_sync(source_site_id, target_site_ids, model_names, pricing_payload)
    changed = sum(1 for item in plan if item.get("action") != "NO_CHANGE")
    _log(f"[INFO] 生成同步预览: {len(plan)} 项, 需要写入 {changed} 项")
    return plan


def execute_sync(sync_plan: List[Dict[str, Any]]) -> Dict[str, Any]:
    result = SyncService(BridgeBackend()).execute_sync(sync_plan)
    for line in result.get("logs", []):
        _log(line)
    for item in sync_plan:
        if item.get("action") != "NO_CHANGE":
            _MODEL_CACHE.pop(item.get("target_site_id", ""), None)
    return result


def get_sync_logs() -> List[str]:
    return list(_LOGS)


def add_log_message(msg: str) -> None:
    _log(msg)
