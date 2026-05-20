from __future__ import annotations

from typing import Any, Dict, Iterable, List

from ..models import ModelPricing


OPTION_KEYS = (
    "ModelRatio",
    "CompletionRatio",
    "CacheRatio",
    "CreateCacheRatio",
    "ModelPrice",
    "billing_setting.billing_mode",
    "billing_setting.billing_expr",
)


class PricingError(ValueError):
    pass


def _blocked_delete_message(model_name: str, details: str) -> str:
    return f"禁止删除模型价格: {model_name}。{details}"


def empty_option_maps() -> Dict[str, Dict[str, Any]]:
    return {key: {} for key in OPTION_KEYS}


def ensure_option_maps(option_maps: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    for key in OPTION_KEYS:
        value = option_maps.get(key)
        option_maps[key] = value if isinstance(value, dict) else {}
    return option_maps


def _float_value(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _round_price(value: float) -> float:
    value = round(float(value), 10)
    return 0.0 if value == -0.0 else value


def _require_non_negative(name: str, value: float) -> None:
    if value < 0:
        raise PricingError(f"{name} 不能为负数")


def tiers_to_expression(tiers: Iterable[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for idx, tier in enumerate(tiers):
        start = int(tier.get("range_start", 0) or 0)
        end = int(tier.get("range_end", -1) or -1)
        price = _float_value(tier.get("price"))
        _require_non_negative("阶梯价格", price)

        condition = f"len >= {start}"
        if end >= 0:
            condition = f"{condition} && len <= {end}"
        parts.append((condition, f'tier("tier_{idx + 1}", (p + c) * {price:g})'))

    if not parts:
        raise PricingError("表达式或阶梯配置不能为空")

    expression = 'tier("fallback", 0)'
    for condition, body in reversed(parts):
        expression = f"{condition} ? {body} : {expression}"
    return expression


def pricing_to_newapi_payload(pricing: ModelPricing) -> Dict[str, Any]:
    mode = pricing.billing_mode

    if mode == "unset":
        raise PricingError(_blocked_delete_message(pricing.name, "不能把模型价格同步为未设置状态。"))

    if mode == "times":
        price = _float_value(pricing.times_price)
        _require_non_negative("按次价格", price)
        return {"mode": "times", "ModelPrice": _round_price(price)}

    if mode == "expr":
        expression = pricing.expression.strip() if pricing.expression else ""
        if not expression:
            expression = tiers_to_expression(pricing.tiers)
        return {
            "mode": "expr",
            "BillingMode": "tiered_expr",
            "BillingExpr": expression,
        }

    if mode != "quota":
        raise PricingError(f"未知计费模式: {mode}")

    input_price = _float_value(pricing.input_price)
    output_price = _float_value(pricing.output_price)
    cache_read_price = _float_value(pricing.cache_read_price)
    cache_create_price = _float_value(pricing.cache_create_price)

    for label, value in (
        ("输入价格", input_price),
        ("输出价格", output_price),
        ("缓存读取价格", cache_read_price),
        ("缓存创建价格", cache_create_price),
    ):
        _require_non_negative(label, value)

    if input_price == 0 and any(v > 0 for v in (output_price, cache_read_price, cache_create_price)):
        raise PricingError("按量计费中，输入价格为 0 时无法换算输出或缓存倍率")

    payload: Dict[str, Any] = {
        "mode": "quota",
        "ModelRatio": _round_price(input_price / 2),
        "CompletionRatio": _round_price(output_price / input_price if input_price else 0),
    }
    if cache_read_price > 0:
        payload["CacheRatio"] = _round_price(cache_read_price / input_price)
    if cache_create_price > 0:
        payload["CreateCacheRatio"] = _round_price(cache_create_price / input_price)
    return payload


def model_from_newapi_options(model_name: str, option_maps: Dict[str, Dict[str, Any]]) -> ModelPricing:
    maps = ensure_option_maps({key: dict(value) for key, value in option_maps.items()})
    billing_mode = maps["billing_setting.billing_mode"].get(model_name)
    billing_expr = maps["billing_setting.billing_expr"].get(model_name, "")
    if billing_mode == "tiered_expr" and billing_expr:
        return ModelPricing(
            name=model_name,
            billing_mode="expr",
            expression=str(billing_expr),
            status="synced",
        )

    if model_name in maps["ModelPrice"]:
        return ModelPricing(
            name=model_name,
            billing_mode="times",
            times_price=_float_value(maps["ModelPrice"].get(model_name)),
            status="synced",
        )

    if model_name in maps["ModelRatio"]:
        input_price = _round_price(_float_value(maps["ModelRatio"].get(model_name)) * 2)
        completion_ratio = _float_value(maps["CompletionRatio"].get(model_name), 1.0)
        cache_ratio = _float_value(maps["CacheRatio"].get(model_name), 0.0)
        create_cache_ratio = _float_value(maps["CreateCacheRatio"].get(model_name), 0.0)
        return ModelPricing(
            name=model_name,
            billing_mode="quota",
            input_price=input_price,
            output_price=_round_price(input_price * completion_ratio),
            cache_read_price=_round_price(input_price * cache_ratio),
            cache_create_price=_round_price(input_price * create_cache_ratio),
            status="synced",
        )

    return ModelPricing(name=model_name, billing_mode="unset", status="synced")


def apply_pricing_to_option_maps(
    option_maps: Dict[str, Dict[str, Any]], pricing: ModelPricing
) -> Dict[str, Dict[str, Any]]:
    maps = ensure_option_maps(option_maps)
    model_name = pricing.name

    payload = pricing_to_newapi_payload(pricing)
    mode = payload["mode"]
    _reject_conflicting_existing_keys(maps, model_name, mode)

    if mode == "times":
        maps["ModelPrice"][model_name] = payload["ModelPrice"]
        return maps

    if mode == "expr":
        maps["billing_setting.billing_mode"][model_name] = payload["BillingMode"]
        maps["billing_setting.billing_expr"][model_name] = payload["BillingExpr"]
        return maps

    maps["ModelRatio"][model_name] = payload["ModelRatio"]
    maps["CompletionRatio"][model_name] = payload["CompletionRatio"]
    if "CacheRatio" in payload:
        maps["CacheRatio"][model_name] = payload["CacheRatio"]
    elif model_name in maps["CacheRatio"]:
        raise PricingError(_blocked_delete_message(model_name, "清空缓存读取价格需要删除 CacheRatio 键。"))
    if "CreateCacheRatio" in payload:
        maps["CreateCacheRatio"][model_name] = payload["CreateCacheRatio"]
    elif model_name in maps["CreateCacheRatio"]:
        raise PricingError(_blocked_delete_message(model_name, "清空缓存创建价格需要删除 CreateCacheRatio 键。"))
    return maps


def clone_pricing(pricing: ModelPricing) -> ModelPricing:
    return ModelPricing.from_dict(pricing.to_dict())


def _reject_conflicting_existing_keys(
    maps: Dict[str, Dict[str, Any]], model_name: str, mode: str
) -> None:
    allowed_keys = {
        "times": {"ModelPrice"},
        "quota": {"ModelRatio", "CompletionRatio", "CacheRatio", "CreateCacheRatio"},
        "expr": {"billing_setting.billing_mode", "billing_setting.billing_expr"},
    }[mode]
    conflicts = [
        key for key in OPTION_KEYS
        if key not in allowed_keys and model_name in maps[key]
    ]
    if conflicts:
        joined = ", ".join(conflicts)
        raise PricingError(_blocked_delete_message(model_name, f"切换计费模式需要先删除旧价格键: {joined}。"))
