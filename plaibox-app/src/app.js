import { loadProjects, initFilter, setSidebarCallback, startWatching } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';
import { initNotes, loadNotes } from './notes.js';

async function init() {
  initFilter();
  initNotes();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
    await loadNotes(project.path);
  });

  await loadProjects();
  await startWatching();
}

window.addEventListener('DOMContentLoaded', init);
