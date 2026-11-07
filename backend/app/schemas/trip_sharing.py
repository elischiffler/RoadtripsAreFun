"""Read-only sharing inputs. A chosen display label never grants authorization."""

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ShareLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class ShareTokenInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr


class ConnectTripInput(ShareTokenInput):
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_label(cls, value):
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Choose a display name")
        return value
