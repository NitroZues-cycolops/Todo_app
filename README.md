# SmartSchedule

A personal task planner built with FastAPI, SQLite, and a server-rendered HTML interface.

## Run locally

```bash
./run.sh
```

Then open http://localhost:8000. The script creates a virtual environment if needed and installs `requirements.txt`.

## GitHub and hosting

Use GitHub to store and share this project's source code. GitHub Pages only serves static files, so it cannot run this FastAPI application or its SQLite database. To make the app available online, deploy it to a Python application host and use persistent storage for the SQLite database. Do not commit `.env`, service-account credentials, the local database, or the virtual environment.