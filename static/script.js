// ---- CONFIGURACIONES Y CONSTANTES ----
const API_BASE_URL = '';
const INACTIVITY_LIMIT = 30 * 60 * 1000; // 30 minutos

// ---- FUNCIÓN HELPER PARA PETICIONES HTTP ----
/**
 * Función auxiliar para realizar peticiones HTTP de forma segura
 * Maneja automáticamente la expiración de sesión y errores comunes
 */
async function fetchJSON(url, method = 'GET', body = null) {
    const opts = { 
        method, 
        credentials: 'include', 
        headers: {} 
    };
    
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

// ---- CONTROL DE INACTIVIDAD ----
/**
 * Sistema de control de inactividad del usuario
 * Avisa antes de cerrar la sesión y la cierra automáticamente tras el límite
 */
let inactivityTimer, warningTimer;

function resetInactivityTimer() {
    clearTimeout(inactivityTimer);
    clearTimeout(warningTimer);

    // Aviso 1 minuto antes de cerrar sesión
    warningTimer = setTimeout(() => {
        if (confirm("Tu sesión expirará en 1 minuto. ¿Quieres mantenerla?")) {
            fetch('/auth/check', { credentials: 'include' });
            resetInactivityTimer();
        }
    }, INACTIVITY_LIMIT - 60 * 1000);

    // Cierre automático de sesión
    inactivityTimer = setTimeout(() => {
        alert("Sesión cerrada por inactividad.");
        localStorage.removeItem('rol');
        fetch('/auth/logout', { method: 'POST', credentials: 'include' });
        window.location.href = '/';
    }, INACTIVITY_LIMIT);
}

// Eventos que resetean el timer de inactividad
['mousemove', 'keydown', 'click'].forEach(evt => {
    window.addEventListener(evt, resetInactivityTimer);
});

// ---- FUNCIONES PARA CARGAR DATOS ----

/**
 * Carga los clientes con préstamos activos (para administradores)
 */
async function cargarClientesAdmin() {
    const tBody = document.querySelector('#clientesTableAdmin tbody');
    if (!tBody) return;

    try {
        const { res, data } = await fetchJSON('/api/clientes');
        if (!res.ok) {
            console.error('Error al cargar clientes:', data?.msg || res.statusText);
            tBody.innerHTML = '<tr><td colspan="14">Error al cargar clientes.</td></tr>';
            return;
        }

        tBody.innerHTML = '';
        
        if (data.length === 0) {
            tBody.innerHTML = '<tr><td colspan="14" class="text-center">No hay clientes con préstamos activos.</td></tr>';
            return;
        }

        data.forEach(cliente => {
            if (cliente.prestamos && cliente.prestamos.length > 0) {
                cliente.prestamos.forEach(prestamo => {
                    const tr = document.createElement('tr');
                    
                    // Calcular clase de alerta por fecha de vencimiento
                    let claseAlerta = '';
                    let diasRestantes = 'N/A';
                    if (prestamo.fecha_fin) {
                        const fechaHoy = new Date();
                        const fechaFin = new Date(prestamo.fecha_fin);
                        const diferenciaMs = fechaFin.getTime() - fechaHoy.getTime();
                        diasRestantes = Math.ceil(diferenciaMs / (1000 * 60 * 60 * 24));
                        
                        if (diasRestantes < 0) {
                            claseAlerta = 'alerta-vencido';
                        } else if (diasRestantes <= 3) {
                            claseAlerta = 'alerta-rojo';
                        } else if (diasRestantes <= 10) {
                            claseAlerta = 'alerta-amarillo';
                        }
                    }
                    
                    tr.className = claseAlerta;
                    tr.innerHTML = `
                        <td>${cliente.id}</td>
                        <td>${cliente.dni || 'N/A'}</td>
                        <td>${cliente.nombre || ''}</td>
                        <td>${cliente.direccion || ''}</td>
                        <td>${cliente.telefono || ''}</td>
                        <td>S/ ${(prestamo.monto || 0).toFixed(2)}</td>
                        <td>S/ ${(prestamo.saldo || 0).toFixed(2)}</td>
                        <td>${prestamo.tipo || 'N/A'}</td>
                        <td>${prestamo.dt || 0}</td>
                        <td>${prestamo.pagos ? prestamo.pagos.length : 0}</td>
                        <td>S/ ${(prestamo.deuda_vencida || 0).toFixed(2)}</td>
                        <td>S/ ${(prestamo.cuota || 0).toFixed(2)}</td>
                        <td>${prestamo.fecha_fin || 'N/A'}</td>
                        <td>
                            <button class="action-btn" onclick="abrirPrestamoModal(${cliente.id})" title="Nuevo Préstamo">
                                <i class="fas fa-plus"></i>
                            </button>
                            <button class="action-btn" onclick="abrirEditClienteModal(${cliente.id}, '${cliente.nombre}', '${cliente.direccion}', '${cliente.telefono}')" title="Editar Cliente">
                                <i class="fas fa-edit"></i>
                            </button>
                            <button class="action-btn delete-btn" onclick="eliminarCliente(${cliente.id})" title="Eliminar Cliente">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                            <button class="action-btn" onclick="marcarPrestamoComoPagado(${prestamo.id})" title="Marcar como Pagado">
                                <i class="fas fa-check"></i>
                            </button>
                            <button class="action-btn" onclick="abrirModalPago(${prestamo.id})" title="Registrar Pago">
                                <i class="fas fa-dollar-sign"></i>
                            </button>
                        </td>
                    `;
                    tBody.appendChild(tr);
                });
            }
        });
    } catch (error) {
        console.error('Error al cargar clientes:', error);
        tBody.innerHTML = '<tr><td colspan="14">Error de conexión al servidor.</td></tr>';
    }
}

/**
 * Carga los clientes para trabajadores (sin botones de administrador)
 */
async function cargarClientesTrabajador() {
    const tBody = document.querySelector('#clientesTableTrabajador tbody');
    if (!tBody) return;

    try {
        const { res, data } = await fetchJSON('/api/clientes');
        if (!res.ok) {
            console.error('Error al cargar clientes:', data?.msg || res.statusText);
            tBody.innerHTML = '<tr><td colspan="13">Error al cargar clientes.</td></tr>';
            return;
        }

        tBody.innerHTML = '';
        
        if (data.length === 0) {
            tBody.innerHTML = '<tr><td colspan="13" class="text-center">No hay clientes con préstamos activos.</td></tr>';
            return;
        }

        data.forEach(cliente => {
            if (cliente.prestamos && cliente.prestamos.length > 0) {
                cliente.prestamos.forEach(prestamo => {
                    const tr = document.createElement('tr');
                    
                    // Calcular clase de alerta por fecha de vencimiento
                    let claseAlerta = '';
                    if (prestamo.fecha_fin) {
                        const fechaHoy = new Date();
                        const fechaFin = new Date(prestamo.fecha_fin);
                        const diferenciaMs = fechaFin.getTime() - fechaHoy.getTime();
                        const diasRestantes = Math.ceil(diferenciaMs / (1000 * 60 * 60 * 24));
                        
                        if (diasRestantes < 0) {
                            claseAlerta = 'alerta-vencido';
                        } else if (diasRestantes <= 3) {
                            claseAlerta = 'alerta-rojo';
                        } else if (diasRestantes <= 10) {
                            claseAlerta = 'alerta-amarillo';
                        }
                    }
                    
                    tr.className = claseAlerta;
                    tr.innerHTML = `
                        <td>${cliente.id}</td>
                        <td>${cliente.dni || 'N/A'}</td>
                        <td>${cliente.nombre || ''}</td>
                        <td>${cliente.direccion || ''}</td>
                        <td>${cliente.telefono || ''}</td>
                        <td>S/ ${(prestamo.monto || 0).toFixed(2)}</td>
                        <td>S/ ${(prestamo.saldo || 0).toFixed(2)}</td>
                        <td>${prestamo.tipo || 'N/A'}</td>
                        <td>${prestamo.dt || 0}</td>
                        <td>${prestamo.pagos ? prestamo.pagos.length : 0}</td>
                        <td>S/ ${(prestamo.deuda_vencida || 0).toFixed(2)}</td>
                        <td>S/ ${(prestamo.cuota || 0).toFixed(2)}</td>
                        <td>${prestamo.fecha_fin || 'N/A'}</td>
                    `;
                    tBody.appendChild(tr);
                });
            }
        });
    } catch (error) {
        console.error('Error al cargar clientes:', error);
        tBody.innerHTML = '<tr><td colspan="13">Error de conexión al servidor.</td></tr>';
    }
}

/**
 * Carga la lista de trabajadores (solo para administradores)
 */
async function cargarTrabajadoresAdmin() {
    const tBody = document.querySelector('#trabajadoresTableAdmin tbody');
    if (!tBody) return;

    try {
        const { res, data } = await fetchJSON('/api/trabajadores');
        if (!res.ok) {
            console.error('Error al cargar trabajadores:', data?.msg || res.statusText);
            tBody.innerHTML = '<tr><td colspan="4">Error al cargar trabajadores.</td></tr>';
            return;
        }

        tBody.innerHTML = '';
        
        if (data.length === 0) {
            tBody.innerHTML = '<tr><td colspan="4" class="text-center">No hay trabajadores registrados.</td></tr>';
            return;
        }

        data.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${t.username}</td>
                <td>${t.dni || 'N/A'}</td>
                <td>${t.telefono || 'N/A'}</td>
                <td>
                    <button class="action-btn" onclick="abrirModal(${t.id}, '${t.username}', '${t.dni || ''}', '${t.telefono || ''}')" title="Editar">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn delete-btn" onclick="eliminarTrabajador(${t.id})" title="Eliminar">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </td>
            `;
            tBody.appendChild(tr);
        });
    } catch (error) {
        console.error('Error al cargar trabajadores:', error);
        tBody.innerHTML = '<tr><td colspan="4">Error de conexión al servidor.</td></tr>';
    }
}

/**
 * Carga el resumen estadístico de créditos
 */
async function cargarResumenCreditos() {
    try {
        const { res, data } = await fetchJSON('/api/resumen_creditos');
        if (res.ok) {
            const elementos = {
                'totalCreditos': document.getElementById('totalCreditos'),
                'totalCreditosTrabajador': document.getElementById('totalCreditosTrabajador'),
                'creditosVigentes': document.getElementById('creditosVigentes'),
                'creditosVigentesTrabajador': document.getElementById('creditosVigentesTrabajador'),
                'creditosVencidos': document.getElementById('creditosVencidos'),
                'creditosVencidosTrabajador': document.getElementById('creditosVencidosTrabajador'),
                'deudaTotal': document.getElementById('deudaTotal'),
                'deudaTotalTrabajador': document.getElementById('deudaTotalTrabajador')
            };

            Object.keys(elementos).forEach(key => {
                if (elementos[key]) {
                    if (key.includes('deuda')) {
                        elementos[key].textContent = `S/ ${parseFloat(data.deudaTotal || 0).toFixed(2)}`;
                    } else if (key.includes('total')) {
                        elementos[key].textContent = data.totalCreditos || 0;
                    } else if (key.includes('vigentes')) {
                        elementos[key].textContent = data.creditosVigentes || 0;
                    } else if (key.includes('vencidos')) {
                        elementos[key].textContent = data.creditosVencidos || 0;
                    }
                }
            });
        } else {
            console.error('Error al cargar el resumen de créditos:', data?.msg);
        }
    } catch (error) {
        console.error('Error en la conexión con la API de resumen:', error);
    }
}

// ---- FUNCIONES DE MODAL Y FORMULARIOS ----

/**
 * Abre el modal para agregar/editar trabajadores
 */
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

/**
 * Abre el modal para agregar clientes con su primer préstamo
 */
function abrirClienteModal() {
    document.getElementById('clienteModal').style.display = 'block';
    document.getElementById('clienteForm').reset();
    document.getElementById('clienteModalTitle').innerText = 'Añadir Cliente y Préstamo';
    document.getElementById('clienteSubmitBtn').innerText = 'Guardar';
    
    // Establecer fecha actual por defecto
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('prestamoFechaInicioInput').value = today;
}

function cerrarClienteModal() {
    document.getElementById('clienteModal').style.display = 'none';
    document.getElementById('clienteForm').reset();
}

/**
 * Abre el modal para editar información de cliente
 */
function abrirEditClienteModal(id, nombre, direccion, telefono) {
    document.getElementById('editClienteId').value = id;
    document.getElementById('editClienteNombre').value = nombre;
    document.getElementById('editClienteDireccion').value = direccion || '';
    document.getElementById('editClienteTelefono').value = telefono || '';
    document.getElementById('editClienteModal').style.display = 'block';
}

function cerrarEditClienteModal() {
    document.getElementById('editClienteModal').style.display = 'none';
    document.getElementById('editClienteForm').reset();
}

/**
 * Abre el modal para agregar nuevos préstamos a clientes existentes
 */
function abrirPrestamoModal(clienteId) {
    document.getElementById('prestamoModal').style.display = 'block';
    document.getElementById('prestamoForm').reset();
    document.getElementById('prestamoClienteId').value = clienteId;
    
    // Establecer fecha actual por defecto
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('prestamoFechaInicioNuevo').value = today;
}

function cerrarPrestamoModal() {
    document.getElementById('prestamoModal').style.display = 'none';
    document.getElementById('prestamoForm').reset();
}

/**
 * Abre el modal para registrar pagos
 */
function abrirModalPago(prestamoId) {
    document.getElementById('pagoModal').style.display = 'block';
    document.getElementById('pagoForm').reset();
    document.getElementById('pagoPrestamoId').value = prestamoId;
}

function cerrarModalPago() {
    document.getElementById('pagoModal').style.display = 'none';
    document.getElementById('pagoForm').reset();
}

// ---- FUNCIONES DE ELIMINACIÓN Y CONFIRMACIÓN ----

/**
 * Elimina un trabajador con confirmación
 */
async function eliminarTrabajador(id) {
    if (!confirm('¿Estás seguro de que quieres eliminar a este trabajador?')) {
        return;
    }
    
    try {
        const { res, data } = await fetchJSON(`/api/trabajadores/${id}`, 'DELETE');
        if (res.ok) {
            await cargarTrabajadoresAdmin();
            showNotification('Trabajador eliminado correctamente', 'success');
        } else {
            alert(data?.msg || 'Error al eliminar el trabajador.');
        }
    } catch (err) {
        console.error('Error:', err);
        alert('Error de conexión al servidor.');
    }
}

/**
 * Elimina un cliente con confirmación
 */
async function eliminarCliente(id) {
    if (!confirm('¿Estás seguro de que quieres eliminar a este cliente? Se eliminarán también todos sus préstamos.')) {
        return;
    }
    
    try {
        const { res, data } = await fetchJSON(`/api/clientes/${id}`, 'DELETE');
        if (res.ok) {
            await cargarClientesAdmin();
            await cargarResumenCreditos();
            showNotification('Cliente eliminado correctamente', 'success');
        } else {
            alert(data?.msg || 'Error al eliminar el cliente.');
        }
    } catch (err) {
        console.error('Error:', err);
        alert('Error de conexión al servidor.');
    }
}

/**
 * Marca un préstamo como pagado manualmente
 */
async function marcarPrestamoComoPagado(prestamoId) {
    if (!confirm('¿Estás seguro de que deseas marcar este préstamo como pagado?')) {
        return;
    }

    try {
        const { res, data } = await fetchJSON(`/api/prestamos/${prestamoId}/pagado_manual`, 'PUT');

        if (res.ok) {
            showNotification('Préstamo marcado como pagado exitosamente', 'success');
            await cargarClientesAdmin();
            await cargarResumenCreditos();
        } else {
            alert(data?.msg || 'Error al marcar el préstamo como pagado.');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Error de conexión al servidor.');
    }
}

// ---- FUNCIONES DE BÚSQUEDA Y FILTRADO ----

/**
 * Busca historial de préstamos por cliente
 */
async function buscarHistorial(searchText) {
    const tBody = document.querySelector('#prestamosTableAdmin tbody');
    if (!tBody) return;
    
    tBody.innerHTML = '';

    if (searchText.length < 2) {
        tBody.innerHTML = '<tr><td colspan="7">Ingresa al menos 2 caracteres para buscar.</td></tr>';
        return;
    }

    try {
        const { res, data } = await fetchJSON(`/api/clientes/search?q=${encodeURIComponent(searchText)}`);
        if (!res.ok) {
            console.error('Error al buscar historial:', data?.msg || res.statusText);
            tBody.innerHTML = '<tr><td colspan="7">Error al cargar el historial.</td></tr>';
            return;
        }

        if (data.length === 0) {
            tBody.innerHTML = '<tr><td colspan="7">No se encontraron clientes para esa búsqueda.</td></tr>';
            return;
        }

        // Mostrar todos los préstamos de los clientes encontrados
        data.forEach(cliente => {
            if (cliente.prestamos && cliente.prestamos.length > 0) {
                cliente.prestamos.forEach(prestamo => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td>${cliente.nombre}</td>
                        <td>${cliente.dni || 'N/A'}</td>
                        <td>S/ ${(prestamo.monto || 0).toFixed(2)}</td>
                        <td>${(prestamo.interes || 0).toFixed(2)}%</td>
                        <td>${prestamo.tipo || 'N/A'}</td>
                        <td>${prestamo.fecha_inicio || 'N/A'}</td>
                        <td>${prestamo.estado || 'N/A'}</td>
                    `;
                    tBody.appendChild(tr);
                });
            }
        });

    } catch (error) {
        console.error('Error en la búsqueda del historial:', error);
        tBody.innerHTML = '<tr><td colspan="7">Error de conexión al servidor.</td></tr>';
    }
}

/**
 * Filtra clientes en la tabla por DNI o nombre
 */
function filtrarClientes(searchText) {
    const table = document.getElementById('clientesTableAdmin') || document.getElementById('clientesTableTrabajador');
    if (!table) return;
    
    const rows = table.getElementsByTagName('tr');
    const filter = searchText.toLowerCase();

    for (let i = 1; i < rows.length; i++) {
        const dni = rows[i].getElementsByTagName('td')[1];
        const nombre = rows[i].getElementsByTagName('td')[2];

        if (dni && nombre) {
            const dniText = dni.textContent || dni.innerText;
            const nombreText = nombre.textContent || nombre.innerText;

            if (dniText.toLowerCase().indexOf(filter) > -1 || 
                nombreText.toLowerCase().indexOf(filter) > -1) {
                rows[i].style.display = "";
            } else {
                rows[i].style.display = "none";
            }
        }
    }
}

/**
 * Filtra trabajadores en la tabla por username o DNI
 */
function filtrarTrabajadores(searchText) {
    const table = document.getElementById('trabajadoresTableAdmin');
    if (!table) return;
    
    const rows = table.getElementsByTagName('tr');
    const filter = searchText.toLowerCase();

    for (let i = 1; i < rows.length; i++) {
        const username = rows[i].getElementsByTagName('td')[0];
        const dni = rows[i].getElementsByTagName('td')[1];

        if (username && dni) {
            const usernameText = username.textContent || username.innerText;
            const dniText = dni.textContent || dni.innerText;

            if (usernameText.toLowerCase().indexOf(filter) > -1 || 
                dniText.toLowerCase().indexOf(filter) > -1) {
                rows[i].style.display = "";
            } else {
                rows[i].style.display = "none";
            }
        }
    }
}

// ---- FUNCIONES UTILITARIAS ----

/**
 * Función para cambiar la visibilidad de la contraseña
 */
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

/**
 * Exporta la tabla de clientes a Excel
 */
function exportarClientesExcel() {
    const table = document.getElementById('clientesTableAdmin') || document.getElementById('clientesTableTrabajador');
    if (!table) {
        alert('No se encontró tabla para exportar');
        return;
    }
    
    let html = table.outerHTML;
    let url = 'data:application/vnd.ms-excel,' + encodeURIComponent(html);
    let a = document.createElement('a');
    a.href = url;
    a.download = `clientes_prestamos_${new Date().toISOString().split('T')[0]}.xls`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

/**
 * Muestra notificaciones al usuario
 */
function showNotification(message, type = 'info') {
    // Crear elemento de notificación si no existe
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
            z-index: 1000;
            display: none;
        `;
        document.body.appendChild(notification);
    }

    // Configurar estilo según tipo
    switch(type) {
        case 'success':
            notification.style.backgroundColor = '#4CAF50';
            break;
        case 'error':
            notification.style.backgroundColor = '#f44336';
            break;
        case 'warning':
            notification.style.backgroundColor = '#ff9800';
            break;
        default:
            notification.style.backgroundColor = '#2196F3';
    }

    notification.textContent = message;
    notification.style.display = 'block';

    // Ocultar después de 3 segundos
    setTimeout(() => {
        notification.style.display = 'none';
    }, 3000);
}

// ---- INICIALIZACIÓN PRINCIPAL ----

document.addEventListener('DOMContentLoaded', async () => {
    const rol = localStorage.getItem('rol');
    const currentPath = window.location.pathname;

    // Verificar autorización según la página
    if (currentPath === '/admin' && rol !== 'admin') {
        window.location.href = '/';
        return;
    } else if (currentPath === '/trabajador' && !['admin', 'trabajador'].includes(rol)) {
        window.location.href = '/';
        return;
    }

    // Actualizar mensaje de bienvenida
    const bienvenida = document.getElementById('bienvenida');
    if (bienvenida) bienvenida.textContent = 'Bienvenido, ' + (rol || 'Usuario');

    // Inicializar sistema de inactividad
    resetInactivityTimer();

    // ---- CONFIGURACIÓN PARA PÁGINA DE ADMIN ----
    if (currentPath === '/admin') {
        // Configurar pestañas
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));

                this.classList.add('active');
                document.getElementById(this.dataset.target).classList.add('active');

                // Cargar datos según la pestaña activa
                if (this.dataset.target === 'trabajadoresTab') {
                    cargarTrabajadoresAdmin();
                } else if (this.dataset.target === 'clientesTab') {
                    cargarClientesAdmin();
                }
            });
        });

        // Cargar datos iniciales
        await cargarClientesAdmin();
        await cargarResumenCreditos();

        // ---- EVENT LISTENERS PARA FORMULARIOS ----

        // Formulario de trabajadores
        const workerForm = document.getElementById('workerForm');
        if (workerForm) {
            workerForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const id = document.getElementById('workerId').value;
                const username = document.getElementById('usernameInput').value;
                const dni = document.getElementById('dniInput').value;
                const telefono = document.getElementById('telefonoInput').value;
                const password = document.getElementById('passwordInput').value;
                const submitBtn = document.getElementById('submitBtn');

                submitBtn.disabled = true;
                submitBtn.innerText = 'Guardando...';

                try {
                    if (id) {
                        // Editar trabajador
                        const body = { username, dni, telefono };
                        if (password) body.password = password;
                        const { res, data } = await fetchJSON(`/api/trabajadores/${id}`, 'PUT', body);
                        
                        if (res.ok) {
                            await cargarTrabajadoresAdmin();
                            showNotification('Trabajador actualizado correctamente', 'success');
                        } else {
                            alert(data?.msg || 'Error al actualizar el trabajador.');
                        }
                    } else {
                        // Crear trabajador
                        const { res, data } = await fetchJSON('/api/trabajadores', 'POST', { 
                            username, password, dni, telefono 
                        });
                        
                        if (res.ok) {
                            await cargarTrabajadoresAdmin();
                            showNotification('Trabajador creado correctamente', 'success');
                        } else {
                            alert(data?.msg || 'Error al crear el trabajador.');
                        }
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error de conexión al servidor.');
                }

                cerrarModal();
                submitBtn.disabled = false;
                submitBtn.innerText = 'Guardar';
            });
        }

        // Formulario de clientes y préstamo inicial
        const clienteForm = document.getElementById('clienteForm');
        if (clienteForm) {
            clienteForm.addEventListener('submit', async function(e) {
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

                const body = { cliente: clienteData, prestamo: prestamoData };
                const submitBtn = document.getElementById('clienteSubmitBtn');
                submitBtn.disabled = true;
                submitBtn.innerText = 'Guardando...';

                try {
                    const { res, data } = await fetchJSON('/api/clientes_con_prestamo', 'POST', body);

                    if (res.ok) {
                        showNotification('Cliente y préstamo creados con éxito', 'success');
                        cerrarClienteModal();
                        await cargarClientesAdmin();
                        await cargarResumenCreditos();
                    } else {
                        alert(data?.msg || 'Error al crear el cliente y el préstamo.');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error de conexión al servidor.');
                }

                submitBtn.disabled = false;
                submitBtn.innerText = 'Guardar';
            });
        }

        // Formulario de edición de cliente
        const editClienteForm = document.getElementById('editClienteForm');
        if (editClienteForm) {
            editClienteForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const id = document.getElementById('editClienteId').value;
                const nombre = document.getElementById('editClienteNombre').value;
                const direccion = document.getElementById('editClienteDireccion').value;
                const telefono = document.getElementById('editClienteTelefono').value;

                const body = { nombre, direccion, telefono };

                try {
                    const { res, data } = await fetchJSON(`/api/clientes/${id}`, 'PUT', body);

                    if (res.ok) {
                        showNotification('Cliente actualizado con éxito', 'success');
                        cerrarEditClienteModal();
                        await cargarClientesAdmin();
                    } else {
                        alert(data?.msg || 'Error al actualizar el cliente.');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error de conexión al servidor.');
                }
            });
        }

        // Formulario de nuevo préstamo
        const prestamoForm = document.getElementById('prestamoForm');
        if (prestamoForm) {
            prestamoForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const cliente_id = document.getElementById('prestamoClienteId').value;
                const monto = parseFloat(document.getElementById('prestamoMontoNuevo').value);
                const interes = parseFloat(document.getElementById('prestamoInteresNuevo').value);
                const tipo = document.getElementById('prestamoTipoNuevo').value;
                const cuota = parseFloat(document.getElementById('prestamoCuotaNuevo').value);
                const fecha_inicio = document.getElementById('prestamoFechaInicioNuevo').value;

                const body = { cliente_id, monto, interes, tipo, cuota, fecha_inicio };

                try {
                    const { res, data } = await fetchJSON('/api/prestamos', 'POST', body);

                    if (res.ok) {
                        showNotification('Préstamo creado con éxito', 'success');
                        cerrarPrestamoModal();
                        await cargarClientesAdmin();
                        await cargarResumenCreditos();
                    } else {
                        alert(data?.msg || 'Error al crear el préstamo.');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error de conexión al servidor.');
                }
            });
        }

        // Formulario de pagos
        const pagoForm = document.getElementById('pagoForm');
        if (pagoForm) {
            pagoForm.addEventListener('submit', async function(e) {
                e.preventDefault();
                const prestamoId = document.getElementById('pagoPrestamoId').value;
                const monto = parseFloat(document.getElementById('pagoMonto').value);

                try {
                    const { res, data } = await fetchJSON(`/api/prestamos/${prestamoId}/pagar`, 'POST', { monto });

                    if (res.ok) {
                        showNotification('Pago registrado exitosamente', 'success');
                        cerrarModalPago();
                        await cargarClientesAdmin();
                        await cargarResumenCreditos();
                    } else {
                        alert(data?.msg || 'Error al registrar el pago.');
                    }
                } catch (error) {
                    console.error('Error:', error);
                    alert('Error de conexión al servidor.');
                }
            });
        }

    }

    // ---- CONFIGURACIÓN PARA PÁGINA DE TRABAJADOR ----
    if (currentPath === '/trabajador') {
        await cargarClientesTrabajador();
        await cargarResumenCreditos();
    }

    // ---- EVENT LISTENER PARA CERRAR SESIÓN ----
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

    // ---- CERRAR MODALES AL HACER CLIC FUERA ----
    window.onclick = function(event) {
        const modales = [
            'workerModal', 'clienteModal', 'editClienteModal', 
            'prestamoModal', 'pagoModal'
        ];
        
        modales.forEach(modalId => {
            const modal = document.getElementById(modalId);
            if (modal && event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    console.log(`Aplicación inicializada correctamente para rol: ${rol}`);
});

// ---- FUNCIONES GLOBALES ADICIONALES ----

/**
 * Función para manejar errores globales
 */
window.addEventListener('error', function(event) {
    console.error('Error global capturado:', event.error);
});

/**
 * Función para manejar promesas rechazadas no capturadas
 */
window.addEventListener('unhandledrejection', function(event) {
    console.error('Promesa rechazada no manejada:', event.reason);
    event.preventDefault();
});

// Exportar funciones principales para uso global
window.cargarClientesAdmin = cargarClientesAdmin;
window.cargarClientesTrabajador = cargarClientesTrabajador;
window.cargarTrabajadoresAdmin = cargarTrabajadoresAdmin;
window.cargarResumenCreditos = cargarResumenCreditos;
window.filtrarClientes = filtrarClientes;
window.filtrarTrabajadores = filtrarTrabajadores;
window.exportarClientesExcel = exportarClientesExcel;
window.buscarHistorial = buscarHistorial;
window.marcarPrestamoComoPagado = marcarPrestamoComoPagado;
window.eliminarCliente = eliminarCliente;
window.eliminarTrabajador = eliminarTrabajador;
window.abrirModal = abrirModal;
window.cerrarModal = cerrarModal;
window.agregarTrabajador = agregarTrabajador;
window.abrirClienteModal = abrirClienteModal;
window.cerrarClienteModal = cerrarClienteModal;
window.abrirEditClienteModal = abrirEditClienteModal;
window.cerrarEditClienteModal = cerrarEditClienteModal;
window.abrirPrestamoModal = abrirPrestamoModal;
window.cerrarPrestamoModal = cerrarPrestamoModal;
window.abrirModalPago = abrirModalPago;
window.cerrarModalPago = cerrarModalPago;
window.togglePasswordVisibility = togglePasswordVisibility;