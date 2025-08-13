// ---- Fetch helper seguro ----
async function fetchJSON(url, method = 'GET', body = null) {
    const opts = { method, credentials: 'include', headers: {} };
    if (body) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);

    // Si la sesión expiró (401), limpiar y redirigir
    if (res.status === 401) {
        localStorage.removeItem('rol');
        window.location.href = '/';
        return { res, data: null };
    }

    let data = null;
    try {
        data = await res.json();
    } catch(e) {}
    return { res, data };
}

// ---- Control de inactividad local ----
const INACTIVITY_LIMIT = 30 * 60 * 1000; // 30 min
let inactivityTimer, warningTimer;

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);

    warningTimer = setTimeout(() => {
        if (confirm("Tu sesión expirará en 1 minuto. ¿Quieres mantenerla?")) {
            fetch('/auth/check', { credentials: 'include' });
            resetInactivityTimer();
        }
    }, INACTIVITY_LIMIT - 60 * 1000);

    inactivityTimer = setTimeout(() => {
        alert("Sesión cerrada por inactividad.");
        localStorage.removeItem('rol');
        fetch('/auth/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/';
    }, INACTIVITY_LIMIT);
}

['mousemove', 'keydown', 'click'].forEach(evt => {
    window.addEventListener(evt, resetInactivityTimer);
});

// ---- ADMIN: cargar clientes (Corregido) ----
// CORREGIDO: la funcion cargarClientesAdmin ahora tiene los onclick en los botones
async function cargarClientesAdmin() {
    const tBody = document.querySelector('#clientesTableAdmin tbody');
    if (!tBody) return;

    try {
        const { res, data } = await fetchJSON('/api/clientes');
        if (!res.ok) {
            console.error('Error al cargar clientes:', data?.msg || res.statusText);
            tBody.innerHTML = '<tr><td colspan="15">Error al cargar clientes.</td></tr>';
            return;
        }

        tBody.innerHTML = '';
        data.forEach(cliente => {
            if (cliente.prestamos && cliente.prestamos.length > 0) {
                cliente.prestamos.forEach(prestamo => {
                    const tr = document.createElement('tr');
                    let claseAlerta = '';
                    let diasRestantes = 'N/A';
                    if (prestamo.fecha_fin) {
                        const fechaHoy = new Date();
                        const fechaFin = new Date(prestamo.fecha_fin);
                        const diferenciaMs = fechaFin.getTime() - fechaHoy.getTime();
                        diasRestantes = Math.ceil(diferenciaMs / (1000 * 60 * 60 * 24));
                        if (diasRestantes <= 3 && diasRestantes >= 0) {
                            claseAlerta = 'alerta-rojo';
                        } else if (diasRestantes <= 10 && diasRestantes > 3) {
                            claseAlerta = 'alerta-amarillo';
                        } else if (diasRestantes < 0) {
                            claseAlerta = 'alerta-vencido';
                        }
                    }
                    tr.className = claseAlerta;
                    tr.innerHTML = `
                        <td>${cliente.id}</td>
                        <td>${cliente.dni || 'N/A'}</td>
                        <td>${cliente.nombre || ''}</td>
                        <td>${cliente.direccion || ''}</td>
                        <td>${cliente.telefono || ''}</td>
                        <td>${(prestamo.monto || 0).toFixed(2)}</td>
                        <td>${(prestamo.saldo || 0).toFixed(2)}</td>
                        <td>${prestamo.tipo || 'N/A'}</td>
                        <td>${prestamo.dias_transcurridos || 'N/A'}</td>
                        <td>${(prestamo.pagos ? prestamo.pagos.length : 0)}</td>
                        <td>${(prestamo.deuda_vencida || 0).toFixed(2)}</td>
                        <td>${(prestamo.cuota || 0).toFixed(2)}</td>
                        <td>${prestamo.fecha_inicio || 'N/A'}</td>
                        <td>${prestamo.fecha_fin || 'N/A'}</td>
                        <td>
                            <button class="action-btn" onclick="abrirPrestamoModal(${cliente.id})"><i class="fas fa-plus"></i></button>
                            <button class="action-btn" onclick="abrirEditClienteModal(${cliente.id}, '${cliente.nombre}', '${cliente.direccion}', '${cliente.telefono}')"><i class="fas fa-edit"></i></button>
                            <button class="action-btn delete-btn" onclick="eliminarCliente(${cliente.id})"><i class="fas fa-trash-alt"></i></button>
                        </td>
                    `;
                    tBody.appendChild(tr);
                });
            } else {
                 const tr = document.createElement('tr');
                 tr.innerHTML = `
                    <td>${cliente.id}</td>
                    <td>${cliente.dni || 'N/A'}</td>
                    <td>${cliente.nombre || ''}</td>
                    <td>${cliente.direccion || ''}</td>
                    <td>${cliente.telefono || ''}</td>
                    <td colspan="9" class="text-center">No tiene préstamos activos</td>
                    <td>
                        <button class="action-btn" onclick="abrirPrestamoModal(${cliente.id})"><i class="fas fa-plus"></i></button>
                        <button class="action-btn" onclick="abrirEditClienteModal(${cliente.id}, '${cliente.nombre}', '${cliente.direccion}', '${cliente.telefono}')"><i class="fas fa-edit"></i></button>
                        <button class="action-btn delete-btn" onclick="eliminarCliente(${cliente.id})"><i class="fas fa-trash-alt"></i></button>
                    </td>
                `;
                tBody.appendChild(tr);
            }
        });
    } catch (error) {
        console.error('Error al cargar clientes:', error);
        tBody.innerHTML = '<tr><td colspan="15">Error al cargar clientes.</td></tr>';
    }
}
// AÑADIDO: Funcion para abrir el modal de edicion de cliente
function abrirEditClienteModal(id, nombre, direccion, telefono) {
    document.getElementById('editClienteId').value = id;
    document.getElementById('editClienteNombre').value = nombre;
    document.getElementById('editClienteDireccion').value = direccion;
    document.getElementById('editClienteTelefono').value = telefono;
    document.getElementById('editClienteModal').style.display = 'block';
}

// AÑADIDO: Funcion para cerrar el modal de edicion de cliente
function cerrarEditClienteModal() {
    document.getElementById('editClienteModal').style.display = 'none';
    document.getElementById('editClienteForm').reset();
}

// AÑADIDO: Manejar el envío del formulario modal para editar clientes
document.getElementById('editClienteForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const id = document.getElementById('editClienteId').value;
    const nombre = document.getElementById('editClienteNombre').value;
    const direccion = document.getElementById('editClienteDireccion').value;
    const telefono = document.getElementById('editClienteTelefono').value;

    const body = { nombre, direccion, telefono };
    const { res, data } = await fetchJSON(`/api/clientes/${id}`, 'PUT', body);

    if (res.ok) {
        alert('Cliente actualizado con éxito.');
        cerrarEditClienteModal();
        await cargarClientesAdmin();
    } else {
        alert(data.msg || 'Error al actualizar el cliente.');
    }
});

// ---- Funciones para el resumen de créditos ----
async function cargarResumenCreditos() {
    try {
        const { res, data } = await fetchJSON('/api/resumen_creditos');
        if (res.ok) {
            document.getElementById('totalCreditos').textContent = data.totalCreditos;
            document.getElementById('creditosVigentes').textContent = data.creditosVigentes;
            document.getElementById('creditosVencidos').textContent = data.creditosVencidos;
            document.getElementById('deudaTotal').textContent = data.deudaTotal;
        } else {
            console.error('Error al cargar el resumen de créditos:', data.msg);
        }
    } catch (error) {
        console.error('Error en la conexión con la API de resumen:', error);
    }
}

// ---- Funciones para el modal de Trabajadores ----
function abrirModal(id = null, username = '', dni = '', telefono = '') {
    document.getElementById('workerId').value = id || '';
    document.getElementById('usernameInput').value = username;
    document.getElementById('dniInput').value = dni;
    document.getElementById('telefonoInput').value = telefono;

    const modalTitle = document.getElementById('modalTitle');
    const passwordInput = document.getElementById('passwordInput');
    const submitBtn = document.getElementById('submitBtn');

    if (id) {
        modalTitle.innerText = 'Editar Trabajador';
        passwordInput.required = false;
        passwordInput.placeholder = 'Dejar en blanco para no cambiar';
        submitBtn.innerText = 'Actualizar';
    } else {
        modalTitle.innerText = 'Añadir Trabajador';
        passwordInput.required = true;
        passwordInput.placeholder = '';
        submitBtn.innerText = 'Guardar';
    }

    document.getElementById('workerModal').style.display = 'block';
}

function cerrarModal() {
    document.getElementById('workerModal').style.display = 'none';
    document.getElementById('workerForm').reset();
    document.getElementById('passwordInput').required = true;
    document.getElementById('passwordInput').placeholder = '';
}

function agregarTrabajador() {
    abrirModal();
}

// ELIMINAR TRABAJADOR
async function eliminarTrabajador(id) {
    if (!confirm('¿Estás seguro de que quieres eliminar a este trabajador?')) {
        return;
    }
    try {
        const { res, data } = await fetchJSON(`/api/trabajadores/${id}`, 'DELETE');
        if (res.ok) {
            cargarTrabajadoresAdmin(); // Vuelve a cargar la tabla
        } else {
            alert(data.msg || 'Error al eliminar el trabajador.');
        }
    } catch (err) {
        console.error('Error:', err);
        alert('Error de conexión al servidor.');
    }
}
// ELIMINAR CLIENTE
async function eliminarCliente(id) {
    if (!confirm('¿Estás seguro de que quieres eliminar a este cliente? Se eliminarán también todos sus préstamos.')) {
        return;
    }
    try {
        const { res, data } = await fetchJSON(`/api/clientes/${id}`, 'DELETE');
        if (res.ok) {
            cargarClientesAdmin(); // Vuelve a cargar la tabla de clientes
            cargarResumenCreditos(); // Actualiza el resumen
        } else {
            alert(data.msg || 'Error al eliminar el cliente.');
        }
    } catch (err) {
        console.error('Error:', err);
        alert('Error de conexión al servidor.');
    }
}

// Función para cambiar la visibilidad de la contraseña
function togglePasswordVisibility() {
    const passwordInput = document.getElementById('passwordInput');
    const passwordIcon = document.getElementById('passwordIcon');

    if (passwordInput.type === 'password') {
        passwordInput.type = 'text';
        passwordIcon.src = "/static/icons/eye-close.svg";
        passwordIcon.alt = 'Ocultar contraseña';
    } else {
        passwordInput.type = 'password';
        passwordIcon.src = "/static/icons/eye-open.svg";
        passwordIcon.alt = 'Mostrar contraseña';
    }
}

function filtrarTrabajadores(searchText) {
    const table = document.getElementById('trabajadoresTableAdmin');
    const rows = table.getElementsByTagName('tr');
    const filter = searchText.toLowerCase();

    for (let i = 1; i < rows.length; i++) {
        const username = rows[i].getElementsByTagName('td')[0];
        const dni = rows[i].getElementsByTagName('td')[1];

        if (username || dni) {
            const usernameText = username.textContent || username.innerText;
            const dniText = dni.textContent || dni.innerText;

            if (usernameText.toLowerCase().indexOf(filter) > -1 || dniText.toLowerCase().indexOf(filter) > -1) {
                rows[i].style.display = "";
            } else {
                rows[i].style.display = "none";
            }
        }
    }
}

async function cargarTrabajadoresAdmin() {
    try {
        const { res, data } = await fetchJSON('/api/trabajadores');
        if (!res.ok) throw new Error('No autorizado');

        const tbody = document.querySelector('#trabajadoresTableAdmin tbody');
        tbody.innerHTML = '';

        data.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${t.username}</td>
                <td>${t.dni || ''}</td>
                <td>${t.telefono || ''}</td>
                <td>
                    <button onclick="abrirModal(${t.id}, '${t.username}', '${t.dni}', '${t.telefono}')">Editar</button>
                    <button class="delete-btn" onclick="eliminarTrabajador(${t.id})">Eliminar</button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error(err);
        alert('Error al cargar trabajadores');
    }
}

// ---- Funciones para el modal de Clientes y Préstamos ----
function abrirClienteModal() {
    document.getElementById('clienteModal').style.display = 'block';
    document.getElementById('clienteForm').reset();
    document.getElementById('clienteModalTitle').innerText = 'Añadir Cliente y Préstamo';
    document.getElementById('clienteSubmitBtn').innerText = 'Guardar';
}

function cerrarClienteModal() {
    document.getElementById('clienteModal').style.display = 'none';
    document.getElementById('clienteForm').reset();
}

// ** Funciones para el modal de préstamos **
function abrirPrestamoModal(clienteId) {
    document.getElementById('prestamoModal').style.display = 'block';
    document.getElementById('prestamoForm').reset();
    document.getElementById('prestamoClienteId').value = clienteId;
}

function cerrarPrestamoModal() {
    document.getElementById('prestamoModal').style.display = 'none';
    document.getElementById('prestamoForm').reset();
}

// ** Funciones de filtrado y exportación **
function filtrarClientes(searchText) {
    const table = document.getElementById('clientesTableAdmin');
    const rows = table.getElementsByTagName('tr');
    const filter = searchText.toLowerCase();

    for (let i = 1; i < rows.length; i++) {
        const dni = rows[i].getElementsByTagName('td')[1];
        const nombre = rows[i].getElementsByTagName('td')[2];

        if (dni || nombre) {
            const dniText = dni.textContent || dni.innerText;
            const nombreText = nombre.textContent || nombre.innerText;

            if (dniText.toLowerCase().indexOf(filter) > -1 || nombreText.toLowerCase().indexOf(filter) > -1) {
                rows[i].style.display = "";
            } else {
                rows[i].style.display = "none";
            }
        }
    }
}

function exportarClientesExcel() {
    let table = document.getElementById('clientesTableAdmin');
    let html = table.outerHTML;
    let url = 'data:application/vnd.ms-excel,' + encodeURIComponent(html);
    let a = document.createElement('a');
    a.href = url;
    a.download = 'clientes_prestamos.xls';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// --- Event listeners principales ---
document.addEventListener('DOMContentLoaded', async () => {
    const rol = localStorage.getItem('rol');
    if (!rol || rol !== 'admin') {
        window.location.pathname = '/';
        return;
    }
    const bienvenida = document.getElementById('bienvenida');
    if (bienvenida) bienvenida.textContent = 'Bienvenido, ' + rol;

    // Lógica para el cambio de pestañas
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

            this.classList.add('active');
            document.getElementById(this.dataset.target).classList.add('active');

            if (this.dataset.target === 'trabajadoresTab') {
                cargarTrabajadoresAdmin();
            }
            if (this.dataset.target === 'clientesTab') {
                cargarClientesAdmin();
            }
        });
    });

    // Cargar la pestaña de clientes por defecto y el resumen
    await cargarClientesAdmin();
    await cargarResumenCreditos();

    // Manejar el envío del formulario modal de trabajadores
    document.getElementById('workerForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const id = document.getElementById('workerId').value;
        const username = document.getElementById('usernameInput').value;
        const dni = document.getElementById('dniInput').value;
        const telefono = document.getElementById('telefonoInput').value;
        const password = document.getElementById('passwordInput').value;
        const submitBtn = document.getElementById('submitBtn');

        submitBtn.disabled = true;
        submitBtn.innerText = 'Guardando...';

        if (id) {
            const body = { username, dni, telefono };
            if (password) body.password = password;
            const { res, data } = await fetchJSON(`/api/trabajadores/${id}`, 'PUT', body);
            if (res.ok) {
                cargarTrabajadoresAdmin();
            } else {
                alert(data.msg || 'Error al actualizar el trabajador.');
            }
        } else {
            const { res, data } = await fetchJSON('/api/trabajadores', 'POST', { username, password, dni, telefono });
            if (res.ok) {
                cargarTrabajadoresAdmin();
            } else {
                alert(data.msg || 'Error al crear el trabajador.');
            }
        }
        cerrarModal();
        submitBtn.disabled = false;
        submitBtn.innerText = 'Guardar';
    });

    // Manejar el envío del formulario modal de clientes y su primer préstamo
    document.getElementById('clienteForm').addEventListener('submit', async function(e) {
        e.preventDefault();

        const clienteData = {
            nombre: document.getElementById('clienteNombreInput').value,
            dni: document.getElementById('clienteDniInput').value,
            telefono: document.getElementById('clienteTelefonoInput').value,
            direccion: document.getElementById('clienteLugarInput').value
        };

        const prestamoData = {
            monto: parseFloat(document.getElementById('prestamoMontoInput').value),
            interes: parseFloat(document.getElementById('prestamoInteresInput').value),
            tipo: document.getElementById('prestamoTipoInput').value,
            cuota: parseFloat(document.getElementById('prestamoCuotaInput').value),
            fecha_inicio: document.getElementById('prestamoFechaInicioInput').value
        };

        const body = {
            cliente: clienteData,
            prestamo: prestamoData
        };

        const submitBtn = document.getElementById('clienteSubmitBtn');
        submitBtn.disabled = true;
        submitBtn.innerText = 'Guardando...';

        const { res, data } = await fetchJSON('/api/clientes_con_prestamo', 'POST', body);

        if (res.ok) {
            alert('Cliente y préstamo creados con éxito.');
            cerrarClienteModal();
            await cargarClientesAdmin();
            await cargarResumenCreditos();
        } else {
            alert(data.msg || 'Error al crear el cliente y el préstamo.');
        }

        submitBtn.disabled = false;
        submitBtn.innerText = 'Guardar';
    });

    // Manejar el envío del formulario modal para añadir nuevos préstamos
    document.getElementById('prestamoForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const cliente_id = document.getElementById('prestamoClienteId').value;
        const monto = parseFloat(document.getElementById('prestamoMontoNuevo').value);
        const interes = parseFloat(document.getElementById('prestamoInteresNuevo').value);
        const tipo = document.getElementById('prestamoTipoNuevo').value;
        const cuota = parseFloat(document.getElementById('prestamoCuotaNuevo').value);
        const fecha_inicio = document.getElementById('prestamoFechaInicioNuevo').value;

        const body = { cliente_id, monto, interes, tipo, cuota, fecha_inicio };
        const { res, data } = await fetchJSON('/api/prestamos', 'POST', body);

        if (res.ok) {
            alert('Préstamo creado con éxito.');
            cerrarPrestamoModal();
            await cargarClientesAdmin();
            await cargarResumenCreditos();
        } else {
            alert(data.msg || 'Error al crear el préstamo.');
        }
    });

    // Event listener para el botón de cerrar sesión
    const btnCerrarSesion = document.getElementById('btnCerrarSesion');
    if (btnCerrarSesion) {
        btnCerrarSesion.addEventListener('click', async () => {
            try {
                await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
            } catch (e) {
                console.warn('Error al cerrar sesión:', e);
            }
            localStorage.removeItem('rol');
            window.location.href = '/';
        });
    }

});

