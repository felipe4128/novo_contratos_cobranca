import os
from datetime import datetime, date
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy

def _get_database_uri():
    # Prefer DATABASE_URL (Render), else local SQLite file (instance/credito.db)
    uri = os.environ.get("DATABASE_URL")
    if uri:
        # Render sometimes gives postgres:// — SQLAlchemy wants postgresql://
        uri = uri.replace("postgres://", "postgresql://")
        return uri
    os.makedirs("instance", exist_ok=True)
    return "sqlite:///instance/credito.db"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = _get_database_uri()
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret")

db = SQLAlchemy(app)

# Jinja filter: format number as BRL-like string
@app.template_filter("brl")
def brl(value):
    try:
        if value is None:
            return "0,00"
        val = Decimal(value)
        s = f"{val:,.2f}"
        s = s.replace(",", "X").replace(".", ",").replace("X", ".")
        return s
    except Exception:
        return str(value)

def parse_money(s):
    if s is None or s == "":
        return None
    s = str(s).strip()
    s = s.replace("R$", "").replace(".", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return None

def parse_int(s):
    try:
        return int(str(s).strip()) if s not in (None, "") else None
    except Exception:
        return None

def parse_date(s):
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None

class Contrato(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Identificadores principais
    contrato = db.Column(db.String(50))
    tipo = db.Column(db.String(50))
    garantia = db.Column(db.String(80))

    # Valores
    valor = db.Column(db.Numeric(15,2))
    baixa_acima_48_meses = db.Column(db.String(50))  # agora texto (não checkbox)
    valor_abatido = db.Column(db.Numeric(15,2))
    ganho = db.Column(db.Numeric(15,2))
    custas = db.Column(db.Numeric(15,2))
    custas_deduzidas = db.Column(db.Numeric(15,2))
    protesto = db.Column(db.Numeric(15,2))
    protesto_deduzido = db.Column(db.Numeric(15,2))
    honorario = db.Column(db.Numeric(15,2))
    honorario_repassado = db.Column(db.Numeric(15,2))
    alvara = db.Column(db.Numeric(15,2))
    alvara_recebido = db.Column(db.Numeric(15,2))

    # Novos solicitados
    cooperado = db.Column(db.String(120))
    cpf = db.Column(db.String(20))
    advogado = db.Column(db.String(120))

    # Entrada / parcelas
    valor_entrada = db.Column(db.Numeric(15,2))
    vencimento_entrada = db.Column(db.Date)
    valor_parcelas = db.Column(db.Numeric(15,2))
    parcelas = db.Column(db.Integer)
    parcelas_restantes = db.Column(db.Integer)
    vencimento_parcelas = db.Column(db.Date)

    # Boletos e baixas
    qtd_boletos_emitidos = db.Column(db.Integer)
    valor_pg_boleto = db.Column(db.Numeric(15,2))
    data_pg_boleto = db.Column(db.Date)
    data_baixa = db.Column(db.Date)

    # Observações e repasse
    obs_contabilidade = db.Column(db.Text)
    obs_contas_receber = db.Column(db.Text)
    valor_repassar_escritorio = db.Column(db.Numeric(15,2))

def ensure_db():
    with app.app_context():
        db.create_all()

@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.id.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        c = Contrato(
            contrato=request.form.get("contrato"),
            tipo=request.form.get("tipo"),
            garantia=request.form.get("garantia"),
            valor=parse_money(request.form.get("valor")),
            baixa_acima_48_meses=request.form.get("baixa_acima_48_meses"),
            valor_abatido=parse_money(request.form.get("valor_abatido")),
            ganho=parse_money(request.form.get("ganho")),
            custas=parse_money(request.form.get("custas")),
            custas_deduzidas=parse_money(request.form.get("custas_deduzidas")),
            protesto=parse_money(request.form.get("protesto")),
            protesto_deduzido=parse_money(request.form.get("protesto_deduzido")),
            honorario=parse_money(request.form.get("honorario")),
            honorario_repassado=parse_money(request.form.get("honorario_repassado")),
            alvara=parse_money(request.form.get("alvara")),
            alvara_recebido=parse_money(request.form.get("alvara_recebido")),

            cooperado=request.form.get("cooperado"),
            cpf=request.form.get("cpf"),
            advogado=request.form.get("advogado"),

            valor_entrada=parse_money(request.form.get("valor_entrada")),
            vencimento_entrada=parse_date(request.form.get("vencimento_entrada")),
            valor_parcelas=parse_money(request.form.get("valor_parcelas")),
            parcelas=parse_int(request.form.get("parcelas")),
            parcelas_restantes=parse_int(request.form.get("parcelas_restantes")),
            vencimento_parcelas=parse_date(request.form.get("vencimento_parcelas")),
            qtd_boletos_emitidos=parse_int(request.form.get("qtd_boletos_emitidos")),
            valor_pg_boleto=parse_money(request.form.get("valor_pg_boleto")),
            data_pg_boleto=parse_date(request.form.get("data_pg_boleto")),
            data_baixa=parse_date(request.form.get("data_baixa")),
            obs_contabilidade=request.form.get("obs_contabilidade"),
            obs_contas_receber=request.form.get("obs_contas_receber"),
            valor_repassar_escritorio=parse_money(request.form.get("valor_repassar_escritorio")),
        )
        db.session.add(c)
        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))
    return render_template("novo.html")

@app.route("/info/<int:id>", methods=["GET", "POST"])
def info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        form = request.form
        c.contrato = form.get("contrato")
        c.tipo = form.get("tipo")
        c.garantia = form.get("garantia")
        c.valor = parse_money(form.get("valor"))
        c.baixa_acima_48_meses = form.get("baixa_acima_48_meses")
        c.valor_abatido = parse_money(form.get("valor_abatido"))
        c.ganho = parse_money(form.get("ganho"))
        c.custas = parse_money(form.get("custas"))
        c.custas_deduzidas = parse_money(form.get("custas_deduzidas"))
        c.protesto = parse_money(form.get("protesto"))
        c.protesto_deduzido = parse_money(form.get("protesto_deduzido"))
        c.honorario = parse_money(form.get("honorario"))
        c.honorario_repassado = parse_money(form.get("honorario_repassado"))
        c.alvara = parse_money(form.get("alvara"))
        c.alvara_recebido = parse_money(form.get("alvara_recebido"))

        c.cooperado = form.get("cooperado")
        c.cpf = form.get("cpf")
        c.advogado = form.get("advogado")

        c.valor_entrada = parse_money(form.get("valor_entrada"))
        c.vencimento_entrada = parse_date(form.get("vencimento_entrada"))
        c.valor_parcelas = parse_money(form.get("valor_parcelas"))
        c.parcelas = parse_int(form.get("parcelas"))
        c.parcelas_restantes = parse_int(form.get("parcelas_restantes"))
        c.vencimento_parcelas = parse_date(form.get("vencimento_parcelas"))
        c.qtd_boletos_emitidos = parse_int(form.get("qtd_boletos_emitidos"))
        c.valor_pg_boleto = parse_money(form.get("valor_pg_boleto"))
        c.data_pg_boleto = parse_date(form.get("data_pg_boleto"))
        c.data_baixa = parse_date(form.get("data_baixa"))
        c.obs_contabilidade = form.get("obs_contabilidade")
        c.obs_contas_receber = form.get("obs_contas_receber")
        c.valor_repassar_escritorio = parse_money(form.get("valor_repassar_escritorio"))
        db.session.commit()
        flash("Contrato atualizado com sucesso!", "success")
        return redirect(url_for("index"))
    return render_template("info.html", c=c)

@app.route("/excluir/<int:id>", methods=["POST"])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "warning")
    return redirect(url_for("index"))

if __name__ == "__main__":
    ensure_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
