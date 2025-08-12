from app import create_app
from app.db import engine_admin
from app.models import Base

app = create_app()

if __name__ == "__main__":
    # crear tablas (si no existen) usando engine_admin (necesario solo la primera vez)
    Base.metadata.create_all(bind=engine_admin)
    app.run(debug=True, host="0.0.0.0", port=5000)
