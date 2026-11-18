# Integração do bot WhatsApp com o Telegram

Documento para enviar ao desenvolvedor/chat na pasta do bot WhatsApp.

## Ativação no servidor Telegram

Os endpoints rodam no mesmo servidor HTTP do site (`webapp.py`), sem nova porta.
Configure duas chaves aleatórias diferentes, com pelo menos 32 bytes aleatórios,
como variáveis de ambiente (recomendado):

```
WHATSAPP_API_KEY=<chave privada para clientes e vínculo>
WHATSAPP_CATALOG_API_KEY=<outra chave privada para catálogo>
```

Alternativa: campos `whatsapp_api_key` e `whatsapp_catalog_api_key` no
`settings/credenciais.json`. Não reutilizar token do Telegram, chave Player ou
chave de estoque dos revendedores. Reinicie o bot após instalar os arquivos.
Sem chave configurada, a respectiva API responde 503. Use a URL HTTPS pública
do site como `BASE_URL`. As chaves ficam apenas no backend do WhatsApp.

## Fluxo do vínculo

1. Cliente abre Meu Perfil no Telegram ou no site. O código é gerado automaticamente.
2. Cliente envia o código ao bot oficial WhatsApp em conversa privada.
3. O backend WhatsApp obtém o número do remetente autenticado pela plataforma,
   em formato internacional apenas dígitos (exemplo fictício `5511999999999`).
   Nunca aceitar um número informado no texto da mensagem como identidade.
4. Backend chama o endpoint de vínculo abaixo. O código expira em 24 horas,
   é consumido uma única vez e cada número só pode vincular um cadastro.
5. Nas próximas consultas, usar o número do remetente. O saldo e histórico
   são lidos do mesmo cadastro do Telegram, sem cópias ou sincronização periódica.

### Vincular

`POST /api/whatsapp/v1/vincular`

Headers: `Authorization: Bearer <WHATSAPP_API_KEY>` e `Content-Type: application/json`.

```json
{"codigo":"CODIGO_COPIADO_DO_PERFIL","whatsapp":"5511999999999"}
```

Resposta 200:

```json
{"vinculado":true,"cliente_id":"123456789"}
```

O vínculo é persistido em `database/whatsapp_links.sqlite3`. Inclua esse arquivo
nos backups. Não há vínculo automático usando o campo WhatsApp editável do perfil.
Depois de vincular, o perfil mostra o estado vinculado em lugar do código.
Se expirar sem uso, abrir o perfil gera outro código automaticamente.

### Consultar cliente e saldo

`GET /api/whatsapp/v1/clientes/5511999999999`

Header: `Authorization: Bearer <WHATSAPP_API_KEY>`.

```json
{"cliente_id":"123456789","username":"cliente","whatsapp":"5511999999999","saldo":25.5,"moeda":"BRL","total_compras":2}
```

### Consultar histórico

`GET /api/whatsapp/v1/clientes/5511999999999/historico`

Mesmo header de clientes. Resposta contém `cliente_id`, `compras` e `pagamentos`.
Cada item contém `servico`, `produto`, `valor` e `data` (campos ausentes são null).
Ordem do mais recente para o mais antigo; datas mantêm o formato do cadastro.
Senhas, e-mails de entrega e IDs de pagamento não são exportados por essa API.

### API separada de estoque e preços

`GET /api/whatsapp/v1/produtos`

Header: `Authorization: Bearer <WHATSAPP_CATALOG_API_KEY>`.
Essa chave não permite consultar clientes ou vincular contas.

```json
{"moeda":"BRL","produtos":[{"id":"Nome do produto","nome":"Nome do produto","preco":19.9,"estoque":3,"descricao":"Descrição"}]}
```

Usa o mesmo catálogo do site, incluindo a origem central quando configurada,
ofertas aplicadas pelo site e produtos Player quando habilitados. Para produtos
sem ID próprio, `id` é o nome; não renomear produtos usados como referência.
Não expõe logins/senhas do estoque. Consulte novamente antes de mostrar disponibilidade;
a consulta não reserva estoque nem garante preço para uma compra futura.

## Erros

Resposta JSON `{"erro":"mensagem"}`. Códigos: 400 corpo/número inválido;
401 chave ausente/incorreta; 403 cliente bloqueado; 404 cliente não vinculado
ou rota inexistente; 409 código expirado/consumido/inválido ou número já vinculado;
503 integração não configurada ou fonte temporariamente indisponível.
Não repetir vínculo automaticamente após erro de rede: consultar o cliente primeiro.

## Exemplo Node.js (backend WhatsApp)

```js
async function telegramApi(path, { method = 'GET', body, catalogo = false } = {}) {
  const key = catalogo ? process.env.WHATSAPP_CATALOG_API_KEY : process.env.WHATSAPP_API_KEY;
  const response = await fetch(`${process.env.TELEGRAM_BASE_URL}${path}`, {
    method,
    headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(15000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(`${response.status}: ${data.erro}`);
  return data;
}
// numero deve vir do remetente real da conversa privada:
await telegramApi('/api/whatsapp/v1/vincular', {
  method: 'POST', body: { codigo, whatsapp: numero }
});
const cliente = await telegramApi(`/api/whatsapp/v1/clientes/${numero}`);
const historico = await telegramApi(`/api/whatsapp/v1/clientes/${numero}/historico`);
const produtos = await telegramApi('/api/whatsapp/v1/produtos', { catalogo: true });
```

O contrato original de leitura foi ampliado pelos endpoints transacionais abaixo. O vínculo não transfere nem soma saldos locais do WhatsApp. Não há operação de desfazer vínculo nesta API.
Nunca registrar chaves ou códigos de vínculo em logs ou enviá-los ao frontend.


## Saldo compartilhado — endpoints transacionais

### Arquivos para publicar no Telegram

Enviar juntos `webapp.py`, `whatsapp_api.py` e `whatsapp_transactions.py` para
a aplicação Telegram na Square Cloud. O módulo de transações é obrigatório;
enviar somente os dois arquivos antigos deixa a integração incompleta.
Preservar o `settings/credenciais.json` do servidor com as duas chaves configuradas
e o banco `database/whatsapp_links.sqlite3` com os vínculos e operações existentes.
Reiniciar a aplicação Telegram após publicar. Commit e push não configuram as
chaves privadas do servidor. Os testes locais usam dados simulados e não comprovam
que a aplicação publicada foi atualizada nem que o gateway PIX está disponível.

Instale `whatsapp_transactions.py` junto das versões atualizadas de `whatsapp_api.py` e `webapp.py`. Reinicie o serviço. Todas as rotas abaixo exigem `Authorization: Bearer <WHATSAPP_API_KEY>`; a chave de catálogo não as autoriza.

- POST `/api/whatsapp/v1/clientes/NUMERO/comprar`: JSON `{"operacao":"HASH_SHA256","produto":"Nome","preco":19.9}`. Executa uma unidade pelo checkout existente do site, no mesmo cadastro Telegram. O servidor revalida preço, estoque e saldo. A resposta de sucesso contém `resultado.entregues` com as credenciais da compra e `resultado.saldo`.
- POST `/api/whatsapp/v1/clientes/NUMERO/pix`: JSON `{"operacao":"HASH_SHA256","valor":10}`. Usa o gateway e verificador existentes do Telegram; a aprovação credita o cadastro central. A resposta contém `resultado.id_pag`, `copia`, `valor`, `total` e `qr`.
- GET `/api/whatsapp/v1/clientes/NUMERO/operacoes/HASH_SHA256`: recupera estado e resultado, apenas para o titular vinculado.
- GET `/api/whatsapp/v1/clientes/NUMERO/pix/ID/status`: consulta `pago` e `saldo` de pagamento criado pela API para o titular vinculado.

Respostas transacionais: `operacao`, `status` e, quando concluído, `resultado`. Estados: DONE, PROCESSING, REVIEW, REJECTED. REJECTED pode incluir `erro_status` (ex.: 402 saldo insuficiente). O cliente deve avaliar o estado, mesmo em HTTP 200.

O ID de 64 caracteres hexadecimais identifica a intenção de compra/recarga e deve permanecer igual ao recuperar uma resposta perdida. O backend persiste a operação antes de executar efeitos externos e devolve o resultado anterior para o mesmo ID e conteúdo. ID reutilizado com dados diferentes é recusado. Operações pendentes bloqueiam novas operações do mesmo tipo para esse usuário. PROCESSING após queda e REVIEW exigem conferência administrativa; não cobrar, estornar nem repetir automaticamente. Os endpoints não aceitam crédito arbitrário de saldo pelo WhatsApp.

Os resultados de operações, inclusive entrega, ficam no mesmo `database/whatsapp_links.sqlite3`. Proteja o arquivo e mantenha-o nos backups. Não exporte os resultados aos logs ou a outros clientes.
