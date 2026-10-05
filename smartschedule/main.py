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

load_dotenv()

models.Base.metadata.create_all(bind=engine)

# Auto-migration: ensure new columns exist on existing tables
def _auto_migrate():
    try:
        from sqlalchemy import inspect, text
        insp = inspect(engine)
        with engine.begin() as conn:
            # TASKS: color, url, video_url
            existing_tasks = {c['name'] for c in insp.get_columns('tasks')}
            for col, sql in [
                ('color', 'ALTER TABLE tasks ADD COLUMN color VARCHAR(20) DEFAULT ""'),
                ('url', 'ALTER TABLE tasks ADD COLUMN url VARCHAR(1000) DEFAULT ""'),
                ('video_url', 'ALTER TABLE tasks ADD COLUMN video_url VARCHAR(1000) DEFAULT ""'),
            ]:
                if col not in existing_tasks:
                    try: conn.execute(text(sql))
                    except Exception: pass

            # EVENTS: url, video_url
            existing_events = {c['name'] for c in insp.get_columns('events')}
            for col, sql in [
                ('url', 'ALTER TABLE events ADD COLUMN url VARCHAR(1000) DEFAULT ""'),
                ('video_url', 'ALTER TABLE events ADD COLUMN video_url VARCHAR(1000) DEFAULT ""'),
            ]:
                if col not in existing_events:
                    try: conn.execute(text(sql))
                    except Exception: pass
    except Exception:
        pass  # ignore migration errors (e.g. tables don't exist yet)

_auto_migrate()

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
    db_task = models.Task(**task.dict())
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
    for key, value in update_data.items():
        setattr(db_task, key, value)
    db.commit()
    db.refresh(db_task)
    return db_task


@app.patch("/api/tasks/{task_id}/toggle", response_model=schemas.Task)
def toggle_task(task_id: int, db: Session = Depends(get_db)):
    db_task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not db_task:
        raise HTTPException(status_code=404, detail="Task not found")
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
