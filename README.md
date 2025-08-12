# Contratos Cobrança (Flask 3.x)

- Banco: **SQLite** por padrão em `instance/credito.db` (persistente no Render via disk).
- Se houver `DATABASE_URL`, usa Postgres (corrige `postgres://`).
- Páginas: index, novo, parcelas, baixar parcela (POST), info, excluir (POST), exportar (CSV).

## Rodar local
```bash
pip install -r requirements.txt
python app.py
# abra http://localhost:5000
```
