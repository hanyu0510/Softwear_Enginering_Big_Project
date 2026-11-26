"""只声明跨模块交接，不建立社区表/文件表，不伪造帖子或头像记录。"""
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import ApiError


class CommunityGateway(Protocol):
    def list_posts(self, conn, *, user_id: str, kind: str, page: int, page_size: int) -> dict:
        """kind=posts/likes/favorites；返回 {list,total,page,pageSize}，收藏仅帖子。"""
        ...


class UploadsGateway(Protocol):
    def resolve_avatar(self, conn, *, user_id: str, file_id: str) -> str:
        """校验文件存在、归属、图片类型及头像公开用途，返回可展示的 URL。"""
        ...


class CommunityNotConnected:
    def list_posts(self, conn, **kwargs):
        raise ApiError(50001, "社区帖子查询尚未接入，请与社区负责人连接查询适配器", 503)


class UploadsNotConnected:
    def resolve_avatar(self, conn, **kwargs):
        raise ApiError(50001, "头像文件查询尚未接入，请与上传负责人连接文件适配器", 503)


@dataclass
class Integrations:
    community: CommunityGateway = None
    uploads: UploadsGateway = None

    def __post_init__(self):
        if self.community is None:
            self.community = CommunityNotConnected()
        if self.uploads is None:
            self.uploads = UploadsNotConnected()
