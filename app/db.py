from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from os import getenv

ADMIN_DB_URL = getenv("ADMIN_DB_URL")
WORKER_DB_URL = getenv("WORKER_DB_URL")

# Engines
engine_admin = create_engine(ADMIN_DB_URL, future=True)
engine_worker = create_engine(WORKER_DB_URL, future=True)

# Session makers
SessionAdmin = scoped_session(sessionmaker(bind=engine_admin, autoflush=False, autocommit=False))
SessionWorker = scoped_session(sessionmaker(bind=engine_worker, autoflush=False, autocommit=False))

def get_session_for_role(role):
    """
    role: 'admin' or 'trabajador'
    Devuelve la sesión correspondiente.
    """
    if role == "admin":
        return SessionAdmin()
    else:
        # trabajador o cualquier otro -> sesión worker (solo SELECTs garantizados por permisos DB)
        return SessionWorker()
