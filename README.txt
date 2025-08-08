OPÇÃO A – PATCH do relatório de PARCELAS PAGAS (sem exigir coluna 'vencimento')

Arquivos:
1) templates/relatorio_parcelas_pagas.html  -> Copie para a pasta templates do seu projeto
2) relatorio_opcaoA_routes.py               -> Abra e cole as duas rotas dentro do seu app.py

Passos rápidos:
- Garanta que seu app.py tenha os imports:
    from datetime import datetime
    from flask import request, render_template, send_file, redirect, url_for, flash
    import pandas as pd
    import io

- Garanta que as classes db, Contrato e Parcela já existam.
- Reinicie o servidor Flask.

URLs:
  /relatorios/parcelas-pagas           (tela com filtro por período)
  /relatorios/parcelas-pagas/exportar  (usada pelo botão Exportar Excel)
