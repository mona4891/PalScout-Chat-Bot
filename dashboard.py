"""
dashboard.py
------------------------------------------------
The web dashboard's backend. Serves a small local website (default
http://localhost:5000) that shows live bot status and lets admins
manage players from a browser instead of editing config.txt or
typing chat commands.

Covers the Status and Players tabs. Moderation and AI & Search tabs
come next.

Runs as a background thread inside bot.py, the same pattern used for
the chat listener and Discord bridge.

Install: pip install flask
"""

import logging
import secrets
import os
from functools import wraps

import config as config_module

logger = logging.getLogger(__name__)

try:
    from flask import Flask, request, session, jsonify, render_template_string, redirect, send_file, Response
except ImportError:
    Flask = None

UPLOAD_DIR = os.path.join(config_module.BASE_DIR, "dashboard_uploads")
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


LOGIN_PAGE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>PalScout Dashboard</title>
<style>
body { font-family: -apple-system, Segoe UI, sans-serif; background: #1a2b26; color: #f0e0be;
       display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
.box { background: #24352f; padding: 2rem; border-radius: 12px; width: 280px; }
h1 { font-size: 1.2rem; margin: 0 0 1rem; }
input { width: 100%; padding: 10px; margin-bottom: 10px; border-radius: 6px; border: none;
        background: #1a2b26; color: #f0e0be; box-sizing: border-box; }
button { width: 100%; padding: 10px; border-radius: 6px; border: none; background: #3a5c4a;
         color: #f0e0be; cursor: pointer; font-weight: bold; }
.error { color: #ff9999; font-size: 0.85rem; margin-bottom: 10px; }
</style></head>
<body>
  <form class="box" method="POST">
    <h1>PalScout Dashboard</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <input type="password" name="password" placeholder="Dashboard password" autofocus>
    <button type="submit">Log in</button>
  </form>
</body></html>
"""

DASHBOARD_PAGE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>PalScout Dashboard</title>
<style>
* { box-sizing: border-box; }
body { font-family: -apple-system, Segoe UI, sans-serif; background: #1a2b26; color: #f0e0be;
       margin: 0; padding: 20px; }
.container { max-width: 900px; margin: 0 auto; }
body.has-bg { background-size: cover; background-position: center; background-attachment: fixed; }
.container.has-bg { background: var(--panel-bg, rgba(26,35,32,0.88)); border-radius: 12px; padding: 20px; }
h1 { font-size: 1.4rem; margin-bottom: 1.5rem; }
.tabs { display: flex; gap: 8px; margin-bottom: 1.25rem; }
.tab-btn { padding: 8px 16px; border-radius: 6px; border: none; background: #24352f;
           color: #a8a08a; cursor: pointer; font-size: 0.85rem; }
.tab-btn.active { background: #3a5c4a; color: #f0e0be; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.card { background: #24352f; border-radius: 10px; padding: 14px; }
.card .label { font-size: 0.8rem; color: #a8a08a; margin-bottom: 6px; }
.card .value { font-size: 1.4rem; font-weight: bold; }
.online { color: #6fcf8f; }
.offline { color: #ff8a8a; }
.offlinebanner { display: none; background: #3a2323; border: 1px solid #a85252; color: #ffb0b0;
                  padding: 10px 14px; border-radius: 8px; font-size: 0.82rem; margin-bottom: 1rem; }
.offlinebanner.show { display: block; }
.loadingbar { position: fixed; top: 0; left: 0; height: 3px; width: 0; background: #6fcf8f;
              transition: width 0.3s ease; z-index: 999; }
.loadingbar.active { width: 70%; transition: width 8s ease-out; }
table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.tablewrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
@media (max-width: 640px) {
  body { padding: 12px; }
  .container.has-bg { padding: 12px; }
  h1 { font-size: 1.15rem; }
  .tabs { gap: 6px; }
  .tab-btn { padding: 7px 11px; font-size: 0.78rem; }
  .grid { grid-template-columns: 1fr 1fr; }
  table { font-size: 0.78rem; }
  th, td { padding: 6px; }
  .modelinput { width: 90px; }
}
th { text-align: left; padding: 8px; color: #a8a08a; font-weight: 500; border-bottom: 1px solid #33463e; }
td { padding: 8px; border-bottom: 1px solid #243530; }
.playerstable { table-layout: fixed; }
.nearby { color: #a8a08a; font-size: 0.8rem; max-width: 0; overflow: hidden;
          text-overflow: ellipsis; white-space: nowrap; cursor: help; }
.badge { font-size: 0.75rem; padding: 2px 8px; border-radius: 10px; }
.badge-admin { background: #3a5c4a; color: #6fcf8f; }
.badge-player { background: #24352f; color: #a8a08a; }
.actioncell { display: flex; flex-wrap: wrap; gap: 6px; }
.smallbtn { font-size: 0.75rem; padding: 4px 8px; border-radius: 5px; border: none;
            background: #33463e; color: #f0e0be; cursor: pointer; white-space: nowrap; }
.smallbtn:hover { background: #3f584e; }
.empty { color: #a8a08a; text-align: center; padding: 20px; }
.toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%) translateY(20px);
         background: #24352f; border: 1px solid #3a5c4a; color: #f0e0be; padding: 12px 20px;
         border-radius: 8px; font-size: 0.85rem; box-shadow: 0 4px 16px rgba(0,0,0,0.3);
         opacity: 0; transition: opacity 0.25s, transform 0.25s; pointer-events: none; max-width: 400px; }
.toast.show { opacity: 1; transform: translateX(-50%) translateY(0); }
.toast.error { border-color: #a85252; }
.section-title { font-size: 1rem; margin: 1.5rem 0 10px; }
.section-title:first-child { margin-top: 0; }
.modcard { background: #24352f; border-radius: 10px; padding: 14px; }
.togglerow { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.hint { font-size: 0.75rem; color: #a8a08a; margin: 0 0 8px; }
.hint.faint { margin-top: 10px; opacity: 0.7; }
.wordtags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
.wordtag { font-size: 0.75rem; background: #1a2b26; border: 1px solid #33463e; border-radius: 10px;
           padding: 3px 10px; display: inline-flex; align-items: center; gap: 6px; }
.wordtag button { background: none; border: none; color: #a8a08a; cursor: pointer; padding: 0;
                   font-size: 0.9rem; line-height: 1; }
.addword { display: flex; gap: 8px; }
.addword input { flex: 1; padding: 8px; border-radius: 6px; border: 1px solid #33463e;
                  background: #1a2b26; color: #f0e0be; }
.notesitem { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;
             padding: 8px 0; border-bottom: 1px solid #243530; font-size: 0.85rem; }
.notesitem:last-child { border-bottom: none; }
.activityitem { padding: 10px 0; border-bottom: 1px solid #243530; font-size: 0.85rem; }
.activityitem:last-child { border-bottom: none; }
.activityitem .meta { color: #a8a08a; font-size: 0.75rem; margin-bottom: 3px; }
.activityitem .q { margin-bottom: 3px; }
.activityitem .a { color: #d8c9a3; }
.switch { position: relative; display: inline-block; width: 38px; height: 20px; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0;
          background: #33463e; border-radius: 20px; transition: 0.2s; }
.slider:before { position: absolute; content: ""; height: 14px; width: 14px; left: 3px; bottom: 3px;
                  background: #f0e0be; border-radius: 50%; transition: 0.2s; }
input:checked + .slider { background: #3a5c4a; }
input:checked + .slider:before { transform: translateX(18px); background: #6fcf8f; }
td.reasoncol { color: #a8a08a; }
.modelinput { width: 140px; padding: 5px 8px; border-radius: 5px; border: 1px solid #33463e;
              background: #1a2b26; color: #f0e0be; font-size: 0.8rem; }
.status-active { color: #6fcf8f; }
.status-cooldown { color: #ffb066; }
.status-off { color: #a8a08a; }
</style></head>
<body>
  <div class="container" id="mainContainer">
    <h1>PalScout Dashboard</h1>
    <div class="offlinebanner" id="offlineBanner">Can't reach the Palworld server -- check that it's running. Showing the last known data below.</div>
    <div class="tabs">
      <button class="tab-btn active" data-tab="status">Status</button>
      <button class="tab-btn" data-tab="players">Players</button>
      <button class="tab-btn" data-tab="moderation">Moderation</button>
      <button class="tab-btn" data-tab="ai">AI and search</button>
      <button class="tab-btn" data-tab="settings">Settings</button>
      <button class="tab-btn" data-tab="memory">Memory and activity</button>
      <button class="tab-btn" data-tab="customize">Customize</button>
    </div>

    <div class="tab-panel active" id="tab-status">
      <div class="grid">
        <div class="card"><div class="label">Connection</div><div class="value" id="connection">--</div></div>
        <div class="card"><div class="label">Players online</div><div class="value" id="players">--</div></div>
        <div class="card"><div class="label">In-game day</div><div class="value" id="ingame">--</div></div>
        <div class="card"><div class="label">Active AI provider</div><div class="value" id="provider">--</div></div>
      </div>
    </div>

    <div class="tab-panel" id="tab-players">
      <div class="tablewrap"><table class="playerstable">
        <thead>
          <tr><th style="width:110px;">Player</th><th style="width:90px;">HP</th><th>Nearby</th><th style="width:80px;">Role</th><th style="width:190px;">Actions</th></tr>
        </thead>
        <tbody id="playersBody">
          <tr><td colspan="5" class="empty">Loading...</td></tr>
        </tbody>
      </table></div>
    </div>

    <div class="tab-panel" id="tab-moderation">
      <div style="display:flex; justify-content:flex-end; margin-bottom:10px;">
        <button class="smallbtn" id="exportBackupBtn">Export backup</button>
      </div>
      <h3 class="section-title">Warnings</h3>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>Count</th><th>Last reason</th><th></th></tr></thead>
        <tbody id="warningsBody"><tr><td colspan="4" class="empty">Loading...</td></tr></tbody>
      </table></div>

      <h3 class="section-title">Active bans</h3>
      <div class="tablewrap"><table>
        <thead><tr><th>Player</th><th>Reason</th><th>Expires</th><th></th></tr></thead>
        <tbody id="bansBody"><tr><td colspan="4" class="empty">Loading...</td></tr></tbody>
      </table></div>

      <h3 class="section-title">Auto-moderation</h3>
      <div class="modcard">
        <div class="togglerow">
          <span>Filter enabled</span>
          <label class="switch"><input type="checkbox" id="autoModToggle"><span class="slider"></span></label>
        </div>
        <p class="hint">Banned words</p>
        <div id="wordTags" class="wordtags"></div>
        <div class="addword">
          <input type="text" id="newWordInput" placeholder="Add a word">
          <button class="smallbtn" id="addWordBtn">Add</button>
        </div>
        <p class="hint faint">Changes here are saved to config.txt automatically and persist across restarts.</p>
      </div>
    </div>

    <div class="tab-panel" id="tab-ai">
      <h3 class="section-title">Provider fallback chain</h3>
      <div class="tablewrap"><table>
        <thead><tr><th>Provider</th><th>Configured</th><th>Model</th><th>Status</th><th></th></tr></thead>
        <tbody id="providersBody"><tr><td colspan="5" class="empty">Loading...</td></tr></tbody>
      </table></div>

      <h3 class="section-title">Search</h3>
      <div class="modcard">
        <div class="togglerow"><span>Web search</span>
          <label class="switch"><input type="checkbox" id="webSearchToggle"><span class="slider"></span></label>
        </div>
        <div class="togglerow" style="margin-bottom:0;"><span>YouTube search</span>
          <label class="switch"><input type="checkbox" id="youtubeSearchToggle"><span class="slider"></span></label>
        </div>
      </div>

      <h3 class="section-title">Test the AI</h3>
      <div class="modcard">
        <p class="hint">Ask as</p>
        <select id="testPlayerSelect" class="modelinput" style="width:100%; margin-bottom:10px;">
          <option value="">No player online -- generic answer only, no position/nearby-Pal data</option>
        </select>
        <div class="addword">
          <input type="text" id="testQuestion" placeholder="Type a question...">
          <button class="smallbtn" id="testAskBtn">Ask</button>
        </div>
        <p class="hint" id="testResult" style="margin-top:10px;"></p>
      </div>
    </div>

    <div class="tab-panel" id="tab-settings">
      <h3 class="section-title">Bot identity</h3>
      <div class="modcard">
        <p class="hint">Bot name</p>
        <input type="text" id="settingBotName" style="width:100%; margin-bottom:10px;">
        <p class="hint">Command prefix</p>
        <input type="text" id="settingBotPrefix" style="width:80px; margin-bottom:10px;">
        <div><button class="smallbtn" id="saveIdentityBtn">Save</button></div>
      </div>

      <h3 class="section-title">Moderation limits</h3>
      <div class="modcard">
        <div class="togglerow">
          <span>Anti-spam cooldown</span>
          <label class="switch"><input type="checkbox" id="settingAntiSpam"><span class="slider"></span></label>
        </div>
        <p class="hint">Cooldown (seconds)</p>
        <input type="number" id="settingCooldown" class="modelinput" style="margin-bottom:10px;">
        <p class="hint">Warnings before auto-kick</p>
        <input type="number" id="settingMaxWarnings" class="modelinput" style="margin-bottom:10px;">
        <div><button class="smallbtn" id="saveLimitsBtn">Save</button></div>
      </div>

      <h3 class="section-title">Admins</h3>
      <div class="modcard">
        <p class="hint">Steam IDs allowed to use moderation commands</p>
        <div id="adminTags" class="wordtags"></div>
        <div class="addword">
          <input type="text" id="newAdminInput" placeholder="steam_7656...">
          <button class="smallbtn" id="addAdminBtn">Add</button>
        </div>
      </div>

      <h3 class="section-title">Discord bridge</h3>
      <div class="modcard">
        <p class="hint">Bot token</p>
        <input type="text" id="settingDiscordToken" style="width:100%; margin-bottom:10px;" placeholder="Leave blank to keep current value">
        <p class="hint">Channel ID</p>
        <input type="text" id="settingDiscordChannel" style="width:100%; margin-bottom:10px;">
        <div><button class="smallbtn" id="saveDiscordBtn">Save</button></div>
        <p class="hint faint">Discord changes require a bot restart to take effect.</p>
      </div>

      <h3 class="section-title">Dashboard</h3>
      <div class="modcard">
        <div class="togglerow" style="margin-bottom:0;">
          <span>Verbose request logging</span>
          <label class="switch"><input type="checkbox" id="settingVerboseLogging"><span class="slider"></span></label>
        </div>
        <p class="hint faint">When off, hides routine "GET /api/status 200" lines from the console. Turn on temporarily if you're debugging the dashboard itself.</p>
      </div>
    </div>

    <div class="tab-panel" id="tab-memory">
      <h3 class="section-title">Permanent memory</h3>
      <div class="modcard">
        <p class="hint">Notes players saved with !ai remember -- included in every future AI answer.</p>
        <div id="memoryNotesList"></div>
      </div>

      <h3 class="section-title">Recent AI activity</h3>
      <div class="modcard">
        <p class="hint">The last 30 questions asked and answered.</p>
        <div id="activityFeed"></div>
      </div>
    </div>

    <div class="tab-panel" id="tab-customize">
      <h3 class="section-title">Background image</h3>
      <div class="modcard">
        <p class="hint">Upload an image to use as the dashboard's background. Saved on this PC, applies for everyone who opens the dashboard.</p>
        <input type="file" id="bgFileInput" accept="image/png,image/jpeg,image/gif,image/webp" style="margin-bottom:10px;">
        <div style="display:flex; gap:8px;">
          <button class="smallbtn" id="uploadBgBtn">Upload</button>
          <button class="smallbtn" id="clearBgBtn">Clear</button>
        </div>
        <p class="hint faint" id="bgStatus" style="margin-top:10px;"></p>
      </div>

      <h3 class="section-title">Content panel color</h3>
      <div class="modcard">
        <p class="hint">Controls the color of the panel behind the dashboard's content, so text stays readable over your background image.</p>
        <div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
          <input type="color" id="panelColorInput" style="width:44px; height:32px; padding:0; border:none; border-radius:6px; background:none;">
          <div style="flex:1;">
            <p class="hint" style="margin-bottom:4px;">Opacity: <span id="panelOpacityValue">88</span>%</p>
            <input type="range" id="panelOpacityInput" min="20" max="100" style="width:100%;">
          </div>
        </div>
        <button class="smallbtn" id="savePanelColorBtn">Save</button>
      </div>
    </div>
  </div>
  <div class="toast" id="toast"></div>
  <div class="loadingbar" id="loadingBar"></div>
<script>
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

let toastTimer = null;
function showToast(message, isError) {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = 'toast show' + (isError ? ' error' : '');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.className = 'toast'; }, 3500);
}

async function refreshStatus() {
  try {
    const resp = await fetch('/api/status');
    if (resp.status === 401) { window.location = '/login'; return; }
    const data = await resp.json();
    document.getElementById('connection').innerHTML =
      data.connected ? '<span class="online">Online</span>' : '<span class="offline">Offline</span>';
    document.getElementById('players').textContent = data.player_count;
    document.getElementById('ingame').textContent = data.in_game_day_time;
    document.getElementById('provider').textContent = data.active_provider;
    document.getElementById('offlineBanner').classList.toggle('show', !data.connected);
  } catch (e) {
    document.getElementById('connection').innerHTML = '<span class="offline">Error</span>';
    document.getElementById('offlineBanner').classList.add('show');
  }
}

async function refreshPlayers() {
  try {
    const resp = await fetch('/api/players');
    if (resp.status === 401) { window.location = '/login'; return; }
    const players = await resp.json();
    const tbody = document.getElementById('playersBody');
    if (!players || players.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="empty">No players online</td></tr>';
      return;
    }
    let html = '';
    for (const p of players) {
      const nearby = (p.nearby && p.nearby.length)
        ? p.nearby.map(n => `${escapeHtml(n.name)} (${n.distance}m)`).join(', ')
        : '--';
      const badge = p.is_admin
        ? '<span class="badge badge-admin">Admin</span>'
        : '<span class="badge badge-player">Player</span>';
      html += `<tr>
        <td>${escapeHtml(p.name)}</td>
        <td>${p.hp} / ${p.max_hp}</td>
        <td class="nearby" title="${nearby}">${nearby}</td>
        <td>${badge}</td>
        <td>
          <div class="actioncell">
            <button class="smallbtn" onclick="doAction('kick','${escapeHtml(p.name)}')">Kick</button>
            <button class="smallbtn" onclick="doAction('ban','${escapeHtml(p.name)}')">Ban</button>
            <button class="smallbtn" onclick="doAction('warn','${escapeHtml(p.name)}')">Warn</button>
          </div>
        </td>
      </tr>`;
    }
    tbody.innerHTML = html;
  } catch (e) {
    document.getElementById('playersBody').innerHTML = '<tr><td colspan="5" class="empty">Error loading players</td></tr>';
  }
}

async function doAction(action, name) {
  let reason = 'Action taken from dashboard';
  if (action !== 'kick' || confirm(`Kick ${name}?`)) {
    if (action === 'ban' && !confirm(`Permanently ban ${name}?`)) return;
    if (action === 'warn') {
      reason = prompt(`Reason for warning ${name}:`);
      if (!reason) return;
    }
    const resp = await fetch(`/api/${action}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name, reason: reason })
    });
    const data = await resp.json();
    showToast(data.result || 'Something went wrong.', !resp.ok);
    setTimeout(refreshPlayers, 1000);
  }
}

function showLoading() {
  document.getElementById('loadingBar').classList.add('active');
}
function hideLoading() {
  const bar = document.getElementById('loadingBar');
  bar.classList.remove('active');
  bar.style.width = '0';
  // Force a reflow so the next showLoading() re-triggers the CSS
  // transition from 0 instead of silently doing nothing because the
  // browser thinks the width never changed.
  void bar.offsetWidth;
}

async function activateTab(tab) {
  const btn = document.querySelector(`.tab-btn[data-tab="${tab}"]`);
  if (!btn) return;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('tab-' + tab).classList.add('active');
  localStorage.setItem('palscout_active_tab', tab);

  const refreshers = {
    players: refreshPlayers, moderation: refreshModeration, ai: refreshAiTab,
    settings: refreshSettings, customize: refreshCustomize, memory: refreshMemory,
  };
  const refresher = refreshers[tab];
  if (refresher) {
    showLoading();
    try { await refresher(); } finally { hideLoading(); }
  }
}

document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => activateTab(btn.dataset.tab));
});

// Restore whichever tab was active before the page was reloaded,
// instead of always starting back on Status.
const savedTab = localStorage.getItem('palscout_active_tab');
if (savedTab && document.querySelector(`.tab-btn[data-tab="${savedTab}"]`)) {
  activateTab(savedTab);
}

async function refreshModeration() {
  refreshWarnings();
  refreshBans();
  refreshAutoMod();
}

async function refreshWarnings() {
  const resp = await fetch('/api/warnings');
  if (resp.status === 401) { window.location = '/login'; return; }
  const warnings = await resp.json();
  const tbody = document.getElementById('warningsBody');
  if (!warnings.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty">No active warnings</td></tr>'; return; }
  tbody.innerHTML = warnings.map(w => `
    <tr>
      <td>${escapeHtml(w.name)}</td>
      <td>${w.count}</td>
      <td class="reasoncol">${escapeHtml(w.last_reason)}</td>
      <td><button class="smallbtn" onclick="clearWarnings('${escapeHtml(w.player_id)}')">Clear</button></td>
    </tr>`).join('');
}

async function refreshBans() {
  const resp = await fetch('/api/bans');
  if (resp.status === 401) { window.location = '/login'; return; }
  const bans = await resp.json();
  const tbody = document.getElementById('bansBody');
  if (!bans.length) { tbody.innerHTML = '<tr><td colspan="4" class="empty">No active bans</td></tr>'; return; }
  tbody.innerHTML = bans.map(b => `
    <tr>
      <td>${escapeHtml(b.name)}</td>
      <td class="reasoncol">${escapeHtml(b.reason)}</td>
      <td>${escapeHtml(b.expires)}</td>
      <td><button class="smallbtn" onclick="unban('${escapeHtml(b.player_id)}')">Unban</button></td>
    </tr>`).join('');
}

async function refreshAutoMod() {
  const resp = await fetch('/api/automod');
  if (resp.status === 401) { window.location = '/login'; return; }
  const data = await resp.json();
  document.getElementById('autoModToggle').checked = data.enabled;
  document.getElementById('wordTags').innerHTML = data.banned_words.map(w =>
    `<span class="wordtag">${escapeHtml(w)}<button onclick="removeWord('${escapeHtml(w)}')">&times;</button></span>`
  ).join('') || '<span class="hint">No banned words yet</span>';
}

document.getElementById('exportBackupBtn').addEventListener('click', () => {
  window.location = '/api/moderation/export';
});

async function clearWarnings(playerId) {
  const resp = await fetch('/api/clearwarnings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: playerId })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  refreshWarnings();
}

async function unban(playerId) {
  if (!confirm('Lift this ban?')) return;
  const resp = await fetch('/api/unban', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_id: playerId })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  refreshBans();
}

document.getElementById('autoModToggle').addEventListener('change', async (e) => {
  const resp = await fetch('/api/automod/toggle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: e.target.checked })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('addWordBtn').addEventListener('click', async () => {
  const input = document.getElementById('newWordInput');
  const word = input.value.trim();
  if (!word) return;
  await fetch('/api/automod/words', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ word: word })
  });
  input.value = '';
  refreshAutoMod();
});

async function removeWord(word) {
  await fetch('/api/automod/words', {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ word: word })
  });
  refreshAutoMod();
}

async function refreshAiTab() {
  const resp = await fetch('/api/ai/status');
  if (resp.status === 401) { window.location = '/login'; return; }
  const data = await resp.json();

  document.getElementById('webSearchToggle').checked = data.web_search_enabled;
  document.getElementById('youtubeSearchToggle').checked = data.youtube_search_enabled;

  const tbody = document.getElementById('providersBody');
  tbody.innerHTML = data.providers.map(p => {
    let statusHtml;
    if (!p.configured) statusHtml = '<span class="status-off">Not configured</span>';
    else if (p.in_cooldown) statusHtml = `<span class="status-cooldown">Cooldown (${p.cooldown_remaining}s)</span>`;
    else statusHtml = '<span class="status-active">Ready</span>';

    return `<tr>
      <td>${escapeHtml(p.display_name)}</td>
      <td>${p.configured ? 'Yes' : 'No'}</td>
      <td><input class="modelinput" type="text" value="${escapeHtml(p.model)}" id="model-${p.key}"></td>
      <td>${statusHtml}</td>
      <td><button class="smallbtn" onclick="saveModel('${p.key}')">Save</button></td>
    </tr>`;
  }).join('');

  // Populate the "ask as" dropdown with real connected players, so
  // the test uses a real position for nearby-Pal grounding instead
  // of a fake name with no location in the game world.
  const playersResp = await fetch('/api/players');
  const players = playersResp.ok ? await playersResp.json() : [];
  const select = document.getElementById('testPlayerSelect');
  select.innerHTML = players.length
    ? players.map(p => `<option value="${escapeHtml(p.name)}">${escapeHtml(p.name)}</option>`).join('')
    : '<option value="">No player online -- generic answer only, no position/nearby-Pal data</option>';
}

async function saveModel(providerKey) {
  const value = document.getElementById('model-' + providerKey).value.trim();
  const resp = await fetch('/api/ai/model', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ provider: providerKey, model: value })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
}

document.getElementById('webSearchToggle').addEventListener('change', async (e) => {
  const resp = await fetch('/api/search/toggle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature: 'web', enabled: e.target.checked })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('youtubeSearchToggle').addEventListener('change', async (e) => {
  const resp = await fetch('/api/search/toggle', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ feature: 'youtube', enabled: e.target.checked })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('testAskBtn').addEventListener('click', async () => {
  const input = document.getElementById('testQuestion');
  const question = input.value.trim();
  if (!question) return;
  const asPlayer = document.getElementById('testPlayerSelect').value;
  const resultEl = document.getElementById('testResult');
  resultEl.textContent = 'Asking...';
  const resp = await fetch('/api/ai/test', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question: question, as_player: asPlayer })
  });
  const data = await resp.json();
  resultEl.innerHTML = `<strong>${escapeHtml(data.provider || 'No provider')}:</strong> ${escapeHtml(data.answer)}`;
});

async function refreshSettings() {
  const resp = await fetch('/api/settings');
  if (resp.status === 401) { window.location = '/login'; return; }
  const data = await resp.json();

  document.getElementById('settingBotName').value = data.bot_name;
  document.getElementById('settingBotPrefix').value = data.bot_prefix;
  document.getElementById('settingAntiSpam').checked = data.anti_spam_enabled;
  document.getElementById('settingCooldown').value = data.cooldown_seconds;
  document.getElementById('settingMaxWarnings').value = data.max_warnings_before_kick;
  document.getElementById('settingDiscordChannel').value = data.discord_channel_id || '';
  document.getElementById('settingDiscordToken').placeholder =
    data.discord_token_set ? 'Currently set -- leave blank to keep it' : 'Leave blank to keep current value';
  document.getElementById('settingVerboseLogging').checked = data.dashboard_verbose_logging;

  document.getElementById('adminTags').innerHTML = data.admin_steam_ids.map(id =>
    `<span class="wordtag">${escapeHtml(id)}<button onclick="removeAdmin('${escapeHtml(id)}')">&times;</button></span>`
  ).join('') || '<span class="hint">No admins configured</span>';
}

document.getElementById('settingVerboseLogging').addEventListener('change', async (e) => {
  const resp = await fetch('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dashboard_verbose_logging: e.target.checked })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('saveIdentityBtn').addEventListener('click', async () => {
  const resp = await fetch('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      bot_name: document.getElementById('settingBotName').value.trim(),
      bot_prefix: document.getElementById('settingBotPrefix').value.trim(),
    })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('saveLimitsBtn').addEventListener('click', async () => {
  const resp = await fetch('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      anti_spam_enabled: document.getElementById('settingAntiSpam').checked,
      cooldown_seconds: document.getElementById('settingCooldown').value,
      max_warnings_before_kick: document.getElementById('settingMaxWarnings').value,
    })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
});

document.getElementById('saveDiscordBtn').addEventListener('click', async () => {
  const token = document.getElementById('settingDiscordToken').value.trim();
  const channel = document.getElementById('settingDiscordChannel').value.trim();
  const resp = await fetch('/api/settings', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ discord_token: token || undefined, discord_channel_id: channel })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  document.getElementById('settingDiscordToken').value = '';
});

document.getElementById('addAdminBtn').addEventListener('click', async () => {
  const input = document.getElementById('newAdminInput');
  const steamId = input.value.trim();
  if (!steamId) return;
  await fetch('/api/settings/admins', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ steam_id: steamId })
  });
  input.value = '';
  refreshSettings();
});

async function removeAdmin(steamId) {
  await fetch('/api/settings/admins', {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ steam_id: steamId })
  });
  refreshSettings();
}

function hexToRgba(hex, opacityPercent) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${opacityPercent / 100})`;
}

function applyPanelColor(hex, opacityPercent) {
  document.documentElement.style.setProperty('--panel-bg', hexToRgba(hex, opacityPercent));
}

function applyBackground(hasBackground) {
  const body = document.body;
  const container = document.getElementById('mainContainer');
  if (hasBackground) {
    body.style.backgroundImage = `url('/api/background/image?v=${Date.now()}')`;
    body.classList.add('has-bg');
    container.classList.add('has-bg');
  } else {
    body.style.backgroundImage = 'none';
    body.classList.remove('has-bg');
    container.classList.remove('has-bg');
  }
}

async function refreshCustomize() {
  const resp = await fetch('/api/background');
  if (resp.status === 401) { window.location = '/login'; return; }
  const data = await resp.json();
  document.getElementById('bgStatus').textContent = data.has_background
    ? 'A background image is currently set.'
    : 'No background image set.';
  applyBackground(data.has_background);

  document.getElementById('panelColorInput').value = data.panel_color;
  document.getElementById('panelOpacityInput').value = data.panel_opacity;
  document.getElementById('panelOpacityValue').textContent = data.panel_opacity;
  applyPanelColor(data.panel_color, data.panel_opacity);
}

document.getElementById('panelOpacityInput').addEventListener('input', (e) => {
  document.getElementById('panelOpacityValue').textContent = e.target.value;
});

document.getElementById('savePanelColorBtn').addEventListener('click', async () => {
  const color = document.getElementById('panelColorInput').value;
  const opacity = parseInt(document.getElementById('panelOpacityInput').value, 10);
  const resp = await fetch('/api/background/panel', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ color: color, opacity: opacity })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  applyPanelColor(color, opacity);
});

document.getElementById('uploadBgBtn').addEventListener('click', async () => {
  const fileInput = document.getElementById('bgFileInput');
  const file = fileInput.files[0];
  if (!file) { showToast('Choose an image first.', true); return; }
  const formData = new FormData();
  formData.append('file', file);
  const resp = await fetch('/api/background', { method: 'POST', body: formData });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  if (resp.ok) refreshCustomize();
});

document.getElementById('clearBgBtn').addEventListener('click', async () => {
  const resp = await fetch('/api/background', { method: 'DELETE' });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  refreshCustomize();
});

// Apply the saved background (if any) as soon as the page loads, not
// just when visiting the Customize tab -- it should be visible from
// the moment the dashboard opens, on Status or any other tab.
(async () => {
  try {
    const resp = await fetch('/api/background');
    if (resp.ok) {
      const data = await resp.json();
      applyBackground(data.has_background);
      applyPanelColor(data.panel_color, data.panel_opacity);
    }
  } catch (e) { /* background is a visual extra, fine to skip silently on error */ }
})();

async function refreshMemory() {
  const [notesResp, activityResp] = await Promise.all([
    fetch('/api/memory'),
    fetch('/api/activity'),
  ]);
  if (notesResp.status === 401 || activityResp.status === 401) { window.location = '/login'; return; }

  const notes = await notesResp.json();
  const notesList = document.getElementById('memoryNotesList');
  notesList.innerHTML = notes.length
    ? notes.map((note, i) => `
        <div class="notesitem">
          <span>${escapeHtml(note)}</span>
          <button class="smallbtn" onclick="deleteNote(${i})">Delete</button>
        </div>`).join('')
    : '<p class="hint">No saved notes yet.</p>';

  const activity = await activityResp.json();
  const feed = document.getElementById('activityFeed');
  feed.innerHTML = activity.length
    ? activity.slice().reverse().map(a => `
        <div class="activityitem">
          <div class="meta">${escapeHtml(a.time)} -- ${escapeHtml(a.player)} -- via ${escapeHtml(a.provider)}</div>
          <div class="q">Q: ${escapeHtml(a.question)}</div>
          <div class="a">A: ${escapeHtml(a.answer)}</div>
        </div>`).join('')
    : '<p class="hint">No AI activity yet.</p>';
}

async function deleteNote(index) {
  const resp = await fetch('/api/memory', {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: index })
  });
  const data = await resp.json();
  showToast(data.result, !resp.ok);
  refreshMemory();
}

refreshStatus();
setInterval(refreshStatus, 5000);
</script>
</body></html>
"""


def _require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "not authenticated"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def _get_nearby_creatures(server_api, player_raw, max_results=5, max_distance_m=100):
    """
    Computes nearby creatures for one player, reusing the same
    position/distance logic as build_game_context() in palworld_api.py,
    but returning structured data instead of a text summary, since the
    dashboard needs to render this as a list, not a sentence.
    """
    game_data = server_api.get_game_data()
    actors = game_data.get("ActorData", [])
    creatures = [a for a in actors if a.get("UnitType") and a.get("UnitType") != "Player"]

    px = player_raw.get("LocationX", 0)
    py = player_raw.get("LocationY", 0)
    pz = player_raw.get("LocationZ", 0)

    nearby = []
    for c in creatures:
        dx = c.get("LocationX", 0) - px
        dy = c.get("LocationY", 0) - py
        dz = c.get("LocationZ", 0) - pz
        distance_m = ((dx**2 + dy**2 + dz**2) ** 0.5) / 100
        if distance_m < max_distance_m:
            name = c.get("NickName") or c.get("Type", "Unknown")
            nearby.append({"name": name, "distance": round(distance_m)})

    nearby.sort(key=lambda n: n["distance"])
    return nearby[:max_results]


def create_dashboard_app(command_handler, dashboard_password, chat_filter=None):
    """
    Builds and returns the Flask app. Kept as a factory function
    (rather than a module-level app) so it can be given a reference to
    the bot's already-running command_handler (and everything it holds
    -- server_api, ai_chain, moderation, admin checks) instead of
    duplicating state or reconnecting to anything.

    chat_filter is passed separately since it's created in bot.py
    alongside (not inside) command_handler.
    """
    if not Flask:
        logger.error("[DASHBOARD] Flask is not installed. Run: pip install flask")
        return None

    server_api = command_handler.server_api
    ai_chain = command_handler.ai_chain
    moderation = command_handler.moderation

    app = Flask(__name__)
    app.secret_key = secrets.token_hex(16)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            if request.form.get("password") == dashboard_password:
                session["logged_in"] = True
                return redirect("/")
            return render_template_string(LOGIN_PAGE, error="Incorrect password.")
        return render_template_string(LOGIN_PAGE, error=None)

    @app.route("/")
    @_require_login
    def index():
        return render_template_string(DASHBOARD_PAGE)

    @app.route("/api/status")
    @_require_login
    def api_status():
        game_data = server_api.get_game_data()
        players = server_api.get_players()

        in_game_day = game_data.get("InGameDays", "?")
        in_game_time = game_data.get("InGameTime", "?")
        try:
            time_display = "Day " + str(in_game_day) + ", " + format(float(in_game_time), ".1f") + "h"
        except (ValueError, TypeError):
            time_display = "Day " + str(in_game_day) + ", " + str(in_game_time)

        active_provider = "None configured"
        for name, _, is_configured in ai_chain.chain:
            if is_configured() and not ai_chain.provider_fail_time.get(name):
                active_provider = name.capitalize()
                break

        return jsonify({
            "connected": server_api.connected,
            "player_count": len(players),
            "in_game_day_time": time_display,
            "active_provider": active_provider,
        })

    @app.route("/api/players")
    @_require_login
    def api_players():
        players = server_api.get_players()
        result = []
        for p in players:
            raw = p.get("raw", {})
            result.append({
                "name": p.get("name", "Unknown"),
                "hp": raw.get("HP", "?"),
                "max_hp": raw.get("MaxHP", "?"),
                "is_admin": command_handler.is_admin(p.get("name", "")),
                "nearby": _get_nearby_creatures(server_api, raw),
            })
        return jsonify(result)

    @app.route("/api/kick", methods=["POST"])
    @_require_login
    def api_kick():
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        if command_handler.is_admin(name):
            return jsonify({"result": "Admins cannot be kicked or banned through this action."}), 403
        result = moderation.kick_player(name, data.get("reason", "Kicked from dashboard"), issued_by="Dashboard")
        return jsonify({"result": result})

    @app.route("/api/ban", methods=["POST"])
    @_require_login
    def api_ban():
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        if command_handler.is_admin(name):
            return jsonify({"result": "Admins cannot be kicked or banned through this action."}), 403
        result = moderation.ban_player(name, data.get("reason", "Banned from dashboard"), issued_by="Dashboard")
        return jsonify({"result": result})

    @app.route("/api/warn", methods=["POST"])
    @_require_login
    def api_warn():
        data = request.get_json(force=True, silent=True) or {}
        name = data.get("name")
        if not name:
            return jsonify({"error": "name is required"}), 400
        if command_handler.is_admin(name):
            return jsonify({"result": "Admins cannot be warned through this action."}), 403
        result = moderation.warn_player(name, data.get("reason", "No reason given"), issued_by="Dashboard")
        return jsonify({"result": result})

    @app.route("/api/warnings")
    @_require_login
    def api_warnings():
        result = []
        for player_id, entry in moderation.get_all_warnings().items():
            reasons = entry.get("reasons", [])
            last_reason = reasons[-1]["reason"] if reasons else "--"
            result.append({
                "player_id": player_id,
                "name": entry.get("name", player_id),
                "count": entry.get("count", 0),
                "last_reason": last_reason,
            })
        return jsonify(result)

    @app.route("/api/clearwarnings", methods=["POST"])
    @_require_login
    def api_clearwarnings():
        data = request.get_json(force=True, silent=True) or {}
        player_id = data.get("player_id")
        if not player_id:
            return jsonify({"error": "player_id is required"}), 400
        entry = moderation.warnings.get(player_id)
        name = entry.get("name", player_id) if entry else player_id
        if player_id in moderation.warnings:
            del moderation.warnings[player_id]
            moderation._save_json(moderation.warnings_file, moderation.warnings)
        return jsonify({"result": f"Cleared warnings for {name}."})

    @app.route("/api/bans")
    @_require_login
    def api_bans():
        import time as _time
        result = []
        for player_id, entry in moderation.get_all_bans().items():
            expires_at = entry.get("expires_at")
            if not expires_at:
                expires = "Permanent"
            else:
                remaining_min = round((expires_at - _time.time()) / 60)
                expires = f"{remaining_min} min left" if remaining_min > 0 else "Expired"
            result.append({
                "player_id": player_id,
                "name": entry.get("name", player_id),
                "reason": entry.get("reason", "--"),
                "expires": expires,
            })
        return jsonify(result)

    @app.route("/api/unban", methods=["POST"])
    @_require_login
    def api_unban():
        data = request.get_json(force=True, silent=True) or {}
        player_id = data.get("player_id")
        if not player_id:
            return jsonify({"error": "player_id is required"}), 400
        result = moderation.unban_player_by_id(player_id)
        return jsonify({"result": result})

    @app.route("/api/automod")
    @_require_login
    def api_automod():
        if not chat_filter:
            return jsonify({"enabled": False, "banned_words": []})
        return jsonify({"enabled": chat_filter.enabled, "banned_words": chat_filter.banned_words})

    @app.route("/api/automod/toggle", methods=["POST"])
    @_require_login
    def api_automod_toggle():
        if not chat_filter:
            return jsonify({"result": "Auto-moderation is not available."}), 400
        data = request.get_json(force=True, silent=True) or {}
        chat_filter.enabled = bool(data.get("enabled"))
        state = "enabled" if chat_filter.enabled else "disabled"
        config_module.update_config_value("AUTO_MODERATION_ENABLED", "true" if chat_filter.enabled else "false")
        return jsonify({"result": f"Auto-moderation {state}."})

    @app.route("/api/automod/words", methods=["POST", "DELETE"])
    @_require_login
    def api_automod_words():
        if not chat_filter:
            return jsonify({"result": "Auto-moderation is not available."}), 400
        data = request.get_json(force=True, silent=True) or {}
        word = (data.get("word") or "").strip().lower()
        if not word:
            return jsonify({"error": "word is required"}), 400
        if request.method == "POST":
            if word not in chat_filter.banned_words:
                chat_filter.banned_words.append(word)
        else:
            if word in chat_filter.banned_words:
                chat_filter.banned_words.remove(word)
        config_module.update_config_value("BANNED_WORDS", ",".join(chat_filter.banned_words))
        return jsonify({"result": "ok"})

    @app.route("/api/ai/status")
    @_require_login
    def api_ai_status():
        import time as _time
        provider_display_names = {
            "groq": "Groq", "cerebras": "Cerebras", "mistral": "Mistral", "openrouter": "OpenRouter",
        }
        providers = []
        for key, _, is_configured in ai_chain.chain:
            fail_time = ai_chain.provider_fail_time.get(key)
            in_cooldown = bool(fail_time and (_time.time() - fail_time) < ai_chain.failure_cooldown_seconds)
            cooldown_remaining = (
                round(ai_chain.failure_cooldown_seconds - (_time.time() - fail_time)) if in_cooldown else 0
            )
            providers.append({
                "key": key,
                "display_name": provider_display_names.get(key, key.capitalize()),
                "configured": is_configured(),
                "model": ai_chain.config.get(f"{key.upper()}_MODEL", ""),
                "in_cooldown": in_cooldown,
                "cooldown_remaining": cooldown_remaining,
            })

        return jsonify({
            "providers": providers,
            "web_search_enabled": command_handler.web_search_enabled,
            "youtube_search_enabled": command_handler.youtube_search_enabled,
        })

    @app.route("/api/ai/model", methods=["POST"])
    @_require_login
    def api_ai_model():
        data = request.get_json(force=True, silent=True) or {}
        provider = data.get("provider")
        model = (data.get("model") or "").strip()
        if not provider or not model:
            return jsonify({"error": "provider and model are required"}), 400
        ai_chain.config[f"{provider.upper()}_MODEL"] = model
        config_module.update_config_value(f"{provider.upper()}_MODEL", model)
        return jsonify({"result": f"{provider.capitalize()} model updated to '{model}'."})

    @app.route("/api/search/toggle", methods=["POST"])
    @_require_login
    def api_search_toggle():
        data = request.get_json(force=True, silent=True) or {}
        feature = data.get("feature")
        enabled = bool(data.get("enabled"))
        if feature == "web":
            command_handler.web_search_enabled = enabled
            config_module.update_config_value("WEB_SEARCH_ENABLED", "true" if enabled else "false")
        elif feature == "youtube":
            command_handler.youtube_search_enabled = enabled
            config_module.update_config_value("YOUTUBE_SEARCH_ENABLED", "true" if enabled else "false")
        else:
            return jsonify({"error": "unknown feature"}), 400
        state = "enabled" if enabled else "disabled"
        return jsonify({"result": f"{feature.capitalize()} search {state}."})

    @app.route("/api/ai/test", methods=["POST"])
    @_require_login
    def api_ai_test():
        data = request.get_json(force=True, silent=True) or {}
        question = (data.get("question") or "").strip()
        if not question:
            return jsonify({"error": "question is required"}), 400
        # Use a real connected player's name if one was selected, so
        # build_game_context() has an actual position to calculate
        # nearby Pals from -- a fake name like "Dashboard" has no
        # in-game location, so the AI would get no creature data at
        # all and could misread "pal" as meaning another player.
        as_player = (data.get("as_player") or "").strip() or "Dashboard"
        answer = command_handler.ask_ai(as_player, question)
        provider = ai_chain.last_used_provider
        provider_display = provider.capitalize() if provider else "No provider"
        return jsonify({"answer": answer, "provider": provider_display})

    @app.route("/api/settings")
    @_require_login
    def api_settings_get():
        token = ai_chain.config.get("DISCORD_BOT_TOKEN", "")
        token_set = bool(token) and "your-" not in token.lower()
        return jsonify({
            "bot_name": command_handler.bot_name,
            "bot_prefix": command_handler.bot_prefix,
            "anti_spam_enabled": command_handler.anti_spam_enabled,
            "cooldown_seconds": command_handler.cooldown_seconds,
            "max_warnings_before_kick": moderation.max_warnings_before_kick,
            "admin_steam_ids": sorted(command_handler.admin_steam_ids),
            "discord_channel_id": ai_chain.config.get("DISCORD_CHANNEL_ID", ""),
            "discord_token_set": token_set,
            "dashboard_verbose_logging": logging.getLogger("werkzeug").level <= logging.INFO,
        })

    @app.route("/api/settings", methods=["POST"])
    @_require_login
    def api_settings_post():
        data = request.get_json(force=True, silent=True) or {}
        changed = []

        if "bot_name" in data and data["bot_name"]:
            command_handler.bot_name = data["bot_name"]
            server_api.chat_prefix = f"[{data['bot_name']}] "
            config_module.update_config_value("BOT_NAME", data["bot_name"])
            changed.append("bot name")

        if "bot_prefix" in data and data["bot_prefix"]:
            command_handler.bot_prefix = data["bot_prefix"]
            config_module.update_config_value("BOT_PREFIX", data["bot_prefix"])
            changed.append("prefix")

        if "anti_spam_enabled" in data:
            command_handler.anti_spam_enabled = bool(data["anti_spam_enabled"])
            config_module.update_config_value("ANTI_SPAM_ENABLED", "true" if data["anti_spam_enabled"] else "false")
            changed.append("anti-spam")

        if "cooldown_seconds" in data and str(data["cooldown_seconds"]).strip():
            try:
                seconds = int(data["cooldown_seconds"])
                command_handler.cooldown_seconds = seconds
                config_module.update_config_value("COOLDOWN_SECONDS", str(seconds))
                changed.append("cooldown")
            except ValueError:
                return jsonify({"result": "Cooldown must be a whole number."}), 400

        if "max_warnings_before_kick" in data and str(data["max_warnings_before_kick"]).strip():
            try:
                limit = int(data["max_warnings_before_kick"])
                moderation.max_warnings_before_kick = limit
                config_module.update_config_value("MAX_WARNINGS_BEFORE_KICK", str(limit))
                changed.append("warning limit")
            except ValueError:
                return jsonify({"result": "Warning limit must be a whole number."}), 400

        discord_changed = False
        if data.get("discord_token"):
            ai_chain.config["DISCORD_BOT_TOKEN"] = data["discord_token"]
            config_module.update_config_value("DISCORD_BOT_TOKEN", data["discord_token"])
            discord_changed = True

        if "discord_channel_id" in data:
            ai_chain.config["DISCORD_CHANNEL_ID"] = data["discord_channel_id"]
            config_module.update_config_value("DISCORD_CHANNEL_ID", data["discord_channel_id"])
            discord_changed = True

        if discord_changed:
            changed.append("Discord settings (restart required to take effect)")

        if "dashboard_verbose_logging" in data:
            verbose = bool(data["dashboard_verbose_logging"])
            logging.getLogger("werkzeug").setLevel(logging.INFO if verbose else logging.WARNING)
            config_module.update_config_value("DASHBOARD_VERBOSE_LOGGING", "true" if verbose else "false")
            changed.append("dashboard logging")

        if not changed:
            return jsonify({"result": "Nothing to update."})
        return jsonify({"result": f"Updated: {', '.join(changed)}."})

    @app.route("/api/settings/admins", methods=["POST", "DELETE"])
    @_require_login
    def api_settings_admins():
        data = request.get_json(force=True, silent=True) or {}
        steam_id = (data.get("steam_id") or "").strip()
        if not steam_id:
            return jsonify({"error": "steam_id is required"}), 400

        if request.method == "POST":
            command_handler.admin_steam_ids.add(steam_id)
        else:
            command_handler.admin_steam_ids.discard(steam_id)

        config_module.update_config_value("ADMIN_STEAM_IDS", ",".join(sorted(command_handler.admin_steam_ids)))
        return jsonify({"result": "ok"})

    def _current_background_path():
        """Finds the currently saved background file, if any, checking
        each allowed extension since we don't store the extension
        separately in config -- simpler to just look for what's there."""
        if not os.path.isdir(UPLOAD_DIR):
            return None
        for ext in ALLOWED_IMAGE_EXTENSIONS:
            candidate = os.path.join(UPLOAD_DIR, f"background{ext}")
            if os.path.exists(candidate):
                return candidate
        return None

    @app.route("/api/background")
    @_require_login
    def api_background_status():
        return jsonify({
            "has_background": _current_background_path() is not None,
            "panel_color": ai_chain.config.get("DASHBOARD_PANEL_COLOR", "#1a2320"),
            "panel_opacity": int(ai_chain.config.get("DASHBOARD_PANEL_OPACITY", "88")),
        })

    @app.route("/api/background/image")
    @_require_login
    def api_background_image():
        path = _current_background_path()
        if not path:
            return jsonify({"error": "no background set"}), 404
        return send_file(path)

    @app.route("/api/background", methods=["POST"])
    @_require_login
    def api_background_upload():
        if "file" not in request.files:
            return jsonify({"result": "No file received."}), 400
        file = request.files["file"]
        if not file.filename:
            return jsonify({"result": "No file selected."}), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({"result": "Only PNG, JPG, GIF, or WEBP images are allowed."}), 400

        try:
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            # Clear any existing background (possibly a different
            # extension) before saving the new one, so we never end up
            # with two stale files satisfying _current_background_path().
            for old_ext in ALLOWED_IMAGE_EXTENSIONS:
                old_path = os.path.join(UPLOAD_DIR, f"background{old_ext}")
                if os.path.exists(old_path):
                    os.remove(old_path)
            file.save(os.path.join(UPLOAD_DIR, f"background{ext}"))
        except OSError as e:
            logger.error(f"[DASHBOARD] Failed to save background image: {e}")
            return jsonify({"result": "Failed to save the image."}), 500

        return jsonify({"result": "Background image updated."})

    @app.route("/api/background", methods=["DELETE"])
    @_require_login
    def api_background_clear():
        path = _current_background_path()
        if path:
            try:
                os.remove(path)
            except OSError as e:
                logger.error(f"[DASHBOARD] Failed to remove background image: {e}")
                return jsonify({"result": "Failed to remove the image."}), 500
        return jsonify({"result": "Background cleared."})

    @app.route("/api/background/panel", methods=["POST"])
    @_require_login
    def api_background_panel():
        data = request.get_json(force=True, silent=True) or {}
        color = (data.get("color") or "").strip()
        opacity = data.get("opacity")

        if not color or not color.startswith("#") or len(color) != 7:
            return jsonify({"result": "Invalid color value."}), 400
        try:
            opacity = int(opacity)
            if not (0 <= opacity <= 100):
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"result": "Opacity must be a number between 0 and 100."}), 400

        ai_chain.config["DASHBOARD_PANEL_COLOR"] = color
        ai_chain.config["DASHBOARD_PANEL_OPACITY"] = str(opacity)
        config_module.update_config_value("DASHBOARD_PANEL_COLOR", color)
        config_module.update_config_value("DASHBOARD_PANEL_OPACITY", str(opacity))
        return jsonify({"result": "Panel color saved."})

    @app.route("/api/memory")
    @_require_login
    def api_memory_get():
        return jsonify(command_handler.permanent_memory.get_notes())

    @app.route("/api/memory", methods=["DELETE"])
    @_require_login
    def api_memory_delete():
        data = request.get_json(force=True, silent=True) or {}
        index = data.get("index")
        if index is None:
            return jsonify({"error": "index is required"}), 400
        removed = command_handler.permanent_memory.delete_note(int(index))
        if removed:
            return jsonify({"result": "Note deleted."})
        return jsonify({"result": "Note not found (it may have already been removed)."}), 404

    @app.route("/api/activity")
    @_require_login
    def api_activity():
        return jsonify(list(command_handler.recent_activity))

    @app.route("/api/moderation/export")
    @_require_login
    def api_moderation_export():
        import json
        from datetime import datetime

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "warnings": moderation.get_all_warnings(),
            "bans": moderation.get_all_bans(),
        }
        filename = f"palscout_moderation_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return Response(
            json.dumps(export_data, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    return app


def start_dashboard(command_handler, dashboard_password, port=5000, chat_filter=None, verbose_logging=False):
    """
    Builds and runs the dashboard. Meant to be called in its own
    background thread from bot.py, same pattern as the chat listener
    and Discord bridge.
    """
    app = create_dashboard_app(command_handler, dashboard_password, chat_filter=chat_filter)
    if not app:
        return

    if not verbose_logging:
        # Flask's built-in dev server logs every single HTTP request
        # (e.g. "GET /api/status 200") via the werkzeug logger by
        # default -- fine while debugging the dashboard itself, but
        # clutters the console during normal use, since the frontend
        # polls /api/status every few seconds. Quieting this down to
        # only show actual errors, not routine successful requests.
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    logger.info("[DASHBOARD] Starting on http://localhost:" + str(port))
    try:
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
    except Exception as e:
        logger.error("[DASHBOARD] Failed to start: " + str(e))
