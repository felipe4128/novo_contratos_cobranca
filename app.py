
import os
from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func

# ---------------- App/DB ----------------
app = Flask(__name__, instance_relative_config=True)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Garante pasta instance (SQLite local persistente)
os.makedirs(app.instance_path, exist_ok=True)
sqlite_uri = "sqlite:///" + os.path.join(app.instance_path, "credito.db")

# Se tiver DATABASE_URL (Render/Postgres), usa; corrige postgres://
uri = (os.environ.get("DATABASE_URL") or "").strip()
if uri and uri.startswith("postgres://"):
    uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = uri or sqlite_uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --------------- Models -----------------
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(20))
    cliente = db.Column(db.String(200))
    contrato = db.Column(db.String(50))
    tipo = db.Column(db.String(50))

    valor = db.Column(db.Float, default=0.0)       # Valor total do contrato
    pago = db.Column(db.Float, default=0.0)        # Valor pago acumulado
    abatido = db.Column(db.Float, default=0.0)

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

    parcelas = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan", lazy=True)

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Date)
    valor = db.Column(db.Float, default=0.0)
    baixado_em = db.Column(db.Date)  # data da baixa

# --------------- Helpers ----------------
@app.template_filter("brl")
def brl(v):
    try:
        return f"{float(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

@app.template_filter("data")
def data_fmt(v):
    if not v:
        return ""
    if isinstance(v, (date, datetime)):
        return v.strftime("%d/%m/%Y")
    try:
        return datetime.fromisoformat(str(v)).strftime("%d/%m/%Y")
    except Exception:
        return str(v)

def parse_date(v):
    if not v:
        return None
    v = v.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(v, fmt).date()
        except Exception:
            pass
    return None

def add_month(d):
    y = d.year + (1 if d.month == 12 else 0)
    m = 1 if d.month == 12 else d.month + 1
    from calendar import monthrange
    last = monthrange(y, m)[1]
    day = min(d.day, last)
    return date(y, m, day)

# ------------- Init DB (Flask 3.x) -------------
with app.app_context():
    db.create_all()

# ----------------- Rotas -----------------
@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.id.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        c = Contrato(
            cpf=(request.form.get("cpf") or "").strip(),
            cliente=(request.form.get("cliente") or "").strip(),
            contrato=(request.form.get("contrato") or "").strip(),
            tipo=(request.form.get("tipo") or "").strip(),
            valor=float(request.form.get("valor_total") or 0),
            pago=float(request.form.get("valor_pago") or 0),
            abatido=float(request.form.get("valor_abatido") or 0),
            custas=float(request.form.get("custas") or 0),
            custas_deduzida=float(request.form.get("custas_deduzida") or 0),
            protesto=float(request.form.get("protesto") or 0),
            protesto_deduzido=float(request.form.get("protesto_deduzido") or 0),
            honorario=float(request.form.get("honorario") or 0),
            honorario_repassado=float(request.form.get("honorario_repassado") or 0),
            alvara=float(request.form.get("alvara") or 0),
            alvara_recebido=float(request.form.get("alvara_recebido") or 0),
            ganho=float(request.form.get("ganho") or 0),
        )
        db.session.add(c)
        db.session.flush()

        qtd = int(request.form.get("qtd_parcelas") or 0)
        v_parcela = request.form.get("valor_parcela")
        v_parcela = float(v_parcela) if v_parcela not in (None, "",) else None
        primeiro_venc = parse_date(request.form.get("primeiro_vencimento"))
        if qtd and primeiro_venc:
            if v_parcela is None and c.valor:
                v_parcela = round(c.valor / qtd, 2)
            venc = primeiro_venc
            for i in range(1, qtd + 1):
                p = Parcela(contrato_id=c.id, numero=i, vencimento=venc, valor=v_parcela or 0.0)
                db.session.add(p)
                venc = add_month(venc)

        db.session.commit()
        flash("Contrato cadastrado com sucesso!", "success")
        return redirect(url_for("parcelas", id=c.id))

    return render_template("novo.html")

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        # Atualiza campos principais e financeiros
        c.cpf = (request.form.get("cpf") or "").strip()
        c.cliente = (request.form.get("cliente") or "").strip()
        c.contrato = (request.form.get("contrato") or "").strip()
        c.tipo = (request.form.get("tipo") or "").strip()
        for fld in ["valor_total","valor_pago","valor_abatido","custas","custas_deduzida",
                    "protesto","protesto_deduzido","honorario","honorario_repassado",
                    "alvara","alvara_recebido","ganho"]:
            val = request.form.get(fld)
            try:
                setattr(c, 
                        {"valor_total":"valor","valor_pago":"pago","valor_abatido":"abatido"}.get(fld, fld), 
                        float(val or 0))
            except Exception:
                setattr(c, 
                        {"valor_total":"valor","valor_pago":"pago","valor_abatido":"abatido"}.get(fld, fld), 
                        0.0)
        db.session.commit()
        flash("Contrato atualizado.", "success")
        return redirect(url_for("index"))
    return render_template("editar.html", c=c)

@app.route("/parcelas/<int:id>")
@app.route("/contrato/<int:id>/parcelas")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()

    total_parcelas = len(parcels)
    pagas = len([p for p in parcels if p.baixado_em])
    abertas = total_parcelas - pagas

    resumo = {
        "valor": c.valor or 0,
        "valor_pago": c.pago or 0,
        "valor_abatido": c.abatido or 0,
        "custas": c.custas or 0,
        "custas_deduzida": c.custas_deduzida or 0,
        "protesto": c.protesto or 0,
        "protesto_deduzido": c.protesto_deduzido or 0,
        "honorario": c.honorario or 0,
        "honorario_repassado": c.honorario_repassado or 0,
        "alvara": c.alvara or 0,
        "alvara_recebido": c.alvara_recebido or 0,
        "ganho": c.ganho or 0,
        "qtd_parcelas": total_parcelas,
        "parcelas_pagas": pagas,
        "parcelas_abertas": abertas,
    }
    return render_template("parcelas.html", contrato=c, parcels=parcels, resumo=resumo)

@app.route("/baixar_parcela/<int:contrato_id>/<int:parcela_id>", methods=["POST"])
def baixar_parcela(contrato_id, parcela_id):
    p = Parcela.query.filter_by(id=parcela_id, contrato_id=contrato_id).first_or_404()
    if not p.baixado_em:
        p.baixado_em = date.today()
        # Atualiza total pago no contrato somando o valor desta parcela
        if p.valor:
            p.contrato.pago = (p.contrato.pago or 0) + p.valor
        db.session.commit()
        flash("Parcela baixada com sucesso!", "success")
    return redirect(url_for("parcelas", id=contrato_id))

@app.route("/info/<int:id>")
def info(id):
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
    from io import StringIO, BytesIO
    import csv
    mem = StringIO()
    w = csv.writer(mem, delimiter=";")
    w.writerow(["id","cpf","cliente","contrato","tipo","valor","pago"])
    for c in Contrato.query.order_by(Contrato.id.asc()).all():
        w.writerow([c.id, c.cpf, c.cliente, c.contrato, c.tipo, c.valor or 0, c.pago or 0])
    mem.seek(0)
    bio = BytesIO(mem.getvalue().encode("utf-8-sig"))
    bio.seek(0)
    return send_file(bio, mimetype="text/csv", as_attachment=True, download_name="contratos.csv")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
