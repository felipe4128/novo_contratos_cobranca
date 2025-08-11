from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)

# Banco: DATABASE_URL (Postgres no Render). Sem ela, usa SQLite na pasta instance/ (dev).
uri = os.getenv("DATABASE_URL", "").strip()
if uri:
    if uri.startswith("postgres://"):
        uri = uri.replace("postgres://", "postgresql+psycopg2://", 1)
else:
    os.makedirs(app.instance_path, exist_ok=True)
    uri = f"sqlite:///{os.path.join(app.instance_path, 'credito.db')}"
app.config['SQLALCHEMY_DATABASE_URI'] = uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Helper para tratar datas ISO (YYYY-MM-DD)
def parse_iso_date(value):
    if not value:
        return None
    value = str(value).strip()[:10]
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


@app.template_filter('brl')
def brl(value):
    try:
        return f"{float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


class Contrato(db.Model):
    # existing fields
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14), nullable=True)
    cliente = db.Column(db.String(100), nullable=True)
    numero = db.Column(db.String(50), nullable=True)
    tipo_contrato = db.Column(db.String(50), nullable=True)
    cooperado = db.Column(db.String(100), nullable=True)
    garantia = db.Column(db.String(100), nullable=True)
    valor = db.Column(db.Float, nullable=True)
    valor_pago = db.Column(db.Float, nullable=True, default=0.0)
    valor_contrato_sistema = db.Column(db.Float, nullable=True)
    baixa_acima_48_meses = db.Column(db.Boolean, nullable=True, default=False)
    valor_abatido = db.Column(db.Float, nullable=True)
    ganho = db.Column(db.Float, nullable=True)
    custas = db.Column(db.Float, nullable=True)
    custas_deduzidas = db.Column(db.Float, nullable=True)
    protesto = db.Column(db.Float, nullable=True)
    protesto_deduzido = db.Column(db.Float, nullable=True)
    honorario = db.Column(db.Float, nullable=True)
    honorario_repassado = db.Column(db.Float, nullable=True)
    alvara = db.Column(db.Float, nullable=True)
    alvara_recebido = db.Column(db.Float, nullable=True)
    valor_entrada = db.Column(db.Float, nullable=True)
    vencimento_entrada = db.Column(db.Date, nullable=True)
    valor_das_parcelas = db.Column(db.Float, nullable=True)
    parcelas = db.Column(db.Integer, default=0)
    parcelas_restantes = db.Column(db.Integer, default=0)
    vencimento_parcelas = db.Column(db.Date, nullable=True)
    quantidade_boletos_emitidos = db.Column(db.Integer, nullable=True)
    valor_pg_com_boleto = db.Column(db.Float, nullable=True)
    data_pg_boleto = db.Column(db.Date, nullable=True)
    data_baixa = db.Column(db.Date, nullable=True)
    obs_contabilidade = db.Column(db.Text, nullable=True)
    obs_contas_receber = db.Column(db.Text, nullable=True)
    valor_repassar_escritorio = db.Column(db.Float, nullable=True)


class Parcela(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contrato.id'), nullable=False)
    numero = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    value = db.Column(db.Float, nullable=False)
    baixa = db.Column(db.Boolean, default=False)
    data_baixa = db.Column(db.Date, nullable=True)

    contrato = db.relationship('Contrato', backref=db.backref('parcelas_list', lazy=True))


@app.route('/')
def index():
    contratos = Contrato.query.all()
    return render_template('index.html', contratos=contratos)

@app.route('/novo', methods=['GET', 'POST'])
def novo():
    if request.method == 'POST':
        c = Contrato(
            cpf=request.form.get('cpf'),
            cliente=request.form.get('cliente'),
            numero=request.form.get('numero'),
            tipo_contrato=request.form.get('tipo_contrato'),
            cooperado=request.form.get('cooperado'),
            garantia=request.form.get('garantia'),
            valor=float(request.form.get('valor')) if request.form.get('valor') else None,
            valor_pago=float(request.form.get('valor_pago')) if request.form.get('valor_pago') else 0.0,
            valor_contrato_sistema=float(request.form.get('valor_contrato_sistema')) if request.form.get('valor_contrato_sistema') else None,
            baixa_acima_48_meses=bool(request.form.get('baixa_acima_48_meses')),
            valor_abatido=float(request.form.get('valor_abatido')) if request.form.get('valor_abatido') else None,
            ganho=float(request.form.get('ganho')) if request.form.get('ganho') else None,
            custas=float(request.form.get('custas')) if request.form.get('custas') else None,
            custas_deduzidas=float(request.form.get('custas_deduzidas')) if request.form.get('custas_deduzidas') else None,
            protesto=float(request.form.get('protesto')) if request.form.get('protesto') else None,
            protesto_deduzido=float(request.form.get('protesto_deduzido')) if request.form.get('protesto_deduzido') else None,
            honorario=float(request.form.get('honorario')) if request.form.get('honorario') else None,
            honorario_repassado=float(request.form.get('honorario_repassado')) if request.form.get('honorario_repassado') else None,
            alvara=float(request.form.get('alvara')) if request.form.get('alvara') else None,
            alvara_recebido=float(request.form.get('alvara_recebido')) if request.form.get('alvara_recebido') else None,
            valor_entrada=float(request.form.get('valor_entrada')) if request.form.get('valor_entrada') else None,
            vencimento_entrada=parse_iso_date(request.form.get('vencimento_entrada')) if request.form.get('vencimento_entrada') else None,
            valor_das_parcelas=float(request.form.get('valor_das_parcelas')) if request.form.get('valor_das_parcelas') else None,
            parcelas=int(request.form.get('parcelas')) if request.form.get('parcelas') else 0,
            parcelas_restantes=int(request.form.get('parcelas_restantes')) if request.form.get('parcelas_restantes') else 0,
            vencimento_parcelas=parse_iso_date(request.form.get('vencimento_parcelas')) if request.form.get('vencimento_parcelas') else None,
            quantidade_boletos_emitidos=int(request.form.get('quantidade_boletos_emitidos')) if request.form.get('quantidade_boletos_emitidos') else None,
            valor_pg_com_boleto=float(request.form.get('valor_pg_com_boleto')) if request.form.get('valor_pg_com_boleto') else None,
            data_pg_boleto=parse_iso_date(request.form.get('data_pg_boleto')) if request.form.get('data_pg_boleto') else None,
            data_baixa=parse_iso_date(request.form.get('data_baixa')) if request.form.get('data_baixa') else None,
            obs_contabilidade=request.form.get('obs_contabilidade'),
            obs_contas_receber=request.form.get('obs_contas_receber'),
            valor_repassar_escritorio=float(request.form.get('valor_repassar_escritorio')) if request.form.get('valor_repassar_escritorio') else None
        )
        db.session.add(c)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('novo.html')


@app.route('/info/<int:id>', methods=['GET', 'POST'])
def editar_info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == 'POST':
        # Map all fields
        fields = ['cpf','cliente','numero','tipo_contrato','cooperado','garantia',
                  'obs_contabilidade','obs_contas_receber']
        for field in fields:
            setattr(c, field, request.form.get(field))
        num_fields = ['valor','valor_pago','valor_contrato_sistema','valor_abatido','ganho',
                      'custas','custas_deduzidas','protesto','protesto_deduzido','honorario',
                      'honorario_repassado','alvara','alvara_recebido','valor_entrada',
                      'valor_das_parcelas','valor_repassar_escritorio']
        for nf in num_fields:
            val = request.form.get(nf)
            if val:
                setattr(c, nf, float(val))
        int_fields = ['parcelas','parcelas_restantes','quantidade_boletos_emitidos']
        for inf in int_fields:
            val = request.form.get(inf)
            if val:
                setattr(c, inf, int(val))
        date_fields = ['vencimento_entrada','vencimento_parcelas','data_pg_boleto','data_baixa']
        for df in date_fields:
            val = request.form.get(df)
            if val:
                setattr(c, df, datetime.strptime(val, '%Y-%m-%d'))
        c.baixa_acima_48_meses = True if request.form.get('baixa_acima_48_meses') else False
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('info.html', contrato=c)




@app.route('/exportar')
def exportar():
    contratos = Contrato.query.all()
    data = [{
        'ID': c.id,
        'CPF': c.cpf,
        'Cliente': c.cliente,
        'Contrato': c.numero,
        'Tipo': c.tipo_contrato,
        'Cooperado': c.cooperado,
        'Garantia': c.garantia,
        'Valor Contrato': c.valor,
        'Valor Pago': c.valor_pago,
        'Valor no Sistema': c.valor_contrato_sistema,
        'Baixa >48m': c.baixa_acima_48_meses,
        'Valor Abatido': c.valor_abatido,
        'Ganho': c.ganho,
        'Custas': c.custas,
        'Custas Deduzidas': c.custas_deduzidas,
        'Protesto': c.protesto,
        'Protesto Deduzido': c.protesto_deduzido,
        'Honorário': c.honorario,
        'Honorário Repassado': c.honorario_repassado,
        'Alvará': c.alvara,
        'Alvará Recebido': c.alvara_recebido,
        'Valor Entrada': c.valor_entrada,
        'Vencimento Entrada': c.vencimento_entrada,
        'Valor das Parcelas': c.valor_das_parcelas,
        'Parcelas': c.parcelas,
        'Parcelas Restantes': c.parcelas_restantes,
        'Vencimento Parcelas': c.vencimento_parcelas,
        'Qtde Boletos Emitidos': c.quantidade_boletos_emitidos,
        'Valor Pg Boleto': c.valor_pg_com_boleto,
        'Data Pg Boleto': c.data_pg_boleto,
        'Data da Baixa': c.data_baixa,
        'Obs Contabilidade': c.obs_contabilidade,
        'Obs Contas a Receber': c.obs_contas_receber,
        'Valor Repassar Escritório': c.valor_repassar_escritorio
    } for c in contratos]
    df = pd.DataFrame(data)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)
    return send_file(buf, download_name='contratos_completos.xlsx', as_attachment=True)




@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    c = Contrato.query.get_or_404(id)
    db.session.delete(c)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    # create tables on startup
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)


# Rotas de parcelas (inclui alias para url_for('parcelas', id=...))
@app.route('/contrato/<int:id>/parcelas')
@app.route('/parcelas/<int:id>', endpoint='parcelas')
def ver_parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcels = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()

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

    return render_template('parcelas.html', contrato=c, parcelas=parcels, resumo=resumo)

