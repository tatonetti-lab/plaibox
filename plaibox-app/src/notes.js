const { invoke } = window.__TAURI__.core;

let currentProjectPath = null;
let saveTimeout = null;

const contentEl = () => document.getElementById('notes-content');
const quickInput = () => document.getElementById('quick-note');

export function initNotes() {
  // Auto-save on edit with 500ms debounce
  contentEl().addEventListener('input', () => {
    if (!currentProjectPath) return;
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
      const content = contentEl().innerText;
      invoke('save_notes', { projectPath: currentProjectPath, content });
    }, 500);
  });

  // Quick-add on Enter
  quickInput().addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter' || !currentProjectPath) return;
    const text = quickInput().value.trim();
    if (!text) return;

    // Flush any pending debounced save before capturing
    if (saveTimeout) {
      clearTimeout(saveTimeout);
      saveTimeout = null;
      await invoke('save_notes', { projectPath: currentProjectPath, content: contentEl().innerText });
    }

    const updated = await invoke('capture_note', {
      projectPath: currentProjectPath,
      text,
    });
    contentEl().innerText = updated;
    quickInput().value = '';

    // Scroll to bottom
    contentEl().scrollTop = contentEl().scrollHeight;
  });
}

export async function loadNotes(projectPath) {
  // Flush pending save for the old project before switching
  if (saveTimeout && currentProjectPath) {
    clearTimeout(saveTimeout);
    saveTimeout = null;
    await invoke('save_notes', { projectPath: currentProjectPath, content: contentEl().innerText });
  }
  currentProjectPath = projectPath;
  const content = await invoke('get_notes', { projectPath });
  contentEl().innerText = content;
}

export async function captureToNotes(text) {
  if (!currentProjectPath) return;
  const updated = await invoke('capture_note', {
    projectPath: currentProjectPath,
    text,
  });
  contentEl().innerText = updated;
  contentEl().scrollTop = contentEl().scrollHeight;
}

export function clearNotes() {
  clearTimeout(saveTimeout);
  saveTimeout = null;
  currentProjectPath = null;
  contentEl().innerText = '';
}
