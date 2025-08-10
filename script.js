let clientes = [];

// Mostrar fecha actual
document.addEventListener("DOMContentLoaded", function () {
  const hoy = new Date();
  const fechaFormateada = `${hoy.getDate()}/${hoy.getMonth() + 1}/${hoy.getFullYear()}`;
  document.getElementById("fechaActual").textContent = fechaFormateada;
  cargarClientes();
});

// Guardar en localStorage
function guardarClientes() {
  localStorage.setItem("clientes", JSON.stringify(clientes));
}

// Cargar de localStorage
function cargarClientes() {
  const data = localStorage.getItem("clientes");
  if (data) {
    clientes = JSON.parse(data);
    actualizarTabla();
  }
}

// Agregar cliente
function agregarCliente() {
  const dni = document.getElementById("dni").value.trim();
  const nombre = document.getElementById("nombre").value.trim();
  const telefono = document.getElementById("telefono").value.trim();
  const monto = parseFloat(document.getElementById("monto").value.trim());
  const cuota = parseFloat(document.getElementById("cuota").value.trim()) || 0;

  if (!dni || !nombre || isNaN(monto)) {
    alert("Completa los campos DNI, nombre y monto.");
    return;
  }

  clientes.push({
    dni,
    nombre,
    telefono,
    monto,
    saldo: monto,
    tipo: "",
    dt: 0,
    cp: 0,
    deudaVend: 0,
    cuota
  });

  guardarClientes();
  actualizarTabla();

  document.getElementById("dni").value = "";
  document.getElementById("nombre").value = "";
  document.getElementById("telefono").value = "";
  document.getElementById("monto").value = "";
  document.getElementById("cuota").value = "";
}

// Eliminar cliente
function eliminarCliente(index) {
  if (confirm("¿Deseas eliminar este cliente?")) {
    clientes.splice(index, 1);
    guardarClientes();
    actualizarTabla();
  }
}

// Buscar cliente
function buscarCliente() {
  const texto = document.getElementById("buscador").value.toLowerCase();
  const filas = document.querySelectorAll("#cuerpoTabla tr");

  filas.forEach(fila => {
    const contenido = fila.textContent.toLowerCase();
    fila.style.display = contenido.includes(texto) ? "" : "none";
  });
}

// Crear cada fila
function crearFila(cliente, index) {
  const fila = document.createElement("tr");

  fila.innerHTML = `
    <td>${cliente.dni}</td>
    <td>${cliente.nombre}</td>
    <td>${cliente.telefono || ""}</td>
    <td>${cliente.monto.toFixed(2)}</td>
  `;

  // SALDO editable con confirmación
  const saldoCelda = document.createElement("td");
  const saldoInput = document.createElement("input");
  saldoInput.type = "number";
  saldoInput.value = cliente.saldo.toFixed(2);
  saldoInput.addEventListener("change", () => {
    const nuevoSaldo = parseFloat(saldoInput.value);
    if (!isNaN(nuevoSaldo) && nuevoSaldo >= 0) {
      if (confirm("¿Estás seguro de cambiar el saldo?")) {
        cliente.saldo = nuevoSaldo;
        guardarClientes();
        actualizarTabla();
      } else {
        saldoInput.value = cliente.saldo.toFixed(2);
      }
    }
  });
  saldoCelda.appendChild(saldoInput);
  fila.appendChild(saldoCelda);

  // Campos adicionales (puedes ajustar esto)
  fila.innerHTML += `
    <td>${cliente.tipo || ""}</td>
    <td>${cliente.dt || 0}</td>
    <td>${cliente.cp || 0}</td>
    <td>${cliente.deudaVend || 0}</td>
    <td>${cliente.cuota || 0}</td>
  `;

  // PAGO - actualiza saldo
  const pagoCelda = document.createElement("td");
  const inputPago = document.createElement("input");
  inputPago.type = "number";
  inputPago.placeholder = "S/ 0.00";
  inputPago.addEventListener("change", () => {
    const pago = parseFloat(inputPago.value);
    if (!isNaN(pago) && pago > 0) {
      cliente.saldo -= pago;
      if (cliente.saldo < 0) cliente.saldo = 0;
      guardarClientes();
      actualizarTabla();
    }
  });
  pagoCelda.appendChild(inputPago);
  fila.appendChild(pagoCelda);

  // Botón eliminar
  const eliminarCelda = document.createElement("td");
  const btnEliminar = document.createElement("button");
  btnEliminar.textContent = "❌";
  btnEliminar.onclick = () => eliminarCliente(index);
  eliminarCelda.appendChild(btnEliminar);
  fila.appendChild(eliminarCelda);

  document.getElementById("cuerpoTabla").appendChild(fila);
}

// Actualizar toda la tabla
function actualizarTabla() {
  const cuerpo = document.getElementById("cuerpoTabla");
  cuerpo.innerHTML = "";

  // Orden alfabético
  clientes.sort((a, b) => a.nombre.localeCompare(b.nombre));

  clientes.forEach((cliente, index) => {
    crearFila(cliente, index);
  });
}

// Exportar a CSV
function exportarExcel() {
  let csv = "DNI,Nombre,Telefono,Monto,Saldo,Tipo,DT,CP,DeudaVend,Cuota\n";
  clientes.forEach(c => {
    csv += `${c.dni},${c.nombre},${c.telefono},${c.monto},${c.saldo},${c.tipo},${c.dt},${c.cp},${c.deudaVend},${c.cuota}\n`;
  });

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "registro_clientes.csv";
  link.click();
}

// Importar CSV
function importarCSV(event) {
  const archivo = event.target.files[0];
  if (!archivo) return;

  const reader = new FileReader();
  reader.onload = function (e) {
    const contenido = e.target.result;
    const lineas = contenido.split("\n").slice(1);
    clientes = [];

    lineas.forEach(linea => {
      const datos = linea.split(",");
      if (datos.length >= 10) {
        clientes.push({
          dni: datos[0],
          nombre: datos[1],
          telefono: datos[2],
          monto: parseFloat(datos[3]),
          saldo: parseFloat(datos[4]),
          tipo: datos[5],
          dt: parseInt(datos[6]),
          cp: parseInt(datos[7]),
          deudaVend: parseFloat(datos[8]),
          cuota: parseFloat(datos[9])
        });
      }
    });

    guardarClientes();
    actualizarTabla();
  };

  reader.readAsText(archivo);
}
