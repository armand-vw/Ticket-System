import sqlite3
import os
from flask import Flask, request, jsonify, g

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "helpdesk.db")

SEED_USERS = [
    ("alice",   "End-User"),
    ("bob",     "Technician"),
    ("charlie", "End-User"),
]

KEYWORD_ROUTES = [
    (["password", "lockout", "login"],         "Identity",   "Medium"),
    (["wi-fi", "network", "down", "internet"], "Networking", "High"),
    (["printer", "hardware", "laptop"],         "Hardware",   "Low"),
]

VALID_STATUSES = ["Open", "In Progress", "Resolved", "Closed"]


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    with open(schema_path) as f:
        schema = f.read()

    db = sqlite3.connect(DATABASE)
    db.executescript(schema)
    db.commit()

    for username, role in SEED_USERS:
        db.execute(
            "INSERT OR IGNORE INTO users (username, role) VALUES (?, ?)",
            (username, role),
        )

    db.commit()
    db.close()


def analyze_and_route(title, description):
    combined = f"{title} {description or ''}".lower()

    for keywords, category, priority in KEYWORD_ROUTES:
        if any(kw in combined for kw in keywords):
            return category, priority

    return "General IT", "Low"


@app.route("/", methods=["GET"])
def index():
    db = get_db()
    users = db.execute("SELECT id, username, role FROM users ORDER BY id").fetchall()
    technicians = [u for u in users if u["role"] == "Technician"]
    tickets = db.execute(
        """SELECT t.id, t.title, t.description, t.category, t.priority, t.status,
                  t.created_at, t.user_id, t.tech_id,
                  u.username AS submitter
           FROM tickets t
           JOIN users u ON t.user_id = u.id
           ORDER BY t.created_at DESC"""
    ).fetchall()

    rows_html = ""
    for t in tickets:
        rows_html += (
            '<tr class="ticket-row"'
            + f' data-id="{t["id"]}"'
            + f' data-title="{t["title"].replace(chr(34), "&quot;")}"'
            + f' data-description="{(t["description"] or "").replace(chr(34), "&quot;")}"'
            + f' data-category="{t["category"]}"'
            + f' data-priority="{t["priority"]}"'
            + f' data-status="{t["status"]}"'
            + f' data-tech="{t["tech_id"] or "0"}"'
            + f' data-submitter="{t["submitter"]}"'
            + f' data-created="{t["created_at"]}"'
            + ">"
            + f"<td>#{t['id']}</td>"
            + f"<td>{t['title']}</td>"
            + f"""<td><span class="badge badge-cat">{t['category']}</span></td>"""
            + f"""<td><span class="badge badge-pri badge-pri-{t['priority'].lower()}">{t['priority']}</span></td>"""
            + f"""<td><span class="badge badge-sts badge-sts-{t['status'].lower().replace(' ','-')}">{t['status']}</span></td>"""
            + f"<td>{t['submitter']}</td>"
            + f"""<td class="col-created" data-raw="{t['created_at']}">{t['created_at']}</td>"""
            + "</tr>"
        )

    users_json = [{"id": u["id"], "username": u["username"], "role": u["role"]} for u in users]

    html = (
        """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>IT Helpdesk Dashboard</title>
<style>
  * { margin:0; padding:0; box-sizing:border-box; }
  body { font-family: system-ui, -apple-system, sans-serif; background:#f1f5f9; color:#1e293b; padding:24px; }
  .container { max-width:1100px; margin:0 auto; }

  header { display:flex; justify-content:space-between; align-items:center; margin-bottom:20px; flex-wrap:wrap; gap:12px; }
  h1 { font-size:1.5rem; }
  .header-right { display:flex; align-items:center; gap:10px; }
  .header-right select { padding:8px 10px; border:1px solid #d1d5db; border-radius:8px; font-size:.85rem; background:#fff; }
  .btn { padding:10px 20px; border:none; border-radius:8px; font-size:.9rem; font-weight:600; cursor:pointer; }
  .btn-primary { background:#2563eb; color:#fff; }
  .btn-primary:hover { background:#1d4ed8; }
  .btn-sm { padding:6px 14px; font-size:.8rem; }
  .btn-cancel { background:#e2e8f0; color:#475569; }

  .panel { background:#fff; border-radius:12px; box-shadow:0 1px 6px rgba(0,0,0,.06); padding:24px; margin-bottom:16px; display:none; }
  .panel.active { display:block; }

  .form-group { margin-bottom:16px; }
  .form-group label { display:block; font-weight:600; font-size:.8rem; margin-bottom:4px; text-transform:uppercase; letter-spacing:.04em; color:#64748b; }
  .form-group select, .form-group input, .form-group textarea { width:100%; padding:10px 12px; border:1px solid #d1d5db; border-radius:8px; font-size:.92rem; font-family:inherit; }
  .form-group textarea { resize:vertical; min-height:80px; }
  .form-actions { display:flex; gap:10px; justify-content:flex-end; }

  .stats-bar { display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap; }
  .stat-badge { padding:5px 14px; border-radius:20px; font-size:.78rem; font-weight:600; cursor:pointer; background:#e2e8f0; color:#475569; border:2px solid transparent; user-select:none; }
  .stat-badge:hover { background:#cbd5e1; }
  .stat-badge.stat-active { background:#dbeafe; color:#1e40af; border-color:#93c5fd; }

  .filter-bar { display:flex; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
  .filter-bar input { flex:2; min-width:180px; padding:8px 12px; border:1px solid #d1d5db; border-radius:8px; font-size:.88rem; }
  .filter-bar select { padding:8px 10px; border:1px solid #d1d5db; border-radius:8px; font-size:.85rem; background:#fff; min-width:120px; }

  table { width:100%; border-collapse:collapse; font-size:.9rem; }
  thead { background:#f8fafc; }
  th { text-align:left; padding:12px 14px; font-weight:600; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; color:#64748b; border-bottom:2px solid #e2e8f0; }
  td { padding:10px 14px; border-bottom:1px solid #f1f5f9; }
  .ticket-row { cursor:pointer; transition:background .12s; }
  .ticket-row:hover { background:#f0f7ff; }
  .ticket-row.selected { background:#dbeafe; }

  .table-wrap { background:#fff; border-radius:12px; box-shadow:0 1px 6px rgba(0,0,0,.06); padding:4px; overflow-x:auto; }

  .detail-grid { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
  .detail-field dt { font-size:.75rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em; color:#64748b; margin-bottom:2px; }
  .detail-field dd { font-size:.92rem; }
  .detail-field.full { grid-column:1/-1; }

  .badge { display:inline-block; padding:3px 10px; border-radius:20px; font-size:.78rem; font-weight:600; }
  .badge-cat { background:#dbeafe; color:#1e40af; }
  .badge-pri-low { background:#dcfce7; color:#166534; }
  .badge-pri-medium { background:#fef3c7; color:#92400e; }
  .badge-pri-high { background:#fee2e2; color:#991b1b; }
  .badge-sts-open { background:#dbeafe; color:#1e40af; }
  .badge-sts-in-progress { background:#fef3c7; color:#92400e; }
  .badge-sts-resolved { background:#dcfce7; color:#166534; }
  .badge-sts-closed { background:#e2e8f0; color:#475569; }

  .toast { position:fixed; bottom:24px; right:24px; padding:12px 20px; border-radius:8px; font-weight:600; font-size:.88rem; display:none; z-index:100; }
  .toast.success { background:#16a34a; color:#fff; display:block; }
  .toast.error { background:#dc2626; color:#fff; display:block; }
  .empty-state { text-align:center; padding:40px; color:#94a3b8; }
  .form-row { display:flex; gap:16px; }
  .form-row > * { flex:1; }
  .auth-note { padding:16px; background:#fef2f2; border:1px solid #fca5a5; border-radius:8px; color:#991b1b; font-size:.85rem; font-weight:600; display:none; }
  .no-matches { text-align:center; padding:40px; color:#94a3b8; display:none; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>IT Helpdesk</h1>
    <div class="header-right">
      <span style="font-size:.78rem;color:#64748b;font-weight:600;">Viewing as</span>
      <select id="viewingAs"></select>
      <button class="btn btn-primary" id="btnNewTicket">+ New Ticket</button>
    </div>
  </header>

  <div class="stats-bar" id="statsBar"></div>

  <div class="filter-bar">
    <input type="text" id="searchFilter" placeholder="Search tickets by title or description...">
    <select id="filterStatus"><option value="">All Statuses</option></select>
    <select id="filterPriority"><option value="">All Priorities</option></select>
    <select id="filterCategory"><option value="">All Categories</option></select>
  </div>

  <div class="panel" id="formPanel">
    <h2 style="font-size:1.1rem;margin-bottom:16px;">Submit a Ticket</h2>
    <div class="form-group">
      <label>Title</label>
      <input type="text" id="formTitle" placeholder="e.g. Cannot log in">
    </div>
    <div class="form-group">
      <label>Description</label>
      <textarea id="formDesc" placeholder="Describe the issue..."></textarea>
    </div>
    <div class="form-actions">
      <button class="btn btn-cancel btn-sm" id="btnCancelForm">Cancel</button>
      <button class="btn btn-primary btn-sm" id="btnSubmit">Submit</button>
    </div>
    <div id="formMsg" style="margin-top:12px;font-size:.85rem;"></div>
  </div>

  <div class="table-wrap">
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Title</th><th>Category</th><th>Priority</th><th>Status</th><th>Submitter</th><th>Created</th>
        </tr>
      </thead>
      <tbody id="ticketBody">
"""
        + (rows_html if rows_html else '<tr><td colspan="7"><div class="empty-state">No tickets yet.</div></td></tr>')
        + """
      </tbody>
    </table>
    <div class="no-matches" id="noMatches">No tickets match your filters.</div>
  </div>

  <div class="panel" id="detailPanel">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
      <h2 style="font-size:1.1rem;">Ticket <span id="detailId"></span></h2>
      <button class="btn btn-cancel btn-sm" id="btnCloseDetail">Close</button>
    </div>
    <div class="detail-grid">
      <div class="detail-field"><dt>Title</dt><dd id="detailTitle"></dd></div>
      <div class="detail-field"><dt>Submitter</dt><dd id="detailSubmitter"></dd></div>
      <div class="detail-field"><dt>Category</dt><dd id="detailCategory"></dd></div>
      <div class="detail-field"><dt>Priority</dt><dd id="detailPriority"></dd></div>
      <div class="detail-field"><dt>Status</dt><dd id="detailStatus"></dd></div>
      <div class="detail-field"><dt>Assigned To</dt><dd id="detailTech"></dd></div>
      <div class="detail-field full"><dt>Description</dt><dd id="detailDesc"></dd></div>
      <div class="detail-field"><dt>Created</dt><dd id="detailCreated"></dd></div>
    </div>
    <div id="updateSection">
      <hr style="margin:20px 0;border:none;border-top:1px solid #e2e8f0;">
      <h3 style="font-size:.95rem;margin-bottom:12px;">Update Ticket</h3>
      <div class="form-row">
        <div class="form-group">
          <label>Status</label>
          <select id="updStatus"></select>
        </div>
        <div class="form-group">
          <label>Assign Technician</label>
          <select id="updTech">
            <option value="0">-- unassigned --</option>
"""
        + "\n".join(
            f'            <option value="{t["id"]}">{t["username"]}</option>'
            for t in technicians
        )
        + """
          </select>
        </div>
      </div>
      <div class="form-actions">
        <button class="btn btn-primary btn-sm" id="btnUpdate">Save Changes</button>
      </div>
      <div id="updMsg" style="margin-top:12px;font-size:.85rem;"></div>
    </div>
    <div class="auth-note" id="authNote">Technician access required to update tickets.</div>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
var USERS = """
        + str(users_json)
        + """;
var VALID_STATUSES = """
        + str(VALID_STATUSES)
        + """;

var currentUserId = null;
var currentUserRole = null;

function timeAgo(dateStr) {
  var iso = dateStr.replace(" ", "T") + "Z";
  var then = new Date(iso);
  var now = new Date();
  var diff = Math.floor((now - then) / 1000);
  if (diff < 10) return "just now";
  if (diff < 60) return diff + "s ago";
  if (diff < 3600) return Math.floor(diff / 60) + "m ago";
  if (diff < 86400) return Math.floor(diff / 3600) + "h ago";
  if (diff < 604800) return Math.floor(diff / 86400) + "d ago";
  return dateStr.substring(0, 10);
}

function showToast(msg, type) {
  var t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast " + type;
  setTimeout(function() { t.className = "toast"; }, 3000);
}

/* ----- Stats Bar ----- */
function updateStats() {
  var rows = document.querySelectorAll(".ticket-row");
  var counts = {};
  var visible = 0;
  var currentFilter = document.getElementById("filterStatus").value;
  VALID_STATUSES.forEach(function(s) { counts[s] = 0; });
  rows.forEach(function(r) {
    if (r.style.display !== "none") {
      visible++;
      var st = r.dataset.status;
      counts[st] = (counts[st] || 0) + 1;
    }
  });
  var html = '<span class="stat-badge' + (currentFilter === "" ? " stat-active" : "") + '" data-filter="">All (' + visible + ")</span>";
  VALID_STATUSES.forEach(function(st) {
    html += '<span class="stat-badge' + (currentFilter === st ? " stat-active" : "") + '" data-filter="' + st + '">' + st + " (" + (counts[st] || 0) + ")</span>";
  });
  var bar = document.getElementById("statsBar");
  bar.innerHTML = html;
  bar.querySelectorAll(".stat-badge").forEach(function(b) {
    b.addEventListener("click", function() {
      document.getElementById("filterStatus").value = b.dataset.filter;
      applyFilters();
      updateStats();
    });
  });
}

/* ----- Filters ----- */
function applyFilters() {
  var search = document.getElementById("searchFilter").value.toLowerCase();
  var statusF = document.getElementById("filterStatus").value;
  var priF = document.getElementById("filterPriority").value;
  var catF = document.getElementById("filterCategory").value;
  var anyVisible = false;

  document.querySelectorAll(".ticket-row").forEach(function(row) {
    var ok = true;
    if (search) {
      var haystack = (row.dataset.title + " " + row.dataset.description).toLowerCase();
      if (haystack.indexOf(search) === -1) ok = false;
    }
    if (statusF && row.dataset.status !== statusF) ok = false;
    if (priF && row.dataset.priority !== priF) ok = false;
    if (catF && row.dataset.category !== catF) ok = false;
    row.style.display = ok ? "" : "none";
    if (ok) anyVisible = true;
  });

  document.getElementById("noMatches").style.display = anyVisible ? "none" : "";
  updateStats();
}

(function() {
  document.getElementById("searchFilter").addEventListener("input", applyFilters);
  document.getElementById("filterStatus").addEventListener("change", applyFilters);
  document.getElementById("filterPriority").addEventListener("change", applyFilters);
  document.getElementById("filterCategory").addEventListener("change", applyFilters);
})();

/* ----- Populate filter dropdowns from existing data ----- */
(function() {
  var cats = new Set();
  var pris = new Set();
  document.querySelectorAll(".ticket-row").forEach(function(r) {
    cats.add(r.dataset.category);
    pris.add(r.dataset.priority);
  });

  var filterP = document.getElementById("filterPriority");
  Array.from(pris).sort().forEach(function(p) {
    var o = document.createElement("option");
    o.value = p; o.textContent = p; filterP.appendChild(o);
  });

  var filterC = document.getElementById("filterCategory");
  Array.from(cats).sort().forEach(function(c) {
    var o = document.createElement("option");
    o.value = c; o.textContent = c; filterC.appendChild(o);
  });

  VALID_STATUSES.forEach(function(s) {
    var o = document.createElement("option");
    o.value = s; o.textContent = s;
    document.getElementById("filterStatus").appendChild(o);
  });
})();

/* ----- Viewing As ----- */
(function() {
  var sel = document.getElementById("viewingAs");
  USERS.forEach(function(u) {
    var o = document.createElement("option");
    o.value = u.id;
    o.textContent = u.username + " (" + u.role + ")";
    sel.appendChild(o);
  });
  sel.addEventListener("change", function() {
    var u = USERS.find(function(x) { return x.id === parseInt(sel.value, 10); });
    currentUserId = u.id;
    currentUserRole = u.role;
    document.getElementById("detailPanel").classList.remove("active");
    document.querySelectorAll(".ticket-row.selected").forEach(function(r) { r.classList.remove("selected"); });
  });
  sel.dispatchEvent(new Event("change"));
})();

/* ----- New Ticket Form ----- */
(function() {
  document.getElementById("btnNewTicket").addEventListener("click", function() {
    var p = document.getElementById("formPanel");
    p.classList.toggle("active");
    if (p.classList.contains("active")) {
      document.getElementById("detailPanel").classList.remove("active");
      document.querySelectorAll(".ticket-row.selected").forEach(function(r) { r.classList.remove("selected"); });
    }
  });

  document.getElementById("btnCancelForm").addEventListener("click", function() {
    document.getElementById("formPanel").classList.remove("active");
    document.getElementById("formMsg").textContent = "";
  });

  document.getElementById("btnSubmit").addEventListener("click", async function() {
    var msg = document.getElementById("formMsg");
    msg.textContent = "";
    var title = document.getElementById("formTitle").value.trim();
    if (!title) { msg.textContent = "Title is required."; msg.style.color = "#dc2626"; return; }
    var payload = {
      title: title,
      description: document.getElementById("formDesc").value.trim(),
      user_id: currentUserId
    };
    try {
      var resp = await fetch("/ticket", {
        method: "POST",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      var data = await resp.json();
      if (resp.ok) {
        msg.style.color = "#16a34a";
        msg.textContent = "Ticket #" + data.ticket_id + " created (Category: " + data.category + ", Priority: " + data.priority + ")";
        document.getElementById("formTitle").value = "";
        document.getElementById("formDesc").value = "";
        showToast("Ticket #" + data.ticket_id + " created", "success");
        setTimeout(function() { location.reload(); }, 600);
      } else {
        msg.style.color = "#dc2626";
        msg.textContent = data.error || "Failed.";
      }
    } catch(e) {
      msg.style.color = "#dc2626";
      msg.textContent = "Network error.";
    }
  });
})();

/* ----- Ticket Detail & Update ----- */
(function() {
  var selStatus = document.getElementById("updStatus");
  VALID_STATUSES.forEach(function(s) {
    var o = document.createElement("option");
    o.value = s; o.textContent = s;
    selStatus.appendChild(o);
  });

  var currentTicketId = null;

  document.querySelectorAll(".ticket-row").forEach(function(row) {
    row.addEventListener("click", function() {
      document.querySelectorAll(".ticket-row.selected").forEach(function(r) { r.classList.remove("selected"); });
      row.classList.add("selected");
      document.getElementById("formPanel").classList.remove("active");
      document.getElementById("formMsg").textContent = "";

      currentTicketId = parseInt(row.dataset.id, 10);
      document.getElementById("detailId").textContent = "#" + currentTicketId;
      document.getElementById("detailTitle").textContent = row.dataset.title;
      document.getElementById("detailDesc").textContent = row.dataset.description || "(none)";
      document.getElementById("detailCategory").textContent = row.dataset.category;
      document.getElementById("detailPriority").textContent = row.dataset.priority;
      document.getElementById("detailStatus").textContent = row.dataset.status;
      document.getElementById("detailCreated").textContent = timeAgo(row.dataset.created);

      var techId = parseInt(row.dataset.tech, 10) || 0;
      var tech = USERS.find(function(u) { return u.id === techId; });
      document.getElementById("detailTech").textContent = tech ? tech.username : "(unassigned)";
      document.getElementById("detailSubmitter").textContent = row.dataset.submitter;

      document.getElementById("updStatus").value = row.dataset.status;
      document.getElementById("updTech").value = techId || "0";

      if (currentUserRole === "Technician") {
        document.getElementById("updateSection").style.display = "";
        document.getElementById("authNote").style.display = "none";
      } else {
        document.getElementById("updateSection").style.display = "none";
        document.getElementById("authNote").style.display = "block";
      }

      document.getElementById("detailPanel").classList.add("active");
      document.getElementById("updMsg").textContent = "";
    });
  });

  document.getElementById("btnCloseDetail").addEventListener("click", function() {
    document.getElementById("detailPanel").classList.remove("active");
    document.querySelectorAll(".ticket-row.selected").forEach(function(r) { r.classList.remove("selected"); });
    currentTicketId = null;
  });

  document.getElementById("btnUpdate").addEventListener("click", async function() {
    if (!currentTicketId) return;
    var msg = document.getElementById("updMsg");
    msg.textContent = "";
    var techVal = parseInt(document.getElementById("updTech").value, 10) || null;
    var payload = {
      status: document.getElementById("updStatus").value,
      tech_id: techVal,
      acting_user_id: currentUserId
    };
    try {
      var resp = await fetch("/ticket/" + currentTicketId, {
        method: "PATCH",
        headers: {"Content-Type":"application/json"},
        body: JSON.stringify(payload)
      });
      var data = await resp.json();
      if (resp.ok) {
        msg.style.color = "#16a34a";
        msg.textContent = "Updated.";
        showToast("Ticket #" + currentTicketId + " updated", "success");
        setTimeout(function() { location.reload(); }, 500);
      } else {
        msg.style.color = "#dc2626";
        msg.textContent = data.error || "Failed.";
      }
    } catch(e) {
      msg.style.color = "#dc2626";
      msg.textContent = "Network error.";
    }
  });
})();

/* ----- Relative timestamps on load ----- */
(function() {
  document.querySelectorAll(".col-created").forEach(function(td) {
    td.textContent = timeAgo(td.dataset.raw);
  });
})();

/* ----- Stats on load ----- */
updateStats();
</script>
</body>
</html>"""
    )

    return html


@app.route("/ticket", methods=["POST"])
def create_ticket():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    user_id = data.get("user_id")

    if not title:
        return jsonify({"error": "title is required"}), 400
    if user_id is None:
        return jsonify({"error": "user_id is required"}), 400

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        return jsonify({"error": f"user_id {user_id} does not exist"}), 400

    category, priority = analyze_and_route(title, description)

    cursor = db.execute(
        "INSERT INTO tickets (title, description, category, priority, user_id) VALUES (?, ?, ?, ?, ?)",
        (title, description, category, priority, user_id),
    )
    db.commit()

    return (
        jsonify(
            {
                "ticket_id": cursor.lastrowid,
                "title": title,
                "category": category,
                "priority": priority,
            }
        ),
        201,
    )


@app.route("/ticket/<int:ticket_id>", methods=["GET"])
def get_ticket(ticket_id):
    db = get_db()
    ticket = db.execute(
        """SELECT t.id, t.title, t.description, t.category, t.priority, t.status,
                  t.created_at, t.user_id, t.tech_id,
                  u.username AS submitter, COALESCE(tech.username, '') AS tech_name
           FROM tickets t
           JOIN users u ON t.user_id = u.id
           LEFT JOIN users tech ON t.tech_id = tech.id
           WHERE t.id = ?""",
        (ticket_id,),
    ).fetchone()

    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    return jsonify(dict(ticket))


@app.route("/ticket/<int:ticket_id>", methods=["PATCH"])
def update_ticket(ticket_id):
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Request body must be valid JSON"}), 400

    db = get_db()
    ticket = db.execute("SELECT id FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404

    acting_user_id = data.get("acting_user_id")
    if not acting_user_id:
        return jsonify({"error": "acting_user_id is required"}), 400

    actor = db.execute("SELECT role FROM users WHERE id = ?", (acting_user_id,)).fetchone()
    if not actor or actor["role"] != "Technician":
        return jsonify({"error": "Only Technicians can update tickets"}), 403

    status = data.get("status")
    tech_id = data.get("tech_id")

    if status is not None:
        if status not in VALID_STATUSES:
            return jsonify({"error": f"Invalid status. Must be one of: {', '.join(VALID_STATUSES)}"}), 400
        db.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))

    if tech_id is not None:
        if tech_id != 0 and tech_id is not None:
            tech = db.execute(
                "SELECT id FROM users WHERE id = ? AND role = 'Technician'",
                (tech_id,),
            ).fetchone()
            if not tech:
                return jsonify({"error": f"user_id {tech_id} is not a valid Technician"}), 400
            db.execute("UPDATE tickets SET tech_id = ? WHERE id = ?", (tech_id, ticket_id))
        else:
            db.execute("UPDATE tickets SET tech_id = NULL WHERE id = ?", (ticket_id,))

    db.commit()

    updated = db.execute(
        """SELECT t.id, t.title, t.description, t.category, t.priority, t.status,
                  t.created_at, t.user_id, t.tech_id
           FROM tickets t WHERE t.id = ?""",
        (ticket_id,),
    ).fetchone()

    return jsonify(dict(updated))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8000, debug=True)
