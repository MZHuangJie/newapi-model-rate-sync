from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from typing import Any, Dict, List

from ..models import ModelPricing, Site
from .pricing import OPTION_KEYS, empty_option_maps, model_from_newapi_options


class NewApiError(RuntimeError):
    pass


class NewApiClient:
    def __init__(self, site: Site, timeout: int = 20):
        self.site = site
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.cookie_jar)]

        # 使用自定义 SSL 上下文，放宽 TLS 兼容性以适配更多服务器
        ctx = ssl.create_default_context()
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        try:
            ctx.set_ciphers("DEFAULT@SECLEVEL=1")
        except ssl.SSLError:
            pass

        handlers.append(urllib.request.HTTPSHandler(context=ctx))
        self.opener = urllib.request.build_opener(*handlers)
        self._authenticated = False

    def test_connection(self) -> Dict[str, Any]:
        enabled_count = len(self.get_enabled_models())
        self.get_options()
        return {
            "success": True,
            "status": "connected",
            "message": f"连接成功，检测到 {enabled_count} 个已启用模型，并具备系统设置权限。",
        }

    def load_models(self) -> List[ModelPricing]:
        enabled_models = sorted(set(self.get_enabled_models()))
        option_maps = self.get_option_maps()
        return [model_from_newapi_options(name, option_maps) for name in enabled_models]

    def get_enabled_models(self) -> List[str]:
        data = self._request("GET", "/api/channel/models_enabled")
        raw_models = data.get("data", []) if isinstance(data, dict) else []
        if isinstance(raw_models, dict):
            raw_models = list(raw_models.keys())
        return sorted(str(model) for model in raw_models if str(model).strip())

    def get_options(self) -> Dict[str, str]:
        data = self._request("GET", "/api/option/")
        options = data.get("data", []) if isinstance(data, dict) else []
        option_values: Dict[str, str] = {}
        if not isinstance(options, list):
            raise NewApiError("站点返回的系统设置格式不正确")
        for item in options:
            if isinstance(item, dict) and "key" in item:
                option_values[str(item["key"])] = str(item.get("value", ""))
        return option_values

    def get_option_maps(self) -> Dict[str, Dict[str, Any]]:
        options = self.get_options()
        maps = empty_option_maps()
        for key in OPTION_KEYS:
            maps[key] = self._parse_option_map(options.get(key, "{}"))
        return maps

    def update_option_maps(self, option_maps: Dict[str, Dict[str, Any]]) -> None:
        for key in OPTION_KEYS:
            value = json.dumps(
                option_maps.get(key, {}),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            self.update_option(key, value)

    def update_option(self, key: str, value: str) -> None:
        self._request("PUT", "/api/option/", {"key": key, "value": value})

    def ensure_authenticated(self) -> None:
        if self._authenticated:
            return

        if self.site.auth_method == "password":
            self._login_with_password()
        else:
            if not self.site.token:
                raise NewApiError("Access Token 不能为空")
            if not self.site.user_id:
                raise NewApiError("Access Token 模式需要填写 New-Api-User 用户 ID")

        self._authenticated = True

    def _login_with_password(self) -> None:
        if not self.site.username or not self.site.password:
            raise NewApiError("账号密码登录需要填写用户名和密码")

        response = self._request(
            "POST",
            "/api/user/login",
            {"username": self.site.username, "password": self.site.password},
            authenticated=False,
        )
        data = response.get("data", {}) if isinstance(response, dict) else {}
        if data.get("require_2fa"):
            raise NewApiError("该账号开启了 2FA，请改用 Access Token + New-Api-User")
        user_id = data.get("id")
        if user_id is None:
            raise NewApiError("登录成功但未返回用户 ID")
        self.site.user_id = str(user_id)

    def _request(
        self,
        method: str,
        path: str,
        payload: Dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> Dict[str, Any]:
        if authenticated:
            self.ensure_authenticated()

        data = None
        headers = self._headers(authenticated=authenticated)
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            self._url(path),
            data=data,
            headers=headers,
            method=method.upper(),
        )

        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise NewApiError(f"HTTP {exc.code}: {self._extract_error_message(body)}") from exc
        except urllib.error.URLError as exc:
            raise NewApiError(f"网络连接失败: {exc.reason}") from exc

        if not raw:
            return {}

        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NewApiError(f"站点返回了非 JSON 内容: {raw[:160]}") from exc

        if isinstance(result, dict) and result.get("success") is False:
            raise NewApiError(str(result.get("message") or "NewAPI 返回失败"))
        if not isinstance(result, dict):
            raise NewApiError("站点返回的 JSON 根节点不是对象")
        return result

    def _headers(self, authenticated: bool) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
        }
        if authenticated:
            if self.site.user_id:
                headers["New-Api-User"] = str(self.site.user_id)
            if self.site.auth_method != "password" and self.site.token:
                token = self.site.token.strip()
                headers["Authorization"] = token if token.startswith("Bearer ") else f"Bearer {token}"
        return headers

    def _url(self, path: str) -> str:
        base = self.site.url.strip().rstrip("/")
        if not base:
            raise NewApiError("站点 URL 不能为空")
        if not path.startswith("/"):
            path = "/" + path
        return urllib.parse.urljoin(base + "/", path.lstrip("/"))

    @staticmethod
    def _parse_option_map(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        if raw is None or str(raw).strip() == "":
            return {}
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}

    @staticmethod
    def _extract_error_message(body: str) -> str:
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                return str(parsed.get("message") or parsed.get("error") or body[:160])
        except json.JSONDecodeError:
            pass
        return body[:160]
