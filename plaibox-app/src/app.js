import { loadProjects, initFilter, setSidebarCallback, startWatching, setActiveByPath } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';
import { initNotes, loadNotes } from './notes.js';

const { invoke } = window.__TAURI__.core;

async function init() {
  initFilter();
  initNotes();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
    await loadNotes(project.path);
    // Save as last opened project
    invoke('set_last_project', { projectPath: project.path });
  });

  const projects = await loadProjects();
  await startWatching();

  // New project button
  document.getElementById('btn-new').addEventListener('click', () => {
    const description = prompt('New project description:');
    if (!description || !description.trim()) return;
    writeToActiveTerminal(`plaibox new "${description.trim()}"\n`);
  });

  // Sync button
  document.getElementById('btn-sync').addEventListener('click', () => {
    writeToActiveTerminal('plaibox sync pull\n');
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
