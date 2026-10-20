import os
from datetime import date, timedelta
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from . import models, schemas
from .database import engine, get_db
from .google_sheets import (
    is_google_sheets_configured,
    sync_tasks_to_sheets,
    sync_events_to_sheets,
)
from .ai_planner import get_ai_planner, GroqAIError
from .file_parser import parse_file, FileParseError

load_dotenv()

models.Base.metadata.create_all(bind=engine)

# Auto-migration: ensure new columns exist on existing tables
def _auto_migrate():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(engine)
        with engine.begin() as conn:
            # TASKS: color, url, video_url, group_id, recurrence_rule, rrule_until, start_time, end_time
            existing_tasks = {c['name'] for c in insp.get_columns('tasks')}
            for col, sql in [
                ('color', 'ALTER TABLE tasks ADD COLUMN color VARCHAR(20) DEFAULT ""'),
                ('url', 'ALTER TABLE tasks ADD COLUMN url VARCHAR(1000) DEFAULT ""'),
                ('video_url', 'ALTER TABLE tasks ADD COLUMN video_url VARCHAR(1000) DEFAULT ""'),
                ('group_id', 'ALTER TABLE tasks ADD COLUMN group_id VARCHAR(36) DEFAULT NULL'),
                ('recurrence_rule', 'ALTER TABLE tasks ADD COLUMN recurrence_rule TEXT DEFAULT NULL'),
                ('rrule_until', 'ALTER TABLE tasks ADD COLUMN rrule_until DATE DEFAULT NULL'),
                ('start_time', 'ALTER TABLE tasks ADD COLUMN start_time VARCHAR(10) DEFAULT NULL'),
                ('end_time', 'ALTER TABLE tasks ADD COLUMN end_time VARCHAR(10) DEFAULT NULL'),
            ]:
                if col not in existing_tasks:
                    try: conn.execute(text(sql))
                    except Exception: pass

            # EVENTS: url, video_url, group_id, recurrence_rule, rrule_until
            existing_events = {c['name'] for c in insp.get_columns('events')}
            for col, sql in [
                ('url', 'ALTER TABLE events ADD COLUMN url VARCHAR(1000) DEFAULT ""'),
                ('video_url', 'ALTER TABLE events ADD COLUMN video_url VARCHAR(1000) DEFAULT ""'),
                ('group_id', 'ALTER TABLE events ADD COLUMN group_id VARCHAR(36) DEFAULT NULL'),
                ('recurrence_rule', 'ALTER TABLE events ADD COLUMN recurrence_rule TEXT DEFAULT NULL'),
                ('rrule_until', 'ALTER TABLE events ADD COLUMN rrule_until DATE DEFAULT NULL'),
            ]:
                if col not in existing_events:
                    try: conn.execute(text(sql))
                    except Exception: pass

            # TASK_OCCURRENCES: new table for tracking per-date completion
            existing_tables = insp.get_table_names()
            if 'task_occurrences' not in existing_tables:
                try:
                    conn.execute(text('''
                        CREATE TABLE task_occurrences (
                            id INTEGER PRIMARY KEY,
                            task_id INTEGER NOT NULL,
                            occurrence_date DATE NOT NULL,
                            completed BOOLEAN DEFAULT 0,
                            cancelled BOOLEAN DEFAULT 0,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                    '''))
                except Exception: pass
    except Exception:
        pass  # ignore migration errors (e.g. tables don't exist yet)

_auto_migrate()


# ============================================================
# Recurrence Expansion Helper
# ============================================================
def parse_rrule(rrule_str: str, start_date: date, end_date: date) -> List[date]:
    """Parse RRULE string and return list of dates in range [start_date, end_date].

    Supported formats:
    - FREQ=DAILY → every day
    - FREQ=DAILY;UNTIL=YYYY-MM-DD → every day until date
    - FREQ=WEEKLY;BYDAY=MO,WE,FR → specific weekdays every week
    - FREQ=WEEKLY → same weekday every week
    - FREQ=ALWAYS → pinned (always visible, returns all dates in range)
    """
    if not rrule_str:
        return []

    occurrences = []
    current = start_date

    # Parse rule components
    parts = {}
    for part in rrule_str.split(';'):
        if '=' in part:
            key, val = part.split('=', 1)
            parts[key.strip()] = val.strip()

    freq = parts.get('FREQ', 'DAILY')
    until = parts.get('UNTIL')
    byday = parts.get('BYDAY', '')

    # Parse until date if present
    until_date = end_date
    if until:
        try:
            until_date = date.fromisoformat(until)
            until_date = min(until_date, end_date)
        except:
            until_date = end_date

    # Weekday name to number mapping (Monday=0, Sunday=6)
    weekday_map = {'MO': 0, 'TU': 1, 'WE': 2, 'TH': 3, 'FR': 4, 'SA': 5, 'SU': 6}

    if freq == 'ALWAYS':
        # Pinned: return all dates in range
        current = start_date
        while current <= until_date:
            if current >= start_date:
                occurrences.append(current)
            current += timedelta(days=1)

    elif freq == 'DAILY':
        # Every day from start_date to until_date
        current = start_date
        while current <= until_date:
            occurrences.append(current)
            current += timedelta(days=1)

    elif freq == 'WEEKLY':
        if byday:
            # Specific weekdays every week
            target_days = {weekday_map.get(day.strip()): day.strip() for day in byday.split(',')}
            current = start_date
            while current <= until_date:
                if current.weekday() in target_days:
                    occurrences.append(current)
                current += timedelta(days=1)
        else:
            # Same weekday every week
            start_weekday = start_date.weekday()
            current = start_date
            while current <= until_date:
                if current.weekday() == start_weekday:
                    occurrences.append(current)
                current += timedelta(days=1)

    return occurrences


app = FastAPI(
    title="SmartSchedule",
    description="SmartSchedule: Personal task manager, calendar scheduler, and hyper tile dashboard",
    version="1.0.0",
)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# ============================================================
# Pages
# ============================================================
@app.get("/", response_class=HTMLResponse)
async def home_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ============================================================
# Tasks API
# ============================================================
@app.post("/api/tasks", response_model=schemas.Task)
def create_task(task: schemas.TaskCreate, db: Session = Depends(get_db)):
    task_dict = task.dict()
    # Mirror start_time to due_time for backward compat (Sheets, reminders, Dashboard)
    if task_dict.get('start_time'):
        task_dict['due_time'] = task_dict['start_time']
    db_task = models.Task(**task_dict)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.get("/api/tasks", response_model=List[schemas.Task])
def list_tasks(
    completed: Optional[bool] = None,
    category: Optional[str] = None,
    due_from: Optional[date] = None,
    due_to: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Task)
    if completed is not None:
        query = query.filter(models.Task.completed == completed)
    if category:
        query = query.filter(models.Task.category == category)
    if due_from:
        query = query.filter(models.Task.due_date >= due_from)
    if due_to:
        query = query.filter(models.Task.due_date <= due_to)
    return query.order_by(models.Task.due_date.asc().nullslast(), models.Task.id.desc()).all()


# Recurrence expansion endpoint (GET with query params to match API pattern)
@app.get("/api/tasks/recurrence-expand")
def expand_task_recurrence(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    """Expand all recurring tasks to their occurrences in the given date range.

    Returns list of {task_id, occurrence_date, completed, cancelled} objects.
    """
    # Get all tasks with recurrence rules
    recurring_tasks = db.query(models.Task).filter(models.Task.recurrence_rule.isnot(None)).all()

    occurrences = []
    for task in recurring_tasks:
        # Get dates this task occurs on
        dates = parse_rrule(task.recurrence_rule, start, end)

        for occ_date in dates:
            # Check if there's an override/exception in task_occurrences
            existing = db.query(models.TaskOccurrence).filter(
                models.TaskOccurrence.task_id == task.id,
                models.TaskOccurrence.occurrence_date == occ_date,
            ).first()

            if existing:
                # Use override from task_occurrences
                occurrences.append({
                    'task_id': task.id,
                    'occurrence_date': occ_date.isoformat(),
                    'completed': existing.completed,
                    'cancelled': existing.cancelled,
                })
            else:
                # Use base task completed status
                occurrences.append({
                    'task_id': task.id,
                    'occurrence_date': occ_date.isoformat(),
                    'completed': task.completed,
                    'cancelled': False,
                })

    return occurrences


@app.get("/api/tasks/range")
def get_tasks_in_range(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    """Get all tasks (including expanded recurring) in date range with their times.

    Returns task objects with expanded occurrences for calendar rendering.
    Non-recurring tasks appear once on their due_date.
    Recurring tasks are expanded to all occurrences in range.
    """
    result = []

    # Get non-recurring tasks in range
    non_recurring = db.query(models.Task).filter(
        models.Task.recurrence_rule.is_(None),
        models.Task.due_date >= start,
        models.Task.due_date <= end,
    ).all()

    for task in non_recurring:
        result.append({
            'id': task.id,
            'title': task.title,
            'description': task.description,
            'due_date': task.due_date.isoformat() if task.due_date else None,
            'start_time': task.start_time,
            'end_time': task.end_time,
            'priority': task.priority,
            'category': task.category,
            'color': task.color,
            'completed': task.completed,
            'url': task.url,
            'video_url': task.video_url,
            'recurrence_rule': task.recurrence_rule,
            'group_id': task.group_id,
            'type': 'task',
            'occurrence_date': task.due_date.isoformat() if task.due_date else None,
        })

    # Get recurring tasks and expand them
    recurring = db.query(models.Task).filter(
        models.Task.recurrence_rule.isnot(None),
    ).all()

    for task in recurring:
        # Get dates this task occurs on
        dates = parse_rrule(task.recurrence_rule, start, end)

        for occ_date in dates:
            # Check if there's an override/exception in task_occurrences
            occ = db.query(models.TaskOccurrence).filter(
                models.TaskOccurrence.task_id == task.id,
                models.TaskOccurrence.occurrence_date == occ_date,
            ).first()

            is_completed = occ.completed if occ else task.completed
            is_cancelled = occ.cancelled if occ else False

            if not is_cancelled:
                result.append({
                    'id': task.id,
                    'title': task.title,
                    'description': task.description,
                    'due_date': occ_date.isoformat(),
                    'start_time': task.start_time,
                    'end_time': task.end_time,
                    'priority': task.priority,
                    'category': task.category,
                    'color': task.color,
                    'completed': is_completed,
                    'url': task.url,
                    'video_url': task.video_url,
                    'recurrence_rule': task.recurrence_rule,
                    'group_id': task.group_id,
                    'type': 'task',
                    'occurrence_date': occ_date.isoformat(),
                })

    return result


@app.get("/api/tasks/{task_id}", response_model=schemas.Task)
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.put("/api/tasks/{task_id}", response_model=schemas.Task)
def update_task(task_id: int, task: schemas.TaskUpdate, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    update_data = task.dict(exclude_unset=True)

    # Validate time constraints on merged values (use start_time || due_time for start)
    merged_start = update_data.get('start_time', db_task.start_time or db_task.due_time)
    merged_end = update_data.get('end_time', db_task.end_time)
    if merged_start and merged_end and merged_end <= merged_start:
        raise HTTPException(status_code=422, detail="end_time must be after start_time")

    # Mirror start_time to due_time for backward compat (Sheets, reminders, Dashboard)
    if 'start_time' in update_data and update_data['start_time']:
        update_data['due_time'] = update_data['start_time']

    for key, value in update_data.items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.patch("/api/tasks/{task_id}/toggle", response_model=schemas.Task)
def toggle_task(task_id: int, occurrence_date: Optional[date] = None, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # If this is a recurring task and an occurrence_date is provided, track per-date completion
    if db_task.recurrence_rule and occurrence_date:
        # Find or create task_occurrence for this date
        occ = db.query(models.TaskOccurrence).filter(
            models.TaskOccurrence.task_id == task_id,
            models.TaskOccurrence.occurrence_date == occurrence_date,
        ).first()

        if occ:
            # Toggle the occurrence
            occ.completed = not occ.completed
            occ.cancelled = False
        else:
            # Create new occurrence (opposite of parent task's current state)
            occ = models.TaskOccurrence(
                task_id=task_id,
                occurrence_date=occurrence_date,
                completed=not db_task.completed,
                cancelled=False,
            )
            db.add(occ)
        db.commit()
    else:
        # Regular task or no occurrence_date: toggle the task itself
        db_task.completed = not db_task.completed
        db.commit()

    db.refresh(db_task)
    return db_task


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(db_task)
    db.commit()
    return {"ok": True}


@app.get("/api/tasks/categories")
def list_task_categories(db: Session = Depends(get_db)):
    cats = db.query(models.Task.category).distinct().all()
    return [c[0] for c in cats if c[0]]


# ============================================================
# Bulk Tasks API
# ============================================================
@app.post("/api/tasks/bulk", response_model=List[schemas.Task])
def create_tasks_bulk(tasks_list: List[schemas.TaskCreate], db: Session = Depends(get_db)):
    """Create multiple tasks from list of task objects (AI Planner format)."""
    created_tasks = []
    try:
        for task_data in tasks_list:
            task_dict = task_data.dict()
            # Mirror start_time to due_time for backward compat (Sheets, reminders, Dashboard)
            if task_dict.get('start_time'):
                task_dict['due_time'] = task_dict['start_time']
            t = models.Task(**task_dict)
            db.add(t)
            created_tasks.append(t)
        db.commit()
        for t in created_tasks:
            db.refresh(t)
        return created_tasks
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/tasks/group/{group_id}", response_model=dict)
def update_tasks_group(group_id: str, update_data: dict, db: Session = Depends(get_db)):
    """Bulk update all tasks in a group (title, priority, color, description only)."""
    tasks = db.query(models.Task).filter(models.Task.group_id == group_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found for this group")

    allowed_fields = {'title', 'description', 'priority', 'color', 'category', 'url', 'video_url'}
    data = {k: v for k, v in update_data.items() if k in allowed_fields}

    try:
        for t in tasks:
            for key, value in data.items():
                setattr(t, key, value)
        db.commit()
        return {'message': f'Updated {len(tasks)} tasks', 'count': len(tasks)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/tasks/group/{group_id}")
def delete_tasks_group(group_id: str, db: Session = Depends(get_db)):
    """Bulk delete all tasks in a group."""
    tasks = db.query(models.Task).filter(models.Task.group_id == group_id).all()
    if not tasks:
        raise HTTPException(status_code=404, detail="No tasks found for this group")

    try:
        for t in tasks:
            db.delete(t)
        db.commit()
        return {'message': f'Deleted {len(tasks)} tasks', 'count': len(tasks)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# Events API
# ============================================================
@app.post("/api/events", response_model=schemas.Event)
def create_event(event: schemas.EventCreate, db: Session = Depends(get_db)):
    if not event.end_date:
        event.end_date = event.start_date
    db_event = models.Event(**event.dict())
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.get("/api/events", response_model=List[schemas.Event])
def list_events(
    start: Optional[date] = None,
    end: Optional[date] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Event)
    if start:
        query = query.filter((models.Event.end_date >= start) | (models.Event.start_date >= start))
    if end:
        query = query.filter(models.Event.start_date <= end)
    if category:
        query = query.filter(models.Event.category == category)
    return query.order_by(models.Event.start_date.asc(), models.Event.start_time.asc()).all()


# Recurrence expansion endpoint (must come before /{event_id} route)
@app.get("/api/events/recurrence-expand")
def expand_event_recurrence(
    start: date = Query(...),
    end: date = Query(...),
    db: Session = Depends(get_db),
):
    """Expand all recurring events to their occurrences in the given date range.

    Returns list of {event_id, occurrence_date} objects.
    """
    # Get all events with recurrence rules
    recurring_events = db.query(models.Event).filter(models.Event.recurrence_rule.isnot(None)).all()

    occurrences = []
    for event in recurring_events:
        # Get dates this event occurs on
        dates = parse_rrule(event.recurrence_rule, start, end)

        for occ_date in dates:
            occurrences.append({
                'event_id': event.id,
                'occurrence_date': occ_date.isoformat(),
            })

    return occurrences


@app.get("/api/events/{event_id}", response_model=schemas.Event)
def get_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@app.put("/api/events/{event_id}", response_model=schemas.Event)
def update_event(event_id: int, event: schemas.EventUpdate, db: Session = Depends(get_db)):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    update_data = event.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_event, key, value)
    db.commit()
    db.refresh(db_event)
    return db_event


@app.delete("/api/events/{event_id}")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    db_event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    db.delete(db_event)
    db.commit()
    return {"ok": True}


@app.get("/api/events/categories")
def list_event_categories(db: Session = Depends(get_db)):
    cats = db.query(models.Event.category).distinct().all()
    return [c[0] for c in cats if c[0]]


# ============================================================
# Bulk Events API
# ============================================================
@app.post("/api/events/bulk", response_model=List[schemas.Event])
def create_events_bulk(events_list: List[dict], db: Session = Depends(get_db)):
    """Create multiple events from list of event objects (AI Planner format)."""
    created_events = []
    try:
        for event_dict in events_list:
            # Calculate end_time from duration_minutes if not provided
            end_time = event_dict.get('end_time')
            if not end_time and event_dict.get('start_time'):
                # Add duration_minutes (default 60) to start_time
                start_h, start_m = map(int, event_dict['start_time'].split(':'))
                duration = event_dict.get('duration_minutes', 60)
                end_mins = start_h * 60 + start_m + duration
                end_h = (end_mins // 60) % 24
                end_m = end_mins % 60
                end_time = f"{end_h:02d}:{end_m:02d}"

            # Build event data, excluding duration_minutes (not a model field)
            event_dict_clean = {k: v for k, v in event_dict.items() if k != 'duration_minutes'}
            event_dict_clean['end_time'] = end_time or "10:00"

            # Create Event object
            event_data = schemas.EventCreate(**event_dict_clean)
            e = models.Event(**event_data.dict())
            db.add(e)
            created_events.append(e)
        db.commit()
        for e in created_events:
            db.refresh(e)
        return created_events
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/api/events/group/{group_id}", response_model=dict)
def update_events_group(group_id: str, update_data: dict, db: Session = Depends(get_db)):
    """Bulk update all events in a group (title, time, color, description only)."""
    events = db.query(models.Event).filter(models.Event.group_id == group_id).all()
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this group")

    allowed_fields = {'title', 'description', 'start_time', 'end_time', 'all_day', 'color', 'category', 'url', 'video_url', 'location'}
    data = {k: v for k, v in update_data.items() if k in allowed_fields}

    try:
        for ev in events:
            for key, value in data.items():
                setattr(ev, key, value)
        db.commit()
        return {'message': f'Updated {len(events)} events', 'count': len(events)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/events/group/{group_id}")
def delete_events_group(group_id: str, db: Session = Depends(get_db)):
    """Bulk delete all events in a group."""
    events = db.query(models.Event).filter(models.Event.group_id == group_id).all()
    if not events:
        raise HTTPException(status_code=404, detail="No events found for this group")

    try:
        for ev in events:
            db.delete(ev)
        db.commit()
        return {'message': f'Deleted {len(events)} events', 'count': len(events)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================
# Bookmarks / Tiles API
# ============================================================
@app.post("/api/bookmarks", response_model=schemas.Bookmark)
def create_bookmark(bm: schemas.BookmarkCreate, db: Session = Depends(get_db)):
    db_bm = models.Bookmark(**bm.dict())
    db.add(db_bm)
    db.commit()
    db.refresh(db_bm)
    return db_bm


@app.get("/api/bookmarks", response_model=List[schemas.Bookmark])
def list_bookmarks(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Bookmark)
    if category:
        query = query.filter(models.Bookmark.category == category)
    return query.order_by(models.Bookmark.order_index.asc(), models.Bookmark.id.asc()).all()


@app.get("/api/bookmarks/{bm_id}", response_model=schemas.Bookmark)
def get_bookmark(bm_id: int, db: Session = Depends(get_db)):
    bm = db.query(models.Bookmark).filter(models.Bookmark.id == bm_id).first()
    if not bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return bm


@app.put("/api/bookmarks/{bm_id}", response_model=schemas.Bookmark)
def update_bookmark(bm_id: int, bm: schemas.BookmarkUpdate, db: Session = Depends(get_db)):
    db_bm = db.query(models.Bookmark).filter(models.Bookmark.id == bm_id).first()
    if not db_bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    update_data = bm.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_bm, key, value)
    db.commit()
    db.refresh(db_bm)
    return db_bm


@app.delete("/api/bookmarks/{bm_id}")
def delete_bookmark(bm_id: int, db: Session = Depends(get_db)):
    db_bm = db.query(models.Bookmark).filter(models.Bookmark.id == bm_id).first()
    if not db_bm:
        raise HTTPException(status_code=404, detail="Bookmark not found")
    db.delete(db_bm)
    db.commit()
    return {"ok": True}


@app.get("/api/bookmarks/categories")
def list_bookmark_categories(db: Session = Depends(get_db)):
    cats = db.query(models.Bookmark.category).distinct().all()
    return [c[0] for c in cats if c[0]]


# ============================================================
# Dashboard / Overview
# ============================================================
@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    today = date.today()
    week_end = today + timedelta(days=7)

    total_tasks = db.query(models.Task).count()
    completed_tasks = db.query(models.Task).filter(models.Task.completed == True).count()
    pending_tasks = total_tasks - completed_tasks
    today_tasks = db.query(models.Task).filter(models.Task.due_date == today).all()
    week_tasks = db.query(models.Task).filter(
        models.Task.due_date >= today, models.Task.due_date <= week_end
    ).all()

    today_events = db.query(models.Event).filter(
        (models.Event.start_date <= today) &
        ((models.Event.end_date >= today) | (models.Event.start_date == today))
    ).all()
    week_events = db.query(models.Event).filter(
        models.Event.start_date <= week_end,
        (models.Event.end_date >= today) | (models.Event.start_date >= today)
    ).all()

    bookmarks = db.query(models.Bookmark).order_by(models.Bookmark.order_index.asc()).all()

    return {
        "stats": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "today_tasks": len(today_tasks),
            "today_events": len(today_events),
            "week_events": len(week_events),
            "bookmarks": len(bookmarks),
        },
        "today_tasks": [schemas.Task.from_orm(t) for t in today_tasks],
        "today_events": [schemas.Event.from_orm(e) for e in today_events],
        "week_tasks": [schemas.Task.from_orm(t) for t in week_tasks],
        "week_events": [schemas.Event.from_orm(e) for e in week_events],
        "bookmarks": [schemas.Bookmark.from_orm(b) for b in bookmarks],
        "today": today.isoformat(),
    }


# ============================================================
# Google Sheets Sync
# ============================================================
@app.get("/api/sync/status")
def sync_status():
    return {
        "configured": is_google_sheets_configured(),
        "sheet_id": os.getenv("GOOGLE_SHEET_ID", ""),
        "tasks_tab": os.getenv("GOOGLE_SHEET_TASKS_TAB", "Tasks"),
        "events_tab": os.getenv("GOOGLE_SHEET_EVENTS_TAB", "Events"),
    }


@app.post("/api/sync", response_model=schemas.SyncResponse)
def sync_all(db: Session = Depends(get_db)):
    if not is_google_sheets_configured():
        raise HTTPException(
            status_code=400,
            detail="Google Sheets not configured. Set GOOGLE_SHEET_ID and credentials in .env file.",
        )
    tasks = db.query(models.Task).all()
    events = db.query(models.Event).all()

    t_count = sync_tasks_to_sheets(tasks)
    e_count = sync_events_to_sheets(events)

    return schemas.SyncResponse(
        message="Sync completed successfully.",
        tasks_synced=t_count,
        events_synced=e_count,
    )


@app.post("/api/sync/tasks")
def sync_tasks_endpoint(db: Session = Depends(get_db)):
    if not is_google_sheets_configured():
        raise HTTPException(status_code=400, detail="Google Sheets not configured.")
    tasks = db.query(models.Task).all()
    count = sync_tasks_to_sheets(tasks)
    return {"message": f"Synced {count} tasks.", "count": count}


@app.post("/api/sync/events")
def sync_events_endpoint(db: Session = Depends(get_db)):
    if not is_google_sheets_configured():
        raise HTTPException(status_code=400, detail="Google Sheets not configured.")
    events = db.query(models.Event).all()
    count = sync_events_to_sheets(events)
    return {"message": f"Synced {count} events.", "count": count}


# ============================================================================
# AI Planner Endpoints
# ============================================================================


@app.post("/api/ai/plan")
async def ai_plan_endpoint(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    AI-powered planning endpoint.
    Accepts text input or file upload and extracts tasks/events.

    Request (multipart/form-data):
    - text: Natural language plan (optional)
    - file: Uploaded file (PDF, image, etc.) (optional)
    - include_conflicts: Boolean to detect calendar conflicts (default: true)

    Returns:
    {
        "tasks": [...],
        "events": [...],
        "conflicts": [...],
        "raw_text": "...",
        "metadata": {...}
    }
    """
    try:
        # Parse form data
        form_data = await request.form()
        text_input = form_data.get("text", "").strip()
        uploaded_file = form_data.get("file")
        include_conflicts = form_data.get("include_conflicts", "true").lower() == "true"

        if not text_input and not uploaded_file:
            raise HTTPException(
                status_code=400,
                detail="Either 'text' or 'file' must be provided",
            )

        # Extract existing calendar for conflict detection
        existing_tasks = None
        existing_events = None

        if include_conflicts:
            existing_tasks = [
                {
                    "title": t.title,
                    "due_date": t.due_date.isoformat() if t.due_date else None,
                    "due_time": t.due_time,
                }
                for t in db.query(models.Task).limit(20).all()
            ]
            existing_events = [
                {
                    "title": e.title,
                    "start_date": e.start_date.isoformat() if e.start_date else None,
                    "start_time": e.start_time,
                    "end_time": e.end_time,
                }
                for e in db.query(models.Event).limit(20).all()
            ]

        # Get AI planner
        try:
            planner = get_ai_planner()
        except GroqAIError as e:
            raise HTTPException(status_code=503, detail=str(e))

        # Process input (text or file)
        if text_input:
            result = planner.plan_from_text(
                text_input,
                existing_tasks=existing_tasks,
                existing_events=existing_events,
            )
        else:
            # Save uploaded file temporarily
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                content = await uploaded_file.read()
                tmp.write(content)
                tmp_path = tmp.name

            try:
                file_content, file_type = parse_file(tmp_path)
                result = planner.plan_from_file(
                    file_content,
                    file_type,
                    existing_tasks=existing_tasks,
                    existing_events=existing_events,
                )
            finally:
                # Clean up temp file
                try:
                    Path(tmp_path).unlink()
                except Exception:
                    pass

        return result

    except FileParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except GroqAIError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        print(f"AI plan error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
