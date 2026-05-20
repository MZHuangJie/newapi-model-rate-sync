from __future__ import annotations

import base64
import ctypes
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models import Site


class CredentialStore:
    def __init__(self, path: Optional[Path] = None):
        if path is None:
            base_dir = Path(os.environ.get("APPDATA") or Path.home()) / "NewApiPriceSync"
            path = base_dir / "sites.json"
        self.path = Path(path)

    def load_sites(self) -> List[Site]:
        if not self.path.exists():
            return []
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        sites = []
        for item in raw.get("sites", []):
            if not isinstance(item, dict):
                continue
            data = dict(item)
            data["token"] = self._decrypt_field(data, "token")
            data["password"] = self._decrypt_field(data, "password")
            sites.append(Site.from_dict(data))
        return sites

    def save_sites(self, sites: List[Site]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"sites": [self._serialize_site(site) for site in sites]}
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(self.path)

    def upsert_site(self, data: Dict[str, Any], site_id: Optional[str] = None) -> Site:
        sites = self.load_sites()
        current = next((site for site in sites if site.id == site_id), None) if site_id else None
        if current is None:
            current = Site(
                id=site_id or f"site_{uuid.uuid4().hex[:12]}",
                name="未命名站点",
                url="",
            )
            sites.append(current)

        for attr in (
            "name",
            "url",
            "token",
            "auth_type",
            "auth_method",
            "user_id",
            "username",
            "password",
        ):
            if attr in data:
                setattr(current, attr, str(data.get(attr) or ""))
        current.auth_type = current.auth_type or "admin"
        current.auth_method = current.auth_method or "access_token"
        current.status = str(data.get("status") or "untested")
        self.save_sites(sites)
        return Site.from_dict(current.to_dict())

    def delete_site(self, site_id: str) -> bool:
        return False

    def get_site(self, site_id: str) -> Site:
        for site in self.load_sites():
            if site.id == site_id:
                return site
        raise KeyError(f"站点不存在: {site_id}")

    def update_status(self, site_id: str, status: str) -> None:
        sites = self.load_sites()
        for site in sites:
            if site.id == site_id:
                site.status = status
                self.save_sites(sites)
                return

    def _serialize_site(self, site: Site) -> Dict[str, Any]:
        data = site.to_dict()
        token = str(data.pop("token", ""))
        password = str(data.pop("password", ""))
        data["token_enc"] = _protect(token)
        data["password_enc"] = _protect(password)
        return data

    @staticmethod
    def _decrypt_field(data: Dict[str, Any], field: str) -> str:
        encrypted = data.get(f"{field}_enc")
        if encrypted:
            return _unprotect(str(encrypted))
        return str(data.get(field, ""))


def _protect(value: str) -> str:
    if not value:
        return ""
    raw = value.encode("utf-8")
    if os.name == "nt":
        return "dpapi:" + base64.b64encode(_dpapi_protect(raw)).decode("ascii")
    return "plain:" + base64.b64encode(raw).decode("ascii")


def _unprotect(value: str) -> str:
    if not value:
        return ""
    try:
        if value.startswith("dpapi:"):
            raw = base64.b64decode(value.removeprefix("dpapi:"))
            return _dpapi_unprotect(raw).decode("utf-8")
        if value.startswith("plain:"):
            return base64.b64decode(value.removeprefix("plain:")).decode("utf-8")
    except Exception:
        return ""
    return value


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_ulong),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _make_blob(data: bytes) -> tuple[_DATA_BLOB, ctypes.Array[Any]]:
    buffer = ctypes.create_string_buffer(data)
    blob = _DATA_BLOB(
        len(data),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
    )
    return blob, buffer


def _dpapi_protect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buffer = _make_blob(data)
    out_blob = _DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    in_blob, _buffer = _make_blob(data)
    out_blob = _DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)
