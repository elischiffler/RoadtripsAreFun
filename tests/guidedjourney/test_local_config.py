import unittest
from urllib.parse import urlparse

from local_config import FixtureConfig


class LocalPreviewConfigTests(unittest.TestCase):
    def test_native_is_loopback_only_and_separate(self):
        config = FixtureConfig(True)
        self.assertEqual(config.bind_host, "127.0.0.1")
        self.assertEqual(
            (
                config.database_port,
                config.api_port,
                config.identity_port,
                config.provider_port,
            ),
            (6544, 8003, 8998, 9010),
        )
        self.assertEqual(
            config.origins, ["http://localhost:5173", "http://127.0.0.1:5173"]
        )
        self.assertTrue(
            config.allows_database(
                urlparse(
                    "postgresql://postgres:disposable-guided-only@127.0.0.1:6544/roadtrips"
                )
            )
        )
        for url in (
            "postgresql://postgres:disposable-guided-only@127.0.0.1:6543/roadtrips",
            "postgresql://postgres:disposable-guided-only@postgres:6544/roadtrips",
            "postgresql://postgres:disposable-guided-only@example.com:6544/roadtrips",
            "postgresql://postgres:disposable-guided-only@127.0.0.1:6544/other",
            "postgresql://postgres:disposable-guided-only@127.0.0.1:6544/roadtrips?host=example.com",
        ):
            with self.subTest(url=url):
                self.assertFalse(config.allows_database(urlparse(url)))

    def test_release_gate_defaults_are_unchanged(self):
        config = FixtureConfig()
        self.assertEqual(
            (
                config.database_port,
                config.api_port,
                config.identity_port,
                config.provider_port,
            ),
            (6543, 8002, 8999, 9009),
        )
        self.assertEqual(config.origins, ["http://127.0.0.1:8082"])
        for host in ("postgres", "127.0.0.1:6543"):
            self.assertTrue(
                config.allows_database(
                    urlparse(
                        f"postgresql://postgres:disposable-guided-only@{host}/roadtrips"
                    )
                )
            )
        self.assertFalse(
            config.allows_database(
                urlparse(
                    "postgresql://postgres:disposable-guided-only@127.0.0.1:6544/roadtrips"
                )
            )
        )
