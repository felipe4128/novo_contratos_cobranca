
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

# --- App & DB config ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# resolve DB path (Render or local). Always ensure ./instance exists.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = os.path.join(INSTANCE_DIR, "credito.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", f"sqlite:///{DB_PATH}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------- Models --------
class Contrato(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contrato = db.Column(db.String(50))          # número do contrato
    cooperado = db.Column(db.String(120))
    cpf = db.Column(db.String(20))
    advogado = db.Column(db.String(120))

    tipo = db.Column(db.String(50))
    garantia = db.Column(db.String(80))

    valor = db.Column(db.Numeric(14,2), default=0)                  # valor do contrato no sistema
    baixa_48_meses = db.Column(db.String(20))                       # texto livre (não checkbox)
    valor_abatido = db.Column(db.Numeric(14,2), default=0)
    ganho = db.Column(db.Numeric(14,2), default=0)

    custas = db.Column(db.Numeric(14,2), default=0)
    custas_deduzidas = db.Column(db.Numeric(14,2), default=0)
    protesto = db.Column(db.Numeric(14,2), default=0)
    protesto_deduzido = db.Column(db.Numeric(14,2), default=0)

    honorario = db.Column(db.Numeric(14,2), default=0)
    honorario_repassado = db.Column(db.Numeric(14,2), default=0)

    alvara = db.Column(db.Numeric(14,2), default=0)
    alvara_recebido = db.Column(db.Numeric(14,2), default=0)

    valor_entrada = db.Column(db.Numeric(14,2), default=0)
    vencimento_entrada = db.Column(db.Date, nullable=True)

    valor_parcela = db.Column(db.Numeric(14,2), default=0)
    parcelas = db.Column(db.Integer, default=0)
    parcelas_restantes = db.Column(db.Integer, default=0)

    vencimento_parcelas = db.Column(db.Date, nullable=True)  # primeiro vencimento

    qtd_boletos = db.Column(db.Integer, default=0)
    valor_pg_boleto = db.Column(db.Numeric(14,2), default=0)
    data_pg_boleto = db.Column(db.Date, nullable=True)
    data_baixa = db.Column(db.Date, nullable=True)

    obs_contabilidade = db.Column(db.Text)
    obs_contas_receber = db.Column(db.Text)
    valor_repassar_escritorio = db.Column(db.Numeric(14,2), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas_rel = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan")

class Parcela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), index=True, nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(14,2), default=0)
    baixado_em = db.Column(db.Date, nullable=True)


# ----- Helpers -----
def parse_decimal(s):
    if s is None or s == "":
        return Decimal("0")
    s = str(s).replace("R$","").replace(".","").replace(",",".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")

def parse_int(s):
    try:
        return int(str(s).strip())
    except Exception:
        return 0

def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d","%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None

def gerar_parcelas(contrato: Contrato):
    # gera somente se houver valor_parcela, parcelas e 1o vencimento
    if not contrato.vencimento_parcelas or contrato.parcelas <= 0 or contrato.valor_parcela is None:
        return
    # apaga existentes
    for p in list(contrato.parcelas_rel):
        db.session.delete(p)
    # cria novas
    dt = contrato.vencimento_parcelas
    for i in range(1, contrato.parcelas+1):
        parc = Parcela(
            contrato_id=contrato.id,
            numero=i,
            vencimento=dt,
            valor=contrato.valor_parcela or Decimal("0"),
        )
        db.session.add(parc)
        # próximo mês
        if dt.month == 12:
            dt = date(dt.year+1, 1, min(dt.day, 28))
        else:
            # manter dia aproximado (use 28 p/ evitar invalid date)
            day = min(dt.day, 28)
            dt = date(dt.year, dt.month, day)
            # add 1 month
            if dt.month == 12:
                dt = date(dt.year+1, 1, day)
            else:
                dt = date(dt.year, dt.month+1, day)

# ----- Routes -----
@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.created_at.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET","POST"])
def novo():
    if request.method == "POST":
        c = Contrato(
            contrato=request.form.get("contrato"),
            cooperado=request.form.get("cooperado"),
            cpf=request.form.get("cpf"),
            advogado=request.form.get("advogado"),
            tipo=request.form.get("tipo"),
            garantia=request.form.get("garantia"),
            valor=parse_decimal(request.form.get("valor")),
            baixa_48_meses=request.form.get("baixa_48_meses"),
            valor_abatido=parse_decimal(request.form.get("valor_abatido")),
            ganho=parse_decimal(request.form.get("ganho")),
            custas=parse_decimal(request.form.get("custas")),
            custas_deduzidas=parse_decimal(request.form.get("custas_deduzidas")),
            protesto=parse_decimal(request.form.get("protesto")),
            protesto_deduzido=parse_decimal(request.form.get("protesto_deduzido")),
            honorario=parse_decimal(request.form.get("honorario")),
            honorario_repassado=parse_decimal(request.form.get("honorario_repassado")),
            alvara=parse_decimal(request.form.get("alvara")),
            alvara_recebido=parse_decimal(request.form.get("alvara_recebido")),
            valor_entrada=parse_decimal(request.form.get("valor_entrada")),
            vencimento_entrada=parse_date(request.form.get("vencimento_entrada")),
            valor_parcela=parse_decimal(request.form.get("valor_parcela")),
            parcelas=parse_int(request.form.get("parcelas")),
            parcelas_restantes=parse_int(request.form.get("parcelas_restantes")),
            vencimento_parcelas=parse_date(request.form.get("vencimento_parcelas")),
            qtd_boletos=parse_int(request.form.get("qtd_boletos")),
            valor_pg_boleto=parse_decimal(request.form.get("valor_pg_boleto")),
            data_pg_boleto=parse_date(request.form.get("data_pg_boleto")),
            data_baixa=parse_date(request.form.get("data_baixa")),
            obs_contabilidade=request.form.get("obs_contabilidade"),
            obs_contas_receber=request.form.get("obs_contas_receber"),
            valor_repassar_escritorio=parse_decimal(request.form.get("valor_repassar_escritorio")),
        )
        db.session.add(c)
        db.session.commit()
        gerar_parcelas(c)
        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))
    return render_template("novo.html")

@app.route("/info/<int:id>", methods=["GET", "POST"])
def info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        fields = [
            "contrato","cooperado","cpf","advogado","tipo","garantia","baixa_48_meses",
            "obs_contabilidade","obs_contas_receber"
        ]
        for f in fields:
            setattr(c, f, request.form.get(f))

        # numéricos
        num_fields = [
            "valor","valor_abatido","ganho","custas","custas_deduzidas","protesto",
            "protesto_deduzido","honorario","honorario_repassado","alvara","alvara_recebido",
            "valor_entrada","valor_parcela","valor_pg_boleto","valor_repassar_escritorio"
        ]
        for f in num_fields:
            setattr(c, f, parse_decimal(request.form.get(f)))

        int_fields = ["parcelas","parcelas_restantes","qtd_boletos"]
        for f in int_fields:
            setattr(c, f, parse_int(request.form.get(f)))

        date_fields = ["vencimento_entrada","vencimento_parcelas","data_pg_boleto","data_baixa"]
        for f in date_fields:
            setattr(c, f, parse_date(request.form.get(f)))

        # regenerar parcelas conforme novos dados
        gerar_parcelas(c)
        db.session.commit()
        flash("Informações salvas.", "success")
        return redirect(url_for("info", id=c.id))

    return render_template("info.html", c=c)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "success")
    return redirect(url_for("index"))

@app.route("/parcelas/<int:id>")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    return render_template("parcelas.html", c=c, parcelas=c.parcelas_rel)

@app.route("/baixa_parcela/<int:pid>", methods=["POST"])
def baixa_parcela(pid):
    p = Parcela.query.get_or_404(pid)
    p.baixado_em = date.today()
    db.session.commit()
    flash(f"Parcela #{p.numero} baixada.", "success")
    return redirect(url_for("parcelas", id=p.contrato_id))

# ensure tables on startup with app context
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
