import { loadProjects, initFilter, setSidebarCallback } from './sidebar.js';

async function init() {
  initFilter();

  setSidebarCallback((project) => {
    document.getElementById('project-name').textContent = project.name;
    const statusSuffix = project.private ? '*' : '';
    document.getElementById('project-status').textContent = project.status + statusSuffix;
    console.log('Selected project:', project.path);
  });

  await loadProjects();
}

window.addEventListener('DOMContentLoaded', init);
