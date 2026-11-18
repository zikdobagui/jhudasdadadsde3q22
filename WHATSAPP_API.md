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

Este contrato permite vínculo e leitura. Não debita saldo, efetua compras,
recarrega, entrega credenciais ou desfaz vínculos. Essas operações exigem
endpoints transacionais próprios antes de serem oferecidas pelo WhatsApp.
Nunca registrar chaves ou códigos de vínculo em logs ou enviá-los ao frontend.
