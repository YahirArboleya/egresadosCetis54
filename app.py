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


# ================== CONFIGURACIÓN ==================
app = Flask(__name__)
app.secret_key = 'clave_secreta'

ADMIN_USER = "admin"
ADMIN_PASS = "cetis54"

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'cetis54_egresados'

mysql = MySQL(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


# ================== FUNCIONES AUX ==================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


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
        return redirect(url_for('home'))

    nom_pago = secure_filename(f"{curp}_PAGO.pdf")
    nom_escolar = secure_filename(f"{curp}_ESCOLAR.pdf")

    file_pago.save(os.path.join(UPLOAD_FOLDER, nom_pago))
    file_escolar.save(os.path.join(UPLOAD_FOLDER, nom_escolar))

    cur = mysql.connection.cursor()

    cur.execute("SELECT id FROM solicitudes WHERE curp = %s", (curp,))
    if cur.fetchone():
        cur.close()
        flash("Esta CURP ya tiene una solicitud registrada")
        return redirect(url_for('home'))

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
    return redirect(url_for('home'))


# ================== PANEL ADMIN ==================
@app.route('/admin')
def admin_panel():
    if not session.get('admin'):
        return redirect(url_for('login'))

    estatus_filtro = request.args.get('estatus')
    cur = mysql.connection.cursor()

    # Contadores
    cur.execute("SELECT estatus_tramite, COUNT(*) FROM solicitudes GROUP BY estatus_tramite")
    conteos = cur.fetchall()

    contadores = {
        'Pendiente': 0,
        'En revisión': 0,
        'Aprobado': 0,
        'Rechazado': 0
    }

    for est, total in conteos:
        contadores[est] = total

    # Listado
    if estatus_filtro:
        cur.execute("""
            SELECT id, nombre_completo, curp, numero_control,
                   especialidad, ruta_pdf_pago, ruta_pdf_escolar, estatus_tramite
            FROM solicitudes
            WHERE estatus_tramite = %s
            ORDER BY fecha_registro DESC
        """, (estatus_filtro,))
    else:
        cur.execute("""
            SELECT id, nombre_completo, curp, numero_control,
                   especialidad, ruta_pdf_pago, ruta_pdf_escolar, estatus_tramite
            FROM solicitudes
            ORDER BY fecha_registro DESC
        """)

    datos = cur.fetchall()
    cur.close()

    return render_template(
        'admin.html',
        solicitudes=datos,
        estatus=estatus_filtro,
        contadores=contadores
    )


# ================== ACTUALIZAR ESTATUS ==================
@app.route('/actualizar_estatus', methods=['POST'])
def actualizar_estatus():
    if not session.get('admin'):
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE solicitudes SET estatus_tramite = %s WHERE id = %s",
        (request.form['estatus'], request.form['id'])
    )
    mysql.connection.commit()
    cur.close()

    return redirect(url_for('admin_panel'))


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


# ================== ARCHIVOS ==================
@app.route('/uploads/<filename>')
def descargar_archivo(filename):
    if not session.get('admin'):
        return redirect(url_for('login'))
    return send_from_directory(UPLOAD_FOLDER, filename)


@app.route('/')
def home():
    return render_template('index.html')


# ================== EXPORTAR PDF ==================
@app.route('/exportar_pdf')
def exportar_pdf():
    if not session.get('admin'):
        return redirect(url_for('login'))

    estatus = request.args.get('estatus')
    cur = mysql.connection.cursor()

    if estatus:
        cur.execute("""
            SELECT nombre_completo, curp, numero_control,
                   especialidad, estatus_tramite
            FROM solicitudes WHERE estatus_tramite = %s
        """, (estatus,))
    else:
        cur.execute("""
            SELECT nombre_completo, curp, numero_control,
                   especialidad, estatus_tramite
            FROM solicitudes
        """)

    datos = cur.fetchall()
    cur.close()

    ruta_pdf = os.path.join(UPLOAD_FOLDER, "solicitudes_cetis54.pdf")
    doc = SimpleDocTemplate(ruta_pdf, pagesize=A4,
                            rightMargin=2*cm, leftMargin=2*cm,
                            topMargin=2*cm, bottomMargin=2*cm)

    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph("<b>CETIS 54</b><br/>Reporte de Solicitudes", estilos['Title']),
        Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilos['Normal']),
        Paragraph("<br/>", estilos['Normal'])
    ]

    tabla_datos = [["Nombre", "CURP", "Control", "Especialidad", "Estatus"]]
    tabla_datos.extend(datos)

    tabla = Table(tabla_datos, colWidths=[5*cm, 3*cm, 3*cm, 3*cm, 3*cm])

    estilo = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#621132")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.white),
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold')
    ])

    for i, fila in enumerate(tabla_datos[1:], start=1):
        colores = {
            "Pendiente": "#ffe08a",
            "En revisión": "#9fd3e6",
            "Aprobado": "#9be7b0",
            "Rechazado": "#f5a3a3"
        }
        estilo.add('BACKGROUND', (0,i), (-1,i), colors.HexColor(colores[fila[4]]))

    tabla.setStyle(estilo)
    elementos.append(tabla)

    doc.build(elementos)
    return send_from_directory(UPLOAD_FOLDER, "solicitudes_cetis54.pdf", as_attachment=True)


# ================== EXPORTAR EXCEL ==================
@app.route('/exportar_excel')
def exportar_excel():
    if not session.get('admin'):
        return redirect(url_for('login'))

    estatus = request.args.get('estatus')
    cur = mysql.connection.cursor()

    if estatus:
        cur.execute("""
            SELECT nombre_completo, curp, numero_control,
                   especialidad, estatus_tramite
            FROM solicitudes WHERE estatus_tramite = %s
        """, (estatus,))
    else:
        cur.execute("""
            SELECT nombre_completo, curp, numero_control,
                   especialidad, estatus_tramite
            FROM solicitudes
        """)

    datos = cur.fetchall()
    cur.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Solicitudes"

    ws.append(["Nombre", "CURP", "No. Control", "Especialidad", "Estatus"])
    for fila in datos:
        ws.append(fila)

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)

    return send_file(
        stream,
        as_attachment=True,
        download_name="solicitudes_duplicados.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == '__main__':
    app.run(debug=True)
