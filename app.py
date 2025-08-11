
import os
from datetime import date, datetime
from io import BytesIO

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from sqlalchemy import text
from dateutil.relativedelta import relativedelta

# -----------------------------
# App & DB config
# -----------------------------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")

# Use DATABASE_URL (Render/Heroku) or SQLite under instance/
uri = os.getenv("DATABASE_URL", "").strip()
if uri:
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    os.makedirs(app.instance_path, exist_ok=True)
    uri = f"sqlite:///{os.path.join(app.instance_path, 'credito.db')}"

app.config["SQLALCHEMY_DATABASE_URI"] = uri
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# -----------------------------
# Models
# -----------------------------
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)

    # Dados básicos
    cpf = db.Column(db.String(20))
    cliente = db.Column(db.String(200))
    contrato = db.Column(db.String(50))  # número do contrato
    tipo = db.Column(db.String(50))

    # Financeiros
    valor = db.Column(db.Float, default=0.0)        # valor total
    pago = db.Column(db.Float, default=0.0)         # valor pago
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

    # Parcelamento
    parcelas = db.Column(db.Integer, default=0)  # quantidade de parcelas
    vencimento_entrada = db.Column(db.Date)      # primeiro vencimento

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    parcelas_rel = relationship("Parcela", back_populates="contrato", cascade="all, delete-orphan")

    # Fallbacks (compatibilidade com templates antigos)
    @property
    def valor_total(self): return self.valor
    @property
    def valor_pago(self): return self.pago
    @property
    def primeiro_vencimento(self): return self.vencimento_entrada


class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    numero = db.Column(db.Integer)

    vencimento = db.Column(db.Date)
    valor = db.Column(db.Float, default=0.0)

    baixa = db.Column(db.Boolean, default=False)
    data_baixa = db.Column(db.Date)

    contrato = relationship("Contrato", back_populates="parcelas_rel")


# -----------------------------
# Filtros de template
# -----------------------------
@app.template_filter("brl")
def brl(value):
    try:
        v = float(value or 0)
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


@app.template_filter("fmtdate")
def fmtdate(value):
    if not value:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%d/%m/%Y")
    # tenta parsear strings comuns
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    return str(value)


# -----------------------------
# Utils
# -----------------------------
def _parse_date(s):
    if not s:
        return None
    if isinstance(s, (date, datetime)):
        return s if isinstance(s, date) else s.date()
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def _parse_money(s):
    if s in (None, ""): return 0.0
    try:
        return float(s)
    except Exception:
        try:
            return float(str(s).replace(".", "").replace(",", ".").strip())
        except Exception:
            return 0.0


# -----------------------------
# Safe migration (adiciona colunas que faltam)
# -----------------------------
def _columns_of(table):
    eng = db.engine
    backend = eng.url.get_backend_name()
    if backend.startswith("sqlite"):
        rows = db.session.execute(text(f"PRAGMA table_info({table})")).fetchall()
        return {r[1] for r in rows}  # name at index 1
    else:
        rows = db.session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=:t
        """), {"t": table}).fetchall()
        return {r[0] for r in rows}

def _add_column_sql(table, name, type_sql):
    backend = db.engine.url.get_backend_name()
    if backend.startswith("sqlite"):
        return f'ALTER TABLE {table} ADD COLUMN {name} {type_sql};'
    else:
        return f'ALTER TABLE public.{table} ADD COLUMN IF NOT EXISTS {name} {type_sql};'

def safe_migrate():
    # Garante tabelas
    db.create_all()

    # contrato
    cols = _columns_of("contrato")
    needed = {
        "cpf": "TEXT",
        "cliente": "TEXT",
        "contrato": "TEXT",
        "tipo": "TEXT",
        "valor": "DOUBLE PRECISION",
        "pago": "DOUBLE PRECISION",
        "abatido": "DOUBLE PRECISION",
        "custas": "DOUBLE PRECISION",
        "custas_deduzida": "DOUBLE PRECISION",
        "protesto": "DOUBLE PRECISION",
        "protesto_deduzido": "DOUBLE PRECISION",
        "honorario": "DOUBLE PRECISION",
        "honorario_repassado": "DOUBLE PRECISION",
        "alvara": "DOUBLE PRECISION",
        "alvara_recebido": "DOUBLE PRECISION",
        "ganho": "DOUBLE PRECISION",
        "parcelas": "INTEGER",
        "vencimento_entrada": "DATE",
        "created_at": "TIMESTAMP"
    }
    for name, t_sql in needed.items():
        if name not in cols:
            db.session.execute(text(_add_column_sql("contrato", name, t_sql)))

    # parcela
    cols = _columns_of("parcela")
    needed_p = {
        "contrato_id": "INTEGER",
        "numero": "INTEGER",
        "vencimento": "DATE",
        "valor": "DOUBLE PRECISION",
        "baixa": "BOOLEAN",
        "data_baixa": "DATE"
    }
    for name, t_sql in needed_p.items():
        if name not in cols:
            db.session.execute(text(_add_column_sql("parcela", name, t_sql)))

    db.session.commit()


# -----------------------------
# Helpers (NÃO são rotas)
# -----------------------------
def _first_due_date(c):
    for name in ('vencimento_entrada', 'primeiro_vencimento', 'vencimento',
                 'data_primeira_parcela', 'dt_primeira'):
        if hasattr(c, name):
            val = getattr(c, name)
            if not val:
                continue
            if isinstance(val, date):
                return val
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, str):
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
                    try:
                        return datetime.strptime(val.strip(), fmt).date()
                    except Exception:
                        pass
    return None


def _get_int(o, *names, default=0):
    for n in names:
        if hasattr(o, n):
            v = getattr(o, n)
            if v not in (None, ""):
                try:
                    return int(v)
                except Exception:
                    try:
                        return int(float(str(v).replace(",", ".").strip()))
                    except Exception:
                        pass
    return default


def _get_float(o, *names, default=0.0):
    for n in names:
        if hasattr(o, n):
            v = getattr(o, n)
            if v not in (None, ""):
                try:
                    return float(v)
                except Exception:
                    try:
                        return float(str(v).replace(",", ".").strip())
                    except Exception:
                        pass
    return default


def ensure_parcelas(c):
    """Se o contrato não tiver parcelas, cria automaticamente a partir do
    valor total, quantidade e data do primeiro vencimento.
    """
    count = Parcela.query.filter_by(contrato_id=c.id).count()
    if count:
        return []

    qtd = _get_int(c, 'parcelas', 'qtd_parcelas', 'num_parcelas', default=0)
    total = _get_float(c, 'valor', 'valor_total', default=0.0)
    first_due = _first_due_date(c)

    if not (qtd and total and first_due):
        return []

    base = round(total / qtd, 2)
    vals = [base] * qtd
    ajuste = round(total - sum(vals), 2)
    if ajuste != 0:
        vals[-1] = round(vals[-1] + ajuste, 2)

    created = []
    for i in range(qtd):
        venc = first_due + relativedelta(months=i)
        p = Parcela(contrato_id=c.id, numero=i+1, vencimento=venc, valor=vals[i])
        db.session.add(p)
        created.append(p)
    db.session.commit()
    return created


# -----------------------------
# Rotas
# -----------------------------
@app.route('/')
def index():
    contratos = Contrato.query.order_by(Contrato.id.desc()).all()
    return render_template('index.html', contratos=contratos)


@app.route('/novo', methods=['GET', 'POST'])
def novo():
    if request.method == 'POST':
        c = Contrato(
            cpf=request.form.get('cpf') or None,
            cliente=request.form.get('cliente') or None,
            contrato=request.form.get('contrato') or None,
            tipo=request.form.get('tipo') or None,
            valor=_parse_money(request.form.get('valor')),
            pago=_parse_money(request.form.get('pago')),
            parcelas=int(request.form.get('parcelas') or 0),
            vencimento_entrada=_parse_date(request.form.get('vencimento_entrada')),
        )
        db.session.add(c)
        db.session.commit()
        flash("Contrato cadastrado.", "success")
        return redirect(url_for('index'))
    return render_template('novo.html')


@app.route('/contrato/<int:id>/excluir', methods=['POST'])
def excluir(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    flash("Contrato excluído.", "success")
    return redirect(url_for('index'))


@app.route('/contrato/<int:id>/info', methods=['GET', 'POST'])
def editar_info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == 'POST':
        # atualiza alguns campos básicos que aparecem nos cards
        campos_float = [
            'valor', 'pago', 'abatido', 'custas', 'custas_deduzida',
            'protesto', 'protesto_deduzido', 'honorario', 'honorario_repassado',
            'alvara', 'alvara_recebido', 'ganho'
        ]
        for nome in campos_float:
            if nome in request.form:
                setattr(c, nome, _parse_money(request.form.get(nome)))
        db.session.commit()
        flash("Informações atualizadas.", "success")
        return redirect(url_for('index'))
    return render_template('info.html', contrato=c)


# --------- Parcelas ---------
@app.route('/contrato/<int:id>/parcelas')
@app.route('/parcelas/<int:id>', endpoint='parcelas')
def ver_parcelas(id):
    c = Contrato.query.get_or_404(id)

    parcels = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()
    if not parcels:
        created = ensure_parcelas(c)
        if created:
            parcels = created

    # resumo com fallback
    def _get(o, *names, default=0):
        for n in names:
            if hasattr(o, n) and getattr(o, n) is not None:
                return getattr(o, n)
        return default

    resumo = {
        "valor":               _get(c, "valor", "valor_total"),
        "valor_pago":          _get(c, "pago", "valor_pago"),
        "valor_abatido":       _get(c, "abatido", "valor_abatido"),
        "custas":              _get(c, "custas"),
        "custas_deduzida":     _get(c, "custas_deduzida", "custas_deduzidas"),
        "protesto":            _get(c, "protesto"),
        "protesto_deduzido":   _get(c, "protesto_deduzido"),
        "honorario":           _get(c, "honorario", "honorarios"),
        "honorario_repassado": _get(c, "honorario_repassado"),
        "alvara":              _get(c, "alvara"),
        "alvara_recebido":     _get(c, "alvara_recebido"),
        "ganho":               _get(c, "ganho"),
    }

    total = resumo["valor"]
    qtd = _get(c, "parcelas", "qtd_parcelas", default=len(parcels) or 1)
    fallback_valor = (total / qtd) if (total and qtd) else 0

    for p in parcels:
        valor = None
        for name in ("valor", "valor_parcela", "valor_total", "vlr", "valor_previsto"):
            if hasattr(p, name) and getattr(p, name) not in (None, ""):
                try:
                    valor = float(getattr(p, name))
                    break
                except Exception:
                    try:
                        valor = float(str(getattr(p, name)).replace(",", ".").strip())
                        break
                    except Exception:
                        pass
        if valor is None:
            valor = fallback_valor
        setattr(p, "_valor_render", valor)

    return render_template('parcelas.html', contrato=c, parcelas=parcels, parcels=parcels, resumo=resumo)


@app.route('/contrato/<int:contrato_id>/parcela/<int:parcela_id>/baixar', methods=['POST'])
def baixar_parcela(contrato_id, parcela_id):
    p = Parcela.query.filter_by(id=parcela_id, contrato_id=contrato_id).first_or_404()
    p.baixa = True
    p.data_baixa = date.today()
    db.session.commit()
    flash("Parcela baixada.", "success")
    return redirect(url_for('parcelas', id=contrato_id))


# --------- Exportação simples para XLSX ---------
@app.route('/exportar')
def exportar():
    # Exporta a lista de contratos para XLSX com pandas se disponível; se não, CSV.
    try:
        import pandas as pd
    except Exception:
        # Fallback CSV
        import csv
        from io import StringIO
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "cpf", "cliente", "contrato", "tipo", "valor", "pago"])
        for c in Contrato.query.order_by(Contrato.id).all():
            writer.writerow([c.id, c.cpf, c.cliente, c.contrato, c.tipo, c.valor, c.pago])
        buf.seek(0)
        return send_file(BytesIO(buf.getvalue().encode("utf-8")),
                         as_attachment=True, download_name="contratos.csv",
                         mimetype="text/csv")

    rows = []
    for c in Contrato.query.order_by(Contrato.id).all():
        rows.append({
            "ID": c.id,
            "CPF": c.cpf,
            "Cliente": c.cliente,
            "Contrato": c.contrato,
            "Tipo": c.tipo,
            "Valor": c.valor,
            "Pago": c.pago,
            "Parcelas": c.parcelas,
            "Primeiro venc.": fmtdate(c.vencimento_entrada),
        })
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Contratos")
    output.seek(0)
    return send_file(output, as_attachment=True,
                     download_name="contratos.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# -----------------------------
# Inicialização
# -----------------------------
with app.app_context():
    # cria tabelas e aplica migração segura se necessário
    safe_migrate()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
