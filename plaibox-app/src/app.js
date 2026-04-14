import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';
import { openProject } from './terminal.js';

async function init() {
  initFilter();

  setSidebarCallback(async (project) => {
    document.getElementById('project-name').textContent = project.name;
    const statusSuffix = project.private ? '*' : '';
    document.getElementById('project-status').textContent = project.status + statusSuffix;
    await openProject(project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
