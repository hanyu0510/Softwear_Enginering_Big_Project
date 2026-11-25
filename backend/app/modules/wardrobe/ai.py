from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import ApiError


@dataclass(frozen=True)
class Recognition:
    category: str | None
    color: str | None
    warmth: int | None
    material: str | None
    pattern: str | None
    season: list[str]
    style: list[str]
    occasion: list[str]
    confidence: float
    low_confidence_fields: list[str]


class DisabledRecognizer:
    def recognize(self, _image_path: str) -> Recognition:
        raise ApiError(50002, "AI 服务未配置，可改用手动添加", 503)


class DevelopmentMockRecognizer:
    """只验证接口和确认流程，不声称真正识别了图片。"""

    def recognize(self, _image_path: str) -> Recognition:
        return Recognition(
            category="other",
            color=None,
            warmth=None,
            material=None,
            pattern=None,
            season=[],
            style=[],
            occasion=[],
            confidence=0.2,
            low_confidence_fields=[
                "category",
                "color",
                "warmth",
                "material",
                "pattern",
                "season",
                "style",
                "occasion",
            ],
        )


def get_recognizer(settings: Settings):
    provider = settings.wardrobe_ai_provider.lower()
    if provider == "mock" and settings.is_development:
        return DevelopmentMockRecognizer()
    return DisabledRecognizer()
