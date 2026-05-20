from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Site:
    id: str
    name: str
    url: str
    token: str = ""
    auth_type: str = "admin"
    status: str = "untested"
    auth_method: str = "access_token"
    user_id: str = ""
    username: str = ""
    password: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "token": self.token,
            "auth_type": self.auth_type,
            "status": self.status,
            "auth_method": self.auth_method,
            "user_id": self.user_id,
            "username": self.username,
            "password": self.password,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Site":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            url=str(data.get("url", "")),
            token=str(data.get("token", "")),
            auth_type=str(data.get("auth_type", "admin")),
            status=str(data.get("status", "untested")),
            auth_method=str(data.get("auth_method", "access_token")),
            user_id=str(data.get("user_id", "")),
            username=str(data.get("username", "")),
            password=str(data.get("password", "")),
        )


@dataclass
class ModelPricing:
    name: str
    billing_mode: str = "unset"
    input_price: float = 0.0
    output_price: float = 0.0
    cache_read_price: float = 0.0
    cache_create_price: float = 0.0
    times_price: float = 0.0
    expression: str = ""
    tiers: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "synced"

    def get_summary(self) -> str:
        if self.billing_mode == "unset":
            return "未设置价格"
        if self.billing_mode == "quota":
            parts = [
                f"输入 ${self.input_price:.4f}/1M",
                f"输出 ${self.output_price:.4f}/1M",
            ]
            if self.cache_read_price > 0:
                parts.append(f"缓存读取 ${self.cache_read_price:.4f}/1M")
            if self.cache_create_price > 0:
                parts.append(f"缓存创建 ${self.cache_create_price:.4f}/1M")
            return " / ".join(parts)
        if self.billing_mode == "times":
            return f"按次 ${self.times_price:.6f}/次"
        if self.billing_mode == "expr":
            if self.expression:
                return f"表达式 {self.expression[:60]}"
            if self.tiers:
                return f"阶梯收费 {len(self.tiers)} 档"
            return "表达式未配置"
        return "未知"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "billing_mode": self.billing_mode,
            "input_price": self.input_price,
            "output_price": self.output_price,
            "cache_read_price": self.cache_read_price,
            "cache_create_price": self.cache_create_price,
            "times_price": self.times_price,
            "expression": self.expression,
            "tiers": [dict(t) for t in self.tiers],
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelPricing":
        return cls(
            name=str(data.get("name", "")),
            billing_mode=str(data.get("billing_mode", "unset")),
            input_price=float(data.get("input_price") or 0.0),
            output_price=float(data.get("output_price") or 0.0),
            cache_read_price=float(data.get("cache_read_price") or 0.0),
            cache_create_price=float(data.get("cache_create_price") or 0.0),
            times_price=float(data.get("times_price") or 0.0),
            expression=str(data.get("expression", "")),
            tiers=[dict(t) for t in data.get("tiers", [])],
            status=str(data.get("status", "synced")),
        )
