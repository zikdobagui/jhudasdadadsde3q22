# Bot Pai

Estrutura inicial separada para controlar bots filhos sem misturar com o bot principal.

## Arquivos

- `main.py`: comandos do bot pai no Telegram.
- `storage.py`: leitura e escrita do banco local.
- `stock_api.py`: API HTTP do estoque central.
- `stock_storage.py`: operacoes seguras do estoque central.
- `data/bots.json`: cadastro dos bots filhos.
- `data/acessos.json`: estoque central dos acessos.
- `config.example.json`: modelo da configuracao privada.
- `squarecloud.app`: config para hospedar esse bot pai na SquareCloud.

## Como configurar

1. Copie `config.example.json` para `config.json`.
2. Coloque o token do bot pai em `bot_token`.
3. Coloque seu ID Telegram em `admin_ids`.
4. Instale as dependencias:

```bash
pip install -r requirements.txt
```

5. Rode:

```bash
python main.py
```

## Comandos

```text
/start
/novo_bot Nome da Loja | ID_DONO | TOKEN | @usuario | 30/09/2026
/bots
/bot ID
/suspender ID
/ativar ID
/estoque
```

Essa primeira etapa apenas cadastra e organiza os bots filhos. A proxima etapa e ligar esse cadastro ao motor multi-cliente ou ao provisionamento automatico.

## API do estoque central

Todas as rotas protegidas precisam do header:

```text
X-Stock-Key: SUA_CHAVE_DO_config.json
```

Listar estoque sem expor login/senha:

```http
GET /api/stock
```

Reservar um login para venda. Essa rota ja remove o login do estoque central.

```http
POST /api/stock/reserve
Content-Type: application/json

{
  "service": "NETFLIX",
  "child_bot_id": "1",
  "buyer_id": "123456",
  "sale_id": "pedido-001"
}
```

Adicionar acesso ao estoque central:

```http
POST /api/stock/add
Content-Type: application/json

{
  "nome": "NETFLIX",
  "valor": 10,
  "descricao": "30 dias",
  "email": "email@teste.com",
  "senha": "senha",
  "duracao": "30 dias"
}
```
