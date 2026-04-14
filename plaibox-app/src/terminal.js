const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;
import { Terminal } from '../node_modules/@xterm/xterm/lib/xterm.mjs';
import { FitAddon } from '../node_modules/@xterm/addon-fit/lib/addon-fit.mjs';

const projectTerminals = new Map();
let currentProjectPath = null;

const container = () => document.getElementById('terminal-container');
const tabBar = () => document.getElementById('terminal-tabs');

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
  const tabIndex = await invoke('spawn_terminal', { projectPath });
  const { terminal, fitAddon } = createXterm();

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

  const entry = { terminal, fitAddon, tabIndex, unlisten, label: null };

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

function showTab(projectPath) {
  const el = container();
  el.innerHTML = '';

  const state = projectTerminals.get(projectPath);
  if (!state || state.tabs.length === 0) return;

  renderTabBar(projectPath);

  const active = state.tabs[state.activeTab];
  const div = document.createElement('div');
  div.style.height = '100%';
  el.appendChild(div);

  active.terminal.open(div);
  active.fitAddon.fit();

  const { rows, cols } = active.terminal;
  invoke('resize_terminal', {
    projectPath,
    tabIndex: active.tabIndex,
    rows,
    cols,
  });

  active.terminal.focus();
}

function closeTab(projectPath, index) {
  const state = projectTerminals.get(projectPath);
  if (!state) return;

  const entry = state.tabs[index];
  entry.unlisten();
  entry.terminal.dispose();
  state.tabs.splice(index, 1);

  if (state.tabs.length === 0) {
    projectTerminals.delete(projectPath);
    container().innerHTML = '';
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
