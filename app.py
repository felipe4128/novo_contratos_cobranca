from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pandas as pd
from io import BytesIO
import os

app = Flask(__name__)
app.secret_key = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///credito.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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

@app.before_request
def before_request():
    db.create_all()

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

# Demais rotas abaixo...
