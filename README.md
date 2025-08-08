
# Contratos Cobrança (corrigido)

- Relacionamento `Contrato` <-> `Parcela` usando **back_populates** (evita o erro de backref duplicado).
- Gera parcelas a partir do 1º vencimento e valor da parcela.
- Baixa de parcela que atualiza `valor_pago` e `parcelas_restantes`.
- Relatório de parcelas pagas por período + exportação para Excel.
- Exportação de todos os contratos (todos os campos) para Excel.

## Rodar
```bash
pip install -r requirements.txt
python app.py
# abra http://127.0.0.1:5000
```
