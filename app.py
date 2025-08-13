# -*- coding: utf-8 -*-
import os
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")

db_url = os.environ.get("DATABASE_URL")
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
if not db_url:
    os.makedirs(os.path.join(app.root_path, "instance"), exist_ok=True)
    db_url = "sqlite:///" + os.path.join(app.root_path, "instance", "credito.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

def to_decimal(value):
    if value is None or value == "":
        return Decimal("0")
    s = str(value).strip().replace("R$", "").replace(" ", "")
    if "," in s and s.rfind(",") > s.rfind("."):
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return Decimal("0")

def to_int(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return int(str(value).strip())
    except Exception:
        return None

def to_date(value):
    if not value: return None
    s = str(value).strip()
    try:
        if "/" in s:
            d,m,y = s.split("/")
            return date(int(y),int(m),int(d))
        return date.fromisoformat(s)
    except Exception:
        return None

class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    contrato = db.Column(db.String(50), index=True)
    tipo = db.Column(db.String(50))
    garantia = db.Column(db.String(100))
    valor = db.Column(db.Numeric(14,2))
    baixa_48m = db.Column(db.Boolean, default=False)
    valor_abatido = db.Column(db.Numeric(14,2))
    ganho = db.Column(db.Numeric(14,2))
    custas = db.Column(db.Numeric(14,2))
    custas_deduzidas = db.Column(db.Numeric(14,2))
    protesto = db.Column(db.Numeric(14,2))
    protesto_deduzido = db.Column(db.Numeric(14,2))
    honorario = db.Column(db.Numeric(14,2))
    honorario_repassado = db.Column(db.Numeric(14,2))
    alvara = db.Column(db.Numeric(14,2))
    alvara_recebido = db.Column(db.Numeric(14,2))
    valor_entrada = db.Column(db.Numeric(14,2))
    vencimento_entrada = db.Column(db.Date)
    valor_parcelas = db.Column(db.Numeric(14,2))
    parcelas = db.Column(db.Integer)
    parcelas_restantes = db.Column(db.Integer)
    vencimento_parcelas = db.Column(db.Integer)  # dia
    qtd_boletos = db.Column(db.Integer)
    valor_pg_boleto = db.Column(db.Numeric(14,2))
    data_pg_boleto = db.Column(db.Date)
    data_baixa = db.Column(db.Date)
    obs_contabilidade = db.Column(db.Text)
    obs_receber = db.Column(db.Text)
    valor_repassar_escritorio = db.Column(db.Numeric(14,2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

def ensure_tables_and_columns():
    db.create_all()
    engine = db.engine
    insp = db.inspect(engine)
    desired = {
        "contrato":"VARCHAR(50)","tipo":"VARCHAR(50)","garantia":"VARCHAR(100)",
        "valor":"NUMERIC(14,2)","baixa_48m":"BOOLEAN","valor_abatido":"NUMERIC(14,2)","ganho":"NUMERIC(14,2)",
        "custas":"NUMERIC(14,2)","custas_deduzidas":"NUMERIC(14,2)","protesto":"NUMERIC(14,2)","protesto_deduzido":"NUMERIC(14,2)",
        "honorario":"NUMERIC(14,2)","honorario_repassado":"NUMERIC(14,2)",
        "alvara":"NUMERIC(14,2)","alvara_recebido":"NUMERIC(14,2)",
        "valor_entrada":"NUMERIC(14,2)","vencimento_entrada":"DATE",
        "valor_parcelas":"NUMERIC(14,2)","parcelas":"INTEGER","parcelas_restantes":"INTEGER","vencimento_parcelas":"INTEGER",
        "qtd_boletos":"INTEGER","valor_pg_boleto":"NUMERIC(14,2)","data_pg_boleto":"DATE","data_baixa":"DATE",
        "obs_contabilidade":"TEXT","obs_receber":"TEXT","valor_repassar_escritorio":"NUMERIC(14,2)"
    }
    if insp.has_table("contrato"):
        existing = {c["name"] for c in insp.get_columns("contrato")}
        missing = [c for c in desired if c not in existing]
        if missing:
            with engine.begin() as conn:
                driver = engine.url.get_backend_name()
                for col in missing:
                    sqltype = desired[col]
                    if driver.startswith("sqlite"):
                        conn.execute(text(f'ALTER TABLE contrato ADD COLUMN "{col}" {sqltype}'))
                    else:
                        conn.execute(text(f'ALTER TABLE contrato ADD COLUMN {col} {sqltype}'))

@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.created_at.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET","POST"])
def novo():
    if request.method == "POST":
        c = Contrato(
            contrato=request.form.get("contrato"),
            tipo=request.form.get("tipo"),
            garantia=request.form.get("garantia"),
            valor=to_decimal(request.form.get("valor")),
            baixa_48m=True if request.form.get("baixa_48m")=="on" else False,
            valor_abatido=to_decimal(request.form.get("valor_abatido")),
            ganho=to_decimal(request.form.get("ganho")),
            custas=to_decimal(request.form.get("custas")),
            custas_deduzidas=to_decimal(request.form.get("custas_deduzidas")),
            protesto=to_decimal(request.form.get("protesto")),
            protesto_deduzido=to_decimal(request.form.get("protesto_deduzido")),
            honorario=to_decimal(request.form.get("honorario")),
            honorario_repassado=to_decimal(request.form.get("honorario_repassado")),
            alvara=to_decimal(request.form.get("alvara")),
            alvara_recebido=to_decimal(request.form.get("alvara_recebido")),
            valor_entrada=to_decimal(request.form.get("valor_entrada")),
            vencimento_entrada=to_date(request.form.get("vencimento_entrada")),
            valor_parcelas=to_decimal(request.form.get("valor_parcelas")),
            parcelas=to_int(request.form.get("parcelas")),
            parcelas_restantes=to_int(request.form.get("parcelas_restantes")),
            vencimento_parcelas=to_int(request.form.get("vencimento_parcelas")),
            qtd_boletos=to_int(request.form.get("qtd_boletos")),
            valor_pg_boleto=to_decimal(request.form.get("valor_pg_boleto")),
            data_pg_boleto=to_date(request.form.get("data_pg_boleto")),
            data_baixa=to_date(request.form.get("data_baixa")),
            obs_contabilidade=request.form.get("obs_contabilidade"),
            obs_receber=request.form.get("obs_receber"),
            valor_repassar_escritorio=to_decimal(request.form.get("valor_repassar_escritorio")),
        )
        db.session.add(c)
        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))
    return render_template("novo.html")

@app.route("/info/<int:id>", methods=["GET","POST"])
def editar_info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        c.contrato=request.form.get("contrato")
        c.tipo=request.form.get("tipo")
        c.garantia=request.form.get("garantia")
        c.valor=to_decimal(request.form.get("valor"))
        c.baixa_48m=True if request.form.get("baixa_48m")=="on" else False
        c.valor_abatido=to_decimal(request.form.get("valor_abatido"))
        c.ganho=to_decimal(request.form.get("ganho"))
        c.custas=to_decimal(request.form.get("custas"))
        c.custas_deduzidas=to_decimal(request.form.get("custas_deduzidas"))
        c.protesto=to_decimal(request.form.get("protesto"))
        c.protesto_deduzido=to_decimal(request.form.get("protesto_deduzido"))
        c.honorario=to_decimal(request.form.get("honorario"))
        c.honorario_repassado=to_decimal(request.form.get("honorario_repassado"))
        c.alvara=to_decimal(request.form.get("alvara"))
        c.alvara_recebido=to_decimal(request.form.get("alvara_recebido"))
        c.valor_entrada=to_decimal(request.form.get("valor_entrada"))
        c.vencimento_entrada=to_date(request.form.get("vencimento_entrada"))
        c.valor_parcelas=to_decimal(request.form.get("valor_parcelas"))
        c.parcelas=to_int(request.form.get("parcelas"))
        c.parcelas_restantes=to_int(request.form.get("parcelas_restantes"))
        c.vencimento_parcelas=to_int(request.form.get("vencimento_parcelas"))
        c.qtd_boletos=to_int(request.form.get("qtd_boletos"))
        c.valor_pg_boleto=to_decimal(request.form.get("valor_pg_boleto"))
        c.data_pg_boleto=to_date(request.form.get("data_pg_boleto"))
        c.data_baixa=to_date(request.form.get("data_baixa"))
        c.obs_contabilidade=request.form.get("obs_contabilidade")
        c.obs_receber=request.form.get("obs_receber")
        c.valor_repassar_escritorio=to_decimal(request.form.get("valor_repassar_escritorio"))
        db.session.commit()
        flash("Informações atualizadas!", "success")
        return redirect(url_for("index"))
    return render_template("info.html", c=c)

@app.route("/parcelas/<int:id>")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    return render_template("parcelas.html", c=c)

@app.post("/excluir/<int:id>")
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "info")
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        ensure_tables_and_columns()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
