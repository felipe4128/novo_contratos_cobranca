
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from io import BytesIO
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///credito.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -------------------- MODELOS --------------------

class Contrato(db.Model):
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
    contrato_id = db.Column(db.Integer, db.ForeignKey('contrato.id'))
    numero = db.Column(db.Integer)
    vencimento = db.Column(db.Date)
    valor = db.Column(db.Float)
    baixada_em = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contrato = db.relationship('Contrato', backref='parcelas')

# -------------------- HELPERS --------------------

def parse_br_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def to_br_date(d):
    return d.strftime('%d/%m/%Y') if d else ''

def float_or_none(x):
    return float(x.replace(',','.')) if x not in (None, '',) else None

# -------------------- ROTAS PRINCIPAIS --------------------

@app.route('/')
def index():
    contratos = Contrato.query.order_by(Contrato.id.desc()).all()
    return render_template('index.html', contratos=contratos)

@app.route('/novo', methods=['GET','POST'])
def novo():
    if request.method == 'POST':
        c = Contrato(
            cpf=request.form.get('cpf'),
            cliente=request.form.get('cliente'),
            numero=request.form.get('numero'),
            tipo_contrato=request.form.get('tipo_contrato'),
            cooperado=request.form.get('cooperado'),
            garantia=request.form.get('garantia'),
            valor=float_or_none(request.form.get('valor')),
            valor_pago=float_or_none(request.form.get('valor_pago')) or 0.0,
            valor_contrato_sistema=float_or_none(request.form.get('valor_contrato_sistema')),
            baixa_acima_48_meses=bool(request.form.get('baixa_acima_48_meses')),
            valor_abatido=float_or_none(request.form.get('valor_abatido')),
            ganho=float_or_none(request.form.get('ganho')),
            custas=float_or_none(request.form.get('custas')),
            custas_deduzidas=float_or_none(request.form.get('custas_deduzidas')),
            protesto=float_or_none(request.form.get('protesto')),
            protesto_deduzido=float_or_none(request.form.get('protesto_deduzido')),
            honorario=float_or_none(request.form.get('honorario')),
            honorario_repassado=float_or_none(request.form.get('honorario_repassado')),
            alvara=float_or_none(request.form.get('alvara')),
            alvara_recebido=float_or_none(request.form.get('alvara_recebido')),
            valor_entrada=float_or_none(request.form.get('valor_entrada')),
            vencimento_entrada=parse_br_date(request.form.get('vencimento_entrada')),
            valor_das_parcelas=float_or_none(request.form.get('valor_das_parcelas')),
            parcelas=int(request.form.get('parcelas') or 0),
            parcelas_restantes=int(request.form.get('parcelas') or 0),
            vencimento_parcelas=parse_br_date(request.form.get('vencimento_parcelas')),
            quantidade_boletos_emitidos=int(request.form.get('quantidade_boletos_emitidos') or 0),
            valor_pg_com_boleto=float_or_none(request.form.get('valor_pg_com_boleto')),
            data_pg_boleto=parse_br_date(request.form.get('data_pg_boleto')),
            data_baixa=parse_br_date(request.form.get('data_baixa')),
            obs_contabilidade=request.form.get('obs_contabilidade'),
            obs_contas_receber=request.form.get('obs_contas_receber'),
            valor_repassar_escritorio=float_or_none(request.form.get('valor_repassar_escritorio')),
        )
        db.session.add(c)
        db.session.commit()

        # Gerar parcelas com base na 1ª data e quantidade
        if c.vencimento_parcelas and c.parcelas and c.valor_das_parcelas:
            vcto = c.vencimento_parcelas
            for i in range(1, c.parcelas+1):
                p = Parcela(contrato_id=c.id, numero=i, vencimento=vcto, valor=c.valor_das_parcelas)
                db.session.add(p)
                vcto = vcto + relativedelta(months=1)
            db.session.commit()

        return redirect(url_for('index'))
    return render_template('novo.html')

@app.route('/info/<int:id>', methods=['GET','POST'])
def info(id):
    c = Contrato.query.get_or_404(id)
    if request.method == 'POST':
        for campo in ['cpf','cliente','numero','tipo_contrato','cooperado','garantia','obs_contabilidade','obs_contas_receber']:
            setattr(c, campo, request.form.get(campo))

        for campo in ['valor','valor_pago','valor_contrato_sistema','valor_abatido','ganho','custas','custas_deduzidas','protesto','protesto_deduzido','honorario','honorario_repassado','alvara','alvara_recebido','valor_entrada','valor_das_parcelas','valor_pg_com_boleto','valor_repassar_escritorio']:
            setattr(c, campo, float_or_none(request.form.get(campo)))

        c.baixa_acima_48_meses = bool(request.form.get('baixa_acima_48_meses'))
        c.parcelas = int(request.form.get('parcelas') or 0)
        c.parcelas_restantes = int(request.form.get('parcelas_restantes') or c.parcelas)
        c.vencimento_entrada = parse_br_date(request.form.get('vencimento_entrada'))
        c.vencimento_parcelas = parse_br_date(request.form.get('vencimento_parcelas'))
        c.quantidade_boletos_emitidos = int(request.form.get('quantidade_boletos_emitidos') or 0)
        c.data_pg_boleto = parse_br_date(request.form.get('data_pg_boleto'))
        c.data_baixa = parse_br_date(request.form.get('data_baixa'))

        db.session.commit()
        flash('Contrato atualizado.', 'success')
        return redirect(url_for('info', id=c.id))
    return render_template('info.html', c=c, to_br_date=to_br_date)

@app.route('/parcelas/<int:id>')
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    parcelas = Parcela.query.filter_by(contrato_id=id).order_by(Parcela.numero.asc()).all()
    return render_template('parcelas.html', c=c, parcelas=parcelas, to_br_date=to_br_date)

@app.route('/parcelas/<int:contrato_id>/baixar/<int:parcela_id>', methods=['POST'])
def baixar_parcela(contrato_id, parcela_id):
    c = Contrato.query.get_or_404(contrato_id)
    p = Parcela.query.get_or_404(parcela_id)
    if not p.baixada_em:
        p.baixada_em = date.today()
        c.valor_pago = (c.valor_pago or 0) + (p.valor or 0)
        if c.parcelas_restantes and c.parcelas_restantes > 0:
            c.parcelas_restantes -= 1
        db.session.commit()
        flash('Parcela baixada.', 'success')
    return redirect(url_for('parcelas', id=contrato_id))

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    c = Contrato.query.get_or_404(id)
    # apaga as parcelas também
    Parcela.query.filter_by(contrato_id=id).delete()
    db.session.delete(c)
    db.session.commit()
    flash('Contrato excluído.', 'success')
    return redirect(url_for('index'))

@app.route('/exportar')
def exportar():
    contratos = Contrato.query.order_by(Contrato.id.asc()).all()
    rows = []
    for c in contratos:
        rows.append({
            'CPF': c.cpf, 'Cliente': c.cliente, 'Contrato': c.numero, 'Tipo': c.tipo_contrato,
            'Cooperado': c.cooperado, 'Garantia': c.garantia, 'Valor': c.valor, 'Valor Pago': c.valor_pago,
            'Valor Sistema': c.valor_contrato_sistema, 'Baixa >48m': c.baixa_acima_48_meses,
            'Valor Abatido': c.valor_abatido, 'Ganho': c.ganho, 'Custas': c.custas, 'Custas Dedu.': c.custas_deduzidas,
            'Protesto': c.protesto, 'Protesto Dedu.': c.protesto_deduzido, 'Honorário': c.honorario,
            'Honorário Rep.': c.honorario_repassado, 'Alvará': c.alvara, 'Alvará Recebido': c.alvara_recebido,
            'Entrada': c.valor_entrada, 'Venc. Entrada': to_br_date(c.vencimento_entrada),
            'Valor Parcela': c.valor_das_parcelas, 'Parcelas': c.parcelas, 'Parcelas Restantes': c.parcelas_restantes,
            '1º Venc. Parcela': to_br_date(c.vencimento_parcelas), 'Qtd Boletos': c.quantidade_boletos_emitidos,
            'Valor Pg Boleto': c.valor_pg_com_boleto, 'Data Pg Boleto': to_br_date(c.data_pg_boleto),
            'Data Baixa': to_br_date(c.data_baixa), 'Obs Contab.': c.obs_contabilidade,
            'Obs CR': c.obs_contas_receber, 'Valor Repassar Escr.': c.valor_repassar_escritorio
        })
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Contratos')
    output.seek(0)
    return send_file(output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='contratos.xlsx')

# -------------------- RELATÓRIO PARCELAS PAGAS --------------------

def _get_pago_col():
    return Parcela.baixada_em, 'baixada_em'

@app.route('/relatorios/parcelas-pagas', methods=['GET', 'POST'])
def relatorio_parcelas_pagas():
    de_str = request.values.get('de', '')
    ate_str = request.values.get('ate', '')
    de = parse_br_date(de_str)
    ate = parse_br_date(ate_str)
    resultados = []
    total = 0.0

    if request.method == 'POST' and de and ate:
        pago_col, pago_name = _get_pago_col()
        q = (db.session.query(Parcela, Contrato)
             .join(Contrato, Parcela.contrato_id == Contrato.id)
             .filter(pago_col.isnot(None))
             .filter(pago_col >= de, pago_col <= ate)
             .order_by(pago_col.asc(), Parcela.id.asc()))
        for p, c in q.all():
            pago_em = getattr(p, 'baixada_em')
            resultados.append({
                'contrato_numero': c.numero or '',
                'cliente': c.cliente or '',
                'cpf': c.cpf or '',
                'parcela_numero': p.numero,
                'vencimento': to_br_date(p.vencimento),
                'valor': float(p.valor or 0),
                'pago_em': to_br_date(pago_em)
            })
            total += float(p.valor or 0)
    return render_template('relatorio_parcelas_pagas.html',
                           resultados=resultados, total=total, de=de_str, ate=ate_str)

@app.route('/relatorios/parcelas-pagas/exportar')
def exportar_parcelas_pagas():
    de = parse_br_date(request.args.get('de',''))
    ate = parse_br_date(request.args.get('ate',''))
    if not (de and ate):
        flash('Informe as datas De e Até.', 'warning')
        return redirect(url_for('relatorio_parcelas_pagas'))
    q = (db.session.query(Parcela, Contrato)
         .join(Contrato, Parcela.contrato_id == Contrato.id)
         .filter(Parcela.baixada_em.isnot(None))
         .filter(Parcela.baixada_em >= de, Parcela.baixada_em <= ate)
         .order_by(Parcela.baixada_em.asc(), Parcela.id.asc()))
    rows = []
    for p, c in q.all():
        rows.append({
            'Contrato Nº': c.numero, 'Cliente': c.cliente, 'CPF': c.cpf,
            'Parcela Nº': p.numero, 'Vencimento': to_br_date(p.vencimento),
            'Pago em': to_br_date(p.baixada_em), 'Valor': float(p.valor or 0)
        })
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Pagas')
    output.seek(0)
    filename = f"parcelas_pagas_{de.strftime('%Y%m%d')}_{ate.strftime('%Y%m%d')}.xlsx"
    return send_file(output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True, download_name=filename)

# -------------------- MAIN --------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
