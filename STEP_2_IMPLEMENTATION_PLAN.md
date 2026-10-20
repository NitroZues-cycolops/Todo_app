# STEP 2: Tasks-Calendar Tab Merge - Detailed Implementation Plan

## Overview
Merge the separate Tasks tab into the Calendar tab by replacing the current day-plan section with a combined form + task list interface. This keeps the calendar on the left and creates a flexible right panel for task creation and browsing.

---

## Answers to Your Questions

### 1. Side Panel vs Bottom Sheet Responsive Design
**Decision: Hybrid responsive layout**
- Desktop (>1024px): Side panel on right (current grid-2 layout)
- Tablet (768px-1024px): Stacked layout with form above task list
- Mobile (<768px): Bottom sheet that slides up (fixed position with scroll)

### 2. Auto-open Form vs Just Prefill Date
**Decision: Just prefill the date**
- Clicking a calendar date prefills `fT_date` input with that date
- Does NOT auto-switch view or scroll to form
- User can continue browsing calendar, form is ready when they're ready to create
- This preserves browse-first workflow without jarring UX

### 3. Always Visible vs Collapsible Task List
**Decision: Always visible with compact styling**
- Task list stays visible below the form (scrolls together on mobile)
- Use compact task card rendering (smaller font, less padding)
- On mobile, task list appears after form scrolls down
- Can implement collapse toggle in Phase 2 if needed

### 4. CSS Breakpoints for Responsive Design
```
Mobile: < 768px
Tablet: 768px - 1024px
Desktop: > 1024px

Key layouts:
- Desktop: grid-2 (1.1fr calendar | 1fr form+tasks)
- Tablet: grid-1 stacked with calendar above
- Mobile: full-width calendar, then full-width form+tasks below
```

### 5. State Management Impact
- Minimal: add `S.showTaskForm` flag for mobile collapse
- Add `S.calendarDateSelected` to track which date was clicked
- Reuse existing `S.editTaskId`, `S.tasks`, `S.events`
- Form state remains in DOM (no new state needed)

### 6. File Change Sequence
1. Update HTML nav to remove Tasks tab, keep Calendar
2. Add CSS for new layout + responsive breakpoints
3. Move task form HTML into calendar view
4. Move task list HTML into calendar view
5. Update JS to wire calendar click → prefill date
6. Test responsive at all breakpoints

---

## Phase Breakdown

### PHASE 1: HTML Structure Refactoring (20 min)
**File: `/home/prab/Prab/Prabjingo/Smart Schedule/smartschedule/templates/index.html`**

#### 1a. Remove Tasks tab from nav
- Line ~1019: Delete `<button class="nav-tab" onclick="switchView('tasks'...">📋 Tasks</button>`
- Now only 3 tabs: Dashboard, Calendar, Hyper Tiles

#### 1b. Restructure calendar view HTML
- Line ~1095: Replace the current calendar section structure
- New right panel will contain:
  - "Create Task" form (moved from view-tasks)
  - "All Tasks" list (moved from view-tasks)
  - Keep existing "Today's Plan" event list? **Decision: Replace it entirely**

#### 1c. Extract form from view-tasks and embed in calendar
- Lines ~1137-1241: Cut the entire `<div id="taskForm">` block
- Paste into new "Create Task" section in calendar view
- Keep same IDs: `fT_title`, `fT_desc`, `fT_prio`, `fT_date`, etc.

#### 1d. Extract task list from view-tasks
- Lines ~1227-1240: Cut the task list section
- Paste into calendar view below form
- Keep filter dropdown, keep `id="allTasksList"`

#### 1e. Keep view-tasks div but hide it or remove
- Decision: **Remove it entirely** – cleaner codebase
- Or keep it hidden for backward compatibility? **Remove it for clean break**

---

### PHASE 2: CSS for New Layout (25 min)
**File: `/home/prab/Prab/Prabjingo/Smart Schedule/smartschedule/templates/index.html` – styles section**

#### 2a. Update .grid-2 for responsive calendar layout
Current (line ~277):
```css
.grid-2 {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 24px;
}
@media (max-width: 1024px) { .grid-2 { grid-template-columns: 1fr; } }
```

**New structure needed:**
- Desktop: 1.1fr calendar | 1fr form+tasks in a scrollable column
- Tablet: Switch to stacked, calendar full-width, form+tasks full-width below
- Mobile: Full-width everything, form+tasks in a bottom sheet

#### 2b. Add new CSS classes for calendar view structure
Add after line ~282 (after current .grid-2):
```css
/* Calendar view specific layout */
.cal-container {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: 24px;
    margin-bottom: 24px;
}

.cal-left {
    /* Calendar on left */
}

.cal-right {
    /* Form + task list on right, scrollable column */
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-height: 800px;  /* Adjust as needed */
    overflow-y: auto;
}

/* Task form section within calendar */
.task-form-section {
    background: var(--bg-card-solid);
    border: 1px solid var(--border);
    border-radius: var(--radius-xl);
    padding: 20px;
    box-shadow: var(--shadow-sm);
}

.task-form-section .section-head {
    margin-bottom: 16px;
}

.task-form-section .form-col {
    margin-bottom: 10px;  /* Tighter spacing than Tasks tab */
}

/* Compact task list styling */
.compact-task-list .card-item {
    padding: 12px;  /* Reduced from 15px */
    gap: 10px;
}

.compact-task-list .ci-title {
    font-size: 13px;  /* Reduced from 14px */
}

.compact-task-list .ci-desc {
    font-size: 11.5px;  /* Reduced from 12.5px */
}

.compact-task-list .chip {
    font-size: 10px;  /* Reduced from 11px */
    padding: 3px 7px;
}

/* Responsive: Tablet (768px - 1024px) */
@media (max-width: 1024px) {
    .cal-container {
        grid-template-columns: 1fr;
    }
    
    .cal-right {
        max-height: none;
        overflow-y: visible;
    }
}

/* Responsive: Mobile (<768px) */
@media (max-width: 768px) {
    .cal-container {
        grid-template-columns: 1fr;
        gap: 16px;
    }
    
    .cal-right {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        max-height: 60vh;
        overflow-y: auto;
        background: var(--bg-card-solid);
        border-top: 1px solid var(--border);
        border-radius: var(--radius-lg) var(--radius-lg) 0 0;
        padding: 16px;
        z-index: 100;
    }
    
    .compact-task-list .card-item {
        padding: 10px;
    }
}
```

#### 2c. Adjust form grid for mobile
Mobile should make form-grid single column:
```css
@media (max-width: 768px) {
    .form-grid, .form-grid-3 {
        grid-template-columns: 1fr !important;
    }
}
```

---

### PHASE 3: HTML Restructuring - Calendar View Content (15 min)
**File: `/home/prab/Prab/Prabjingo/Smart Schedule/smartschedule/templates/index.html`**

Replace lines ~1094-1134 (current calendar view) with:

```html
<!-- ============== CALENDAR ============== -->
<div id="view-calendar" class="view">
    <div class="cal-container">
        <!-- LEFT: Calendar -->
        <div class="cal-left">
            <div class="section">
                <div class="cal-toolbar">
                    <div class="cal-nav">
                        <button class="icon-btn" onclick="nav(-1)">‹</button>
                        <div class="cal-title" id="calTitle">October 2026</div>
                        <button class="icon-btn" onclick="nav(1)">›</button>
                    </div>
                    <div style="display:flex; gap:10px; align-items:center;">
                        <div class="seg" id="viewSeg">
                            <button data-v="month" class="on">Month</button>
                            <button data-v="week">Week</button>
                        </div>
                        <div class="checkrow">
                            <input type="checkbox" id="multiSelectToggle" onchange="toggleMultiSelect()">
                            <label for="multiSelectToggle" style="margin: 0;">Select Multiple</label>
                        </div>
                        <button class="btn btn-sm" onclick="goToday()">Today</button>
                    </div>
                </div>
                <div id="calendar" class="calendar"></div>
            </div>
        </div>
        
        <!-- RIGHT: Create Task Form + Task List -->
        <div class="cal-right">
            <!-- CREATE TASK FORM -->
            <div class="task-form-section">
                <div class="section-head">
                    <div class="section-title">
                        <span class="dot"></span>
                        <span id="formKindTitle">New Task</span>
                    </div>
                </div>
                <div id="taskForm">
                    <div class="form-col" style="margin-bottom:10px;">
                        <label class="form-label">Task Title *</label>
                        <input id="fT_title" placeholder="What do you need to do?">
                    </div>
                    <div class="form-col" style="margin-bottom:10px;">
                        <label class="form-label">Description</label>
                        <textarea id="fT_desc" placeholder="Add details..." rows="2"></textarea>
                    </div>
                    <div class="form-grid" style="margin-bottom:10px;">
                        <div class="form-col">
                            <label class="form-label">Priority</label>
                            <select id="fT_prio">
                                <option value="low">🟢 Low</option>
                                <option value="medium" selected>🟡 Medium</option>
                                <option value="high">🔴 High</option>
                            </select>
                        </div>
                        <div class="form-col">
                            <label class="form-label">Category</label>
                            <input id="fT_cat" placeholder="Work / Personal" value="General">
                        </div>
                    </div>
                    <div class="form-grid" style="margin-bottom:10px;">
                        <div class="form-col">
                            <label class="form-label">Due Date</label>
                            <input id="fT_date" type="date">
                        </div>
                        <div class="form-col">
                            <label class="form-label">Due Time</label>
                            <input id="fT_time" type="time">
                        </div>
                    </div>
                    <div class="form-col" style="margin-bottom:10px;">
                        <label class="form-label">🔄 Repeat</label>
                        <select id="fT_repeat" onchange="updateRepeatUI()">
                            <option value="">Never</option>
                            <option value="FREQ=DAILY">Every day</option>
                            <option value="FREQ=WEEKLY;BYDAY=custom">Selected weekdays</option>
                            <option value="FREQ=WEEKLY">Every week</option>
                            <option value="FREQ=ALWAYS">Always (pinned)</option>
                        </select>
                    </div>
                    <div id="fT_weekday_container" class="form-col" style="margin-bottom:10px; display:none;">
                        <label class="form-label">Select Days</label>
                        <div style="display:grid; grid-template-columns:repeat(4,1fr); gap:6px;">
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="MO"> Mon</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="TU"> Tue</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="WE"> Wed</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="TH"> Thu</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="FR"> Fri</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="SA"> Sat</label>
                            <label class="checkrow" style="margin:0; font-size:12px;"><input type="checkbox" name="wd" value="SU"> Sun</label>
                            <button type="button" class="btn btn-sm" style="grid-column:4; font-size:11px; padding:5px 8px;" onclick="selectWeekdays([1,2,3,4,5])">Wkdays</button>
                        </div>
                    </div>
                    <div class="form-grid" style="margin-bottom:10px;">
                        <div class="form-col">
                            <label class="form-label">🎨 Color</label>
                            <input id="fT_color" type="color" value="#6366f1">
                        </div>
                        <div class="form-col">
                            <label class="form-label">Completed</label>
                            <div class="checkrow">
                                <input type="checkbox" id="fT_done">
                            </div>
                        </div>
                    </div>
                    <div class="form-col" style="margin-bottom:10px;">
                        <label class="form-label">🔗 Website Link</label>
                        <input id="fT_url" placeholder="https://example.com" style="font-size:12px;">
                    </div>
                    <div class="form-col" style="margin-bottom:12px;">
                        <label class="form-label">🎬 Video Link</label>
                        <input id="fT_vurl" placeholder="https://youtube.com/..." style="font-size:12px;">
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button class="btn btn-primary" style="flex:1; font-size:13px; padding:10px;" onclick="submitTask()">💾 Save</button>
                        <button class="btn btn-ghost" style="font-size:13px; padding:10px;" onclick="resetTaskForm()">Reset</button>
                    </div>
                </div>
            </div>

            <!-- ALL TASKS LIST -->
            <div class="section compact-task-list" style="flex: 1; overflow-y: auto;">
                <div class="section-head" style="margin-bottom:12px;">
                    <div class="section-title"><span class="dot"></span> All Tasks</div>
                    <select id="taskFilter" style="max-width:140px; font-size:12px; padding:7px;" onchange="renderAllTasksWithRecurrence()">
                        <option value="all">📋 All</option>
                        <option value="pending">⏳ Pending</option>
                        <option value="done">✅ Done</option>
                        <option value="today">🎯 Today</option>
                        <option value="week">🗓 Week</option>
                    </select>
                </div>
                <div id="allTasksList" class="list-group"></div>
            </div>
        </div>
    </div>
</div>
```

#### Remove old view-tasks entirely
Delete lines ~1136-1241 (entire `<div id="view-tasks"...>` block)

---

### PHASE 4: JavaScript Updates (30 min)
**File: `/home/prab/Prab/Prabjingo/Smart Schedule/smartschedule/templates/index.html`**

#### 4a. Update switchView() to handle calendar render
Current line ~1328-1336:
```javascript
function switchView(name, btn){
    document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    btn.classList.add('active');
    $('view-'+name).classList.add('active');
    if(name==='calendar') renderCalendar();
    if(name==='tasks') renderAllTasks();      // DELETE THIS LINE
    if(name==='bookmarks') renderBookmarksPage();
}
```

Change to:
```javascript
function switchView(name, btn){
    document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
    document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));
    btn.classList.add('active');
    $('view-'+name).classList.add('active');
    if(name==='calendar') {
        renderCalendar();
        renderAllTasksWithRecurrence();  // Also render task list
    }
    if(name==='bookmarks') renderBookmarksPage();
}
```

#### 4b. Add calendar date click handler to prefill form
After pickDate() function (around line ~1640-1644), add:
```javascript
function pickDate(ds){
    S.selected = new Date(ds);
    renderCalendar();
    renderSelected();
    // NEW: Prefill task form with selected date
    $('fT_date').value = ds;
}
```

#### 4c. Update openTaskModal() to NOT switch view
Current line ~1950-1957:
```javascript
function openTaskModal(id, presetDate){
    if(id===null || id===undefined){
        resetTaskForm();
        if(presetDate) $('fT_date').value = presetDate;
        switchView('tasks', document.querySelectorAll('.nav-tab')[2]);  // DELETE THIS
        $('fT_title').focus();
        return;
    }
    // ... rest
}
```

Change to:
```javascript
function openTaskModal(id, presetDate){
    if(id===null || id===undefined){
        resetTaskForm();
        if(presetDate) $('fT_date').value = presetDate;
        // Don't switch view - form is always visible in calendar
        $('fT_title').focus();
        return;
    }
    // ... rest
}
```

#### 4d. Update loadTaskIntoForm() similarly
Line ~1976, remove:
```javascript
switchView('tasks', document.querySelectorAll('.nav-tab')[2]);
```

#### 4e. Update renderSelected() to not show in calendar view
The current calendar view had two sections:
1. Calendar grid
2. "Today's Plan" event list

Decision: **Replace "Today's Plan" with the task form + task list**

So we need to ensure `renderSelected()` is NOT called when rendering the calendar view.

Current line ~1456-1468 is fine as-is (it's used by Dashboard).

---

### PHASE 5: Testing & Refinement (20 min)

#### 5a. Desktop Testing (>1024px)
- [ ] Calendar displays on left
- [ ] Form + task list on right in scrollable column
- [ ] Clicking calendar date prefills form
- [ ] Form submits correctly
- [ ] Task list filters work
- [ ] Scrolling right panel doesn't scroll calendar

#### 5b. Tablet Testing (768px-1024px)
- [ ] Layout switches to stacked (calendar top, form+tasks below)
- [ ] Calendar full-width
- [ ] Form+tasks full-width
- [ ] No bottom sheet
- [ ] Scroll behavior natural

#### 5c. Mobile Testing (<768px)
- [ ] Calendar full-width at top
- [ ] Form+tasks as bottom sheet (60vh, fixed)
- [ ] Form fields stack vertically
- [ ] Task list visible after scrolling
- [ ] Can still see calendar while bottom sheet is open

#### 5d. Functionality Testing
- [ ] Create task with date
- [ ] Task appears on calendar
- [ ] Recurring tasks display correctly
- [ ] Task filters work
- [ ] Edit task from list
- [ ] Delete task
- [ ] Complete task checkbox works

---

## Implementation Order (Recommended)

1. **10 min**: Remove Tasks tab from nav, delete old view-tasks div
2. **10 min**: Add CSS for .cal-container, .cal-left, .cal-right, responsive breakpoints
3. **15 min**: Restructure HTML - move form and task list into calendar view
4. **10 min**: Update JavaScript switchView() and calendar click handler
5. **15 min**: Test on desktop, verify layout and functionality
6. **10 min**: Test on tablet and mobile breakpoints
7. **5 min**: Fine-tune responsive CSS if needed

**Total: ~75 minutes**

---

## Potential Gotchas & Solutions

### Gotcha 1: Scroll performance on mobile with fixed bottom sheet
**Problem**: Scrolling inside .cal-right while .cal-left is visible might be slow
**Solution**: Use `will-change: transform` on .cal-right CSS

### Gotcha 2: Form reset not visible on mobile when bottom sheet closes
**Problem**: User resets form but can't see the cleared inputs
**Solution**: Scroll bottom sheet to top when form is reset

### Gotcha 3: Date picker on mobile takes up whole screen
**Problem**: Mobile date picker might hide the form
**Solution**: This is standard OS behavior, acceptable

### Gotcha 4: Task list height conflicts with bottom sheet
**Problem**: Task list .max-height: 800px might be wrong for mobile
**Solution**: Use JavaScript to calculate max-height based on viewport

### Gotcha 5: Recurring task rendering slows calendar
**Problem**: Already handled in current code with expandedTasks cache
**Solution**: Verify S.expandedTasks is populated in renderCalendar()

### Gotcha 6: Form validation might not trigger properly
**Problem**: Form is now always visible, might submit prematurely
**Solution**: Keep existing validation in submitTask() function

---

## After Phase 1-5: Remaining Work (Phase 2+)

These are NOT included in STEP 2, but document them for later:

- [ ] Per-date completion tracking (task_occurrences table usage)
- [ ] Edit/delete scope dialogs for recurring tasks
- [ ] Dashboard "Today's Plan" column updates
- [ ] Google Sheets sync compatibility with new columns
- [ ] AI Planner compatibility
- [ ] Drag-drop tasks to calendar dates
- [ ] Task completion calendar heat map
- [ ] Recurring task visual indicators

---

## Key Files to Modify

1. `/home/prab/Prab/Prabjingo/Smart Schedule/smartschedule/templates/index.html`
   - Nav tabs (line ~1019)
   - CSS styles (lines ~8-995)
   - HTML structure (lines ~1094-1241)
   - JavaScript (lines ~1258-2076 and beyond)

2. No backend changes needed for STEP 2

---

## Verification Checklist

- [ ] Remove Tasks tab from nav
- [ ] CSS responsive design implemented
- [ ] Form moved to calendar view
- [ ] Task list moved to calendar view
- [ ] Calendar click prefills date
- [ ] openTaskModal() doesn't switch tabs
- [ ] Responsive tested at all breakpoints
- [ ] Task CRUD works from new location
- [ ] Recurring tasks still expand correctly
- [ ] No console errors

---

## Questions for Refinement

1. Should "Today's Plan" section disappear entirely, or show events only in that location?
   - **Recommendation**: Remove entirely, consolidate to single "Create Task + All Tasks" view

2. Should clicking date auto-scroll form into view on mobile?
   - **Recommendation**: No, just prefill. User can scroll manually.

3. Should there be a "Close" button for bottom sheet on mobile?
   - **Recommendation**: Yes, or swipe-down to close (Phase 2)

4. Should task form have a "Save & Create Another" button?
   - **Recommendation**: No, keep simple for Phase 1

5. Should Dashboard "Today's Plan" be updated to reflect new structure?
   - **Recommendation**: Leave as-is for Phase 1, update in Phase 2
