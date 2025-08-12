// --- Variables de datos (clientes y trabajadores de prueba) ---
let clientes = [
  {dni:"12345678", nombre:"Ana Pérez", lugar:"Lima", telefono:"987654321", montoTotal:1000, saldo:500, tipo:"DT", dt:"DT1", cp:"CP1", deudaVencida:200, cuota:100, fechaPago:"15/08/2025"},
  {dni:"87654321", nombre:"Luis Gómez", lugar:"Arequipa", telefono:"912345678", montoTotal:1500, saldo:0, tipo:"CP", dt:"DT2", cp:"CP2", deudaVencida:0, cuota:150, fechaPago:"01/09/2025"},
  {dni:"11223344", nombre:"María Ruiz", lugar:"Cusco", telefono:"999888777", montoTotal:1200, saldo:300, tipo:"DT", dt:"DT3", cp:"CP3", deudaVencida:100, cuota:120, fechaPago:"10/08/2025"}
];
let trabajadores = [
  {nombre:"Carlos Torres", dni:"44556677", telefono:"987123456"},
  {nombre:"Sofía Martínez", dni:"99887766", telefono:"912345679"}
];

// --- Login ---
document.getElementById("loginForm")?.addEventListener("submit", function(e) {
  e.preventDefault();

  const nombre = document.getElementById("username").value.trim();
  const contraseña = document.getElementById("password").value;

  if (!nombre) {
    mostrarMensaje("Por favor, ingresa tu nombre.");
    return;
  }

  if (contraseña === "cash2025") {
    // Admin
    localStorage.setItem("rol", "admin");
    localStorage.setItem("nombreUsuario", nombre);
    window.location.href = "admin.html";
  } else if (contraseña === "exitos2025") {
    // Trabajador
    localStorage.setItem("rol", "trabajador");
    localStorage.setItem("nombreUsuario", nombre);
    window.location.href = "trabajador.html";
  } else {
    mostrarMensaje("Contraseña incorrecta.");
  }
});

function mostrarMensaje(msg) {
  const mensaje = document.getElementById("loginMessage");
  if(mensaje){
    mensaje.textContent = msg;
    mensaje.style.color = "red";
  }
}

// --- Cerrar sesión ---
document.getElementById("btnCerrarSesion")?.addEventListener("click", () => {
  localStorage.clear();
  window.location.href = "index.html";
});

// --- Mostrar bienvenida ---
function mostrarBienvenida() {
  const rol = localStorage.getItem("rol");
  const nombre = localStorage.getItem("nombreUsuario");

  if (!rol || !nombre) {
    window.location.href = "index.html";
    return;
  }

  const bienvenidaDiv = document.getElementById("bienvenida");
  if (bienvenidaDiv) {
    const textoRol = rol === "admin" ? "Administrador" : "Trabajador";
    bienvenidaDiv.textContent = `Bienvenido ${textoRol} ${nombre}`;
  }
}

// --- Tabs ---
document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

    btn.classList.add("active");
    const target = btn.dataset.target;
    document.getElementById(target).classList.add("active");
  });
});

// --- Render clientes ---
function renderClientes(esAdmin) {
  // Ordenar clientes por nombre A-Z
  clientes.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));

  const tbody = document.querySelector(esAdmin ? "#clientesTableAdmin tbody" : "#clientesTableTrabajador tbody");
  tbody.innerHTML = "";

  const hoy = new Date();

  clientes.forEach((cli, i) => {
    // Evaluar días restantes a fechaPago
    let colorClase = "";
    if (cli.fechaPago) {
      const partes = cli.fechaPago.split("/");
      if (partes.length === 3) {
        const fechaPago = new Date(`${partes[2]}-${partes[1]}}-${partes[0]}T00:00:00`);
        const diffTime = fechaPago - hoy;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        if (diffDays <= 4) {
          colorClase = "fila-alerta-roja";
        } else if (diffDays <= 7) {
          colorClase = "fila-alerta-amarilla";
        }
      }
    }

    const tr = document.createElement("tr");
    if (colorClase) tr.classList.add(colorClase);

    tr.innerHTML = `
      <td>${cli.dni}</td>
      <td>${cli.nombre}</td>
      <td>${cli.lugar}</td>
      <td>${cli.telefono}</td>
      <td>${cli.montoTotal}</td>
      <td>${cli.saldo}</td>
      <td>${cli.tipo}</td>
      <td>${cli.dt}</td>
      <td>${cli.cp}</td>
      <td>${cli.deudaVencida}</td>
      <td>${cli.cuota}</td>
      <td>${cli.fechaPago}</td>
      ${esAdmin ? `
      <td>
        <button class="action-btn edit-btn" onclick="editarCliente(${i})">Editar</button>
        <button class="action-btn delete-btn" onclick="eliminarCliente(${i})">Eliminar</button>
      </td>
      ` : ""}
    `;

    tbody.appendChild(tr);
  });

  actualizarResumen();
}

// --- Render trabajadores ---
function renderTrabajadores(esAdmin) {
  // Ordenar trabajadores por nombre A-Z
  trabajadores.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));

  const tbody = document.querySelector("#trabajadoresTableAdmin tbody");
  tbody.innerHTML = "";

  trabajadores.forEach((trab, i) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${trab.nombre}</td>
      <td>${trab.dni}</td>
      <td>${trab.telefono}</td>
      ${esAdmin ? `
      <td>
        <button class="action-btn edit-btn" onclick="editarTrabajador(${i})">Editar</button>
        <button class="action-btn delete-btn" onclick="eliminarTrabajador(${i})">Eliminar</button>
      </td>
      ` : ""}
    `;
    tbody.appendChild(tr);
  });
}

// --- Actualizar resumen ---
function actualizarResumen() {
  const hoy = new Date();
  let totalCreditos = clientes.length;
  let creditosVigentes = 0;
  let creditosVencidos = 0;
  let deudaTotal = 0;

  clientes.forEach(cli => {
    deudaTotal += cli.saldo;

    if (cli.fechaPago) {
      const partes = cli.fechaPago.split("/");
      if (partes.length === 3) {
        const fechaPago = new Date(`${partes[2]}-${partes[1]}-${partes[0]}T00:00:00`);
        if (fechaPago >= hoy) {
          creditosVigentes++;
        } else {
          creditosVencidos++;
        }
      }
    }
  });

  // Actualizar en DOM según rol
  const rol = localStorage.getItem("rol");
  if (rol === "admin") {
    document.getElementById("totalCreditos").textContent = totalCreditos;
    document.getElementById("creditosVigentes").textContent = creditosVigentes;
    document.getElementById("creditosVencidos").textContent = creditosVencidos;
    document.getElementById("deudaTotal").textContent = deudaTotal;
  } else {
    document.getElementById("totalCreditosTrabajador").textContent = totalCreditos;
    document.getElementById("creditosVigentesTrabajador").textContent = creditosVigentes;
    document.getElementById("creditosVencidosTrabajador").textContent = creditosVencidos;
    document.getElementById("deudaTotalTrabajador").textContent = deudaTotal;
  }
}

// --- Filtrar clientes ---
function filtrarClientes(valor, esAdmin) {
  valor = valor.toLowerCase();
  const tabla = esAdmin ? document.getElementById("clientesTableAdmin") : document.getElementById("clientesTableTrabajador");
  const filas = tabla.tBodies[0].rows;

  for (let fila of filas) {
    const dni = fila.cells[0].textContent.toLowerCase();
    const nombre = fila.cells[1].textContent.toLowerCase();
    if (dni.includes(valor) || nombre.includes(valor)) {
      fila.style.display = "";
    } else {
      fila.style.display = "none";
    }
  }
}

// --- Filtrar trabajadores ---
function filtrarTrabajadores(valor, esAdmin) {
  valor = valor.toLowerCase();
  const tabla = document.getElementById("trabajadoresTableAdmin");
  const filas = tabla.tBodies[0].rows;

  for (let fila of filas) {
    const dni = fila.cells[1].textContent.toLowerCase();
    const nombre = fila.cells[0].textContent.toLowerCase();
    if (dni.includes(valor) || nombre.includes(valor)) {
      fila.style.display = "";
    } else {
      fila.style.display = "none";
    }
  }
}

// --- Añadir cliente ---
function agregarCliente() {
  const nuevo = {
    dni: prompt("DNI:") || "",
    nombre: prompt("Nombre:") || "",
    lugar: prompt("Lugar donde reside:") || "",
    telefono: prompt("Teléfono:") || "",
    montoTotal: Number(prompt("Monto Total:") || 0),
    saldo: Number(prompt("Saldo:") || 0),
    tipo: prompt("Tipo (DT o CP):") || "",
    dt: prompt("DT:") || "",
    cp: prompt("CP:") || "",
    deudaVencida: Number(prompt("Deuda Vencida:") || 0),
    cuota: Number(prompt("Cuota:") || 0),
    fechaPago: prompt("Fecha de Pago (dd/mm/aaaa):") || "",
  };

  if (!nuevo.dni || !nuevo.nombre) {
    alert("DNI y Nombre son obligatorios.");
    return;
  }

  clientes.push(nuevo);
  renderClientes(true);
}

// --- Añadir trabajador ---
function agregarTrabajador() {
  const nuevo = {
    nombre: prompt("Nombre:") || "",
    dni: prompt("DNI:") || "",
    telefono: prompt("Teléfono:") || "",
  };

  if (!nuevo.nombre || !nuevo.dni) {
    alert("Nombre y DNI son obligatorios.");
    return;
  }

  trabajadores.push(nuevo);
  renderTrabajadores(true);
}

// --- Editar cliente ---
function editarCliente(index) {
  const cli = clientes[index];
  const dni = prompt("DNI:", cli.dni) || cli.dni;
  const nombre = prompt("Nombre:", cli.nombre) || cli.nombre;
  const lugar = prompt("Lugar donde reside:", cli.lugar) || cli.lugar;
  const telefono = prompt("Teléfono:", cli.telefono) || cli.telefono;
  const montoTotal = Number(prompt("Monto Total:", cli.montoTotal) || cli.montoTotal);
  const saldo = Number(prompt("Saldo:", cli.saldo) || cli.saldo);
  const tipo = prompt("Tipo (DT o CP):", cli.tipo) || cli.tipo;
  const dt = prompt("DT:", cli.dt) || cli.dt;
  const cp = prompt("CP:", cli.cp) || cli.cp;
  const deudaVencida = Number(prompt("Deuda Vencida:", cli.deudaVencida) || cli.deudaVencida);
  const cuota = Number(prompt("Cuota:", cli.cuota) || cli.cuota);
  const fechaPago = prompt("Fecha de Pago (dd/mm/aaaa):", cli.fechaPago) || cli.fechaPago;

  clientes[index] = {dni, nombre, lugar, telefono, montoTotal, saldo, tipo, dt, cp, deudaVencida, cuota, fechaPago};
  renderClientes(true);
}

// --- Editar trabajador ---
function editarTrabajador(index) {
  const trab = trabajadores[index];
  const nombre = prompt("Nombre:", trab.nombre) || trab.nombre;
  const dni = prompt("DNI:", trab.dni) || trab.dni;
  const telefono = prompt("Teléfono:", trab.telefono) || trab.telefono;

  trabajadores[index] = {nombre, dni, telefono};
  renderTrabajadores(true);
}

// --- Eliminar cliente ---
function eliminarCliente(index) {
  if (confirm("¿Eliminar cliente?")) {
    clientes.splice(index, 1);
    renderClientes(true);
  }
}

// --- Eliminar trabajador ---
function eliminarTrabajador(index) {
  if (confirm("¿Eliminar trabajador?")) {
    trabajadores.splice(index, 1);
    renderTrabajadores(true);
  }
}

// --- Exportar a Excel (simple CSV) ---
function exportarClientesExcel(esAdmin) {
  const tabla = esAdmin ? document.getElementById("clientesTableAdmin") : document.getElementById("clientesTableTrabajador");
  let csv = [];

  for (let fila of tabla.rows) {
    let cols = [];
    for (let celda of fila.cells) {
      // No exportar columna de acciones
      if (celda.innerText.trim() === "Acciones") continue;
      if (celda.querySelector("button")) continue;
      cols.push(`"${celda.innerText.replace(/"/g, '""')}"`);
    }
    if(cols.length) csv.push(cols.join(","));
  }

  const csvContent = csv.join("\n");
  const blob = new Blob([csvContent], {type: "text/csv;charset=utf-8;"});
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = esAdmin ? "clientes_admin.csv" : "clientes_trabajador.csv";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// --- Inicialización páginas ---
window.onload = function() {
  const rol = localStorage.getItem("rol");

  if (window.location.pathname.endsWith("admin.html")) {
    if (rol !== "admin") {
      alert("Acceso denegado.");
      window.location.href = "index.html";
      return;
    }
    mostrarBienvenida();
    renderClientes(true);
    renderTrabajadores(true);
  } else if (window.location.pathname.endsWith("trabajador.html")) {
    if (rol !== "trabajador") {
      alert("Acceso denegado.");
      window.location.href = "index.html";
      return;
    }
    mostrarBienvenida();
    renderClientes(false);
  }
};
