
import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
import csv
from io import StringIO

def fix_database_url(uri: str) -> str:
    # render sometimes gives postgres://
    if uri and uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql+psycopg2://", 1)
    return uri

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

# ensure instance folder
os.makedirs(app.instance_path, exist_ok=True)

# DB config
uri = os.environ.get("DATABASE_URL", "").strip()
if uri:
    uri = fix_database_url(uri)
else:
    db_path = os.path.join(app.instance_path, "credito.db")
    uri = f"sqlite:///{db_path}"

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# Models
class Contrato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(20))
    cliente = db.Column(db.String(120))
    contrato = db.Column(db.String(50))
    tipo = db.Column(db.String(50))

    valor = db.Column(db.Float, default=0)          # valor total
    pago = db.Column(db.Float, default=0)           # valor pago
    abatido = db.Column(db.Float, default=0)
    custas = db.Column(db.Float, default=0)
    custas_deduzida = db.Column(db.Float, default=0)
    protesto = db.Column(db.Float, default=0)
    protesto_deduzido = db.Column(db.Float, default=0)
    honorario = db.Column(db.Float, default=0)
    honorario_repassado = db.Column(db.Float, default=0)
    alvara = db.Column(db.Float, default=0)
    alvara_recebido = db.Column(db.Float, default=0)
    ganho = db.Column(db.Float, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan", lazy=True)

class Parcela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Float, default=0)
    baixado_em = db.Column(db.Date)

def brl(value):
    try:
        v = float(value or 0)
    except Exception:
        v = 0.0
    # Simple Brazilian format
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

app.jinja_env.filters["brl"] = brl

def parse_iso_date(s: str):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

@app.before_first_request
def init_db():
    db.create_all()

@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.created_at.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        cpf = request.form.get("cpf", "").strip()
        cliente = request.form.get("cliente", "").strip()
        numero_contrato = request.form.get("contrato", "").strip()
        tipo = request.form.get("tipo", "").strip()
        try:
            valor_total = float(request.form.get("valor", "0").replace(",", ".") or 0)
        except:
            valor_total = 0.0
        try:
            valor_pago = float(request.form.get("pago", "0").replace(",", ".") or 0)
        except:
            valor_pago = 0.0

        try:
            qtd_parcelas = int(request.form.get("parcelas", "0") or 0)
        except:
            qtd_parcelas = 0

        venc_entrada = parse_iso_date(request.form.get("vencimento_entrada", ""))

        c = Contrato(
            cpf=cpf, cliente=cliente, contrato=numero_contrato, tipo=tipo,
            valor=valor_total, pago=valor_pago
        )
        db.session.add(c)
        db.session.flush()  # get id

        if qtd_parcelas > 0 and venc_entrada:
            valor_parcela = round((valor_total / qtd_parcelas) if valor_total else 0, 2)
            # gerar mensal
            v = venc_entrada
            for n in range(1, qtd_parcelas + 1):
                p = Parcela(contrato_id=c.id, numero=n, vencimento=v, valor=valor_parcela)
                db.session.add(p)
                # proximo mês (aprox, soma 30 dias até cair no mesmo dia)
                month = v.month + 1
                year = v.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                # mantém dia se possível, senão último dia do mês
                day = min(v.day, [31, 29 if year%4==0 and (year%100!=0 or year%400==0) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
                v = date(year, month, day)

        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("novo.html")

@app.route("/parcelas/<int:id>")
@app.route("/contrato/<int:id>/parcelas")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()

    # resumo simples (poderia ser ajustado conforme regra)
    resumo = dict(
        valor=c.valor or 0,
        pago=c.pago or 0,
        abatido=c.abatido or 0,
        custas=c.custas or 0,
        custas_deduzida=c.custas_deduzida or 0,
        protesto=c.protesto or 0,
        protesto_deduzido=c.protesto_deduzido or 0,
        honorario=c.honorario or 0,
        honorario_repassado=c.honorario_repassado or 0,
        alvara=c.alvara or 0,
        alvara_recebido=c.alvara_recebido or 0,
        ganho=c.ganho or 0,
    )
    return render_template("parcelas.html", contrato=c, parcels=parcels, resumo=resumo)

@app.route("/baixar_parcela/<int:contrato_id>/<int:parcela_id>", methods=["POST"])
def baixar_parcela(contrato_id, parcela_id):
    p = Parcela.query.filter_by(id=parcela_id, contrato_id=contrato_id).first_or_404()
    if not p.baixado_em:
        p.baixado_em = date.today()
        # acumula no contrato.pago
        if p.valor:
            c = p.contrato
            c.pago = (c.pago or 0) + p.valor
    db.session.commit()
    flash("Parcela baixada com sucesso!", "success")
    return redirect(url_for("parcelas", id=contrato_id))

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "warning")
    return redirect(url_for("index"))

@app.route("/info/<int:id>")
def info(id):
    c = Contrato.query.get_or_404(id)
    return render_template("info.html", c=c)

@app.route("/exportar")
def exportar():
    si = StringIO()
    writer = csv.writer(si, delimiter=";")
    writer.writerow(["id","cpf","cliente","contrato","tipo","valor","pago"])
    for c in Contrato.query.order_by(Contrato.id.asc()).all():
        writer.writerow([c.id,c.cpf,c.cliente,c.contrato,c.tipo,c.valor or 0,c.pago or 0])
    si.seek(0)
    return send_file(
        StringIO(si.read()),
        mimetype="text/csv",
        as_attachment=True,
        download_name="contratos.csv"
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
