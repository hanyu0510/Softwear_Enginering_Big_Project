import re
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]
Nickname = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30)]


def normalize_email(value):
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", value):
        raise ValueError("邮箱格式不正确")
    local, domain = value.rsplit('@',1)
    if len(local)>64 or local.startswith('.') or local.endswith('.') or '..' in local or any(len(label)>63 for label in domain.split('.')):
        raise ValueError("邮箱格式不正确")
    return value


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterBody(StrictBody):
    email: str
    password: Password
    nickname: Nickname
    _email = field_validator("email")(normalize_email)


class LoginBody(StrictBody):
    email: str
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    _email = field_validator("email")(normalize_email)


class ForgotBody(StrictBody):
    email: str
    newPassword: Password
    _email = field_validator("email")(normalize_email)


class ChangePasswordBody(StrictBody):
    oldPassword: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    newPassword: Password


class ProfilePatch(StrictBody):
    nickname: Nickname | None = None
    email: str | None = None
    avatarFileId: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, value):
        return normalize_email(value) if value is not None else None


class PreferencesBody(StrictBody):
    styles: list[str] = Field(max_length=7)
    avoid_colors: list[str] = Field(max_length=30)
    notes: str = Field(max_length=500)
