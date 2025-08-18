# Imagen base con Python 3.10 (compatible con tu versión)
FROM python:3.10-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Copiar todo el proyecto
COPY . .

# Exponer el puerto
EXPOSE 8080

# Comando de arranque (Gunicorn + Flask)
CMD ["gunicorn", "-b", ":8080", "app:app"]
