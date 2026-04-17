from __future__ import annotations

from datetime import datetime

from .base import BaseModel, mapped


class ResumeModel(BaseModel):
    id: str
    title: str
    url: str | None = None
    alternate_url: str | None = None
    status_id: str | None = mapped(path="status.id", default=None)
    status_name: str | None = mapped(path="status.name", default=None)
    can_publish_or_update: bool = False
    total_views: int = mapped(path="counters.total_views", default=0)
    new_views: int = mapped(path="counters.new_views", default=0)
    created_at: datetime | None = None
    updated_at: datetime | None = None
