let MEETING_SCHEDULE = [];
let currentWeekIndex = null;

// ---- Local notes ----
function notesKey() {
  return "pioneer-notes-v1";
}
function loadNotesStore() {
  try {
    const raw = localStorage.getItem(notesKey());
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}
function saveNotesStore(store) {
  localStorage.setItem(notesKey(), JSON.stringify(store));
}
function getWeekId(week) {
  return week.startDate || week.weekLabel || "";
}
function getWeekNotes(weekId) {
  const store = loadNotesStore();
  return store[weekId] || { note: "", checks: {} };
}
function setWeekNotes(weekId, data) {
  const store = loadNotesStore();
  store[weekId] = data;
  saveNotesStore(store);
}

// ---- Date helpers ----
function parseLocalDate(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return new Date(y, m - 1, d);
}
function findCurrentWeekIndex() {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  for (let i = 0; i < MEETING_SCHEDULE.length; i++) {
    const w = MEETING_SCHEDULE[i];
    if (!w.startDate || !w.endDate) continue;
    const start = parseLocalDate(w.startDate);
    const end = parseLocalDate(w.endDate);
    end.setHours(23, 59, 59, 999);
    if (today >= start && today <= end) return i;
  }
  if (!MEETING_SCHEDULE.length) return null;
  return MEETING_SCHEDULE.length - 1;
}

// ---- Rendering ----
function jwLink(url, text) {
  if (!url) return text;
  return `<a href="${url}" target="_blank" rel="noopener noreferrer">${text}</a>`;
}

function renderCurrentSchedule() {
  if (!MEETING_SCHEDULE.length) return;

  if (currentWeekIndex == null) {
    currentWeekIndex = findCurrentWeekIndex();
  }
  if (currentWeekIndex == null) currentWeekIndex = 0;

  const schedule = MEETING_SCHEDULE[currentWeekIndex];
  const weekId = getWeekId(schedule);
  const notes = getWeekNotes(weekId);

  const weekInfo = document.querySelector(".week-info");
  if (weekInfo) {
    weekInfo.innerHTML = jwLink(
      schedule.workbookUrl,
      "Week of " + (schedule.weekLabel || weekId)
    );
  }

  const themeElement = document.querySelector(".meeting-theme");
  if (themeElement) {
    themeElement.innerHTML =
      'Midweek Meeting Theme: ' +
      jwLink(
        schedule.workbookUrl,
        `<strong>"${schedule.theme || ""}"</strong>`
      );
  }

  const scriptureVerse = document.querySelector(".scripture-verse");
  if (scriptureVerse) {
    scriptureVerse.innerHTML = jwLink(
      schedule.workbookUrl,
      schedule.scripture || ""
    );
  }

  const wtArticleEl = document.querySelector(".wt-article-title");
  if (wtArticleEl && schedule.watchtowerTitle) {
    wtArticleEl.innerHTML = jwLink(
      schedule.watchtowerUrl,
      schedule.watchtowerTitle
    );
  }

  const bibleReadingEl = document.querySelector(".bible-reading");
  if (bibleReadingEl && schedule.bibleReading) {
    bibleReadingEl.innerHTML = jwLink(
      schedule.bibleReadingUrl,
      schedule.bibleReading
    );
  }

  const noteArea = document.querySelector("[data-note-id='my-comments']");
  if (noteArea) {
    noteArea.value = notes.note || "";
    noteArea.oninput = function () {
      const n = getWeekNotes(weekId);
      n.note = noteArea.value;
      setWeekNotes(weekId, n);
    };
  }

  document.querySelectorAll("[data-check-id]").forEach((el) => {
    const id = el.getAttribute("data-check-id");
    const checked = notes.checks[id] || false;
    el.checked = !!checked;
    el.onchange = function () {
      const n = getWeekNotes(weekId);
      n.checks[id] = el.checked;
      setWeekNotes(weekId, n);
    };
  });

  let nav = document.querySelector(".week-navigation");
  if (!nav) {
    nav = document.createElement("div");
    nav.className = "week-navigation";
    nav.style.cssText =
      "display:flex;gap:10px;justify-content:center;margin:15px 0;";
    const prevBtn = document.createElement("button");
    prevBtn.textContent = "← Previous Week";
    prevBtn.onclick = () => navigateWeek(-1);
    const nextBtn = document.createElement("button");
    nextBtn.textContent = "Next Week →";
    nextBtn.onclick = () => navigateWeek(1);
    nav.appendChild(prevBtn);
    nav.appendChild(nextBtn);
    if (weekInfo && weekInfo.parentNode) {
      weekInfo.parentNode.insertBefore(nav, weekInfo.nextSibling);
    } else {
      document.body.insertBefore(nav, document.body.firstChild);
    }
  }
  const prevBtn = nav.querySelector("button:first-child");
  const nextBtn = nav.querySelector("button:last-child");
  if (prevBtn) prevBtn.disabled = currentWeekIndex <= 0;
  if (nextBtn)
    nextBtn.disabled = currentWeekIndex >= MEETING_SCHEDULE.length - 1;

  console.log("Loaded week:", schedule.weekLabel || weekId);
}

function navigateWeek(direction) {
  if (!MEETING_SCHEDULE.length) return;
  if (currentWeekIndex == null) currentWeekIndex = findCurrentWeekIndex();
  const newIndex = currentWeekIndex + direction;
  if (newIndex < 0 || newIndex >= MEETING_SCHEDULE.length) return;
  currentWeekIndex = newIndex;
  renderCurrentSchedule();
}

// ---- Load from Vercel API ----
async function loadSchedule() {
  try {
    const res = await fetch("/api/jw-schedule");
    const data = await res.json();
    MEETING_SCHEDULE = Array.isArray(data) ? data : [];
    currentWeekIndex = null;
    renderCurrentSchedule();
  } catch (e) {
    console.error("Failed to load schedule", e);
  }
}

document.addEventListener("DOMContentLoaded", loadSchedule);
