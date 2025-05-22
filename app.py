from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.security import generate_password_hash, check_password_hash
import re
from flask_mail import Mail, Message
from datetime import datetime  # <-- NUEVO IMPORT

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta'

# Configuración de la base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:Ryuzaki12599806@localhost/sesionCarbono'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración del correo
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'paulinaarreguinruiz108@gmail.com'
app.config['MAIL_PASSWORD'] = 'kyhk gpnm ftnp lbpn'

# Inicialización
db = SQLAlchemy(app)
mail = Mail(app)

EMAIL_REGEX = r"[^@]+@[^@]+\.[^@]+"

# -------------------------- MODELOS --------------------------

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    registros = db.relationship('RegistroHuella', backref='usuario', cascade="all, delete", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class RegistroHuella(db.Model):
    __tablename__ = 'registro_huella'
    id = db.Column(db.Integer, primary_key=True)
    km = db.Column(db.Float, nullable=False)
    transporte = db.Column(db.String(50), nullable=False)
    huella = db.Column(db.Float, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)
    creado_en = db.Column(db.DateTime, server_default=text('CURRENT_TIMESTAMP'))

# -------------------------- DB INIT --------------------------

with app.app_context():
    try:
        db.session.execute(text('SELECT 1'))
        print("✅ Conexión a MySQL exitosa.")
    except Exception as e:
        print("❌ Error al conectar con MySQL:", e)

    db.create_all()

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

            usuario_id = session.get('user_id')
            if usuario_id:
                nuevo_registro = RegistroHuella(km=km, transporte=transporte, huella=round(huella, 2), usuario_id=usuario_id)
                db.session.add(nuevo_registro)
                db.session.commit()
            else:
                result = "Debes iniciar sesión para guardar tu huella de carbono."

        except ValueError as e:
            result = f"Error: {e}"

    nombre_usuario = None
    if 'user_id' in session:
        usuario = Usuario.query.get(session['user_id'])
        if usuario:
            nombre_usuario = usuario.nombre

    return render_template("index.html", result=result, nombre_usuario=nombre_usuario, mensajes_flash=mensajes_flash)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and usuario.check_password(password):
            session['user_id'] = usuario.id
            flash(f'Bienvenido, {usuario.nombre}!', 'success')
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

        if Usuario.query.filter_by(email=email).first():
            flash('El correo ya está registrado', 'warning')
            return redirect(url_for('register'))

        nuevo_usuario = Usuario(nombre=nombre, email=email)
        nuevo_usuario.set_password(password)
        db.session.add(nuevo_usuario)
        db.session.commit()

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
    usuario_id = session.get('user_id')
    if usuario_id:
        usuario = Usuario.query.get(usuario_id)
        if usuario:
            try:
                ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                msg = Message(subject="Sesión cerrada exitosamente",
                              sender=app.config['MAIL_USERNAME'],
                              recipients=[usuario.email])
                msg.html = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
                        <div style="max-width: 600px; margin: auto; background-color: #ffffff; padding: 20px; border-radius: 10px;">
                            <h2 style="color: #2e8b57;">Hola, {usuario.nombre} 👋</h2>
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
        db.session.execute(text('SELECT 1'))
        return "✅ Conexión a la base de datos establecida correctamente."
    except Exception as e:
        return f"❌ Error en la conexión a la base de datos: {e}"


# -------------------------- RUN --------------------------

if __name__ == "__main__":
    app.run(debug=True)
