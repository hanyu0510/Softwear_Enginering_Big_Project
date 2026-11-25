from dataclasses import dataclass
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    database_path: Path = ROOT / "data" / "account.db"
    allowed_origins: tuple[str, ...] = ("http://127.0.0.1:5173", "http://localhost:5173")
    cookie_secure: bool = False
    access_seconds: int = 7200
    refresh_seconds: int = 7 * 86400
    rate_limit_enabled: bool = True
    enable_test_page: bool = True
    color_names: tuple[str, ...] = ()  # 等衣橱/推荐共同提供白名单，账号模块不自造。

    @classmethod
    def from_env(cls):
        return cls(
            database_path=Path(os.getenv("ACCOUNT_DATABASE_PATH", str(ROOT / "data" / "account.db"))).expanduser().resolve(),
            allowed_origins=tuple(value.strip() for value in os.getenv(
                "ACCOUNT_ALLOWED_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(",") if value.strip()),
            cookie_secure=os.getenv("ACCOUNT_COOKIE_SECURE", "false").lower() == "true",
            enable_test_page=os.getenv("ACCOUNT_TEST_PAGE", "true").lower() == "true",
            color_names=tuple(value.strip() for value in os.getenv("ACCOUNT_COLOR_NAMES", "").split(",") if value.strip()),
        )
