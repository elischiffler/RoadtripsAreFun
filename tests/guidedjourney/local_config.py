"""Fixed local-only ports for the optional native development preview."""

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

OWNER_MARKER = "roadtrips-native-preview-v1\n"


def _private_path(path, *, directory=False):
    info = path.lstat()
    if (
        stat.S_ISLNK(info.st_mode)
        or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise RuntimeError("Refusing unsafe native fixture state")


def _native_signing_key(state):
    """Only called with the fixed checkout-local state; no environment path input."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    parent = state.parent.lstat()
    if (
        not stat.S_ISDIR(parent.st_mode)
        or parent.st_uid != os.getuid()
        or parent.st_mode & 0o022
    ):
        raise RuntimeError("Refusing unsafe native fixture state")
    _private_path(state, directory=True)
    _private_path(state / "db", directory=True)
    owner = state / "preview-owner"
    _private_path(owner)
    if owner.stat().st_size != len(OWNER_MARKER) or owner.read_text() != OWNER_MARKER:
        raise RuntimeError("Refusing unowned native fixture state")
    destination = state / "signing-key.pem"
    if not destination.exists() and not destination.is_symlink():
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        encoded = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                dir=state, prefix=".signing-key-", delete=False
            ) as file:
                temporary = Path(file.name)
                file.write(encoded)
                file.flush()
                os.fsync(file.fileno())
            try:
                os.link(temporary, destination, follow_symlinks=False)
            except FileExistsError:
                pass  # Another explicit fixture start published its complete key.
        finally:
            if temporary:
                temporary.unlink()
    _private_path(destination)
    if destination.stat().st_size > 16384:
        raise RuntimeError("Refusing invalid native fixture signing key")
    try:
        # Never follow a key symlink, including one swapped after lstat.
        descriptor = os.open(destination, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as file:
            key = serialization.load_pem_private_key(file.read(16385), password=None)
        if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != 2048:
            raise ValueError("Unexpected key type")
    except (ValueError, TypeError, OSError):
        raise RuntimeError("Refusing invalid native fixture signing key") from None
    return key


@dataclass(frozen=True)
class FixtureConfig:
    native: bool = False

    def apply_origins(self):
        # CORS is fixed for BOTH fixture modes, regardless of ambient settings.
        os.environ["CORS_ORIGINS"] = ",".join(self.origins)

    def signing_key(self):
        if self.native:
            state = (
                Path(__file__).resolve().parents[2] / ".artifacts" / "native-preview"
            )
            return _native_signing_key(state)
        from cryptography.hazmat.primitives.asymmetric import rsa

        return rsa.generate_private_key(public_exponent=65537, key_size=2048)

    @property
    def database_port(self):
        return 6544 if self.native else 6543

    @property
    def api_port(self):
        return 8003 if self.native else 8002

    @property
    def identity_port(self):
        return 8998 if self.native else 8999

    @property
    def provider_port(self):
        return 9010 if self.native else 9009

    @property
    def bind_host(self):
        return "127.0.0.1" if self.native else "0.0.0.0"

    @property
    def origins(self):
        return (
            ["http://localhost:5173", "http://127.0.0.1:5173"]
            if self.native
            else ["http://127.0.0.1:8082"]
        )

    def allows_database(self, target):
        return (
            target.hostname
            in (
                {"127.0.0.1", "localhost"}
                if self.native
                else {"postgres", "127.0.0.1", "localhost"}
            )
            and target.path == "/roadtrips"
            and target.username == "postgres"
            and target.password == "disposable-guided-only"
            and target.scheme == "postgresql"
            and not target.query
            and not target.fragment
            and target.port
            in ({None, 5432} if target.hostname == "postgres" else {self.database_port})
        )
