const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const ROLE_COLORS = { admin: "#f472b6", devops: "#22d3ee", developer: "#a78bfa", viewer: "#94a3b8" };
const ROLE_LABELS = { admin: "Admin", devops: "DevOps", developer: "Developer", viewer: "Viewer" };
const STATUS_LABELS = { healthy: "Saludable", warning: "Advertencia", critical: "Crítico", unknown: "Sin datos" };
const LEVELS = {
    cpu_percent: [70, 85], memory_percent: [80, 90], disk_percent: [75, 85], latency_p95_ms: [500, 1000],
};
const REFRESH_MS = 10000;

const state = { q: "", role: "", editing: null, deleting: null };

// ---------- Utilidades ----------
async function api(path, options = {}) {
    const resp = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        ...options,
        body: options.body ? JSON.stringify(options.body) : undefined,
    });
    const data = await resp.json().catch(() => ({}));
    if (resp.status === 401) {
        location.href = "/login";  // sesión vencida
        throw new Error(data.error || "Sesión vencida");
    }
    if (!resp.ok) {
        const err = new Error(data.error || `Error ${resp.status}`);
        err.status = resp.status;
        err.fields = data.fields || {};
        throw err;
    }
    return data;
}

function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function toast(message, type = "ok") {
    const el = document.createElement("div");
    el.className = `toast ${type === "error" ? "error" : ""}`;
    el.textContent = message;
    $("#toasts").appendChild(el);
    setTimeout(() => el.remove(), 4000);
}

function fmt(value, digits = 1) {
    if (value === null || value === undefined) return "—";
    return Number(value).toLocaleString("es-CO", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

function duration(seconds) {
    if (!seconds) return "—";
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`;
}

function initials(name) {
    return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
}

function avatarColor(seed) {
    let hash = 0;
    for (const ch of seed) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
    const hue = hash % 360;
    return `linear-gradient(135deg, hsl(${hue} 70% 55%), hsl(${(hue + 40) % 360} 70% 45%))`;
}

function relativeDate(iso) {
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 60) return "hace un momento";
    if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
    if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
    return new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

// Markdown mínimo y seguro: se escapa todo y luego se aplican pocos formatos.
function renderMarkdown(md) {
    const lines = escapeHtml(md).split("\n");
    let html = "";
    let inList = false;
    let inCode = false;
    const inline = (t) => t
        .replace(/`([^`]+)`/g, "<code>$1</code>")
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
    for (const line of lines) {
        if (line.startsWith("```")) {
            if (inList) { html += "</ul>"; inList = false; }
            html += inCode ? "</code></pre>" : "<pre><code>";
            inCode = !inCode;
            continue;
        }
        if (inCode) { html += line + "\n"; continue; }
        const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
        if (item) {
            if (!inList) { html += "<ul>"; inList = true; }
            html += `<li>${inline(item[1])}</li>`;
            continue;
        }
        if (inList) { html += "</ul>"; inList = false; }
        const heading = line.match(/^(#{1,3})\s+(.*)/);
        if (heading) html += `<h${heading[1].length === 3 ? 3 : 2}>${inline(heading[2])}</h${heading[1].length === 3 ? 3 : 2}>`;
        else if (line.trim()) html += `<p>${inline(line)}</p>`;
    }
    if (inList) html += "</ul>";
    if (inCode) html += "</code></pre>";
    return html;
}

function sparkline(svg, points, key) {
    const values = points.map((p) => p[1]).filter((v) => v !== null);
    if (values.length < 2) { svg.innerHTML = ""; return; }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const step = 100 / (points.length - 1);
    const coords = points
        .map((p, i) => (p[1] === null ? null : [i * step, 28 - ((p[1] - min) / span) * 24]))
        .filter(Boolean);
    const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
    const area = `${line} L${coords.at(-1)[0]},30 L${coords[0][0]},30 Z`;
    svg.innerHTML = `
        <defs><linearGradient id="g-${key}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="var(--accent)" stop-opacity=".35"/>
            <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
        </linearGradient></defs>
        <path class="area" d="${area}" fill="url(#g-${key})"/>
        <path class="line" d="${line}"/>`;
}

function levelFor(key, value) {
    const limits = LEVELS[key];
    if (!limits || value === null || value === undefined) return "";
    return value >= limits[1] ? "critical" : value >= limits[0] ? "warning" : "";
}

// ---------- Monitoreo ----------
function setService(name, up, label) {
    const li = $(`.services li[data-svc="${name}"]`);
    if (!li) return;
    li.dataset.state = up ? "up" : "down";
    $(".svc-state", li).textContent = label ?? (up ? "en línea" : "caído");
}

function setHealthPill(status, score) {
    const pill = $("#health-pill");
    pill.dataset.status = status;
    $("#health-text").textContent = score === undefined ? STATUS_LABELS[status] : `${STATUS_LABELS[status]} · ${score}/100`;
}

async function refreshHealth() {
    try {
        const health = await fetch("/health").then((r) => r.json());
        setService("nginx", true, "HTTPS");
        setService("app", health.status === "ok" || health.database === "down");
        setService("db", health.database === "ok");
    } catch {
        setService("app", false);
    }
}

async function refreshMetrics() {
    try {
        const data = await api("/api/metrics/overview?minutes=30");
        const m = data.metrics;
        for (const key of ["cpu_percent", "memory_percent", "disk_percent", "latency_p95_ms"]) {
            $(`#kpi-${key}`).textContent = fmt(m[key], key === "latency_p95_ms" ? 0 : 1);
            $(`.kpi[data-key="${key}"]`).dataset.level = levelFor(key, m[key]);
        }
        $("#kpi-request_rate").textContent = fmt(m.request_rate, 2);
        $("#meter-disk").style.width = `${Math.min(m.disk_percent ?? 0, 100)}%`;
        for (const [key, points] of Object.entries(data.series)) {
            const svg = $(`#spark-${key}`);
            if (svg) sparkline(svg, points, key);
        }
        $("#meta-uptime").textContent = duration(m.uptime_seconds);
        $("#meta-cores").textContent = m.cpu_cores ?? "—";
        const up = (m.targets_total ?? 0) - (m.targets_down ?? 0);
        $("#meta-targets").textContent = m.targets_total ? `${up}/${m.targets_total}` : "—";

        setHealthPill(data.health.status, data.health.score);
        setService("prometheus", true);
        setService("node_exporter", m.cpu_percent !== null);
        renderAlerts(data.alerts);
    } catch (err) {
        setHealthPill("unknown");
        setService("prometheus", false);
        setService("node_exporter", false, "sin datos");
    }
}

function renderAlerts(alerts) {
    const firing = alerts.filter((a) => a.state === "firing" || a.state === "pending");
    const list = $("#alerts");
    if (!firing.length) {
        list.innerHTML = '<li class="muted">Sin alertas activas.</li>';
        return;
    }
    list.innerHTML = firing.map((a) => `
        <li class="${a.severity === "critical" ? "critical" : ""}">
            <b>${escapeHtml(a.name)}</b> · ${escapeHtml(a.state)}<br><small>${escapeHtml(a.summary)}</small>
        </li>`).join("");
}

// ---------- Copiloto ----------
async function analyze(question) {
    const btn = $("#ask-btn");
    btn.disabled = true;
    btn.classList.add("loading");
    $("#ai-empty").hidden = false;
    $("#ai-empty").innerHTML = '<div class="skeleton"><span></span><span style="width:85%"></span><span style="width:70%"></span><span style="width:90%"></span></div>';
    try {
        const data = await api("/api/ai/insights", { method: "POST", body: { question } });
        const { health } = data;
        const ring = $("#ring-fg");
        const color = { healthy: "var(--ok)", warning: "var(--warn)", critical: "var(--crit)" }[health.status];
        ring.style.stroke = color;
        ring.style.strokeDashoffset = String(326.7 * (1 - health.score / 100));
        $("#score-value").textContent = health.score;
        const label = $("#score-status");
        label.dataset.status = health.status;
        label.textContent = STATUS_LABELS[health.status];

        const provider = $("#ai-provider");
        provider.dataset.provider = data.provider;
        provider.textContent = data.provider === "claude" ? `Claude · ${data.model}` : "Motor de reglas local";

        const notice = $("#ai-notice");
        notice.hidden = !data.notice;
        notice.textContent = data.notice || "";
        $("#ai-analysis").innerHTML = renderMarkdown(data.analysis);
        $("#ai-findings").innerHTML = health.findings
            .map((f) => `<li data-level="${f.level}">${escapeHtml(f.title)}</li>`).join("");
        const when = new Date(data.snapshot.collected_at * 1000).toLocaleTimeString("es-CO");
        $("#ai-foot").textContent = `Métricas tomadas a las ${when}${question ? ` · Pregunta: “${question}”` : ""}`;

        $("#ai-empty").hidden = true;
        $("#ai-result").hidden = false;
    } catch (err) {
        $("#ai-empty").innerHTML = `<p>${escapeHtml(err.status === 429 ? "Demasiadas solicitudes. Espera un minuto." : err.message)}</p>`;
        toast(err.message, "error");
    } finally {
        btn.disabled = false;
        btn.classList.remove("loading");
    }
}

// ---------- Usuarios ----------
async function loadUsers() {
    const params = new URLSearchParams({ per_page: 100 });
    if (state.q) params.set("q", state.q);
    if (state.role) params.set("role", state.role);
    try {
        const [list, stats] = await Promise.all([api(`/api/users?${params}`), api("/api/users/stats")]);
        renderUsers(list.items);
        renderStats(stats);
    } catch (err) {
        toast(`No se pudieron cargar los usuarios: ${err.message}`, "error");
    }
}

function renderUsers(users) {
    $("#users-empty").hidden = users.length > 0;
    $("#users-body").innerHTML = users.map((u) => `
        <tr>
            <td><div class="who">
                <span class="avatar" style="background:${avatarColor(u.username)}">${escapeHtml(initials(u.name))}</span>
                <div><b>${escapeHtml(u.name)}</b><small>@${escapeHtml(u.username)}</small></div>
            </div></td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="role role-${u.role}">${ROLE_LABELS[u.role] || u.role}</span></td>
            <td title="${escapeHtml(new Date(u.created_at).toLocaleString("es-CO"))}">${relativeDate(u.created_at)}</td>
            <td class="right admin-only"><div class="actions">
                <button class="btn btn-sm" data-edit="${u.id}">Editar</button>
                <button class="btn btn-sm btn-ghost" data-delete="${u.id}" ${String(u.id) === document.body.dataset.userId ? "hidden" : ""} data-name="${escapeHtml(u.name)}">Eliminar</button>
            </div></td>
        </tr>`).join("");
}

function renderStats(stats) {
    $("#kpi-users").textContent = stats.total;
    $("#users-count").textContent = stats.total;
    const total = stats.total || 1;
    $("#role-bar").innerHTML = Object.entries(stats.by_role)
        .filter(([, n]) => n > 0)
        .map(([role, n]) => `<span title="${ROLE_LABELS[role]}: ${n}" style="width:${(n / total) * 100}%;background:${ROLE_COLORS[role]}"></span>`)
        .join("");
}

const fields = ["name", "email", "username", "role", "password"];

function clearErrors() {
    $$(".err").forEach((el) => { el.textContent = ""; });
    $$(".modal .invalid").forEach((el) => el.classList.remove("invalid"));
}

function openModal(user = null) {
    state.editing = user;
    clearErrors();
    $("#modal-title").textContent = user ? `Editar a ${user.name}` : "Nuevo usuario";
    $("#f-name").value = user?.name ?? "";
    $("#f-email").value = user?.email ?? "";
    $("#f-username").value = user?.username ?? "";
    $("#f-role").value = user?.role ?? "viewer";
    $("#f-password").value = "";
    $("#f-password").required = !user;
    $("#pw-hint").textContent = user ? "Déjala vacía para conservar la actual." : "Mínimo 8 caracteres.";
    $("#user-modal").showModal();
    $("#f-name").focus();
}

async function saveUser(event) {
    event.preventDefault();
    clearErrors();
    const body = Object.fromEntries(fields.map((f) => [f, $(`#f-${f}`).value]));
    const editing = state.editing;
    if (editing && !body.password) delete body.password;
    const btn = $("#save-user");
    btn.disabled = true;
    try {
        if (editing) await api(`/api/users/${editing.id}`, { method: "PUT", body });
        else await api("/api/users", { method: "POST", body });
        $("#user-modal").close();
        toast(editing ? "Usuario actualizado" : "Usuario creado");
        loadUsers();
    } catch (err) {
        for (const [field, msg] of Object.entries(err.fields)) {
            const slot = $(`.err[data-for="${field}"]`);
            if (slot) slot.textContent = msg;
            $(`#f-${field}`)?.classList.add("invalid");
        }
        if (!Object.keys(err.fields).length) toast(err.message, "error");
    } finally {
        btn.disabled = false;
    }
}

async function onTableClick(event) {
    const edit = event.target.closest("[data-edit]");
    const del = event.target.closest("[data-delete]");
    if (edit) {
        try {
            openModal(await api(`/api/users/${edit.dataset.edit}`));
        } catch (err) {
            toast(err.message, "error");
        }
    } else if (del) {
        state.deleting = del.dataset.delete;
        $("#confirm-text").textContent = `Se eliminará a ${del.dataset.name}. Esta acción no se puede deshacer.`;
        $("#confirm-modal").showModal();
    }
}

async function onConfirmClose() {
    if ($("#confirm-modal").returnValue !== "ok" || !state.deleting) return;
    try {
        await api(`/api/users/${state.deleting}`, { method: "DELETE" });
        toast("Usuario eliminado");
        loadUsers();
    } catch (err) {
        toast(err.message, "error");
    } finally {
        state.deleting = null;
    }
}

// ---------- Tema y arranque ----------
function initTheme() {
    let theme = "dark";
    try { theme = localStorage.getItem("opscenter-theme") || theme; } catch { /* almacenamiento bloqueado */ }
    document.documentElement.dataset.theme = theme;
    $("#theme-toggle").addEventListener("click", () => {
        const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = next;
        try { localStorage.setItem("opscenter-theme", next); } catch { /* sin persistencia */ }
    });
}

async function initLinks() {
    try {
        const cfg = await api("/api/config");
        const grafana = cfg.grafana_url || `${location.protocol}//${location.hostname}:3000`;
        const prometheus = cfg.prometheus_url || `${location.protocol}//${location.hostname}:9090`;
        $("#link-grafana").href = `${grafana}/d/opscenter`;
        $("#link-prometheus").href = prometheus;
        const li = $('.services li[data-svc="grafana"]');
        li.dataset.state = "up";
        $(".svc-state", li).innerHTML = `<a href="${escapeHtml(grafana)}/d/opscenter" target="_blank" rel="noopener">abrir ↗</a>`;
    } catch { /* enlaces opcionales */ }
}

function debounce(fn, ms) {
    let t;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function init() {
    initTheme();
    initLinks();

    $("#new-user").addEventListener("click", () => openModal());
    $("#user-form").addEventListener("submit", saveUser);
    $$("[data-close]").forEach((b) => b.addEventListener("click", () => $("#user-modal").close()));
    $("#users-body").addEventListener("click", onTableClick);
    $("#confirm-modal").addEventListener("close", onConfirmClose);

    $("#search").addEventListener("input", debounce((e) => { state.q = e.target.value.trim(); loadUsers(); }, 250));
    $("#role-filter").addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        $$("#role-filter button").forEach((b) => b.classList.toggle("active", b === btn));
        state.role = btn.dataset.role;
        loadUsers();
    });

    $("#ask-form").addEventListener("submit", (e) => { e.preventDefault(); analyze($("#ask-input").value.trim()); });
    $("#ask-chips").addEventListener("click", (e) => {
        const chip = e.target.closest(".chip");
        if (!chip) return;
        $("#ask-input").value = chip.dataset.q;
        analyze(chip.dataset.q);
    });

    loadUsers();
    refreshHealth();
    refreshMetrics();
    setInterval(() => { refreshMetrics(); refreshHealth(); }, REFRESH_MS);
}

init();
