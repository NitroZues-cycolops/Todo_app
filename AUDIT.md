# SmartSchedule — Read-Only Audit

Audit date: 2026-10-20  
Scope: current working tree (`git status` clean at start/end), FastAPI backend + Jinja/JS frontend + SQLite schema.  
Method: code read, grep, read-only SQLite/API experiments against **shared in-memory SQLite** (`sqlite+pysqlite:///file:auditmem...?mode=memory&cache=shared&uri=true`) and `TestClient`. No real database was modified. No browser was run.

Severity: **high** = broken feature, wrong data, or data corruption; **medium** = wrong behaviour/visible inconsistency; **low** = edge case, cleanup, or documentation.

---

## (a) Feature flows

### 1. Create task

1. UI form fields `#fT_title`, `#fT_date`, `#fT_start_time`, `#fT_end_time`, `#fT_repeat` — `smartschedule/templates/index.html:1249-1336`.
2. `submitTask()` builds the body with `due_date`, `start_time`, `end_time`, `completed`, and `recurrence_rule` — `index.html:2421-2465`.
3. `POST /api/tasks` → `create_task()` — `smartschedule/main.py:184-194`.
4. `create_task()` mirrors `start_time` into `due_time` — `main.py:187-189`; inserts a `Task` row and commits.
5. Success path: `resetTaskForm()` then `loadAll()` — `index.html:2462-2464`.
6. `loadAll()` fetches `/api/tasks`, `/api/dashboard`, `/api/bookmarks`, `/api/events` for the current month through month+2, and recurrence expansions — `index.html:2981-3004`.

There is no `rrule_until` input in the task form. The repeat choices are only `FREQ=DAILY`, `FREQ=WEEKLY;BYDAY=custom`, `FREQ=WEEKLY`, `FREQ=ALWAYS` — `index.html:1288-1310`.

### 2. Edit task

1. Task card click/edit button → `openTaskModal(id)` — `index.html:1570-1587`, `2294-2317`.
2. If `recurrence_rule` is set → `showRecurrenceScopeDialog('edit', task)` — `index.html:2304-2306`, `2383-2407`.
3. If `group_id` is set → `showEditScopeDialog('task', task)` — `index.html:2309-2312`, `2621-2637`.
4. Otherwise `loadTaskIntoForm(t)` — `index.html:2319-2381`. It fills `start_time` from `start_time || due_time` (`2353-2354`) and stores `S.editTaskScope` (`2321`, `2413-2414`).
5. `submitTask()` always sends a full body to `PUT /api/tasks/{id}` — `index.html:2445-2461`.
6. `update_task()` validates merged start/end, mirrors `start_time` to `due_time`, updates fields, commits — `main.py:354-381`.

Important: `S.editTaskScope` and `S.editTaskOccurrenceDate` are never read by `submitTask()` — see F08.

### 3. Delete task

1. Delete button/icon → `delTask(id)` — `index.html:2477-2507`.
2. Recurring task → scope dialog (`showRecurrenceScopeDialog('delete', t)`) — `2477-2485`.
3. Grouped task → one-confirm/one-all confirm dialogs → `DELETE /api/tasks/group/{group_id}` or `DELETE /api/tasks/{id}` — `2487-2498`.
4. Regular task → confirm → `DELETE /api/tasks/{id}` — `2500-2506`.
5. Recurring “this” branch → `delTaskWithRecurrenceScope()` → `PATCH /api/tasks/{id}/toggle?occurrence_date=...` — `2509-2516`.
6. Backend `delete_task()` deletes only the master `Task` row — `main.py:421-428`.

`TaskOccurrence` rows are not deleted and are not linked by a foreign key — see F05.

### 4. Recurring tasks

1. Stored in `Task.recurrence_rule` / `Event.recurrence_rule` — `models.py:24-25`, `47-48`.
2. Expansion is `parse_rrule()` — `main.py:86-158`.
3. Task expansion endpoints:
   - `GET /api/tasks/recurrence-expand` — `main.py:218-260`, calls `parse_rrule(task.recurrence_rule, start, end)` at `234`.
   - `GET /api/tasks/range` — `main.py:263-343`, calls `parse_rrule(...)` at `311`.
4. Event expansion endpoint: `GET /api/events/recurrence-expand` — `main.py:532-556`, calls `parse_rrule(...)` at `548`.
5. Frontend expansion:
   - `getTasksForDateRange()` calls the task expansion endpoint and clones one task per occurrence — `index.html:2932-2958`.
   - `getEventsForDateRange()` does the same for events — `index.html:2959-2989`.
6. Calendar uses `S.expandedTasks` / `S.expandedEvents` — `index.html:1825-1836`, `1869-1882`.
7. Tasks list uses master `S.tasks` and counts occurrences only for the date filters — `index.html:1702-1743`.
8. Dashboard does **not** expand recurrence — `main.py:735-746`, `index.html:1634-1639`.

Per-occurrence completion lives in `task_occurrences` — `models.py:77-86`, toggled by `PATCH /api/tasks/{id}/toggle?occurrence_date=...` — `main.py:384-418`.

### 5. Events

1. Event form `openEventModal()` — `index.html:2530-2617`. There is **no repeat/recurrence field** in this form.
2. `submitEvent()` posts `POST /api/events` or `PUT /api/events/{id}` — `index.html:2776-2801`.
3. `create_event()` fills `end_date` from `start_date` if absent — `main.py:503-511`.
4. `list_events()` filters by overlap — `main.py:514-528`.
5. Calendar renders events through `S.expandedEvents` (`getEventsForDateRange`) — `index.html:2959-2989`, `1825-1836`.
6. Grouped events use `showEditScopeDialog('event', e)` and `submitEventWithScope()` — `index.html:2535-2539`, `2621-2718`, `2720-2758`.
7. Recurring events can only exist if created outside the current UI (or manually in DB), because the event form has no repeat control.

### 6. Multi-date select

1. Toggle `#multiSelectToggle` → `toggleMultiSelect()` — `index.html:1231-1232`, `1991-1993`.
2. Drag path: `mousedown`/`mousemove`/`mouseup` on `#calendar` — `index.html:2057-2103`.
3. Drag release → `showMultiSelectPopover()` — `index.html:2105-2198`.
4. Checkbox/ctrl-click path: `handleCalendarClick()` only toggles dates; it never calls `showMultiSelectPopover()` — `index.html:2037-2055`.
5. `submitMultiSelect()` posts a **single object** with a `dates` array to `/api/events/bulk` or `/api/tasks/bulk` — `index.html:2200-2245`.
6. Backend bulk endpoints require a JSON **list** — `main.py:440-441` (`List[schemas.TaskCreate]`) and `main.py:599-600` (`List[dict]`).

The documented Feature 1 payloads in `FEATURE_1_TESTING.md:21-78` also use the `{dates: [...]}` object, but the current endpoints reject it. See F01.

### 7. AI Planner (plan and Create All)

1. `openAIPlannerModal()` / `submitAIPlan()` — `index.html:3030-3152`.
2. UI posts multipart/form-data to `POST /api/ai/plan` with text or file — `index.html:3118-3133`.
3. Backend reads form fields, loads at most 20 existing tasks/events for conflict context, calls Groq planner — `main.py:834-939`.
4. Planner normalizes tasks/events/conflicts — `ai_planner.py:42-298`.
5. Preview `showAIPlanPreview()` — `index.html:3154-3254`.
6. `createAIPlanItems()` posts task arrays to `/api/tasks/bulk`, then event arrays to `/api/events/bulk` — `index.html:3256-3305`.
7. AI task bodies contain `due_time` but not `start_time` — `index.html:3267-3274`.
8. AI event bodies contain `start_date`/`start_time`/`duration_minutes` but **not `end_date`** — `index.html:3283-3290`; backend bulk leaves `end_date` NULL — `main.py:599-626`.

File upload path: backend writes the upload to `tempfile.NamedTemporaryFile(delete=False)` — `main.py:907-917`; `parse_file()` determines type from the path suffix/MIME — `file_parser.py:52-70`. The temp name has no original suffix.

### 8. Dashboard

1. `loadAll()` calls `GET /api/dashboard` — `index.html:2981-2986`.
2. Backend uses `date.today()`, counts master tasks only, and sets:
   - `today_tasks = Task.due_date == today`
   - `week_tasks = Task.due_date between today and today+7`
   - events by overlap
   — `main.py:735-775`.
3. `updateStats()` only reads scalar counts — `index.html:1502-1511`.
4. `renderToday()` uses `S.tasks` filtered by `due_date === today` and `S.events` by overlap — `index.html:1634-1639`.
5. `renderWeek()` renders **events only** — `index.html:1642-1661`.
6. Dashboard never consults `task_occurrences` and never expands recurrence.

### 9. Google Sheets sync

1. `syncAll()` → `POST /api/sync` — `index.html:2913-2918`.
2. Backend checks `is_google_sheets_configured()` then calls `sync_tasks_to_sheets()` and `sync_events_to_sheets()` — `main.py:791-808`.
3. Credentials are read from `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON` — `google_sheets.py:26-49`.
4. Sync writes fixed header/rows into the configured tabs — `google_sheets.py:121-161`, `164-203`.
5. It is an **export only**; there is no import/read-back path.

`.env:14-15` sets `GOOGLE_SHEET_ID` and `CREDENTIALS_PATH`, but the code does not read `CREDENTIALS_PATH` — see F14.

### 10. Reminders

No reminder, notification, alarm, scheduler, or push code was found. The only occurrences of “reminders” are comments in `main.py:187`, `367`, and `447`. There is no reminder model, endpoint, UI, cron job, or browser Notification use. This feature is **UNVERIFIED / not implemented** in the current codebase.

---

## (b) Findings table

| ID | Severity | File:line | What is wrong | How to reproduce | Suggested fix (one line) |
|---|---|---|---|---|---|
| F01 | **high** | `index.html:2210-2237`; `main.py:440-441`, `599-600` | Multi-date create posts one object with `dates`, but both bulk endpoints require a JSON list. All multi-date tasks/events fail with 422. Docs claim PASS. | `TestClient` POST `/api/tasks/bulk` with `{"dates":["2026-10-20"],"title":"Multi task"}` → 422 `Input should be a valid list`; same for events. | Post an array of per-date rows (with generated `group_id`) or make endpoints accept `{dates,...}`. |
| F02 | **high** | `main.py:86-158` (esp. `100`, `133-156`), callers `234`, `311`, `548` | Recurrence is anchored to the query range start, not the task/event start. `FREQ=WEEKLY` without `BYDAY` uses `start_date.weekday()` (`151`), so it generates the wrong weekday. | Weekly task `due_date=2026-10-14`, expand Oct 1–31 → `2026-10-01, 08, 15, 22, 29` (Thursdays), not Wednesdays. Daily task due Oct 20 → 31 occurrences from Oct 1. | Pass `task.due_date` / `event.start_date` as the anchor and clamp to it. |
| F03 | **high** | `main.py:110-120`, `229-235`; `models.py:24-25`; `schemas.py:33` | `rrule_until` column is never read by `parse_rrule()`; only `UNTIL=` inside the rule string is honored. | Daily task with `rrule_until=2026-10-05`, expand Oct 1–31 → 31 occurrences. | Pass `rrule_until` into expansion and use `min(rrule_until, end)`. |
| F04 | **high** | `index.html:2509-2516`; `main.py:384-411` | “Delete this occurrence only” calls the toggle endpoint, so it marks the occurrence completed instead of cancelling/deleting it. `cancelled` is never set true anywhere. | Toggle occurrence `2026-10-02` → expand returns `{completed: true, cancelled: false}`. | Add a cancel/delete-occurrence endpoint and filter cancelled rows. |
| F05 | **high** | `main.py:61-76`, `421-428`; `models.py:77-86` | Deleting a task leaves `task_occurrences` rows. The table has no FK/unique constraint, and SQLite reuses the max row id, so a new task can inherit old completions. | Delete recurring id 1, create a new task → new id is 1; expand `2026-10-02` shows old occurrence `completed: true`. | Add FK `ON DELETE CASCADE` or delete occurrences in `delete_task`; add `UNIQUE(task_id, occurrence_date)` and AUTOINCREMENT. |
| F06 | **high** | `index.html:3283-3290`, `1591-1600`, `1642-1661`; `main.py:599-626` | AI-created events omit `end_date`; backend leaves it NULL. `eventChips()` calls `fmtShort(e.end_date)`, and `fmtShort(null)` throws, breaking Today’s Plan/This Week rendering. | Bulk event `{"title":"AI event","start_date":"2026-10-20","start_time":"09:00","duration_minutes":60}` → `end_date: null`. `node -e` `fmtShort(null)` → `TypeError: Cannot read properties of null`. | Default `end_date=start_date` in bulk create and make `fmtShort`/`eventChips` null-safe. |
| F07 | **high** | `main.py:907-917`; `file_parser.py:52-70`; `ai_planner.py:112-126` | Uploaded files are written to an extensionless temp file. `parse_file()` depends on suffix/MIME, so PDF/text/image uploads are rejected. Image path is also explicitly unsupported by the planner. | Code inspection: `NamedTemporaryFile(delete=False)` then `parse_file(tmp_path)`; no original filename/suffix is passed. | Preserve `uploaded_file.filename` suffix or pass content type directly; remove/disable image accept unless vision is implemented. |
| F08 | **high** | `index.html:2383-2419`, `2445-2465`, `2321` | “This occurrence only” is stored in `S.editTaskScope`, but `submitTask()` never reads it; every edit updates the master series. The dialog also uses master `task.due_date`, not the clicked occurrence. | Code inspection: `S.editTaskScope` only assigned at `2321`/`2413`; `submitTask` always `PUT /api/tasks/{S.editTaskId}`. | Implement an occurrence override endpoint, or remove the “this occurrence” option until supported. |
| F09 | **high** | `main.py:735-746`; `index.html:1634-1639`, `1502-1506` | Dashboard and Today’s Plan use master `due_date` only. Recurring occurrences and per-occurrence completion are ignored. | Daily task due yesterday → dashboard `today_tasks: []`, `week_tasks: []`, while recurrence-expand returns today. Toggling today’s occurrence leaves `stats.completed_tasks: 0`, `pending_tasks: 1`. | Expand recurrence for today/week and aggregate occurrence completion for stats. |
| F10 | **high** | `index.html:1570-1577`, `2472-2475`; `main.py:384-411` | Recurring task checkbox uses master `t.due_date`, not the displayed occurrence. If master `due_date` is null (the existing Gym row), it sends `occurrence_date=null` and gets 422; otherwise it toggles the master’s date only. | `PATCH /api/tasks/1/toggle?occurrence_date=null` → 422 `input is too short`. | Pass the actual occurrence date or disable the checkbox for master rows; handle null due dates. |
| F11 | **medium** | `index.html:2981-2999`, `1785-1791`, `1838-1857` | Recurrence/event cache covers only current month through month+2. Calendar navigation to previous or later months renders no recurring tasks/events (and no events from `S.events`). | Code inspection: `nav()` only changes `S.cursor` and calls `renderCalendar()`; no fetch for the new range. | Fetch expansion/events for the visible `S.cursor` range on navigation. |
| F12 | **medium** | `index.html:2309-2312`, `2639-2718` | `openEditForScope()` only has an `if(type === 'event')` branch. For a grouped task it renders nothing, so the scope dialog stays and editing is a no-op. | Code inspection: no `else`/task branch in `openEditForScope()`. | Implement the task edit/update path or remove the grouped-task scope dialog. |
| F13 | **medium** | `main.py:346/431`, `559/590`, `695/726` | `/api/*/categories` routes are declared **after** `/{id}` routes, so the dynamic route matches `categories` and returns 422. | `GET /api/tasks/categories` → 422 `unable to parse string as an integer`; same for events and bookmarks. | Move `categories` routes before the `/{id}` routes. |
| F14 | **medium** | `.env:14-15`; `google_sheets.py:31-48`, `52-60`; `requirements.txt:8-10` | Code reads `GOOGLE_SERVICE_ACCOUNT_FILE`/`_JSON`, but `.env` sets `CREDENTIALS_PATH`. Current venv also has no `google` package installed. Sync reports not configured. | `is_google_sheets_configured() -> False`; `_check_google_libs() -> False`; `GOOGLE_SERVICE_ACCOUNT_FILE -> None`; `CREDENTIALS_PATH -> credentials.json`. | Align the env var name and install the declared Google dependencies. |
| F15 | **medium** | `google_sheets.py:121-161`, `164-203` | Export is lossy and stale: it does not include recurrence/rrule/group_id/url/video_url/task start/end times, and never clears rows below the new data length. | Code inspection of headers `121-122` and range write `151-157`/`193-199`. | Clear/rewrite the full used range and include all needed columns; document export-only semantics. |
| F16 | **medium** | `main.py:791-808`; `google_sheets.py:153-161`, `195-203`; `index.html:2913-2918` | Sync helpers swallow exceptions and return 0; `/api/sync` still returns success. The frontend catch reads `e.response`, which the API helper never sets. | Code inspection: helpers `except Exception: return 0`; `api.request()` throws a plain `Error` at `1455-1457`. | Raise/propagate sync failures and show `e.message`. |
| F17 | **medium** | `schemas.py:76-95`; `main.py:503-511`, `599-626`; `index.html:2776-2794` | No event validation for `end_date >= start_date` or `end_time > start_time`. Bulk create can leave `end_date` null or compute an end time across midnight without validation. | Code inspection; bulk event output has `end_date: None`. | Add model validators/defaults and reject invalid ranges. |
| F18 | **medium** | `index.html:2959-2966`, `1825-1836`, `1591-1600` | Recurring event clones change `start_date` to the occurrence but leave the original `end_date`. Multi-day recurring events get the wrong range; `end_date` may precede the new `start_date`. | Code inspection: `{...baseEvent, start_date: occ.occurrence_date}` only. | Shift `end_date` by the same offset or carry an occurrence end date. |
| F19 | **medium** | `index.html:1991-2055`, `2105-2198` | “Select Multiple” checkbox/ctrl-click mode only toggles dates; it never opens the create popover. Drag selection is the only path that opens it. | `grep showMultiSelectPopover` shows only the `mouseup` call at `2101`. | Open the popover when a selection exists or add an explicit “Create” button. |
| F20 | **medium** | `index.html:1731-1732`; `main.py:740-746` | Pending/Done filters and stats use master `completed`; per-occurrence completion is ignored, so a recurring task with all occurrences done still appears pending. | Code inspection; dashboard occurrence toggle output shows `completed_tasks` unchanged. | Derive recurring status from `task_occurrences` for filters/stats. |
| F21 | **medium** | `models.py:77-86`; `main.py:393-410` | `task_occurrences` has no `UNIQUE(task_id, occurrence_date)` and no FK. Concurrent/rapid toggles can create duplicate rows; `first()` hides them. | Code inspection. | Add a unique constraint and use upsert or handle duplicates. |
| F22 | **medium** | `main.py:27-80` | `_auto_migrate()` swallows every exception with `except Exception: pass`; a failed column/table migration leaves the app running against an incompatible schema. | Code inspection. | Log/raise migration failures or use Alembic. |
| F23 | **low** | `index.html:1390-1398`, `1645`, `1653-1654`, `1983`, `2017-2018`, `2030-2031` | Date-only strings are parsed with `new Date('YYYY-MM-DD')` (UTC midnight) then displayed with local getters. No `toISOString()` exists anywhere, so the classic India shift is not present; UTC-negative zones can show the previous day. | `TZ=Asia/Kolkata new Date('2026-10-20')` → local 2026-10-20; `TZ=America/New_York` → local 2026-10-19; `grep toISOString` → none. | Parse date-only values as local `new Date(y, m-1, d)` or append `T00:00:00`. |
| F24 | **low** | `index.html:1545-1553`; `main.py:187-189` | A normal task has both `start_time` and mirrored `due_time`, so the card shows two time chips (`📅 ... ⋅ 09:00` and `⏰ 09:00`). | Code inspection; create mirrors at `main.py:187-189`. | Show one canonical time chip. |
| F25 | **low** | `index.html:2530-2617` vs `1288-1310`; `main.py:532-556` | Event form has no repeat/recurrence field, so recurring events cannot be created/edited from the UI even though the backend/DB support them. | Code inspection. | Add event repeat UI or remove the unsupported event-recurrence surface. |
| F26 | **low** | `index.html:3262-3305` | “Create All” posts tasks and events as two separate requests. If the event request fails, tasks remain committed while the UI reports overall failure. | Code inspection. | Add a combined transactional endpoint or clearly report partial success. |
| F27 | **low** | `index.html:2913-2918`; `index.html:1455-1457` | `syncAll()` catch reads `e.response`, but `api.request()` throws a plain `Error`; the real error message is lost and “not configured” is shown for every failure. | Code inspection. | Use `e.message` and avoid double-toasting. |
| F28 | **low** | `index.html:1666-1684` | `renderAllTasks()` is dead code and does not implement the month filter; if called it duplicates the list logic inconsistently. | `grep` shows only the definition; the filter uses `renderAllTasksWithRecurrence`. | Remove it or delegate to the async renderer. |
| F29 | **low** | `index.html:2932-2967`, `2981-3004` | Expansion fetch failures are caught and replaced with non-recurring data silently; `loadAll()`’s initial `Promise.all` has no catch. Users see incomplete/stale calendar/list data with no warning. | Code inspection. | Surface errors, retry, and distinguish partial data. |
| F30 | **low** | `main.py:781-788` | `/api/sync/status` returns the private `sheet_id` and tab names to any unauthenticated caller. | Code inspection. | Return only `configured`, or add auth. |
| F31 | **low** | `index.html:1565-1566`, `1762-1763`, `2903-2905` | User URLs are interpolated into `onclick`/iframe markup without full attribute escaping; a crafted URL can break out of the attribute. | Code inspection. | Use event listeners/`encodeURIComponent` and escape attribute values. |

---

## (c) Recommended fix order for the high findings

1. **F05** — stop occurrence data corruption first (cascade/delete + unique key + stable IDs).
2. **F04** — make “delete this occurrence” actually cancel/delete, and use `cancelled` consistently.
3. **F02 + F03** — fix recurrence anchoring and honor `rrule_until`; this affects calendar, list counts, edits, and deletes.
4. **F01** — make multi-date create work (frontend array or backend object support), then verify grouped edit/delete.
5. **F08** — implement real per-occurrence edit overrides, or remove the option.
6. **F09 + F10** — make Dashboard/Today’s Plan and the task checkbox use occurrence data, not master due dates.
7. **F06 + F07** — default AI event `end_date`, null-safe rendering, and preserve upload filenames/types.

---

## What looks fine

- Basic task/event CRUD uses SQLAlchemy sessions with `commit()`/`refresh()`; bulk endpoints roll back on a single-request failure — `main.py:184-194`, `440-459`, `599-632`.
- The `start_time` → `due_time` mirror works, including clearing: in-memory test produced `start_time: null`, `due_time: null` after `PUT {"start_time": null}` — `main.py:187-189`, `367-375`.
- The task list was changed to render one row per master task and added the Month filter — `index.html:1687-1743`.
- `parse_rrule()` handles the intended basic forms (`DAILY`, `WEEKLY`, `WEEKLY;BYDAY`, `ALWAYS`, `UNTIL` in the rule string) — `main.py:86-158`.
- API error handling converts FastAPI validation arrays into readable toasts — `index.html:1427-1465`.
- Titles/descriptions are escaped in most render paths — `index.html:1412`, `1545-1587`.
- `.gitignore` covers `.env`, `.env.*` (with `.env.example` unignored), `credentials.json`, `*.db`, `*.sqlite3`, `*.sqlite`, and `token.json` — `.gitignore:1-15`.
- No `.env`, `credentials.json`, database, or token file is tracked in git, and none has ever been added in history:
  - `git check-ignore -v` matched `.env`, `credentials.json`, `smartschedule.db`, `db.sqlite3`, `smartschedule_test_diag.db`, `token.json`.
  - `git ls-files | grep -E ...` → `none`.
  - `git log --all --pretty=format: --name-only --diff-filter=A | ...` → `none ever added`.
- No `toISOString()` usage exists outside `venv/` and `.git`, so the classic India “date shifts by one” combination is absent.

---

## What I did NOT check / limitations

- **No browser, no Playwright, no UI click-through.** UI findings are from code reading, not rendered behaviour.
- **No Groq network call.** AI planner model output, model availability, and real conflict detection were not exercised.
- **No Google Sheets API call.** Sync was not run end-to-end; only configuration and code paths were inspected.
- **No real database mutation.** API experiments used shared in-memory SQLite. The real `smartschedule.db` was not opened for writes.
- **No migration rehearsal.** `_auto_migrate()` was inspected, not run against a copy of the production schema.
- **No concurrency/load tests.** The duplicate/race concerns (F21) are code-level, not stress-tested.
- **No mobile/touch testing.** No touch/pointer handlers were found; mobile behaviour is UNVERIFIED.
- **No auth/security review beyond secrets and obvious URL interpolation.** The app has no authentication layer; deployment exposure was not assessed.

---

## Evidence appendix (real outputs from this session)

### A. Multi-date bulk create and category routes

```text
POST /api/tasks/bulk object -> 422 {"detail":[{"type":"list_type","loc":["body"],"msg":"Input should be a valid list","input":{"dates":["2026-10-20"],"title":"Multi task"}}]}
POST /api/events/bulk object -> 422 {"detail":[{"type":"list_type","loc":["body"],"msg":"Input should be a valid list","input":{"dates":["2026-10-20"],"title":"Multi event"}}]}
GET /api/tasks/categories -> 422 {"detail":[{"type":"int_parsing","loc":["path","task_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"categories"}]}
GET /api/events/categories -> 422 {"detail":[{"type":"int_parsing","loc":["path","event_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"categories"}]}
GET /api/bookmarks/categories -> 422 {"detail":[{"type":"int_parsing","loc":["path","bm_id"],"msg":"Input should be a valid integer, unable to parse string as an integer","input":"categories"}]}
```

### B. Recurrence anchoring and `rrule_until`

```text
weekly due 2026-10-14, range Oct 1-31 -> ['2026-10-01', '2026-10-08', '2026-10-15', '2026-10-22', '2026-10-29']
daily due 2026-10-20 count in Oct -> 31 first= 2026-10-01
daily with rrule_until=2026-10-05 count in Oct -> 31
after toggle 2026-10-02 -> [{'task_id': 4, 'occurrence_date': '2026-10-02', 'completed': True, 'cancelled': False}]
```

### C. Orphaned occurrences and ID reuse

```text
occurrences before delete -> 1
delete -> 200
occurrences after delete -> 1
old id 1 new id 1
new task occurrence 2026-10-02 -> [{'task_id': 1, 'occurrence_date': '2026-10-02', 'completed': True, 'cancelled': False}]
```

### D. Dashboard / per-occurrence completion

```text
recurring daily due yesterday -> dashboard today_tasks: []
recurring daily due yesterday -> dashboard week_tasks: []
recurrence-expand for today -> ['2026-10-20']

dashboard today_tasks -> ['Daily today']
dashboard week_tasks count -> 1 stats completed -> 0
after occurrence toggle: stats completed -> 0 pending -> 1
master task completed -> False
```

### E. Null `end_date` from AI bulk events

```text
bulk event status 200
created event end_date/end_time -> None 10:00
events range contains -> [('AI event', '2026-10-20', None)]
```

```text
node -e "fmtShort(null)" -> TypeError: Cannot read properties of null (reading 'toLocaleDateString')
```

### F. Start-time clearing

```text
created -> {'start_time': '09:00', 'due_time': '09:00', 'end_time': '10:00'}
PUT null -> {'start_time': None, 'due_time': None, 'end_time': '10:00'}
```

### G. Date parsing / timezone

```text
TZ=Asia/Kolkata new Date('2026-10-20') -> Tue Oct 20 2026 05:30:00 GMT+0530; local 2026-10-20
TZ=America/New_York new Date('2026-10-20') -> Mon Oct 19 2026 20:00:00 GMT-0400; local 2026-10-19
grep -rn "toISOString" --exclude-dir=venv --exclude-dir=.git . -> no toISOString found outside venv/.git
```

### H. Google Sheets configuration

```text
is_google_sheets_configured -> False
libs available -> False
CREDENTIALS_PATH -> credentials.json
GOOGLE_SERVICE_ACCOUNT_FILE -> None
creds -> None
no google packages installed in venv
```

### I. Git/secret checks

```text
git status --short -> (clean at start and end)
git ls-files | grep -E '(^|/)\.env|credentials|\.db$|\.sqlite3?$' -> none
git check-ignore -v .env credentials.json smartschedule.db db.sqlite3 smartschedule_test_diag.db token.json
  .gitignore:10:.env  .env
  .gitignore:9:credentials.json  credentials.json
  .gitignore:12:*.db  smartschedule.db
  .gitignore:15:*.sqlite3  db.sqlite3
  .gitignore:12:*.db  smartschedule_test_diag.db
  .gitignore:13:token.json  token.json
git log --all --pretty=format: --name-only --diff-filter=A | sort -u | grep -E '(^|/)\.env$|credentials|\.db$|\.sqlite3?$' -> none ever added
```
