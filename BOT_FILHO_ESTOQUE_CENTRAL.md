# Bot Filho com Estoque Central

O bot filho usa o mesmo codigo do bot principal, mas com o estoque apontando para a API do bot central.

No `settings/credenciais.json` do bot filho, preencha:

```json
{
  "central_stock_api_url": "https://vendasdoramon.squareweb.app",
  "central_stock_api_key": "MESMA_CHAVE_stock_api_key_DO_BOT_CENTRAL",
  "child_bot_id": "cliente-001"
}
```

Quando esses campos estiverem preenchidos:

- a listagem de produtos usa `GET /api/stock`;
- a consulta de quantidade usa `GET /api/stock`;
- a venda usa `POST /api/stock/reserve`;
- o login vendido e removido do estoque do bot central antes da entrega;
- `database/acessos.json` local deixa de ser necessario para venda.

O bot central continua usando o estoque local normalmente. Nele, deixe `central_stock_api_url` e `central_stock_api_key` vazios.
