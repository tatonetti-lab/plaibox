import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';
import { openProject, writeToActiveTerminal } from './terminal.js';
import { updateActionBar, setTerminalWriter } from './action-bar.js';

async function init() {
  initFilter();
  setTerminalWriter(writeToActiveTerminal);

  setSidebarCallback(async (project) => {
    updateActionBar(project);
    await openProject(project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
