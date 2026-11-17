from flask_sqlalchemy import SQLAlchemy

# Una sola instancia compartida por todos los modelos; se conecta a la app en create_app().
db = SQLAlchemy()
