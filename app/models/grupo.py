from app.extensions import db

# Tabla de asociación muchos a muchos entre grupos y usuarios.
grupo_miembros = db.Table(
    "grupo_miembros",
    db.Column("grupo_id", db.Integer, db.ForeignKey("grupos.id"), primary_key=True),
    db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), primary_key=True),
)


class Grupo(db.Model):
    __tablename__ = "grupos"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False, default="")
    creado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    miembros = db.relationship("Usuario", secondary=grupo_miembros, lazy="select")
    # Al borrar un grupo se borran sus gastos y pagos.
    gastos = db.relationship("Gasto", backref="grupo", cascade="all, delete-orphan")
    pagos = db.relationship("Pago", backref="grupo", cascade="all, delete-orphan")

    def es_miembro(self, usuario_id):
        return any(m.id == usuario_id for m in self.miembros)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "creado_por": self.creado_por,
            "miembros": [m.to_dict() for m in self.miembros],
        }
