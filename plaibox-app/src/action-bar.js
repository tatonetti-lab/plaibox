import { getCurrentProjectPath } from './terminal.js';

const { invoke } = window.__TAURI__.core;

let currentProject = null;
let writeToTerminal = null;

export function setTerminalWriter(fn) {
  writeToTerminal = fn;
}

export function updateActionBar(project) {
  currentProject = project;

  document.getElementById('project-name').textContent = project.name;
  const statusSuffix = project.private ? '*' : '';
  document.getElementById('project-status').textContent = project.status + statusSuffix;

  const buttons = document.getElementById('action-buttons');
  buttons.innerHTML = '';

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

function runAction(command) {
  if (!command || !writeToTerminal) return;
  writeToTerminal(command + '\n');
}

export function clearActionBar() {
  document.getElementById('project-name').textContent = 'No project selected';
  document.getElementById('project-status').textContent = '';
  document.getElementById('action-buttons').innerHTML = '';
  currentProject = null;
}
