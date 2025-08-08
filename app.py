
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy

# --- App / DB setup ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-key")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///credito.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# --- Models ---

class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14), nullable=True)
    cliente = db.Column(db.String(100), nullable=True)
    numero = db.Column(db.String(50), nullable=True)
    tipo_contrato = db.Column(db.String(50), nullable=True)
    cooperado = db.Column(db.String(100), nullable=True)
    garantia = db.Column(db.String(100), nullable=True)

    valor = db.Column(db.Float, nullable=True, default=0.0)
    valor_pago = db.Column(db.Float, nullable=True, default=0.0)
    valor_contrato_sistema = db.Column(db.Float, nullable=True, default=0.0)
    baixa_acima_48_meses = db.Column(db.Boolean, nullable=True, default=False)
    valor_abatido = db.Column(db.Float, nullable=True, default=0.0)
    ganho = db.Column(db.Float, nullable=True, default=0.0)
    custas = db.Column(db.Float, nullable=True, default=0.0)
    custas_deduzidas = db.Column(db.Float, nullable=True, default=0.0)
    protesto = db.Column(db.Float, nullable=True, default=0.0)
    protesto_deduzido = db.Column(db.Float, nullable=True, default=0.0)
    honorario = db.Column(db.Float, nullable=True, default=0.0)
    honorario_repassado = db.Column(db.Float, nullable=True, default=0.0)
    alvara = db.Column(db.Float, nullable=True, default=0.0)
    alvara_recebido = db.Column(db.Float, nullable=True, default=0.0)

    valor_entrada = db.Column(db.Float, nullable=True, default=0.0)
    vencimento_entrada = db.Column(db.Date, nullable=True)

    valor_das_parcelas = db.Column(db.Float, nullable=True, default=0.0)
    parcelas = db.Column(db.Integer, nullable=True, default=0)
    parcelas_restantes = db.Column(db.Integer, nullable=True, default=0)
    vencimento_parcelas = db.Column(db.Date, nullable=True)

    quantidade_boletos_emitidos = db.Column(db.Integer, nullable=True, default=0)
    valor_pg_com_boleto = db.Column(db.Float, nullable=True, default=0.0)
    data_pg_boleto = db.Column(db.Date, nullable=True)
    data_baixa = db.Column(db.Date, nullable=True)

    obs_contabilidade = db.Column(db.Text, nullable=True)
    obs_contas_receber = db.Column(db.Text, nullable=True)

    valor_repassar_escritorio = db.Column(db.Float, nullable=True, default=0.0)

    parcelas_rel = db.relationship("Parcela", back_populates="contrato", cascade="all, delete-orphan")

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.Integer, nullable=False)
    contrato_id = db.Column(db.Integer, db.ForeignKey("contrato.id"), nullable=False)
    vencimento = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Float, nullable=False, default=0.0)
    baixada_em = db.Column(db.Date, nullable=True)

    contrato = db.relationship("Contrato", back_populates="parcelas_rel")

# --- Utils ---
def parse_date_br(s):
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        # dd/mm/aaaa
        return datetime.strptime(s, "%d/%m/%Y").date()
    except ValueError:
        try:
            return datetime.fromisoformat(s).date()
        except Exception:
            return None

def br_date(d):
    if not d:
        return ""
    return d.strftime("%d/%m/%Y")

app.jinja_env.filters['br_date'] = br_date

def gerar_parcelas(contrato: Contrato):
    # Apaga existentes e recria
    contrato.parcelas_rel.clear()
    db.session.flush()
    n = contrato.parcelas or 0
    if n <= 0 or not contrato.vencimento_parcelas:
        return
    valor = contrato.valor_das_parcelas or 0.0
    venc = contrato.vencimento_parcelas
    for i in range(1, n + 1):
        p = Parcela(numero=i, vencimento=venc, valor=valor)
        contrato.parcelas_rel.append(p)
        # próximo mês: tenta manter o dia
        mes = venc.month + 1
        ano = venc.year + (mes - 1) // 12
        mes = ((mes - 1) % 12) + 1
        dia = min(venc.day, 28)  # simplificação segura
        venc = date(ano, mes, dia)

# --- Routes ---

@app.route("/")
def index():
    contratos = Contrato.query.order_by(Contrato.id.desc()).all()
    return render_template("index.html", contratos=contratos)

@app.route("/novo", methods=["GET", "POST"])
def novo():
    if request.method == "POST":
        c = Contrato(
            cpf=request.form.get("cpf"),
            cliente=request.form.get("cliente"),
            numero=request.form.get("numero"),
            tipo_contrato=request.form.get("tipo_contrato"),
            cooperado=request.form.get("cooperado"),
            garantia=request.form.get("garantia"),
            valor=float(request.form.get("valor") or 0),
            valor_contrato_sistema=float(request.form.get("valor_contrato_sistema") or 0),
            baixa_acima_48_meses=(request.form.get("baixa_acima_48_meses") == "on"),
            valor_abatido=float(request.form.get("valor_abatido") or 0),
            ganho=float(request.form.get("ganho") or 0),
            custas=float(request.form.get("custas") or 0),
            custas_deduzidas=float(request.form.get("custas_deduzidas") or 0),
            protesto=float(request.form.get("protesto") or 0),
            protesto_deduzido=float(request.form.get("protesto_deduzido") or 0),
            honorario=float(request.form.get("honorario") or 0),
            honorario_repassado=float(request.form.get("honorario_repassado") or 0),
            alvara=float(request.form.get("alvara") or 0),
            alvara_recebido=float(request.form.get("alvara_recebido") or 0),
            valor_entrada=float(request.form.get("valor_entrada") or 0),
            vencimento_entrada=parse_date_br(request.form.get("vencimento_entrada")),
            valor_das_parcelas=float(request.form.get("valor_das_parcelas") or 0),
            parcelas=int(request.form.get("parcelas") or 0),
            parcelas_restantes=int(request.form.get("parcelas") or 0),
            vencimento_parcelas=parse_date_br(request.form.get("vencimento_parcelas")),
            quantidade_boletos_emitidos=int(request.form.get("quantidade_boletos_emitidos") or 0),
            valor_pg_com_boleto=float(request.form.get("valor_pg_com_boleto") or 0),
            data_pg_boleto=parse_date_br(request.form.get("data_pg_boleto")),
            data_baixa=parse_date_br(request.form.get("data_baixa")),
            obs_contabilidade=request.form.get("obs_contabilidade"),
            obs_contas_receber=request.form.get("obs_contas_receber"),
            valor_repassar_escritorio=float(request.form.get("valor_repassar_escritorio") or 0),
        )
        db.session.add(c)
        db.session.flush()
        gerar_parcelas(c)
        db.session.commit()
        flash("Contrato criado com sucesso!", "success")
        return redirect(url_for("index"))
    return render_template("novo.html")

@app.route("/info/<int:id>", methods=["GET", "POST"])
def info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == "POST":
        f = request.form
        c.cpf = f.get("cpf")
        c.cliente = f.get("cliente")
        c.numero = f.get("numero")
        c.tipo_contrato = f.get("tipo_contrato")
        c.cooperado = f.get("cooperado")
        c.garantia = f.get("garantia")
        c.valor = float(f.get("valor") or 0)
        c.valor_contrato_sistema = float(f.get("valor_contrato_sistema") or 0)
        c.baixa_acima_48_meses = (f.get("baixa_acima_48_meses") == "on")
        c.valor_abatido = float(f.get("valor_abatido") or 0)
        c.ganho = float(f.get("ganho") or 0)
        c.custas = float(f.get("custas") or 0)
        c.custas_deduzidas = float(f.get("custas_deduzidas") or 0)
        c.protesto = float(f.get("protesto") or 0)
        c.protesto_deduzido = float(f.get("protesto_deduzido") or 0)
        c.honorario = float(f.get("honorario") or 0)
        c.honorario_repassado = float(f.get("honorario_repassado") or 0)
        c.alvara = float(f.get("alvara") or 0)
        c.alvara_recebido = float(f.get("alvara_recebido") or 0)
        c.valor_entrada = float(f.get("valor_entrada") or 0)
        c.vencimento_entrada = parse_date_br(f.get("vencimento_entrada"))
        c.valor_das_parcelas = float(f.get("valor_das_parcelas") or 0)
        old_qtd = c.parcelas or 0
        c.parcelas = int(f.get("parcelas") or 0)
        c.vencimento_parcelas = parse_date_br(f.get("vencimento_parcelas"))
        c.quantidade_boletos_emitidos = int(f.get("quantidade_boletos_emitidos") or 0)
        c.valor_pg_com_boleto = float(f.get("valor_pg_com_boleto") or 0)
        c.data_pg_boleto = parse_date_br(f.get("data_pg_boleto"))
        c.data_baixa = parse_date_br(f.get("data_baixa"))
        c.obs_contabilidade = f.get("obs_contabilidade")
        c.obs_contas_receber = f.get("obs_contas_receber")
        c.valor_repassar_escritorio = float(f.get("valor_repassar_escritorio") or 0)

        # Regerar parcelas se quantidade ou 1o vencimento/valor mudarem
        if (c.parcelas != old_qtd) or ("vencimento_parcelas" in f) or ("valor_das_parcelas" in f):
            c.parcelas_restantes = max(0, c.parcelas - sum(1 for p in c.parcelas_rel if p.baixada_em))
            gerar_parcelas(c)

        db.session.commit()
        flash("Contrato atualizado!", "success")
        if "voltar" in request.form:
            return redirect(url_for("index"))
        return redirect(url_for("info", id=c.id))
    return render_template("info.html", c=c)

@app.route("/parcelas/<int:id>")
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    return render_template("parcelas.html", c=c, parcelas=c.parcelas_rel)

@app.route("/baixar/<int:pid>", methods=["POST"])
def baixar(pid):
    p = Parcela.query.get_or_404(pid)
    if not p.baixada_em:
        p.baixada_em = date.today()
        # atualiza totas do contrato
        p.contrato.valor_pago = round((p.contrato.valor_pago or 0) + (p.valor or 0.0), 2)
        if (p.contrato.parcelas_restantes or 0) > 0:
            p.contrato.parcelas_restantes -= 1
    db.session.commit()
    return redirect(url_for("parcelas", id=p.contrato_id))

# -- Relatório de parcelas pagas --
@app.route("/relatorios/parcelas-pagas", methods=["GET", "POST"])
def rel_parcelas_pagas():
    inicio = fim = None
    resultados = []
    if request.method == "POST":
        inicio = parse_date_br(request.form.get("inicio"))
        fim = parse_date_br(request.form.get("fim"))
        query = Parcela.query.filter(Parcela.baixada_em.isnot(None))
        if inicio:
            query = query.filter(Parcela.baixada_em >= inicio)
        if fim:
            query = query.filter(Parcela.baixada_em <= fim)
        resultados = query.order_by(Parcela.baixada_em.asc()).all()
        if "exportar" in request.form:
            # monta dataframe
            rows = []
            for p in resultados:
                c = p.contrato
                rows.append({
                    "Contrato": c.numero,
                    "Cliente": c.cliente,
                    "CPF": c.cpf,
                    "Parcela": p.numero,
                    "Vencimento": br_date(p.vencimento),
                    "Pago em": br_date(p.baixada_em),
                    "Valor": float(p.valor or 0.0),
                })
            import pandas as pd
            from io import BytesIO
            path = "/mnt/data/relatorio_parcelas_pagas.xlsx"
            df = pd.DataFrame(rows)
            with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
                df.to_excel(writer, sheet_name="Pagas", index=False)
            return send_file(path, as_attachment=True, download_name="parcelas_pagas.xlsx")
    total = sum((p.valor or 0.0) for p in resultados) if resultados else 0.0
    return render_template("relatorio_parcelas_pagas.html", inicio=inicio, fim=fim, resultados=resultados, total=total)

# -- Exportar todos os contratos (todos os campos) --
@app.route("/exportar")
def exportar():
    import pandas as pd
    rows = []
    for c in Contrato.query.all():
        rows.append({
            "cpf": c.cpf, "cliente": c.cliente, "numero": c.numero, "tipo_contrato": c.tipo_contrato,
            "cooperado": c.cooperado, "garantia": c.garantia, "valor": c.valor, "valor_pago": c.valor_pago,
            "valor_contrato_sistema": c.valor_contrato_sistema, "baixa_acima_48_meses": c.baixa_acima_48_meses,
            "valor_abatido": c.valor_abatido, "ganho": c.ganho, "custas": c.custas, "custas_deduzidas": c.custas_deduzidas,
            "protesto": c.protesto, "protesto_deduzido": c.protesto_deduzido, "honorario": c.honorario,
            "honorario_repassado": c.honorario_repassado, "alvara": c.alvara, "alvara_recebido": c.alvara_recebido,
            "valor_entrada": c.valor_entrada, "vencimento_entrada": br_date(c.vencimento_entrada),
            "valor_das_parcelas": c.valor_das_parcelas, "parcelas": c.parcelas, "parcelas_restantes": c.parcelas_restantes,
            "vencimento_parcelas": br_date(c.vencimento_parcelas), "quantidade_boletos_emitidos": c.quantidade_boletos_emitidos,
            "valor_pg_com_boleto": c.valor_pg_com_boleto, "data_pg_boleto": br_date(c.data_pg_boleto),
            "data_baixa": br_date(c.data_baixa), "obs_contabilidade": c.obs_contabilidade,
            "obs_contas_receber": c.obs_contas_receber, "valor_repassar_escritorio": c.valor_repassar_escritorio,
        })
    path = "/mnt/data/contratos.xlsx"
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Contratos", index=False)
    return send_file(path, as_attachment=True, download_name="contratos.xlsx")

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for("index"))

# --- bootstrap db
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=True)
