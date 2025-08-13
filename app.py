
import os
from datetime import date, datetime, timedelta
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, send_file, Response, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# ----------------------------------------------------------------------------
# App & DB
# ----------------------------------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev")

# DB URL (Render/Postgres ou local SQLite)
db_url = os.environ.get("DATABASE_URL", "").strip()
if db_url:
    db_url = db_url.replace("postgres://", "postgresql://")
else:
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    db_url = "sqlite:///" + os.path.join(app.root_path, "instance", "credito.db")

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def brl(value):
    try:
        val = Decimal(value or 0)
    except Exception:
        return "0,00"
    s = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s

def parse_date(value):
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except Exception:
            pass
    return None

app.jinja_env.filters["brl"] = brl

# ----------------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------------
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)

    # básicos
    contrato = db.Column(db.String(100))
    tipo = db.Column(db.String(50))
    garantia = db.Column(db.String(100))
    cliente = db.Column(db.String(200))
    cpf = db.Column(db.String(20))

    # financeiros e status
    valor_contrato_sistema = db.Column(db.Numeric(14,2), default=0)
    baixa_acima_48m = db.Column(db.Boolean, default=False)
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
    vencimento_entrada = db.Column(db.Date)

    valor_parcela = db.Column(db.Numeric(14,2), default=0)
    parcelas_qtd = db.Column(db.Integer, default=0)
    parcelas_restantes = db.Column(db.Integer, default=0)
    primeiro_vencimento = db.Column(db.Date)

    qtd_boletos = db.Column(db.Integer, default=0)
    valor_pg_boleto = db.Column(db.Numeric(14,2), default=0)
    data_pg_boleto = db.Column(db.Date)

    data_baixa = db.Column(db.Date)

    obs_contabilidade = db.Column(db.Text)
    obs_receber = db.Column(db.Text)
    valor_repassar_escritorio = db.Column(db.Numeric(14,2), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan", lazy=True)

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(14,2), default=0)
    baixado_em = db.Column(db.Date)

# ----------------------------------------------------------------------------
# "Migração" simples para SQLite (adiciona colunas se não existirem)
# ----------------------------------------------------------------------------
def ensure_tables_and_columns():
    db.create_all()
    if db.engine.url.get_backend_name().startswith("sqlite"):
        # colunas esperadas -> SQL para add column
        expected = {
            "contrato": {
                "contrato":"TEXT", "tipo":"TEXT","garantia":"TEXT","cliente":"TEXT","cpf":"TEXT",
                "valor_contrato_sistema":"NUMERIC","baixa_acima_48m":"INTEGER","valor_abatido":"NUMERIC",
                "ganho":"NUMERIC","custas":"NUMERIC","custas_deduzidas":"NUMERIC","protesto":"NUMERIC",
                "protesto_deduzido":"NUMERIC","honorario":"NUMERIC","honorario_repassado":"NUMERIC",
                "alvara":"NUMERIC","alvara_recebido":"NUMERIC","valor_entrada":"NUMERIC",
                "vencimento_entrada":"DATE","valor_parcela":"NUMERIC","parcelas_qtd":"INTEGER",
                "parcelas_restantes":"INTEGER","primeiro_vencimento":"DATE","qtd_boletos":"INTEGER",
                "valor_pg_boleto":"NUMERIC","data_pg_boleto":"DATE","data_baixa":"DATE",
                "obs_contabilidade":"TEXT","obs_receber":"TEXT","valor_repassar_escritorio":"NUMERIC",
                "created_at":"DATETIME"
            },
            "parcela": {
                "contrato_id":"INTEGER","numero":"INTEGER","vencimento":"DATE",
                "valor":"NUMERIC","baixado_em":"DATE"
            }
        }
        for table, cols in expected.items():
            cur = db.session.execute(text(f"PRAGMA table_info({table})"))
            existing = {row[1] for row in cur}
            for col, typ in cols.items():
                if col not in existing:
                    db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typ}"))
        db.session.commit()

ensure_tables_and_columns()

# ----------------------------------------------------------------------------
# Views
# ----------------------------------------------------------------------------
@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.created_at.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET","POST"])
def novo():
    if request.method == "POST":
        f = request.form
        c = Contrato(
            contrato=f.get("contrato"),
            tipo=f.get("tipo"),
            garantia=f.get("garantia"),
            cliente=f.get("cliente"),
            cpf=f.get("cpf"),
            valor_contrato_sistema=f.get("valor_contrato_sistema") or 0,
            baixa_acima_48m=bool(f.get("baixa_acima_48m")),
            valor_abatido=f.get("valor_abatido") or 0,
            ganho=f.get("ganho") or 0,
            custas=f.get("custas") or 0,
            custas_deduzidas=f.get("custas_deduzidas") or 0,
            protesto=f.get("protesto") or 0,
            protesto_deduzido=f.get("protesto_deduzido") or 0,
            honorario=f.get("honorario") or 0,
            honorario_repassado=f.get("honorario_repassado") or 0,
            alvara=f.get("alvara") or 0,
            alvara_recebido=f.get("alvara_recebido") or 0,
            valor_entrada=f.get("valor_entrada") or 0,
            vencimento_entrada=parse_date(f.get("vencimento_entrada")),
            valor_parcela=f.get("valor_parcela") or 0,
            parcelas_qtd=int(f.get("parcelas_qtd") or 0),
            parcelas_restantes=int(f.get("parcelas_qtd") or 0),
            primeiro_vencimento=parse_date(f.get("primeiro_vencimento")),
            qtd_boletos=int(f.get("qtd_boletos") or 0),
            valor_pg_boleto=f.get("valor_pg_boleto") or 0,
            data_pg_boleto=parse_date(f.get("data_pg_boleto")),
            data_baixa=parse_date(f.get("data_baixa")),
            obs_contabilidade=f.get("obs_contabilidade"),
            obs_receber=f.get("obs_receber"),
            valor_repassar_escritorio=f.get("valor_repassar_escritorio") or 0
        )
        db.session.add(c)
        db.session.commit()

        # gerar parcelas (se informado)
        try:
            if c.parcelas_qtd and c.primeiro_vencimento and c.valor_parcela:
                for i in range(1, c.parcelas_qtd + 1):
                    venc = c.primeiro_vencimento + timedelta(days=30*(i-1))
                    p = Parcela(contrato_id=c.id, numero=i, vencimento=venc, valor=c.valor_parcela)
                    db.session.add(p)
                db.session.commit()
        except Exception as e:
            flash(f"Parcelas não foram geradas automaticamente: {e}", "warning")

        return redirect(url_for("index"))
    return render_template("novo.html")

@app.route("/editar/<int:id>", methods=["GET","POST"])
def editar(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        for attr in [
            "contrato","tipo","garantia","cliente","cpf","valor_contrato_sistema",
            "valor_abatido","ganho","custas","custas_deduzidas","protesto","protesto_deduzido",
            "honorario","honorario_repassado","alvara","alvara_recebido","valor_entrada",
            "valor_parcela","parcelas_qtd","qtd_boletos","valor_pg_boleto","obs_contabilidade",
            "obs_receber","valor_repassar_escritorio"
        ]:
            setattr(c, attr, f.get(attr) or getattr(c, attr))

        c.baixa_acima_48m = bool(f.get("baixa_acima_48m"))
        c.vencimento_entrada = parse_date(f.get("vencimento_entrada"))
        c.primeiro_vencimento = parse_date(f.get("primeiro_vencimento"))
        c.data_pg_boleto = parse_date(f.get("data_pg_boleto"))
        c.data_baixa = parse_date(f.get("data_baixa"))
        c.parcelas_restantes = int(f.get("parcelas_restantes") or c.parcelas_restantes or 0)

        db.session.commit()
        return redirect(url_for("info", id=c.id))
    return render_template("editar.html", c=c)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for("index"))

@app.route("/info/<int:id>")
def info(id):
    c = Contrato.query.get_or_404(id)
    return render_template("info.html", c=c)

@app.route("/parcelas/<int:id>")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()
    # resumo simples que aparece no topo
    resumo = {
        "valor": c.valor_contrato_sistema or 0,
        "pago": (c.valor_pg_boleto or 0),
        "abatido": c.valor_abatido or 0,
        "custas": c.custas or 0,
        "honorario": c.honorario or 0,
        "alvara": c.alvara or 0,
        "ganho": c.ganho or 0,
    }
    return render_template("parcelas.html", contrato=c, parcels=parcels, resumo=resumo)

@app.route("/baixar_parcela/<int:parcela_id>", methods=["POST"])
def baixar_parcela(parcela_id):
    p = Parcela.query.get_or_404(parcela_id)
    if not p.baixado_em:
        p.baixado_em = date.today()
        c = p.contrato
        if c.parcelas_restantes and c.parcelas_restantes > 0:
            c.parcelas_restantes -= 1
    db.session.commit()
    return redirect(url_for("parcelas", id=p.contrato_id))

@app.route("/exportar")
def exportar():
    # Exporta TODOS os contratos + colunas
    cols = [
        "id","contrato","tipo","garantia","cliente","cpf",
        "valor_contrato_sistema","baixa_acima_48m","valor_abatido","ganho",
        "custas","custas_deduzidas","protesto","protesto_deduzido",
        "honorario","honorario_repassado","alvara","alvara_recebido",
        "valor_entrada","vencimento_entrada","valor_parcela","parcelas_qtd",
        "parcelas_restantes","primeiro_vencimento","qtd_boletos",
        "valor_pg_boleto","data_pg_boleto","data_baixa",
        "obs_contabilidade","obs_receber","valor_repassar_escritorio","created_at"
    ]
    def row_to_dict(c):
        d = {}
        for k in cols:
            v = getattr(c, k)
            if isinstance(v, (date, datetime)):
                v = v.strftime("%Y-%m-%d")
            d[k] = v
        return d

    contratos = Contrato.query.order_by(Contrato.id.asc()).all()

    def generate():
        # header
        yield ";".join(cols) + "\n"
        for c in contratos:
            d = row_to_dict(c)
            line = ";".join("" if d[k] is None else str(d[k]) for k in cols) + "\n"
            yield line

    return Response(generate(), mimetype="text/csv",
                    headers={"Content-Disposition":"attachment; filename=contratos.csv"})

# ----------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
