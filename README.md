
# Contratos Cobrança

Projeto Flask + SQLAlchemy com SQLite por padrão (persistido em `instance/credito.db`).

## Rodando localmente
```bash
pip install -r requirements.txt
python app.py
# http://localhost:5000
```

## Render
- Usa `instance/` como volume (ver `render.yaml`).
- Postgres opcional via `DATABASE_URL` (o app corrige `postgres://` → `postgresql+psycopg2://`).

## Funcionalidades
- Lista de contratos (com **Parcelas**, **Info**, **Excluir**).
- Criação de contrato com geração automática de parcelas mensais.
- Tela de parcelas com cards de resumo e botão **Dar Baixa** (registra data e soma no **Pago**).
- Exporta CSV.
