from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    completed = Column(Boolean, default=False)
    priority = Column(String(20), default="medium")
    due_date = Column(Date, nullable=True)
    due_time = Column(String(10), nullable=True)
    start_time = Column(String(10), nullable=True)
    end_time = Column(String(10), nullable=True)
    category = Column(String(100), default="General")
    color = Column(String(20), default="")
    url = Column(String(1000), default="")
    video_url = Column(String(1000), default="")
    group_id = Column(String(36), nullable=True)
    recurrence_rule = Column(Text, nullable=True)
    rrule_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, default="")
    start_date = Column(Date, nullable=False)
    start_time = Column(String(10), default="09:00")
    end_date = Column(Date, nullable=True)
    end_time = Column(String(10), default="10:00")
    all_day = Column(Boolean, default=False)
    location = Column(String(300), default="")
    color = Column(String(20), default="#4772fa")
    category = Column(String(100), default="General")
    url = Column(String(1000), default="")
    video_url = Column(String(1000), default="")
    group_id = Column(String(36), nullable=True)
    recurrence_rule = Column(Text, nullable=True)
    rrule_until = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Bookmark(Base):
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)
    description = Column(Text, default="")
    url = Column(String(1000), default="")
    video_url = Column(String(1000), default="")
    color = Column(String(20), default="#4772fa")
    icon = Column(String(50), default="🔗")
    category = Column(String(100), default="General")
    order_index = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True)
    value = Column(Text, default="")


class TaskOccurrence(Base):
    __tablename__ = "task_occurrences"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, nullable=False, index=True)
    occurrence_date = Column(Date, nullable=False, index=True)
    completed = Column(Boolean, default=False)
    cancelled = Column(Boolean, default=False)
    override_title = Column(String(500), nullable=True)
    override_description = Column(Text, nullable=True)
    override_start_time = Column(String(10), nullable=True)
    override_end_time = Column(String(10), nullable=True)
    override_color = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
