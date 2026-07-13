# IT Helpdesk Portal

A lightweight, production-ready internal helpdesk web application built with **Flask** and **SQLite**. Users submit support tickets that are automatically categorized and prioritized via keyword routing. Technicians manage and resolve tickets through a live dashboard with role-based access control.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Quick Start](#quick-start)
- [Demo Users](#demo-users)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Testing with cURL](#testing-with-curl)

---

## Features

### Automatic Ticket Routing
Ticket title and description are scanned for keywords on submission. Category and priority are assigned automatically:

| Keywords | Category | Priority |
|---|---|---|
| `password`, `lockout`, `login` | Identity | Medium |
| `wi-fi`, `network`, `down`, `internet` | Networking | High |
| `printer`, `hardware`, `laptop` | Hardware | Low |
| *(no match)* | General IT | Low |

### Live Dashboard
- Full ticket table with color-coded priority and status badges
- Full-text search across title and description (filters live, no page reload)
- Filter dropdowns for status, priority, and category
- Clickable stats bar showing counts per status — click a badge to filter
- Click any row to open an inline detail panel with all ticket fields

### Role-Based Access
- **End-Users** can view the dashboard and submit tickets
- **Technicians** can update ticket status and assign tickets to themselves
- The PATCH endpoint enforces technician-only access server-side
- The frontend hides update controls for non-technician users and shows a notice

### Relative Timestamps
All dates display as relative time — "just now", "5m ago", "2h ago", "3d ago" — both in the table and the detail panel.

### Security
- All SQL queries use parameterized `?` placeholders — no SQL injection
- No ORM — uses Python's built-in `sqlite3` module
- Schema defined in a separate `schema.sql` file with `CHECK` constraints

---

## Tech Stack

`Python 3` · `Flask` · `SQLite` · `Vanilla JavaScript` · `HTML5` · `CSS3`

---

## Quick Start

```bash
git clone https://github.com/armand-vw/Ticket-System.git
cd Ticket-System
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:8000** in your browser. The database is created automatically on first run with three seeded users.

---

## Demo Users

| Username | Role | Purpose |
|---|---|---|
| `alice` | End-User | Submit tickets |
| `bob` | Technician | Update and assign tickets |
| `charlie` | End-User | Submit tickets |

Use the **"Viewing as"** dropdown in the dashboard header to switch between users and test both roles.

---

## API Reference

### `GET /`
Returns the dashboard HTML page with all tickets, stats, search, and filters.

### `POST /ticket`
Creates a new ticket with automatic category and priority assignment.

**Request Body (JSON):**
```json
{
  "title": "Cannot log in to email",
  "description": "Password reset not working",
  "user_id": 1
}
```

**Response `201 Created`:**
```json
{
  "ticket_id": 5,
  "title": "Cannot log in to email",
  "category": "Identity",
  "priority": "Medium"
}
```

**Error Responses:**
| Status | Condition |
|---|---|
| `400` | Missing `title`, `user_id`, or invalid `user_id` |
| `400` | Invalid JSON body |

### `GET /ticket/<id>`
Returns full ticket details including submitter name and assigned technician.

**Response `200 OK`:**
```json
{
  "id": 5,
  "title": "Cannot log in to email",
  "description": "Password reset not working",
  "category": "Identity",
  "priority": "Medium",
  "status": "Open",
  "created_at": "2026-07-13 14:00:00",
  "user_id": 1,
  "tech_id": null,
  "submitter": "alice",
  "tech_name": ""
}
```

| Status | Condition |
|---|---|
| `404` | Ticket not found |

### `PATCH /ticket/<id>`
Updates ticket status and/or assigns a technician. **Requires technician role.**

**Request Body (JSON):**
```json
{
  "status": "In Progress",
  "tech_id": 2,
  "acting_user_id": 2
}
```

**Response `200 OK`:**
```json
{
  "id": 5,
  "title": "Cannot log in to email",
  "status": "In Progress",
  "tech_id": 2
}
```

| Status | Condition |
|---|---|
| `400` | Missing `acting_user_id`, invalid status, or invalid `tech_id` (not a technician) |
| `403` | `acting_user_id` does not have Technician role |
| `404` | Ticket not found |

### Valid Statuses

`Open` · `In Progress` · `Resolved` · `Closed`

---

## Project Structure

```
Ticket-System/
├── app.py              # Flask application (routes, auto-router, inline frontend)
├── schema.sql          # Database DDL (users + tickets with CHECK constraints)
├── requirements.txt    # Python dependencies
├── .gitignore          # Excludes .venv/, *.db, __pycache__/, .env
└── README.md
```

---

## Architecture

### Database
- `schema.sql` is read at startup by `init_db()`
- `users` table has a `CHECK` constraint limiting `role` to `End-User` or `Technician`
- `tickets` table has foreign keys to `users` for both `user_id` (submitter) and `tech_id` (assigned technician)
- Default `status` is `Open`, timestamps use `CURRENT_TIMESTAMP`

### Auto-Routing
`analyze_and_route(title, description)` is a pure helper function that joins title and description, lowercases them, then checks keyword lists with first-match-wins strategy. No external API calls, no machine learning — deterministic and fast.

### Frontend
Single-page dashboard with all HTML, CSS, and JavaScript inline in `app.py`. No external frameworks. The `GET /` route queries the database and renders rows server-side with `data-*` attributes. All filtering, stats computation, and relative timestamps happen client-side in vanilla JavaScript.

### Role Enforcement
- The PATCH endpoint validates `acting_user_id` against the `users` table
- If the acting user's role is not `Technician`, the request is rejected with `403`
- The frontend listens to the "Viewing as" dropdown and shows/hides the update section based on `currentUserRole`

### Port
Runs on port **8000** to avoid conflicts with common development servers (e.g., Flask defaults and the port 5000 range).

---

## Testing with cURL

```bash
# Submit a ticket (auto-routed to Identity / Medium)
curl -X POST http://127.0.0.1:8000/ticket \
  -H "Content-Type: application/json" \
  -d '{"title":"Password lockout","description":"Cannot log in","user_id":1}'

# Get ticket details
curl http://127.0.0.1:8000/ticket/1

# Update ticket as bob (Technician)
curl -X PATCH http://127.0.0.1:8000/ticket/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"In Progress","tech_id":2,"acting_user_id":2}'

# Attempt update as non-technician (returns 403)
curl -X PATCH http://127.0.0.1:8000/ticket/1 \
  -H "Content-Type: application/json" \
  -d '{"status":"Resolved","acting_user_id":1}'
```
