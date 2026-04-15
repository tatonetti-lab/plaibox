const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
import { captureToNotes } from './notes.js';

const Terminal = globalThis.Terminal;
const FitAddon = globalThis.FitAddon?.FitAddon ?? globalThis.FitAddon;

const projectTerminals = new Map();
let currentProjectPath = null;

const container = () => document.getElementById('terminal-container');
const tabBar = () => document.getElementById('terminal-tabs');

function measureTerminalSize() {
  const el = container();
  const div = document.createElement('div');
  div.style.height = '100%';
  div.style.visibility = 'hidden';
  el.appendChild(div);

  const t = new Terminal({
    fontSize: 13,
    fontFamily: "'SF Mono', 'Menlo', 'Consolas', monospace",
  });
  const fit = new FitAddon();
  t.loadAddon(fit);
  t.open(div);
  fit.fit();
  const rows = t.rows;
  const cols = t.cols;
  t.dispose();
  el.removeChild(div);
  return { rows, cols };
}

function createXterm() {
  const terminal = new Terminal({
    fontSize: 13,
    fontFamily: "'SF Mono', 'Menlo', 'Consolas', monospace",
    theme: {
      background: '#0d0d1a',
      foreground: '#cccccc',
      cursor: '#7c6fff',
      selectionBackground: '#2a2a6a',
    },
    cursorBlink: true,
    scrollback: 10000,
  });
  const fitAddon = new FitAddon();
  terminal.loadAddon(fitAddon);
  return { terminal, fitAddon };
}

async function spawnTab(projectPath) {
  const { terminal, fitAddon } = createXterm();
  const { rows, cols } = measureTerminalSize();

  const tabIndex = await invoke('spawn_terminal', { projectPath, rows, cols });

  const eventName = `pty-output-${projectPath}-${tabIndex}`;
  const unlisten = await listen(eventName, (event) => {
    terminal.write(event.payload);
  });

  terminal.onData((data) => {
    invoke('write_terminal', { projectPath, tabIndex, data });
  });

  terminal.onResize(({ rows, cols }) => {
    invoke('resize_terminal', { projectPath, tabIndex, rows, cols });
  });

  // Create a persistent DOM element for this terminal
  const div = document.createElement('div');
  div.style.height = '100%';
  div.style.display = 'none';
  container().appendChild(div);
  terminal.open(div);

  const entry = { terminal, fitAddon, tabIndex, unlisten, label: null, div };

  if (!projectTerminals.has(projectPath)) {
    projectTerminals.set(projectPath, { tabs: [], activeTab: 0 });
  }

  const state = projectTerminals.get(projectPath);
  state.tabs.push(entry);
  state.activeTab = state.tabs.length - 1;

  return entry;
}

function renderTabBar(projectPath) {
  const bar = tabBar();
  bar.innerHTML = '';

  const state = projectTerminals.get(projectPath);
  if (!state) return;

  state.tabs.forEach((entry, i) => {
    const tab = document.createElement('div');
    tab.className = 'term-tab' + (i === state.activeTab ? ' active' : '');

    const label = document.createElement('span');
    label.className = 'term-tab-label';
    label.textContent = entry.label || `zsh${i > 0 ? ` (${i + 1})` : ''}`;
    tab.appendChild(label);

    tab.addEventListener('click', () => {
      state.activeTab = i;
      showTab(projectPath);
    });

    label.addEventListener('dblclick', (e) => {
      e.stopPropagation();
      const input = document.createElement('input');
      input.type = 'text';
      input.value = label.textContent;
      input.style.cssText = 'width:60px;font-size:11px;background:var(--bg-dark);color:var(--text-bright);border:1px solid var(--accent);padding:1px 4px;border-radius:2px;outline:none;';
      label.replaceWith(input);
      input.focus();
      input.select();

      const finish = () => {
        entry.label = input.value.trim() || label.textContent;
        renderTabBar(projectPath);
      };
      input.addEventListener('blur', finish);
      input.addEventListener('keydown', (ev) => {
        if (ev.key === 'Enter') finish();
        if (ev.key === 'Escape') renderTabBar(projectPath);
      });
    });

    if (state.tabs.length > 1) {
      const close = document.createElement('span');
      close.className = 'term-tab-close';
      close.textContent = '\u00d7';
      close.addEventListener('click', (e) => {
        e.stopPropagation();
        closeTab(projectPath, i);
      });
      tab.appendChild(close);
    }

    bar.appendChild(tab);
  });

  const addBtn = document.createElement('button');
  addBtn.id = 'tab-add';
  addBtn.textContent = '+';
  addBtn.addEventListener('click', async () => {
    await spawnTab(projectPath);
    showTab(projectPath);
  });
  bar.appendChild(addBtn);
}

function hideAllTerminals() {
  // Hide all terminal divs across all projects
  for (const [, state] of projectTerminals) {
    for (const entry of state.tabs) {
      entry.div.style.display = 'none';
    }
  }
}

function showTab(projectPath) {
  const state = projectTerminals.get(projectPath);
  if (!state || state.tabs.length === 0) return;

  hideAllTerminals();
  renderTabBar(projectPath);

  const active = state.tabs[state.activeTab];
  active.div.style.display = 'block';

  // Fit to current container size and sync with PTY
  active.fitAddon.fit();
  const { rows, cols } = active.terminal;
  invoke('resize_terminal', {
    projectPath,
    tabIndex: active.tabIndex,
    rows,
    cols,
  });

  active.terminal.focus();
  setupMakeNote(active.terminal);
}

let selectionDisposable = null;

function setupMakeNote(terminal) {
  if (selectionDisposable) {
    selectionDisposable.dispose();
  }
  const btn = document.getElementById('make-note-btn');

  selectionDisposable = terminal.onSelectionChange(() => {
    const selection = terminal.getSelection();
    if (selection && selection.trim().length > 0) {
      const rect = container().getBoundingClientRect();
      btn.style.display = 'block';
      btn.style.top = (rect.top + 8) + 'px';
      btn.style.right = (window.innerWidth - rect.right + 8) + 'px';

      btn.onclick = () => {
        captureToNotes(selection.trim());
        terminal.clearSelection();
        btn.style.display = 'none';
      };
    } else {
      btn.style.display = 'none';
    }
  });
}

function closeTab(projectPath, index) {
  const state = projectTerminals.get(projectPath);
  if (!state) return;

  const entry = state.tabs[index];
  entry.unlisten();
  entry.terminal.dispose();
  entry.div.remove();
  invoke('close_terminal', { projectPath, tabIndex: entry.tabIndex });
  state.tabs.splice(index, 1);

  if (state.tabs.length === 0) {
    projectTerminals.delete(projectPath);
    tabBar().innerHTML = '';
    return;
  }

  if (state.activeTab >= state.tabs.length) {
    state.activeTab = state.tabs.length - 1;
  }

  showTab(projectPath);
}

export async function openProject(projectPath) {
  currentProjectPath = projectPath;

  if (!projectTerminals.has(projectPath)) {
    await spawnTab(projectPath);
  }

  showTab(projectPath);
}

export function getCurrentProjectPath() {
  return currentProjectPath;
}

export function writeToActiveTerminal(data) {
  if (!currentProjectPath) return;
  const state = projectTerminals.get(currentProjectPath);
  if (!state) return;
  const active = state.tabs[state.activeTab];
  if (active) {
    invoke('write_terminal', {
      projectPath: currentProjectPath,
      tabIndex: active.tabIndex,
      data,
    });
  }
}

window.addEventListener('resize', () => {
  if (!currentProjectPath) return;
  const state = projectTerminals.get(currentProjectPath);
  if (!state) return;
  const active = state.tabs[state.activeTab];
  if (active) {
    active.fitAddon.fit();
  }
});
