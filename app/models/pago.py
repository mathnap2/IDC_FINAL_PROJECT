from datetime import date

from app.extensions import db


class Pago(db.Model):
    """Transferencia de un miembro a otro para saldar deudas dentro de un grupo."""

    __tablename__ = "pagos"

    id = db.Column(db.Integer, primary_key=True)
    grupo_id = db.Column(db.Integer, db.ForeignKey("grupos.id"), nullable=False)
    de_usuario = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    a_usuario = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    monto = db.Column(db.Numeric(10, 2), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=date.today)

    def to_dict(self):
        return {
            "id": self.id,
            "grupo_id": self.grupo_id,
            "de_usuario": self.de_usuario,
            "a_usuario": self.a_usuario,
            "monto": str(self.monto),
            "fecha": self.fecha.isoformat(),
        }
