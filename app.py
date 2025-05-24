from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
import re

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Configuración MongoDB Atlas
MONGO_URI = "mongodb+srv://root:Ryuzaki12599806@sesioncarbono.oahkgwc.mongodb.net/?retryWrites=true&w=majority&appName=sesionCarbono"
client = MongoClient(MONGO_URI)
db = client.mi_basedatos
usuarios = db.usuarios
registro_huella = db.registro_huella

# Configuración del correo
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'paulinaarreguinruiz108@gmail.com'
app.config['MAIL_PASSWORD'] = 'kyhk gpnm ftnp lbpn'
mail = Mail(app)

EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"

# -------------------------- RUTAS --------------------------

@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    mensajes_flash = get_flashed_messages(with_categories=True)

    if request.method == "POST":
        try:
            km = float(request.form["km"])
            if km < 0:
                raise ValueError("La distancia no puede ser negativa.")

            transporte = request.form["transporte"]
            factores = {
                "auto": 0.192,
                "bus": 0.089,
                "tren": 0.041,
                "bicicleta": 0.0,
                "moto": 0.103
            }

            if transporte not in factores:
                raise ValueError("Medio de transporte no válido.")

            factor = factores[transporte]
            huella = km * factor
            result = f"Usando {transporte}, tu huella semanal estimada es de {huella:.2f} kg de CO₂."

            user_id = session.get('user_id')
            if user_id:
                nuevo_registro = {
                    "km": km,
                    "transporte": transporte,
                    "huella": round(huella, 2),
                    "usuario_id": ObjectId(user_id),
                    "creado_en": datetime.utcnow()
                }
                registro_huella.insert_one(nuevo_registro)
            else:
                result = "Debes iniciar sesión para guardar tu huella de carbono."

        except ValueError as e:
            result = f"Error: {e}"

    nombre_usuario = None
    if 'user_id' in session:
        usuario = usuarios.find_one({"_id": ObjectId(session['user_id'])})
        if usuario:
            nombre_usuario = usuario.get("nombre")

    return render_template("index.html", result=result, nombre_usuario=nombre_usuario, mensajes_flash=mensajes_flash)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        usuario = usuarios.find_one({"email": email})
        if usuario and check_password_hash(usuario["password_hash"], password):
            session['user_id'] = str(usuario["_id"])
            flash(f'Bienvenido, {usuario["nombre"]}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')
            return redirect(url_for('login'))

    mensajes_flash = [msg for msg in get_flashed_messages(with_categories=True) if msg[0] == 'danger']
    return render_template('login.html', mensajes_flash=mensajes_flash)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nombre = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if not nombre or not email or not password:
            flash('Todos los campos son obligatorios.', 'warning')
            return redirect(url_for('register'))

        if not re.match(EMAIL_REGEX, email):
            flash('Correo electrónico no válido.', 'warning')
            return redirect(url_for('register'))

        if usuarios.find_one({"email": email}):
            flash('El correo ya está registrado', 'warning')
            return redirect(url_for('register'))

        password_hash = generate_password_hash(password)
        nuevo_usuario = {
            "nombre": nombre,
            "email": email,
            "password_hash": password_hash,
            "creado_en": datetime.utcnow()
        }
        usuarios.insert_one(nuevo_usuario)

        try:
            msg = Message(subject="Bienvenido a EcoHuella",
                          sender=app.config['MAIL_USERNAME'],
                          recipients=[email])
            msg.body = f"Hola {nombre},\n\nGracias por registrarte en EcoHuella. ¡Bienvenido/a!\n\nSaludos,\nEl equipo de EcoHuella"
            mail.send(msg)
        except Exception as e:
            print(f"Error enviando correo: {e}")

        flash('Registro exitoso, ya puedes iniciar sesión', 'success')
        return redirect(url_for('login'))

    mensajes_flash = [msg for msg in get_flashed_messages(with_categories=True) if msg[0] in ['warning', 'danger']]
    return render_template('register.html', mensajes_flash=mensajes_flash)


@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        usuario = usuarios.find_one({"_id": ObjectId(user_id)})
        if usuario:
            try:
                ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                msg = Message(subject="Sesión cerrada exitosamente",
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[usuario['email']])
                msg.html = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                        <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 20px; border-radius: 10px;">
                            <h2 style="color: #2e8b57;">Hola, {usuario['nombre']} 👋</h2>
                            <p>Tu sesión en <strong>EcoHuella</strong> se ha cerrado correctamente.</p>
                            <p><strong>Fecha y hora:</strong> {ahora}</p>
                            <p>Si no fuiste tú, por favor contáctanos lo antes posible.</p>
                            <br>
                            <p style="color: #888888;">Gracias por usar EcoHuella 🌱</p>
                        </div>
                    </body>
                </html>
                """
                mail.send(msg)
            except Exception as e:
                print(f"Error enviando correo de logout: {e}")

    session.pop('user_id', None)
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('index'))


@app.route("/test-db")
def test_db():
    try:
        # Prueba simple: contar usuarios
        count = usuarios.count_documents({})
        return f"✅ Conexión a la base de datos establecida. Usuarios registrados: {count}"
    except Exception as e:
        return f"❌ Error en la conexión a la base de datos: {e}"


# -------------------------- RUN --------------------------

if __name__ == "__main__":
    app.run(debug=True)
