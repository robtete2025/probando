import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change_me")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_jwt")
    # NO ponemos SQLALCHEMY_DATABASE_URI global: usaremos 2 conexiones separadas
