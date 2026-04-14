const { invoke } = window.__TAURI__.core;
const { listen } = window.__TAURI__.event;

let allProjects = [];
let activeProjectPath = null;
let onProjectSelect = null;

export function setSidebarCallback(callback) {
  onProjectSelect = callback;
}

export async function loadProjects() {
  allProjects = await invoke('list_projects');
  renderSidebar(allProjects);
  return allProjects;
}

export function getActiveProject() {
  return allProjects.find(p => p.path === activeProjectPath) || null;
}

function renderSidebar(projects) {
  const container = document.getElementById('project-list');
  container.innerHTML = '';

  const groups = { sandbox: [], projects: [], archive: [] };
  for (const p of projects) {
    if (groups[p.space]) {
      groups[p.space].push(p);
    }
  }

  for (const [space, items] of Object.entries(groups)) {
    if (items.length === 0) continue;

    const group = document.createElement('div');
    group.className = 'space-group';

    const label = document.createElement('div');
    label.className = 'space-label';
    label.textContent = space.charAt(0).toUpperCase() + space.slice(1);
    group.appendChild(label);

    for (const project of items) {
      const item = document.createElement('div');
      item.className = 'project-item';
      if (project.path === activeProjectPath) {
        item.classList.add('active');
      }

      let displayName = project.name;
      if (project.private) {
        displayName += ' *';
      }
      item.textContent = displayName;
      item.title = project.description;

      item.addEventListener('click', () => {
        activeProjectPath = project.path;
        renderSidebar(projects);
        if (onProjectSelect) {
          onProjectSelect(project);
        }
      });

      group.appendChild(item);
    }

    container.appendChild(group);
  }
}

function applyFilterAndRender() {
  const query = document.getElementById('filter-input').value.toLowerCase();
  if (!query) {
    renderSidebar(allProjects);
    return;
  }
  const filtered = allProjects.filter(
    p => p.name.toLowerCase().includes(query) ||
         p.description.toLowerCase().includes(query)
  );
  renderSidebar(filtered);
}

export function initFilter() {
  const input = document.getElementById('filter-input');
  input.addEventListener('input', () => {
    applyFilterAndRender();
  });
}

export function setActiveByPath(path) {
  activeProjectPath = path;
  renderSidebar(allProjects);
}

export async function startWatching() {
  await listen('projects-changed', (event) => {
    allProjects = event.payload;
    applyFilterAndRender();
  });
}
