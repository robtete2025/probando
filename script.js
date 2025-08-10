const buttons = document.querySelectorAll('.tab-buttons button[data-tab]');
const contents = document.querySelectorAll('.tab-content');

const loginSection = document.getElementById('login-section');
const mainContent = document.getElementById('main-content');
const loginBtn = document.getElementById('login-btn');
const passwordInput = document.getElementById('password');
const loginError = document.getElementById('login-error');
const logoutBtn = document.getElementById('logout-btn');

const searchInput = document.getElementById('search-input');

let currentRole = null; // "admin" or "worker"

buttons.forEach(btn => {
  btn.addEventListener('click', () => {
    buttons.forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    const target = btn.getAttribute('data-tab');
    contents.forEach(content => {
      content.style.display = (content.id === target) ? 'block' : 'none';
    });

    searchInput.value = '';
    filterTable('');

    updateFormVisibility();
  });
});

loginBtn.addEventListener('click', () => {
  const pwd = passwordInput.value.trim();
  if (pwd === 'cash2025') {
    currentRole = 'admin';
    loginSuccess();
  } else if (pwd === 'exitos2025') {
    currentRole = 'worker';
    loginSuccess();
  } else {
    loginError.style.display = 'block';
  }
});

function loginSuccess() {
  loginError.style.display = 'none';
  loginSection.style.display = 'none';
  mainContent.style.display = 'block';
  passwordInput.value = '';

  setupEditButtons(currentRole);
  updateFormVisibility();

  updateDiasRestantesAll();
}

logoutBtn.addEventListener('click', () => {
  currentRole = null;
  mainContent.style.display = 'none';
  loginSection.style.display = 'block';
  clearEditing();
  searchInput.value = '';
  updateFormVisibility();
});

function setupEditButtons(role) {
  const editButtons = document.querySelectorAll('.edit-btn');
  const deleteButtons = document.querySelectorAll('.delete-btn');
  
  if(role === 'admin') {
    editButtons.forEach(btn => {
      btn.disabled = false;
      btn.style.display = 'inline-block';
      btn.addEventListener('click', startEditing);
    });
    deleteButtons.forEach(btn => {
      btn.disabled = false;
      btn.style.display = 'inline-block';
      btn.addEventListener('click', deleteRow);
    });
  } else {
    editButtons.forEach(btn => {
      btn.disabled = true;
      btn.style.display = 'none';
      btn.removeEventListener('click', startEditing);
    });
    deleteButtons.forEach(btn => {
      btn.disabled = true;
      btn.style.display = 'none';
      btn.removeEventListener('click', deleteRow);
    });
  }
}

function startEditing(e) {
  const btn = e.target;
  const tr = btn.closest('tr');

  if(tr.classList.contains('editing')) return;

  tr.classList.add('editing');

  // Para editar, menos columnas días restantes y editar/eliminar
  for(let i=0; i < tr.cells.length - 3; i++) {
    const cell = tr.cells[i];
    const text = cell.textContent;
    cell.innerHTML = `<input type="text" value="${text}"/>`;
  }

  // Para fecha límite (col 6) usamos input date
  const fechaCell = tr.cells[6];
  const fechaText = fechaCell.textContent.trim();
  fechaCell.innerHTML = `<input type="date" value="${fechaText}" />`;

  // Columna días restantes (7) no editable, vacía
  tr.cells[7].textContent = '';

  // Botones guardar y cancelar
  const editCell = tr.cells[tr.cells.length -3];
  editCell.innerHTML = `
    <button class="save-btn">💾</button>
    <button class="cancel-btn">❌</button>
  `;

  editCell.querySelector('.save-btn').addEventListener('click', () => saveEdit(tr));
  editCell.querySelector('.cancel-btn').addEventListener('click', () => cancelEdit(tr));
}

function saveEdit(tr) {
  const inputs = tr.querySelectorAll('input');
  inputs.forEach((input, idx) => {
    tr.cells[idx].textContent = input.value.trim() || '—';
  });

  // Recalcular días restantes y aplicar color
  updateDiasRestantes(tr);

  finishEditing(tr);
}

function cancelEdit(tr) {
  const inputs = tr.querySelectorAll('input');
  inputs.forEach((input, idx) => {
    tr.cells[idx].textContent = input.defaultValue || '—';
  });

  finishEditing(tr);
}

function finishEditing(tr) {
  tr.classList.remove('editing');
  const editCell = tr.cells[tr.cells.length -3];
  editCell.innerHTML = `<button class="edit-btn">✏️</button>`;

  if(currentRole === 'admin') {
    editCell.querySelector('.edit-btn').addEventListener('click', startEditing);
  }
}

function clearEditing() {
  document.querySelectorAll('tr.editing').forEach(tr => {
    cancelEdit(tr);
  });
}

searchInput.addEventListener('input', () => {
  const searchTerm = searchInput.value.toLowerCase();
  filterTable(searchTerm);
});

function filterTable(searchTerm) {
  const activeTab = document.querySelector('.tab-content:not([style*="display: none"])');
  if (!activeTab) return;

  const tbody = activeTab.querySelector('tbody');
  if (!tbody) return;

  Array.from(tbody.rows).forEach(row => {
    const rowText = row.textContent.toLowerCase();
    if(rowText.includes(searchTerm)) {
      row.style.display = '';
    } else {
      row.style.display = 'none';
    }
  });
}

function updateFormVisibility() {
  const clientesForm = document.getElementById('form-clientes');
  const trabajadoresForm = document.getElementById('form-trabajadores');
  const activeTabBtn = document.querySelector('.tab-buttons button.active');
  if(!activeTabBtn) return;
  const tab = activeTabBtn.getAttribute('data-tab');

  if(currentRole === 'admin') {
    clientesForm.style.display = (tab === 'clientes') ? 'block' : 'none';
    trabajadoresForm.style.display = (tab === 'trabajadores') ? 'block' : 'none';
  } else {
    clientesForm.style.display = 'none';
    trabajadoresForm.style.display = 'none';
  }
}

// Añadir cliente
const addClientForm = document.getElementById('add-client-form');
addClientForm.addEventListener('submit', e => {
  e.preventDefault();
  const nombre = document.getElementById('cli-nombre').value.trim();
  const telefono = document.getElementById('cli-telefono').value.trim();
  const dni = document.getElementById('cli-dni').value.trim();
  const lugar = document.getElementById('cli-lugar').value.trim();
  const cuota = document.getElementById('cli-cuota').value.trim();
  const monto = document.getElementById('cli-monto').value.trim();
  const fechaLimite = document.getElementById('cli-fecha').value;

  if(!nombre || !telefono || !dni || !lugar || !cuota || !monto || !fechaLimite) return;

  const tbody = document.getElementById('clientes-tbody');
  const tr = document.createElement('tr');

  tr.innerHTML = `
    <td>${nombre}</td>
    <td>${telefono}</td>
    <td>${dni}</td>
    <td>${lugar}</td>
    <td>${cuota}</td>
    <td>${monto}</td>
    <td>${fechaLimite}</td>
    <td></td>
    <td class="edit-col"><button class="edit-btn">✏️</button></td>
    <td class="delete-col"><button class="delete-btn">🗑️</button></td>
  `;

  tbody.appendChild(tr);
  updateDiasRestantes(tr);

  if(currentRole === 'admin') {
    tr.querySelector('.edit-btn').addEventListener('click', startEditing);
    tr.querySelector('.delete-btn').addEventListener('click', deleteRow);
  }

  addClientForm.reset();
});

// Añadir trabajador
const addWorkerForm = document.getElementById('add-worker-form');
addWorkerForm.addEventListener('submit', e => {
  e.preventDefault();
  const nombre = document.getElementById('worker-nombre').value.trim();
  const dni = document.getElementById('worker-dni').value.trim();
  const telefono = document.getElementById('worker-telefono').value.trim();

  if(!nombre || !dni || !telefono) return;

  const tbody = document.getElementById('trabajadores-tbody');
  const tr = document.createElement('tr');

  tr.innerHTML = `
    <td>${nombre}</td>
    <td>${dni}</td>
    <td>${telefono}</td>
    <td class="edit-col"><button class="edit-btn">✏️</button></td>
    <td class="delete-col"><button class="delete-btn">🗑️</button></td>
  `;

  tbody.appendChild(tr);

  if(currentRole === 'admin') {
    tr.querySelector('.edit-btn').addEventListener('click', startEditing);
    tr.querySelector('.delete-btn').addEventListener('click', deleteRow);
  }

  addWorkerForm.reset();
});

function deleteRow(e) {
  const btn = e.target;
  const tr = btn.closest('tr');
  const nombre = tr.cells[0].textContent;

  if(confirm(`¿Seguro que quieres eliminar a ${nombre}?`)) {
    tr.remove();
  }
}

function updateDiasRestantes(tr) {
  // Solo clientes tienen fecha límite (col 6)
  const tbodyId = tr.parentElement.id;
  if(tbodyId !== 'clientes-tbody') return;

  const fechaLimiteText = tr.cells[6].textContent.trim();
  if(!fechaLimiteText) {
    tr.cells[7].textContent = '';
    tr.classList.remove('plazo-rojo', 'plazo-amarillo');
    return;
  }

  const hoy = new Date();
  const fechaLimite = new Date(fechaLimiteText + 'T23:59:59'); // Para considerar fin del día
  const diffMs = fechaLimite - hoy;
  const diffDias = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  tr.cells[7].textContent = diffDias >= 0 ? diffDias : 0;

  // Quitar clases
  tr.classList.remove('plazo-rojo', 'plazo-amarillo');

  if(diffDias <= 4 && diffDias >= 0) {
    tr.classList.add('plazo-rojo');
  } else if(diffDias <= 7 && diffDias > 4) {
    tr.classList.add('plazo-amarillo');
  }
}

function updateDiasRestantesAll() {
  const clientesRows = document.querySelectorAll('#clientes-tbody tr');
  clientesRows.forEach(tr => {
    updateDiasRestantes(tr);
  });
}

// Actualizar días restantes y resaltar cada minuto para que sea automático mientras la app esté abierta
setInterval(() => {
  if(mainContent.style.display !== 'none') {
    updateDiasRestantesAll();
  }
}, 60000); // cada 60 segundos

// Inicializa la pestaña activa
document.addEventListener('DOMContentLoaded', () => {
  buttons[0].click();
});
