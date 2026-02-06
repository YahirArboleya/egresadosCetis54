import os
import io
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, send_from_directory, send_file
)
from werkzeug.utils import secure_filename
from flask_mysqldb import MySQL

# ===== PDF =====
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

# ===== EXCEL =====
from openpyxl import Workbook

# ===== ENV =====
from dotenv import load_dotenv
load_dotenv()

# ================== APP ==================
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

# ================== CONFIG MYSQL ==================
app.config['MYSQL_HOST'] = os.getenv("DB_HOST")
app.config['MYSQL_USER'] = os.getenv("DB_USER")
app.config['MYSQL_PASSWORD'] = os.getenv("DB_PASSWORD")
app.config['MYSQL_DB'] = os.getenv("DB_NAME")

mysql = MySQL(app)

# ================== CONFIG GENERAL ==================
ADMIN_USER = "admin"
ADMIN_PASS = "cetis54"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ================== UTILIDADES ==================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ================== HOME ==================
@app.route('/')
def home():
    return render_template('inicio.html')

#================ FORMULARIO ==================
@app.route('/formulario')
def formulario():
    return render_template('index.html')


#============== VERIFICACIÓN ==================
@app.route('/verificacion', methods=['GET', 'POST'])
def verificacion():
    if request.method == 'POST':
        documentos = request.form.get('documentos')

        if documentos != 'si':
            flash("Para continuar con el trámite en línea debes contar con los documentos oficiales en PDF.")
            return redirect(url_for('verificacion'))

        return redirect(url_for('pago_sep'))

    return render_template('verificacion.html')



#====== PAGO SEP ==================
@app.route('/pago', methods=['GET', 'POST'])
def pago_sep():
    if request.method == 'POST':
        if request.form.get('pago') == 'si':
            return redirect(url_for('aviso_privacidad'))
        else:
            flash("Si no cuentas con el pago, el trámite debe realizarse de manera presencial.")
            return redirect(url_for('pago_sep'))

    return render_template('pago_sep.html')


#================= AVISO DE PRIVACIDAD ==================
@app.route('/aviso-privacidad', methods=['GET', 'POST'])
def aviso_privacidad():
    if request.method == 'POST':
        if request.form.get('acepta'):
            return redirect(url_for('formulario'))
        else:
            flash("Debes aceptar el aviso de privacidad para continuar.")
            return redirect(url_for('aviso_privacidad'))

    return render_template('aviso_privacidad.html')


# ================== REGISTRO ==================
@app.route('/registrar', methods=['POST'])
def registrar():
    paterno = request.form['paterno'].upper()
    materno = request.form['materno'].upper()
    nombre = request.form['nombre'].upper()
    nombre_completo = f"{paterno} {materno} {nombre}"

    curp = request.form['curp'].upper()
    control = request.form['control']
    especialidad = request.form['especialidad']
    turno = request.form['turno']
    generacion = request.form['generacion']
    correo = request.form['correo']
    telefono = request.form['telefono']

    banco = request.form['banco']
    llave = request.form['llave']
    monto = request.form['monto']

    file_pago = request.files['file_pago']
    file_escolar = request.files['file_escolar']

    if not (allowed_file(file_pago.filename) and allowed_file(file_escolar.filename)):
        flash("Archivos inválidos")
        return redirect(url_for('formulario'))

    nom_pago = secure_filename(f"{curp}_PAGO.pdf")
    nom_escolar = secure_filename(f"{curp}_ESCOLAR.pdf")

    file_pago.save(os.path.join(UPLOAD_FOLDER, nom_pago))
    file_escolar.save(os.path.join(UPLOAD_FOLDER, nom_escolar))

    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM solicitudes WHERE curp = %s", (curp,))
    if cur.fetchone():
        cur.close()
        flash("Esta CURP ya tiene una solicitud registrada")
        return redirect(url_for('formulario'))

    cur.execute("""
        INSERT INTO solicitudes (
            apellido_paterno, apellido_materno, nombre_completo,
            curp, numero_control, especialidad, turno, generacion,
            correo_electronico, telefono_celular,
            banco_pago, llave_pago, monto_pago,
            ruta_pdf_pago, ruta_pdf_escolar, estatus_tramite
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'Pendiente')
    """, (
        paterno, materno, nombre_completo,
        curp, control, especialidad, turno, generacion,
        correo, telefono, banco, llave, monto,
        nom_pago, nom_escolar
    ))

    mysql.connection.commit()
    cur.close()

    flash("Solicitud registrada correctamente")
    return redirect(url_for('formulario'))

# ================== LOGIN ==================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['usuario'] == ADMIN_USER and request.form['password'] == ADMIN_PASS:
            session['admin'] = True
            return redirect(url_for('admin_panel'))
        flash("Credenciales incorrectas")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ================== ADMIN ==================
@app.route('/admin')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('login'))

    estatus = request.args.get('estatus')
    cur = mysql.connection.cursor()

    cur.execute("SELECT estatus_tramite, COUNT(*) FROM solicitudes GROUP BY estatus_tramite")
    contadores = {e: 0 for e in ['Pendiente', 'En revisión', 'Aprobado', 'Rechazado']}
    for e, t in cur.fetchall():
        contadores[e] = t

    if estatus:
        cur.execute("""
            SELECT id, nombre_completo, curp, numero_control,
                   especialidad, ruta_pdf_pago, ruta_pdf_escolar, estatus_tramite
            FROM solicitudes WHERE estatus_tramite=%s
            ORDER BY fecha_registro DESC
        """, (estatus,))
    else:
        cur.execute("""
            SELECT id, nombre_completo, curp, numero_control,
                   especialidad, ruta_pdf_pago, ruta_pdf_escolar, estatus_tramite
            FROM solicitudes ORDER BY fecha_registro DESC
        """)

    datos = cur.fetchall()
    cur.close()

    return render_template("admin.html", solicitudes=datos, contadores=contadores, estatus=estatus)

# ================== ACTUALIZAR ESTATUS ==================
@app.route('/actualizar_estatus', methods=['POST'])
def actualizar_estatus():
    if not session.get('admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE solicitudes SET estatus_tramite=%s WHERE id=%s",
        (request.form['estatus'], request.form['id'])
    )
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin_panel'))

# ================== DESCARGAR ARCHIVOS ==================
@app.route('/uploads/<filename>')
def descargar_archivo(filename):
    if not session.get('admin'):
        return redirect(url_for('login'))
    return send_from_directory(UPLOAD_FOLDER, filename)

# ================== EXPORTAR PDF ==================
@app.route('/exportar_pdf')
def exportar_pdf():
    if not session.get('admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT nombre_completo, curp, numero_control, especialidad, estatus_tramite
        FROM solicitudes
    """)
    datos = cur.fetchall()
    cur.close()

    ruta = os.path.join(UPLOAD_FOLDER, "solicitudes.pdf")
    doc = SimpleDocTemplate(ruta, pagesize=A4)

    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph("<b>CETIS 54</b><br/>Reporte de Solicitudes", estilos['Title']),
        Paragraph(datetime.now().strftime("%d/%m/%Y %H:%M"), estilos['Normal'])
    ]

    tabla = Table([["Nombre","CURP","Control","Especialidad","Estatus"]] + datos)
    tabla.setStyle(TableStyle([
        ('GRID',(0,0),(-1,-1),0.5,colors.grey),
        ('BACKGROUND',(0,0),(-1,0),colors.HexColor("#621132")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.white)
    ]))

    elementos.append(tabla)
    doc.build(elementos)

    return send_from_directory(UPLOAD_FOLDER, "solicitudes.pdf", as_attachment=True)

# ================== EXPORTAR EXCEL ==================
@app.route('/exportar_excel')
def exportar_excel():
    if not session.get('admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT nombre_completo, curp, numero_control, especialidad, estatus_tramite
        FROM solicitudes
    """)
    datos = cur.fetchall()
    cur.close()

    wb = Workbook()
    ws = wb.active
    ws.append(["Nombre","CURP","Control","Especialidad","Estatus"])
    for fila in datos:
        ws.append(fila)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return send_file(stream, as_attachment=True,
        download_name="solicitudes.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ================== RUN ==================
if __name__ == '__main__':
    app.run(debug=True)
