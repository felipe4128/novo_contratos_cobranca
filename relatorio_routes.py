"""
Rotas do relatório de PARCELAS PAGAS + exportação para Excel.

Copie/cole este conteúdo no seu app.py (ou importe as funções)
e garanta que existam: app, db, Contrato, Parcela.

Também inclua a função _ensure_db_columns() e chame no startup,
conforme o arquivo PATCH_GUIDE.md deste pacote.
"""
from datetime import datetime
from flask import request, render_template, send_file, redirect, url_for, flash
import pandas as pd
import io

@app.route('/relatorios/parcelas-pagas', methods=['GET', 'POST'])
def relatorio_parcelas_pagas():
    resultados = []
    total = 0.0
    inicio = fim = None

    if request.method == 'POST':
        try:
            inicio = datetime.strptime(request.form['inicio'], '%Y-%m-%d').date()
            fim = datetime.strptime(request.form['fim'], '%Y-%m-%d').date()
        except Exception:
            flash('Datas inválidas.', 'warning')
            return render_template('relatorio_parcelas_pagas.html', resultados=[], total=0, inicio=None, fim=None)

        q = (db.session.query(
                Parcela.numero.label('parcela_num'),
                Parcela.valor.label('valor'),
                Parcela.baixada_em.label('baixada_em'),
                Contrato.numero.label('contrato_num'),
                Contrato.cliente.label('cliente')
            )
            .join(Contrato, Parcela.contrato_id == Contrato.id)
            .filter(Parcela.baixada_em.isnot(None),
                    Parcela.baixada_em.between(inicio, fim))
            .order_by(Parcela.baixada_em.asc())
        )

        resultados = q.all()
        total = sum((r.valor or 0) for r in resultados)

    return render_template('relatorio_parcelas_pagas.html',
                           resultados=resultados, total=total,
                           inicio=inicio, fim=fim)

@app.route('/relatorios/parcelas-pagas/exportar')
def exportar_relatorio_parcelas_pagas():
    try:
        inicio = datetime.strptime(request.args.get('inicio'), '%Y-%m-%d').date()
        fim = datetime.strptime(request.args.get('fim'), '%Y-%m-%d').date()
    except Exception:
        flash('Datas inválidas para exportação.', 'warning')
        return redirect(url_for('relatorio_parcelas_pagas'))

    q = (db.session.query(
            Parcela.numero.label('Parcela'),
            Parcela.valor.label('Valor'),
            Parcela.baixada_em.label('Data Baixa'),
            Contrato.numero.label('Contrato'),
            Contrato.cliente.label('Cliente')
        )
        .join(Contrato, Parcela.contrato_id == Contrato.id)
        .filter(Parcela.baixada_em.isnot(None),
                Parcela.baixada_em.between(inicio, fim))
        .order_by(Parcela.baixada_em.asc())
    )

    dados = [{
        'Data Baixa': r[2],
        'Cliente'   : r[4],
        'Contrato'  : r[3],
        'Parcela'   : r[0],
        'Valor'     : float(r[1] or 0)
    } for r in q.all()]

    df = pd.DataFrame(dados)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        (df if not df.empty else pd.DataFrame(columns=dados[0].keys() if dados else []))            .to_excel(writer, index=False, sheet_name='Parcelas Pagas')
    output.seek(0)

    filename = f"parcelas_pagas_{inicio.isoformat()}_{fim.isoformat()}.xlsx"
    return send_file(output,
                     as_attachment=True,
                     download_name=filename,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
