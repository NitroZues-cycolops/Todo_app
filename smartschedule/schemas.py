from pydantic import BaseModel, field_validator, model_validator
from typing import List, Optional, Generic, TypeVar
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
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = "General"
    color: Optional[str] = ""
    url: Optional[str] = ""
    video_url: Optional[str] = ""
    group_id: Optional[str] = None
    recurrence_rule: Optional[str] = None
    rrule_until: Optional[date] = None

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = (value or '').strip()
        if not value:
            raise ValueError('title is required')
        return value


class TaskCreate(TaskBase):
    @model_validator(mode='after')
    def validate_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        if self.recurrence_rule and not self.due_date:
            raise ValueError('A repeating task needs a due date')
        return self


class TaskBulkCreate(TaskBase):
    dates: List[date]

    @field_validator('dates')
    @classmethod
    def dates_required_unique(cls, value: List[date]) -> List[date]:
        dates = sorted(set(value))
        if not dates:
            raise ValueError('at least one date is required')
        return dates

    @model_validator(mode='after')
    def validate_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        return self


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    due_time: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    category: Optional[str] = None
    color: Optional[str] = None
    url: Optional[str] = None
    video_url: Optional[str] = None
    group_id: Optional[str] = None
    recurrence_rule: Optional[str] = None
    rrule_until: Optional[date] = None

    @model_validator(mode='after')
    def validate_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        return self


class TaskOccurrenceUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    color: Optional[str] = None
    completed: Optional[bool] = None

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError('title is required')
        return value

    @model_validator(mode='after')
    def validate_times(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValueError('end_time must be after start_time')
        return self


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
    group_id: Optional[str] = None
    recurrence_rule: Optional[str] = None
    rrule_until: Optional[date] = None

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = (value or '').strip()
        if not value:
            raise ValueError('title is required')
        return value

    @model_validator(mode='after')
    def validate_dates_times(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError('end_date must be on or after start_date')
        same_day = self.end_date is None or self.end_date == self.start_date
        if same_day and not self.all_day and self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError('end_time must be after start_time')
        return self


class EventCreate(EventBase):
    pass


class EventBulkCreate(BaseModel):
    dates: List[date]
    title: str
    description: Optional[str] = ""
    start_time: Optional[str] = "09:00"
    end_time: Optional[str] = "10:00"
    all_day: Optional[bool] = False
    location: Optional[str] = ""
    color: Optional[str] = "#4772fa"
    category: Optional[str] = "General"
    url: Optional[str] = ""
    video_url: Optional[str] = ""
    recurrence_rule: Optional[str] = None
    rrule_until: Optional[date] = None

    @field_validator('title')
    @classmethod
    def title_not_blank(cls, value: str) -> str:
        value = (value or '').strip()
        if not value:
            raise ValueError('title is required')
        return value

    @field_validator('dates')
    @classmethod
    def dates_required_unique(cls, value: List[date]) -> List[date]:
        dates = sorted(set(value))
        if not dates:
            raise ValueError('at least one date is required')
        return dates

    @model_validator(mode='after')
    def validate_times(self):
        if not self.all_day and self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError('end_time must be after start_time')
        return self


class EventBatchItem(EventBase):
    end_time: Optional[str] = None
    duration_minutes: Optional[int] = None

    @model_validator(mode='after')
    def validate_duration(self):
        if self.duration_minutes is not None and self.duration_minutes <= 0:
            raise ValueError('duration_minutes must be greater than 0')
        return self


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
    group_id: Optional[str] = None
    recurrence_rule: Optional[str] = None
    rrule_until: Optional[date] = None


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
