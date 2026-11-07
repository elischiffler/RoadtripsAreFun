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


class NativeSigningStateTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path

        from local_config import OWNER_MARKER

        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name) / ".artifacts"
        self.parent.mkdir(mode=0o700)
        self.state = self.parent / "native-preview"
        self.state.mkdir(mode=0o700)
        (self.state / "db").mkdir(mode=0o700)
        (self.state / "preview-owner").write_text(OWNER_MARKER)
        (self.state / "preview-owner").chmod(0o600)

    def test_native_key_reuses_signed_session_after_reload(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        from local_config import _native_signing_key

        first = _native_signing_key(self.state)
        signature = first.sign(
            b"synthetic session only", padding.PKCS1v15(), hashes.SHA256()
        )
        reloaded = _native_signing_key(self.state)
        reloaded.public_key().verify(
            signature, b"synthetic session only", padding.PKCS1v15(), hashes.SHA256()
        )
        self.assertEqual(
            first.public_key().public_numbers(), reloaded.public_key().public_numbers()
        )
        self.assertEqual((self.state / "signing-key.pem").stat().st_mode & 0o777, 0o600)

    def test_default_key_is_ephemeral_and_never_uses_native_state(self):
        from unittest.mock import patch

        with patch(
            "local_config._native_signing_key", side_effect=AssertionError("not native")
        ):
            first = FixtureConfig().signing_key()
            second = FixtureConfig().signing_key()
        self.assertNotEqual(
            first.public_key().public_numbers(), second.public_key().public_numbers()
        )

    def test_native_state_has_no_environment_path_override(self):
        import os
        from pathlib import Path
        from unittest.mock import patch

        checkout = Path(self.temporary.name)
        module = checkout / "tests" / "guidedjourney" / "local_config.py"
        for path in (
            module,
            checkout / "scripts" / "dev-offline.mjs",
            checkout / "backend" / "app" / "main.py",
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# owned fake full checkout for locator test\n")
        with (
            patch("local_config.__file__", str(module)),
            patch.dict(
                os.environ, {"GUIDED_JOURNEY_NATIVE_STATE": "/outside/not-a-preview"}
            ),
            patch("local_config._native_signing_key") as load,
        ):
            FixtureConfig(True).signing_key()
        load.assert_called_once_with(self.state)

    def test_shallow_mount_rejects_native_before_state_access_but_default_stays_ephemeral(
        self,
    ):
        from unittest.mock import patch

        with (
            patch("local_config.__file__", "/journey/local_config.py"),
            patch("local_config._native_signing_key") as load,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "requires a complete local checkout"
            ):
                FixtureConfig(True).signing_key()
            first = FixtureConfig().signing_key()
            second = FixtureConfig().signing_key()
        load.assert_not_called()
        self.assertNotEqual(
            first.public_key().public_numbers(), second.public_key().public_numbers()
        )

    def test_incomplete_checkout_rejects_native_without_fallback(self):
        from pathlib import Path
        from unittest.mock import patch

        module = (
            Path(self.temporary.name) / "tests" / "guidedjourney" / "local_config.py"
        )
        module.parent.mkdir(parents=True)
        module.write_text("# incomplete test fixture only\n")
        with (
            patch("local_config.__file__", str(module)),
            patch("local_config._native_signing_key") as load,
            self.assertRaisesRegex(RuntimeError, "requires a complete local checkout"),
        ):
            FixtureConfig(True).signing_key()
        load.assert_not_called()

    def test_hostile_ambient_origins_are_replaced_in_both_modes(self):
        import os
        from unittest.mock import patch

        for native in (False, True):
            with (
                self.subTest(native=native),
                patch.dict(os.environ, {"CORS_ORIGINS": "https://not-local.invalid"}),
            ):
                config = FixtureConfig(native)
                config.apply_origins()
                self.assertEqual(os.environ["CORS_ORIGINS"], ",".join(config.origins))

    def test_symlinked_state_is_rejected(self):
        from local_config import _native_signing_key

        real = self.parent / "real-state"
        self.state.rename(real)
        self.state.symlink_to(real, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)
        self.assertFalse((real / "signing-key.pem").exists())

    def test_symlinked_parent_is_rejected(self):
        from local_config import _native_signing_key

        real = self.parent.with_name("real-artifacts")
        self.parent.rename(real)
        self.parent.symlink_to(real, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)

    def test_writable_parent_is_rejected_but_0755_parent_is_allowed(self):
        from local_config import _native_signing_key

        self.parent.chmod(0o777)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)
        self.parent.chmod(0o755)
        self.assertIsNotNone(_native_signing_key(self.state))

    def test_symlinked_data_is_rejected(self):
        from local_config import _native_signing_key

        real = self.parent / "other-db"
        (self.state / "db").rename(real)
        (self.state / "db").symlink_to(real, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)

    def test_symlinked_key_does_not_read_or_overwrite_target(self):
        from local_config import _native_signing_key

        target = self.parent / "unrelated"
        target.write_text("must remain untouched")
        target.chmod(0o600)
        (self.state / "signing-key.pem").symlink_to(target)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)
        self.assertEqual(target.read_text(), "must remain untouched")

    def test_unowned_or_public_state_is_rejected(self):
        import os
        from unittest.mock import patch

        from local_config import _native_signing_key

        with (
            patch("local_config.os.getuid", return_value=os.getuid() + 1),
            self.assertRaises(RuntimeError),
        ):
            _native_signing_key(self.state)
        self.state.chmod(0o755)
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)

    def test_wrong_marker_and_invalid_key_fail_without_regeneration(self):
        from local_config import OWNER_MARKER, _native_signing_key

        owner = self.state / "preview-owner"
        owner.write_text("unowned")
        with self.assertRaises(RuntimeError):
            _native_signing_key(self.state)
        owner.write_text(OWNER_MARKER)
        key = self.state / "signing-key.pem"
        key.write_text("invalid synthetic key")
        key.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError, "invalid native fixture signing key"):
            _native_signing_key(self.state)
        self.assertEqual(key.read_text(), "invalid synthetic key")
