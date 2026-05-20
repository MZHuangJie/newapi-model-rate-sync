import json
import tempfile
import unittest
from pathlib import Path

from app.core.client import NewApiClient
from app.core.store import CredentialStore
from app.models import Site


class StoreAndClientTests(unittest.TestCase):
    def test_store_encrypts_secret_fields_and_loads_site(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = CredentialStore(Path(tmp_dir) / "sites.json")

            site = store.upsert_site(
                {
                    "name": "local",
                    "url": "http://127.0.0.1:3000",
                    "auth_method": "password",
                    "username": "root",
                    "password": "secret-password",
                    "token": "secret-token",
                    "user_id": "1",
                }
            )

            raw = json.loads(store.path.read_text(encoding="utf-8"))
            raw_text = json.dumps(raw, ensure_ascii=False)
            self.assertNotIn("secret-token", raw_text)
            self.assertNotIn("secret-password", raw_text)

            loaded = store.load_sites()[0]
            self.assertEqual(loaded.id, site.id)
            self.assertEqual(loaded.token, "secret-token")
            self.assertEqual(loaded.password, "secret-password")
            self.assertEqual(loaded.auth_method, "password")

    def test_access_token_headers_include_new_api_user(self):
        site = Site(
            id="site_1",
            name="main",
            url="https://newapi.example",
            token="abc123",
            user_id="7",
        )

        headers = NewApiClient(site)._headers(authenticated=True)

        self.assertEqual(headers["Authorization"], "Bearer abc123")
        self.assertEqual(headers["New-Api-User"], "7")

    def test_store_delete_site_is_disabled(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = CredentialStore(Path(tmp_dir) / "sites.json")
            site = store.upsert_site({"name": "keep", "url": "https://example.com"})

            deleted = store.delete_site(site.id)

            self.assertFalse(deleted)
            self.assertEqual([s.id for s in store.load_sites()], [site.id])


if __name__ == "__main__":
    unittest.main()
