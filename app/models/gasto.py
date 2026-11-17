from datetime import date

from app.extensions import db

TIPOS_DIVISION = ("iguales", "porcentaje", "montos")


class Gasto(db.Model):
    __tablename__ = "gastos"

    id = db.Column(db.Integer, primary_key=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey("grupos.id"), nullable=False)
    pagado_por = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)
    tipo_division = db.Column(db.String(20), nullable=False, default="iguales")

    divisiones = db.relationship("Division", backref="gasto", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "grupo_id": self.grupo_id,
            "pagado_por": self.pagado_por,
            "descripcion": self.descripcion,
            "monto": str(self.monto),
            "fecha": self.fecha.isoformat(),
            "tipo_division": self.tipo_division,
            "divisiones": [d.to_dict() for d in self.divisiones],
        }


class Division(db.Model):
    """Parte de un gasto que le toca a un usuario. La crea Gasto.dividir_gasto."""

    __tablename__ = "divisiones"

    gasto_id = db.Column(db.Integer, db.ForeignKey("gastos.id"), primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), primary_key=True)
    monto = db.Column(db.Numeric(10, 2), nullable=False)

    def to_dict(self):
        return {"usuario_id": self.usuario_id, "monto": str(self.monto)}
