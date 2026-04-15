import { getCurrentProjectPath } from './terminal.js';

const { invoke } = window.__TAURI__.core;

let currentProject = null;
let writeToTerminal = null;
let inSession = false; // true when an AI session (Claude/Codex) is active in the terminal

export function setTerminalWriter(fn) {
  writeToTerminal = fn;
}

export function refreshActionBar() {
  // Re-fetch project data from the backend and update the bar
  if (!currentProject) return;
  invoke('list_projects').then(projects => {
    const updated = projects.find(p => p.path === currentProject.path);
    if (updated) {
      updateActionBar(updated);
    }
  });
}

export function updateActionBar(project) {
  currentProject = project;
  inSession = false; // reset when switching projects

  document.getElementById('project-name').textContent = project.name;
  const statusSuffix = project.private ? '*' : '';
  document.getElementById('project-status').textContent = project.status + statusSuffix;

  const buttons = document.getElementById('action-buttons');
  buttons.innerHTML = '';

  // AI session buttons
  if (project.session) {
    const resumeBtn = document.createElement('button');
    resumeBtn.textContent = 'Resume';
    resumeBtn.title = project.session;
    resumeBtn.style.borderColor = 'var(--accent)';
    resumeBtn.addEventListener('click', () => {
      const cmd = project.session.replace(/^(claude|codex)\b/, 'plaibox $1');
      runAction(cmd, false); // don't prefix — this IS the session launch
      inSession = true;
      resumeBtn.disabled = true;
      resumeBtn.textContent = 'Resumed';
    });
    buttons.appendChild(resumeBtn);
  } else {
    // No session — offer to launch Claude or Codex
    const claudeBtn = document.createElement('button');
    claudeBtn.textContent = 'Claude';
    claudeBtn.addEventListener('click', () => {
      runAction('plaibox claude', false);
      inSession = true;
      claudeBtn.remove();
      codexBtn.remove();
    });
    buttons.appendChild(claudeBtn);

    const codexBtn = document.createElement('button');
    codexBtn.textContent = 'Codex';
    codexBtn.addEventListener('click', () => {
      runAction('plaibox codex', false);
      inSession = true;
      claudeBtn.remove();
      codexBtn.remove();
    });
    buttons.appendChild(codexBtn);
  }

  const actions = getActionsForStatus(project.status, project.space);
  for (const action of actions) {
    const btn = document.createElement('button');
    btn.textContent = action.label;
    btn.disabled = action.disabled || false;

    if (!action.disabled) {
      btn.addEventListener('click', () => {
        runAction(action.command);
      });
    }

    buttons.appendChild(btn);
  }
}

function getActionsForStatus(status, space) {
  switch (space) {
    case 'sandbox':
      return [
        { label: 'Promote', command: 'plaibox promote' },
        { label: 'Archive', command: 'plaibox archive' },
        { label: 'Delete', command: '', disabled: true },
      ];
    case 'projects':
      return [
        { label: 'Archive', command: 'plaibox archive' },
        { label: 'Delete', command: '', disabled: true },
      ];
    case 'archive':
      return [
        { label: 'Delete', command: 'plaibox delete' },
      ];
    default:
      return [];
  }
}

function runAction(command, useSessionPrefix = true) {
  if (!command || !writeToTerminal) return;
  const prefix = (useSessionPrefix && inSession) ? '! ' : '';
  writeToTerminal(prefix + command + '\n');
}

export function clearActionBar() {
  document.getElementById('project-name').textContent = 'No project selected';
  document.getElementById('project-status').textContent = '';
  document.getElementById('action-buttons').innerHTML = '';
  currentProject = null;
}
