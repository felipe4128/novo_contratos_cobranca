# -*- coding: utf-8 -*-
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy

# -------------------- App & DB config --------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# Ensure instance folder exists (for SQLite)
os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)

db_url = os.environ.get("DATABASE_URL", "").strip()
if db_url and db_url.startswith("postgres"):
    # Render/Heroku style
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
else:
    sqlite_path = os.path.join(app.root_path, "instance", "credito.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + sqlite_path

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# -------------------- Helpers --------------------
def brl(value):
    try:
        if value is None:
            value = 0
        value = Decimal(value)
        s = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except Exception:
        return str(value)

def datefmt(value, fmt="%d/%m/%Y"):
    if not value:
        return ""
    if isinstance(value, (datetime, date)):
        return value.strftime(fmt)
    try:
        # try parse ISO
        return datetime.fromisoformat(str(value)).strftime(fmt)
    except Exception:
        return str(value)

app.jinja_env.filters["brl"] = brl
app.jinja_env.filters["datefmt"] = datefmt

# -------------------- Models --------------------
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)

    # Campos básicos
    contrato = db.Column(db.String(80), nullable=True)  # número do contrato
    tipo = db.Column(db.String(50), nullable=True)
    garantia = db.Column(db.String(100), nullable=True)
    cliente = db.Column(db.String(150), nullable=True)
    cpf = db.Column(db.String(20), nullable=True)

    # Financeiros principais
    valor_total = db.Column(db.Numeric(14,2), default=0)
    pago = db.Column(db.Numeric(14,2), default=0)  # valor pago acumulado

    # Extras solicitados
    baixa_acima_48 = db.Column(db.Boolean, default=False)
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
    vencimento_parcelas = db.Column(db.Date, nullable=True)  # data inicial
    qtd_boletos_emitidos = db.Column(db.Integer, default=0)
    valor_pg_boleto = db.Column(db.Numeric(14,2), default=0)
    data_pg_boleto = db.Column(db.Date, nullable=True)
    data_baixa = db.Column(db.Date, nullable=True)
    obs_contabilidade = db.Column(db.Text, nullable=True)
    obs_contas_receber = db.Column(db.Text, nullable=True)
    valor_repassar_escritorio = db.Column(db.Numeric(14,2), default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parcelas_rel = db.relationship("Parcela", backref="contrato", cascade="all, delete-orphan")

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer, nullable=False, default=1)
    vencimento = db.Column(db.Date, nullable=True)
    valor = db.Column(db.Numeric(14,2), default=0)
    baixado_em = db.Column(db.Date, nullable=True)

# -------------------- DB bootstrap --------------------
def ensure_tables_and_columns():
    """
    Cria as tabelas se não existirem.
    Caso esteja em Postgres, o SQLAlchemy fará o create_all sem problemas.
    """
    db.create_all()

def _bootstrap():
    with app.app_context():
        ensure_tables_and_columns()

_bootstrap()

# -------------------- Rotas --------------------
@app.route("/")
def index():
    contratos = (Contrato.query
                 .order_by(Contrato.created_at.desc())
                 .all())
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        form = request.form

        def _to_decimal(k):
            v = form.get(k) or "0"
            v = v.replace(".", "").replace(",", ".")
            try: return Decimal(v)
            except: return Decimal("0")

        c = Contrato(
            contrato=form.get("contrato"),
            tipo=form.get("tipo"),
            garantia=form.get("garantia"),
            cliente=form.get("cliente"),
            cpf=form.get("cpf"),
            valor_total=_to_decimal("valor_total"),
            valor_parcela=_to_decimal("valor_parcela"),
            parcelas=int(form.get("parcelas") or 0),
            vencimento_parcelas=_parse_date(form.get("vencimento_parcelas")),
        )
        c.parcelas_restantes = c.parcelas or 0
        db.session.add(c)
        db.session.commit()

        # Gera parcelas, se informadas
        if c.parcelas and c.valor_parcela and c.vencimento_parcelas:
            due = c.vencimento_parcelas
            for i in range(1, c.parcelas + 1):
                p = Parcela(
                    contrato_id=c.id,
                    numero=i,
                    vencimento=due,
                    valor=c.valor_parcela,
                )
                db.session.add(p)
                # próximo mês: incrementando 1 mês (simples, add 30 dias como aproximação)
                # para maior precisão, poderíamos usar dateutil.relativedelta.
                month = due.month + 1
                year = due.year + (1 if month > 12 else 0)
                month = 1 if month > 12 else month
                day = min(due.day, 28)  # evita problemas com meses curtos
                due = date(year, month, day)
            db.session.commit()

        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))

    return render_template("novo.html")

@app.route("/info/<int:id>", methods=["GET", "POST"])
def editar_info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        form = request.form

        def _dec(v):
            if v is None: return Decimal("0")
            v = v.replace(".", "").replace(",", ".")
            try: return Decimal(v)
            except: return Decimal("0")

        # Atualiza vários campos (apenas alguns principais aqui; adicione os demais conforme necessidade)
        c.tipo = form.get("tipo") or c.tipo
        c.garantia = form.get("garantia") or c.garantia
        c.valor_total = _dec(form.get("valor_total") or "0")
        c.valor_abatido = _dec(form.get("valor_abatido") or "0")
        c.custas = _dec(form.get("custas") or "0")
        c.custas_deduzidas = _dec(form.get("custas_deduzidas") or "0")
        c.protesto = _dec(form.get("protesto") or "0")
        c.protesto_deduzido = _dec(form.get("protesto_deduzido") or "0")
        c.honorario = _dec(form.get("honorario") or "0")
        c.honorario_repassado = _dec(form.get("honorario_repassado") or "0")
        c.alvara = _dec(form.get("alvara") or "0")
        c.alvara_recebido = _dec(form.get("alvara_recebido") or "0")
        c.ganho = _dec(form.get("ganho") or "0")
        c.obs_contabilidade = form.get("obs_contabilidade")
        c.obs_contas_receber = form.get("obs_contas_receber")
        c.valor_repassar_escritorio = _dec(form.get("valor_repassar_escritorio") or "0")
        db.session.commit()
        flash("Informações do contrato atualizadas.", "success")
        return redirect(url_for("index"))
    return render_template("editar.html", c=c)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "info")
    return redirect(url_for("index"))

@app.route("/contrato/<int:id>/parcelas")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = (Parcela.query
               .filter_by(contrato_id=id)
               .order_by(Parcela.numero.asc())
               .all())
    # resumo simples
    resumo = {
        "valor": c.valor_total or 0,
        "valor_pago": c.pago or 0,
        "valor_abatido": c.valor_abatido or 0,
        "custas": c.custas or 0,
        "custas_deduzidas": c.custas_deduzidas or 0,
        "protesto": c.protesto or 0,
        "protesto_deduzido": c.protesto_deduzido or 0,
        "honorario": c.honorario or 0,
        "honorario_repassado": c.honorario_repassado or 0,
        "alvara": c.alvara or 0,
        "alvara_recebido": c.alvara_recebido or 0,
        "ganho": c.ganho or 0,
    }
    return render_template("parcelas.html", contrato=c, parcels=parcels, resumo=resumo)

@app.route("/contrato/<int:id>/parcela/<int:pid>/baixar", methods=["POST"])
def baixar_parcela(id, pid):
    p = Parcela.query.filter_by(id=pid, contrato_id=id).first_or_404()
    if p.baixado_em:
        p.baixado_em = None
    else:
        p.baixado_em = date.today()
    db.session.commit()
    return redirect(url_for("parcelas", id=id))

# -------------------- Utils --------------------
def _parse_date(s):
    if not s:
        return None
    s = s.strip()
    # tenta formatos comuns
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

# -------------------- Run --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port, debug=False)
