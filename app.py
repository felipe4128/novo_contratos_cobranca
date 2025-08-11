
import os
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy

# ----------------------------------------------------------------------------
# App e DB
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Caminho para SQLite local (persistente)
os.makedirs(app.instance_path, exist_ok=True)
default_sqlite = "sqlite:///" + os.path.join(app.instance_path, "credito.db")

# DATABASE_URL (Render / Postgres) ou SQLite local
uri = os.environ.get("DATABASE_URL", "").strip()
if uri:
    # Render às vezes envia 'postgres://'
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    uri = default_sqlite

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------------
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(20), nullable=True)
    cliente = db.Column(db.String(200), nullable=False)
    contrato = db.Column(db.String(50), nullable=True)          # número do contrato
    tipo = db.Column(db.String(20), nullable=True)

    valor = db.Column(db.Float, default=0.0)                     # valor total
    pago = db.Column(db.Float, default=0.0)                      # valor pago

    # Campos do resumo
    valor_abatido = db.Column(db.Float, default=0.0)
    custas = db.Column(db.Float, default=0.0)
    custas_deduzida = db.Column(db.Float, default=0.0)
    protesto = db.Column(db.Float, default=0.0)
    protesto_deduzido = db.Column(db.Float, default=0.0)
    honorario = db.Column(db.Float, default=0.0)
    honorario_repassado = db.Column(db.Float, default=0.0)
    alvara = db.Column(db.Float, default=0.0)
    alvara_recebido = db.Column(db.Float, default=0.0)
    ganho = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan", lazy="dynamic")

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False, default=1)
    vencimento = db.Column(db.Date, nullable=True)
    valor = db.Column(db.Float, default=0.0)
    baixado_em = db.Column(db.Date, nullable=True)

# ----------------------------------------------------------------------------
# Helpers / Filtros Jinja
# ----------------------------------------------------------------------------
def brl(v):
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

def data(dt):
    if not dt:
        return ""
    if isinstance(dt, (datetime, date)):
        return dt.strftime("%d/%m/%Y")
    return str(dt)

app.jinja_env.filters["brl"] = brl
app.jinja_env.filters["data"] = data

# ----------------------------------------------------------------------------
# Migração mínima (cria tabelas se não existirem)
# ----------------------------------------------------------------------------
with app.app_context():
    db.create_all()

# ----------------------------------------------------------------------------
# Rotas
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    contratos = (
        Contrato.query
        .order_by(Contrato.created_at.desc())
        .all()
    )
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        # Campos básicos
        c = Contrato(
            cpf=request.form.get("cpf") or "",
            cliente=request.form.get("cliente") or "",
            contrato=request.form.get("contrato") or "",
            tipo=request.form.get("tipo") or "",
            valor=float(request.form.get("valor_total") or 0),
            pago=float(request.form.get("valor_pago") or 0),
        )
        db.session.add(c)
        db.session.flush()  # obter id antes de gerar parcelas

        # Geração de parcelas
        try:
            qtd = int(request.form.get("qtd_parcelas") or 0)
        except Exception:
            qtd = 0
        valor_parcela = float(request.form.get("valor_parcela") or 0)
        primeiro_venc = request.form.get("primeiro_vencimento") or ""
        try:
            base = datetime.strptime(primeiro_venc, "%Y-%m-%d").date() if primeiro_venc else None
        except Exception:
            base = None

        for i in range(qtd):
            venc = base + relativedelta(months=i) if base else None
            p = Parcela(contrato_id=c.id, numero=i+1, vencimento=venc, valor=valor_parcela)
            db.session.add(p)

        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("parcelas", id=c.id))

    return render_template("novo.html")

@app.route("/contrato/<int:id>/parcelas")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = c.parcelas.order_by(Parcela.numero.asc()).all()

    # Monta 'resumo' para exibição no topo (cards)
    resumo = {
        "valor": c.valor,
        "valor_pago": c.pago,
        "valor_abatido": c.valor_abatido,
        "custas": c.custas,
        "custas_deduzida": c.custas_deduzida,
        "protesto": c.protesto,
        "protesto_deduzido": c.protesto_deduzido,
        "honorario": c.honorario,
        "honorario_repassado": c.honorario_repassado,
        "alvara": c.alvara,
        "alvara_recebido": c.alvara_recebido,
        "ganho": c.ganho,
    }
    return render_template("parcelas.html", contrato=c, parcels=parcels, resumo=resumo)

@app.route("/contrato/<int:cid>/parcela/<int:pid>/baixar", methods=["POST"])
def baixar_parcela(cid, pid):
    p = Parcela.query.filter_by(id=pid, contrato_id=cid).first_or_404()
    if not p.baixado_em:
        p.baixado_em = date.today()
        db.session.commit()
        flash("Parcela baixada com sucesso!", "success")
    return redirect(url_for("parcelas", id=cid))

@app.route("/info/<int:id>")
def editar_info(id):
    c = Contrato.query.get_or_404(id)
    return render_template("info.html", c=c)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "warning")
    return redirect(url_for("index"))

@app.route("/exportar")
def exportar():
    # CSV simples
    from io import StringIO, BytesIO
    import csv
    output = StringIO()
    writer = csv.writer(output, delimiter=';')
    writer.writerow(["ID","CPF","Cliente","Contrato","Tipo","Valor","Pago"])
    for x in Contrato.query.order_by(Contrato.id.asc()).all():
        writer.writerow([x.id, x.cpf, x.cliente, x.contrato, x.tipo, f"{x.valor:.2f}", f"{x.pago:.2f}"])
    data = output.getvalue().encode("utf-8-sig")
    mem = BytesIO(data)
    mem.seek(0)
    return send_file(mem, as_attachment=True, download_name="contratos.csv", mimetype="text/csv")

# Alias compatível com o que você já usava (se necessário)
@app.route("/parcelas/<int:id>")
def ver_parcelas_compat(id):
    return redirect(url_for("parcelas", id=id))

# ----------------------------------------------------------------------------
# Run
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
