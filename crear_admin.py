import os
from dotenv import load_dotenv
from flask_mysqldb import MySQL
from flask import Flask
from werkzeug.security import generate_password_hash

# Cargar variables de entorno
load_dotenv()

app = Flask(__name__)

# Configuración MySQL (igual que en app.py)
app.config['MYSQL_HOST'] = os.getenv("DB_HOST")
app.config['MYSQL_USER'] = os.getenv("DB_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("DB_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("DB_NAME")

mysql = MySQL(app)

def crear_admin(usuario, password):
    hash_password = generate_password_hash(password)

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO admins (usuario, password_hash) VALUES (%s, %s)",
        (usuario, hash_password)
    )
    mysql.connection.commit()
    cur.close()

    print("✅ Admin creado correctamente")

if __name__ == "__main__":
    usuario = input("Usuario: ")
    password = input("Contraseña: ")

    with app.app_context():
        crear_admin(usuario, password)
