"""Fixed local-only ports for the optional native development preview."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FixtureConfig:
    native: bool = False

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
