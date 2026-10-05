from pydantic import BaseModel
from typing import Optional, Generic, TypeVar
from datetime import date, datetime


T = TypeVar("T")


class Timestamped(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskBase(BaseModel):
    title: str
    description: Optional[str] = ""
    completed: Optional[bool] = False
    priority: Optional[str] = "medium"
    due_date: Optional[date] = None
    due_time: Optional[str] = None
    category: Optional[str] = "General"
    color: Optional[str] = ""
    url: Optional[str] = ""
    video_url: Optional[str] = ""


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    due_time: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    url: Optional[str] = None
    video_url: Optional[str] = None


class Task(TaskBase, Timestamped):
    pass


class EventBase(BaseModel):
    title: str
    description: Optional[str] = ""
    start_date: date
    start_time: Optional[str] = "09:00"
    end_date: Optional[date] = None
    end_time: Optional[str] = "10:00"
    all_day: Optional[bool] = False
    location: Optional[str] = ""
    color: Optional[str] = "#4772fa"
    category: Optional[str] = "General"
    url: Optional[str] = ""
    video_url: Optional[str] = ""


class EventCreate(EventBase):
    pass


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[date] = None
    start_time: Optional[str] = None
    end_date: Optional[date] = None
    end_time: Optional[str] = None
    all_day: Optional[bool] = None
    location: Optional[str] = None
    color: Optional[str] = None
    category: Optional[str] = None
    url: Optional[str] = None
    video_url: Optional[str] = None


class Event(EventBase, Timestamped):
    pass


class BookmarkBase(BaseModel):
    title: str
    description: Optional[str] = ""
    url: Optional[str] = ""
    video_url: Optional[str] = ""
    color: Optional[str] = "#4772fa"
    icon: Optional[str] = "🔗"
    category: Optional[str] = "General"
    order_index: Optional[int] = 0


class BookmarkCreate(BookmarkBase):
    pass


class BookmarkUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    video_url: Optional[str] = None
    color: Optional[str] = None
    icon: Optional[str] = None
    category: Optional[str] = None
    order_index: Optional[int] = None


class Bookmark(BookmarkBase, Timestamped):
    pass


class SyncResponse(BaseModel):
    message: str
    tasks_synced: int = 0
    events_synced: int = 0
