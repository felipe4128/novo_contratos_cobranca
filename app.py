
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date
from io import BytesIO
import pandas as pd
import os

app = Flask(__name__)
app.secret_key = 'dev'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///credito.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# === MODELOS (coloque aqui os seus modelos reais) ===
# OBS: este bloco serve como esqueleto para você colar os imports/definições
# dos seus modelos atuais. Se o seu projeto já tem esses modelos definidos
# acima, mantenha-os e remova esta seção.
class Contrato(db.Model):
    __tablename__ = "contrato"
    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14))
    cliente = db.Column(db.String(100))
    numero = db.Column(db.String(50))
    valor = db.Column(db.Float)

class Parcela(db.Model):
    __tablename__ = "parcela"
    id = db.Column(db.Integer, primary_key=True)
    contrato_id = db.Column(db.Integer, db.ForeignKey('contrato.id'))
    numero = db.Column(db.Integer)
    vencimento = db.Column(db.Date)
    valor = db.Column(db.Float)
    # tente compatibilizar com seu campo real de pagamento:
    baixada_em = db.Column(db.Date, nullable=True)  # ajuste se o seu nome for diferente

    contrato = db.relationship('Contrato', backref='parcelas')

# ================== FIM MODELOS DEMO ==================

def _parse_br_date(s):
    if not s:
        return None
    s = s.strip()
    # aceita dd/mm/aaaa ou aaaa-mm-dd
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None

def _get_pago_col():
    # tenta detectar o nome verdadeiro do campo de data de baixa na Parcela
    for name in ("baixada_em", "baixa_em", "paga_em", "data_pagamento", "data_baixa"):
        if hasattr(Parcela, name):
            return getattr(Parcela, name), name
    return None, None

@app.route('/relatorios/parcelas-pagas', methods=['GET', 'POST'])
def relatorio_parcelas_pagas():
    de_str = request.values.get('de', '')
    ate_str = request.values.get('ate', '')
    de = _parse_br_date(de_str)
    ate = _parse_br_date(ate_str)

    pago_col, pago_name = _get_pago_col()
    if not pago_col:
        flash("Não encontrei o campo de data de pagamento na tabela Parcela. Ajuste o nome em _get_pago_col().", "danger")
        return render_template('relatorio_parcelas_pagas.html', resultados=[], total=0.0, de=de_str, ate=ate_str)

    resultados = []
    total = 0.0

    if request.method == 'POST' and de and ate:
        q = (db.session.query(Parcela, Contrato)
             .join(Contrato, Parcela.contrato_id == Contrato.id)
             .filter(pago_col.isnot(None))
             .filter(pago_col >= de, pago_col <= ate)
             .order_by(pago_col.asc(), Parcela.id.asc()))
        for parcela, contrato in q.all():
            pago_em = getattr(parcela, pago_name)
            resultados.append({
                'contrato_id': contrato.id,
                'contrato_numero': contrato.numero,
                'cpf': contrato.cpf,
                'cliente': contrato.cliente,
                'parcela_numero': parcela.numero,
                'vencimento': parcela.vencimento.strftime('%d/%m/%Y') if parcela.vencimento else '',
                'valor': float(parcela.valor or 0),
                'pago_em': pago_em.strftime('%d/%m/%Y') if pago_em else ''
            })
            total += float(parcela.valor or 0)

    return render_template('relatorio_parcelas_pagas.html',
                           resultados=resultados, total=total, de=de_str, ate=ate_str)

@app.route('/relatorios/parcelas-pagas/exportar')
def exportar_parcelas_pagas():
    de_str = request.args.get('de', '')
    ate_str = request.args.get('ate', '')
    de = _parse_br_date(de_str)
    ate = _parse_br_date(ate_str)

    pago_col, pago_name = _get_pago_col()
    if not pago_col:
        # retorna erro amigável
        return jsonify({'erro': 'Campo de pagamento não encontrado em Parcela.'}), 400

    if not (de and ate):
        return jsonify({'erro': 'Informe os parâmetros de e ate (datas).'}), 400

    q = (db.session.query(Parcela, Contrato)
         .join(Contrato, Parcela.contrato_id == Contrato.id)
         .filter(pago_col.isnot(None))
         .filter(pago_col >= de, pago_col <= ate)
         .order_by(pago_col.asc(), Parcela.id.asc()))

    rows = []
    for parcela, contrato in q.all():
        pago_em = getattr(parcela, pago_name)
        rows.append({
            'Contrato ID': contrato.id,
            'Contrato Nº': contrato.numero,
            'CPF': contrato.cpf,
            'Cliente': contrato.cliente,
            'Parcela Nº': parcela.numero,
            'Vencimento': parcela.vencimento.strftime('%d/%m/%Y') if parcela.vencimento else '',
            'Valor': float(parcela.valor or 0),
            'Pago em': pago_em.strftime('%d/%m/%Y') if pago_em else ''
        })

    df = pd.DataFrame(rows)
    # escreve em Excel em memória
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Pagas')
    output.seek(0)

    filename = f"parcelas_pagas_{de.strftime('%Y%m%d')}_{ate.strftime('%Y%m%d')}.xlsx"
    return send_file(output,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=filename)

# NOTA: integre essas rotas ao seu app existente.
# Se o seu app.py já tem app/run etc, mantenha o seu bloco principal.

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
