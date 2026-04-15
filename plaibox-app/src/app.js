import { loadProjects, initFilter, setSidebarCallback, startWatching, setActiveByPath } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter, refreshActionBar } from './action-bar.js';
import { initNotes, loadNotes } from './notes.js';

const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

async function init() {
  initFilter();
  initNotes();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
    await loadNotes(project.path);
    invoke('set_last_project', { projectPath: project.path });
  });

  const projects = await loadProjects();
  await startWatching();

  // Refresh the action bar when project metadata changes (e.g. session field updated)
  await listen('projects-changed', () => {
    refreshActionBar();
  });

  // New project button — show an inline input in the sidebar
  document.getElementById('btn-new').addEventListener('click', () => {
    const existing = document.getElementById('new-project-input');
    if (existing) { existing.focus(); return; }

    const actionsDiv = document.getElementById('sidebar-actions');
    const input = document.createElement('input');
    input.id = 'new-project-input';
    input.type = 'text';
    input.placeholder = 'Project description...';
    input.style.cssText = 'width:100%;padding:6px 8px;background:var(--bg-dark);border:1px solid var(--accent);border-radius:4px;color:var(--text);font-size:12px;outline:none;margin-top:6px;';
    actionsDiv.appendChild(input);
    input.focus();

    const submit = () => {
      const desc = input.value.trim();
      input.remove();
      if (!desc) return;
      writeToActiveTerminal(`plaibox new "${desc}"\n`);
    };

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') submit();
      if (e.key === 'Escape') input.remove();
    });
    input.addEventListener('blur', () => input.remove());
  });

  // Sync button
  document.getElementById('btn-sync').addEventListener('click', () => {
    writeToActiveTerminal('plaibox sync pull\n');
  });

  // Notes panel resize handle
  const resizeHandle = document.getElementById('notes-resize-handle');
  const notesPanel = document.getElementById('notes-panel');
  resizeHandle.addEventListener('mousedown', (e) => {
    e.preventDefault();
    resizeHandle.classList.add('active');
    const onMove = (e) => {
      const newWidth = window.innerWidth - e.clientX;
      notesPanel.style.width = Math.max(160, Math.min(600, newWidth)) + 'px';
    };
    const onUp = () => {
      resizeHandle.classList.remove('active');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });

  // Restore last project
  const lastPath = await invoke('get_last_project');
  if (lastPath) {
    setActiveByPath(lastPath);
    const project = projects?.find(p => p.path === lastPath);
    if (project) {
      updateActionBar(project);
      await openProject(project.path);
      await loadNotes(project.path);
    }
  }
}

window.addEventListener('DOMContentLoaded', init);
