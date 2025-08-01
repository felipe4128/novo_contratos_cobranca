from flask import Flask, render_template, request, redirect, url_for, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///credito.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
            vencimento_entrada=datetime.strptime(request.form.get('vencimento_entrada'), '%Y-%m-%d') if request.form.get('vencimento_entrada') else None,
            valor_das_parcelas=float(request.form.get('valor_das_parcelas')) if request.form.get('valor_das_parcelas') else None,
            parcelas=int(request.form.get('parcelas')) if request.form.get('parcelas') else 0,
            parcelas_restantes=int(request.form.get('parcelas_restantes')) if request.form.get('parcelas_restantes') else 0,
            vencimento_parcelas=datetime.strptime(request.form.get('vencimento_parcelas'), '%Y-%m-%d') if request.form.get('vencimento_parcelas') else None,
            quantidade_boletos_emitidos=int(request.form.get('quantidade_boletos_emitidos')) if request.form.get('quantidade_boletos_emitidos') else None,
            valor_pg_com_boleto=float(request.form.get('valor_pg_com_boleto')) if request.form.get('valor_pg_com_boleto') else None,
            data_pg_boleto=datetime.strptime(request.form.get('data_pg_boleto'), '%Y-%m-%d') if request.form.get('data_pg_boleto') else None,
            data_baixa=datetime.strptime(request.form.get('data_baixa'), '%Y-%m-%d') if request.form.get('data_baixa') else None,
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


@app.route('/parcelas/<int:id>')
def parcelas(id):
    c = Contrato.query.get_or_404(id)
    # generate parcelas if not exist
    if not Parcela.query.filter_by(contrato_id=c.id).first():
        first_due = c.vencimento_parcelas or c.vencimento_entrada
        if first_due and c.parcelas and c.valor_das_parcelas:
            for i in range(c.parcelas):
                due = first_due + relativedelta(months=i)
                p = Parcela(contrato_id=c.id, numero=i+1, due_date=due, value=c.valor_das_parcelas)
                db.session.add(p)
            db.session.commit()
    parcels = Parcela.query.filter_by(contrato_id=c.id).order_by(Parcela.numero).all()
    return render_template('parcelas.html', contrato=c, parcels=parcels)

@app.route('/parcelas/<int:contrato_id>/baixar/<int:parcela_id>', methods=['POST'])
def baixar_parcela(contrato_id, parcela_id):
    p = Parcela.query.get_or_404(parcela_id)
    p.baixa = True
    p.data_baixa = datetime.today().date()
    # update valor_pago
    c = p.contrato
    c.valor_pago = (c.valor_pago or 0) + p.value
    db.session.commit()
    return redirect(url_for('parcelas', id=contrato_id))

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
