const { invoke } = window.__TAURI__.core;

async function init() {
  const config = await invoke('get_config');
  const projects = await invoke('list_projects');
  console.log('Config:', config);
  console.log('Projects:', projects);
  document.getElementById('project-name').textContent =
    projects.length > 0 ? 'Select a project' : 'No projects found';
}

window.addEventListener('DOMContentLoaded', init);
