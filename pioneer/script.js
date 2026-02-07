// Supabase Auto-Save for Pioneer Spiritual Growth Tracker
const SUPABASE_URL = 'https://vqgratxiuwcxvelzgncl.supabase.co';
const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZxZ3JhdHhpdXdjeHZlbHpnbmNsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk5MTgwNTIsImV4cCI6MjA4NTQ5NDA1Mn0.kUYtA_0Jmx1SQZiYG090IPntfWe5sOXes_1LjzyDCKI';

let saveTimeout = null;
let sessionId = null;
let statusEl = null;

function getSessionId() {
  const params = new URLSearchParams(window.location.search);
  let sid = params.get('session');
  if (!sid) {
    sid = localStorage.getItem('pioneer_session_id');
  }
  if (!sid) {
    sid = 'pioneer_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
  }
  localStorage.setItem('pioneer_session_id', sid);
  if (!params.get('session')) {
    const url = new URL(window.location);
    url.searchParams.set('session', sid);
    window.history.replaceState({}, '', url);
  }
  return sid;
}

// Collect all form data into a single object
function collectAllData() {
  const data = {};

  // Checkboxes - save by their ID
  document.querySelectorAll('input[type="checkbox"]').forEach(function(cb, i) {
    const key = cb.id || ('checkbox_' + i);
    data['cb_' + key] = cb.checked;
  });

  // Range sliders - save by their ID or index
  document.querySelectorAll('input[type="range"]').forEach(function(slider, i) {
    const key = slider.id || ('range_' + i);
    data['range_' + key] = slider.value;
  });

  // Textareas - save by index (unique per position)
  document.querySelectorAll('textarea').forEach(function(ta, i) {
    if (ta.value && ta.value.trim()) {
      data['textarea_' + i] = ta.value;
    }
  });

  // Stat boxes (editable content)
  var statIds = ['hours-today', 'hours-week', 'rvs-count', 'studies-count'];
  statIds.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) {
      data['stat_' + id] = el.textContent;
    }
  });

  // Active tab
  var activeTab = document.querySelector('.tab-content.active');
  if (activeTab) {
    data['active_tab'] = activeTab.id;
  }

  return data;
}

// Apply saved data back to the form
function applyData(data) {
  if (!data || Object.keys(data).length === 0) return;

  // Checkboxes
  document.querySelectorAll('input[type="checkbox"]').forEach(function(cb, i) {
    var key = cb.id || ('checkbox_' + i);
    if (data['cb_' + key] !== undefined) {
      cb.checked = data['cb_' + key];
    }
  });

  // Range sliders
  document.querySelectorAll('input[type="range"]').forEach(function(slider, i) {
    var key = slider.id || ('range_' + i);
    if (data['range_' + key] !== undefined) {
      slider.value = data['range_' + key];
    }
  });

  // Textareas
  document.querySelectorAll('textarea').forEach(function(ta, i) {
    if (data['textarea_' + i]) {
      ta.value = data['textarea_' + i];
    }
  });

  // Stat boxes
  var statIds = ['hours-today', 'hours-week', 'rvs-count', 'studies-count'];
  statIds.forEach(function(id) {
    if (data['stat_' + id]) {
      var el = document.getElementById(id);
      if (el) el.textContent = data['stat_' + id];
    }
  });

  // Restore active tab
  if (data['active_tab']) {
    var tabEl = document.getElementById(data['active_tab']);
    if (tabEl) {
      document.querySelectorAll('.tab-content').forEach(function(t) { t.classList.remove('active'); });
      document.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('active'); });
      tabEl.classList.add('active');
      // Find matching tab button
      var tabName = data['active_tab'];
      document.querySelectorAll('.tab-btn').forEach(function(btn) {
        if (btn.getAttribute('onclick') && btn.getAttribute('onclick').indexOf(tabName) !== -1) {
          btn.classList.add('active');
        }
      });
    }
  }
}

async function saveNotes() {
  var data = collectAllData();
  showStatus('Saving...');
  try {
    var checkRes = await fetch(
      SUPABASE_URL + '/rest/v1/assembly_notes?session_id=eq.' + sessionId + '&select=id',
      {
        headers: {
          'apikey': SUPABASE_KEY,
          'Authorization': 'Bearer ' + SUPABASE_KEY
        }
      }
    );
    var existing = await checkRes.json();
    if (existing.length > 0) {
      await fetch(
        SUPABASE_URL + '/rest/v1/assembly_notes?session_id=eq.' + sessionId,
        {
          method: 'PATCH',
          headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': 'Bearer ' + SUPABASE_KEY,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
          },
          body: JSON.stringify({ notes: data })
        }
      );
    } else {
      await fetch(
        SUPABASE_URL + '/rest/v1/assembly_notes',
        {
          method: 'POST',
          headers: {
            'apikey': SUPABASE_KEY,
            'Authorization': 'Bearer ' + SUPABASE_KEY,
            'Content-Type': 'application/json',
            'Prefer': 'return=minimal'
          },
          body: JSON.stringify({ session_id: sessionId, notes: data })
        }
      );
    }
    showStatus('Saved!');
    setTimeout(function() { showStatus(''); }, 2000);
  } catch (err) {
    console.error('Save error:', err);
    showStatus('Save failed');
  }
}

async function loadNotes() {
  try {
    showStatus('Loading...');
    var controller = new AbortController();
    var timeout = setTimeout(function() { controller.abort(); }, 3000);
    var res = await fetch(
      SUPABASE_URL + '/rest/v1/assembly_notes?session_id=eq.' + sessionId + '&select=notes',
      {
        headers: {
          'apikey': SUPABASE_KEY,
          'Authorization': 'Bearer ' + SUPABASE_KEY
        },
        signal: controller.signal
      }
    );
    clearTimeout(timeout);
    var result = await res.json();
    if (result.length > 0 && result[0].notes) {
      applyData(result[0].notes);
      showStatus('Data loaded!');
    } else {
      showStatus('Ready!');
    }
    setTimeout(function() { showStatus(''); }, 2000);
  } catch (err) {
    if (err.name === 'AbortError') {
      showStatus('Timed out - offline mode');
    } else {
      showStatus('Offline mode');
    }
  }
}

function debounceSave() {
  if (saveTimeout) clearTimeout(saveTimeout);
  saveTimeout = setTimeout(saveNotes, 1500);
  showStatus('Typing...');
}

function showStatus(msg) {
  if (statusEl) statusEl.textContent = msg;
}

function createStatusBar() {
  var bar = document.createElement('div');
  bar.id = 'save-status-bar';
  bar.style.cssText = 'position:fixed;bottom:0;left:0;right:0;background:linear-gradient(135deg,#2C5F8D,#1a3a5c);color:white;padding:8px 16px;display:flex;justify-content:space-between;align-items:center;font-size:13px;z-index:9999;box-shadow:0 -2px 10px rgba(0,0,0,0.3);';

  var left = document.createElement('div');
  left.textContent = 'Session: ' + sessionId.substring(0, 15) + '...';
  left.style.cssText = 'opacity:0.8;font-size:11px;';

  var right = document.createElement('div');
  right.style.cssText = 'display:flex;align-items:center;gap:10px;';

  statusEl = document.createElement('span');
  statusEl.style.cssText = 'background:rgba(255,255,255,0.15);padding:3px 10px;border-radius:10px;font-size:11px;';

  // Export PDF Button
  var pdfBtn = document.createElement('button');
  pdfBtn.textContent = 'Export PDF';
  pdfBtn.style.cssText = 'background:#70AD47;color:white;border:none;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;';
  pdfBtn.onclick = function() {
    document.querySelectorAll('textarea').forEach(function(ta) {
      ta.style.height = 'auto';
      ta.style.height = ta.scrollHeight + 'px';
      ta.style.overflow = 'visible';
    });
    setTimeout(function() { window.print(); }, 300);
  };

  // Share Button
  var shareBtn = document.createElement('button');
  shareBtn.textContent = 'Share';
  shareBtn.style.cssText = 'background:#5B9BD5;color:white;border:none;padding:5px 14px;border-radius:6px;cursor:pointer;font-size:12px;';
  shareBtn.onclick = function() {
    navigator.clipboard.writeText(window.location.href).then(function() {
      shareBtn.textContent = 'Copied!';
      setTimeout(function() { shareBtn.textContent = 'Share'; }, 2000);
    });
  };

  right.appendChild(statusEl);
  right.appendChild(pdfBtn);
  right.appendChild(shareBtn);
  bar.appendChild(left);
  bar.appendChild(right);
  document.body.appendChild(bar);
  document.body.style.paddingBottom = '45px';
}

// Listen for all form changes using event delegation
function setupEventListeners() {
  document.body.addEventListener('input', function(e) {
    if (e.target.matches('input[type="checkbox"], input[type="range"], textarea')) {
      debounceSave();
    }
  });
  document.body.addEventListener('change', function(e) {
    if (e.target.matches('input[type="checkbox"], input[type="range"]')) {
      debounceSave();
    }
  });
}

// Make stat boxes editable by clicking
function makeStatsEditable() {
  var statIds = ['hours-today', 'hours-week', 'rvs-count', 'studies-count'];
  statIds.forEach(function(id) {
    var el = document.getElementById(id);
    if (el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', function() {
        var current = el.textContent;
        var newVal = prompt('Enter new value:', current);
        if (newVal !== null) {
          el.textContent = newVal;
          debounceSave();
        }
      });
    }
  });
}

document.addEventListener('DOMContentLoaded', function() {
  sessionId = getSessionId();
  createStatusBar();
  setupEventListeners();
  makeStatsEditable();
  if ('requestIdleCallback' in window) {
    requestIdleCallback(function() { loadNotes(); });
  } else {
    setTimeout(loadNotes, 50);
  }
});
