# Categorias do catálogo — Contas Globais

A API do Player (`/api/v1/products`) **não devolve o campo `category`**, então
antes todos os 670 produtos apareciam numa lista única, paginada de 12 em 12.
Agora a categoria é deduzida do nome do produto e o menu principal mostra
**um botão por categoria**; os produtos aparecem só depois de escolher uma.

## Arquivos

| Arquivo | O que faz |
|---|---|
| `player_categories.py` (novo) | Detecta a categoria pelo nome, agrupa, ordena e gera os resumos/slugs |
| `settings/player_categories.json` (novo) | Ajustes manuais: `overrides`, `order`, `hidden_categories` |
| `player_handlers.py` (alterado) | Menu de categorias + nova tela de listagem por categoria |

`bot.py` não precisou mudar: o callback `player_cat:` já estava na lista de
exceções do handler genérico (linha ~9109).

## O que aparece no menu

Só contas/serviços **globais**: o menu filtra os produtos pelo campo `source`
da API Player e mantém apenas `global`. Ficam fora os `acessos` (logins
prontos), os `macs` (aplicativos por MAC) e os `outros_manual` — hoje 492 dos
677 produtos da API.

Para mudar isso, edite `settings/player_categories.json`:

```json
"sources": ["global"],
"exclude_sources": []
```

`"sources": []` ou a remoção da chave volta a mostrar o catálogo inteiro;
`exclude_sources` bloqueia origens específicas.

## Como ficou o fluxo

```
🌍 CONTAS GLOBAIS
   🎬 Streaming › 28 produtos
   🎵 Música › 18 produtos
   🤖 IA / Criação › 228 produtos
   📺 IPTV / Servidores › 172 produtos
   🪟 Microsoft / Office › 61 produtos
   🎨 Design / Produtividade › 113 produtos
   🛡️ VPN / Proxy › 34 produtos
   🎮 Jogos › 13 produtos
   🌍 Contas Globais › 3 produtos
   Pesquisar produto
   Atualizar | Voltar ao menu
        ↓ (player_cat:<slug>)
🎬 STREAMING (pág. 1/3)
   28 produtos · 28 em estoque
   CONTA NETFLIX 4K NOVA › 165 · a partir de R$39.00
   ...
   Anterior | · 1/3 · | Próximo
   Atualizar | Categorias
        ↓ (player_prod:<id>)
   Detalhes → Comprar → botão "Voltar" retorna à categoria de origem
```

## Categorias e palavras-chave

A ordem das regras em `CATEGORY_RULES` importa: a primeira que casar define a
categoria. Palavras-chave atuais:
- **Streaming** — netflix, disney, hbo, paramount, globoplay, prime video, crunchyroll, hotstar, shahid, apple tv, conta max/tela max, claro tv, uni tv, telecine
- **Música** — spotify, apple music, tidal, deezer, youtube premium
- **IA / Criação** — chatgpt, gpt, gemini, claude, copilot, perplexity, grok, kling, midjourney, elevenlabs, minimax, gamma, manus, runway, dreamina, veo, suno, heygen, openart, kimi, genspark, lovable, bolt, replit, framer, n8n, warp, railway, canva, capcut, filmora, vidiq, …
- **Microsoft / Office** — outlook, hotmail, office, microsoft, 365, gmail, windows, icloud
- **Design / Produtividade** — adobe, figma, ilovepdf, scribd, notion, airtable, miro, zoom, autodesk, jetbrains, linkedin, udemy, coursera, duolingo, github, proton, corel, …
- **VPN / Proxy** — vpn, proxy, hma, expressvpn, avira, surfshark, v2ray, nordvpn, mcafee, eset, antivírus
- **Jogos** — discord, nitro, steam, xbox, psn, nintendo, gift card
- **IPTV / Servidores** — player, server, iptv, xtream, tivimate, smart, tv, play, box, sports, …
- **Contas Globais** — conta, tela, codigo, acesso, chave, assinatura, tiktok
- **Outros** — o que não casar com nada (hoje: 0 produtos)

## Como ajustar sem mexer no código

`settings/player_categories.json`:

```json
{
    "overrides": { "nome-ou-trecho": "Categoria desejada" },
    "order": ["Streaming", "Música", "..."],
    "hidden_categories": ["Jogos"]
}
```

- `overrides` — casa por trecho do nome (sem acento, sem caixa) e ganha de todas as regras.
- `order` — ordem dos botões no menu.
- `hidden_categories` — categorias que não aparecem.

## Observações

- Dentro de cada categoria os produtos são ordenados por estoque (maior primeiro) e depois por nome.
- **Botões sem emoji padrão:** o texto do botão vai limpo (sem emoji Unicode) e o ícone animado entra só por `icon_custom_emoji_id`. Antes o botão trazia `🎬 Streaming` **e** o ícone premium, aparecendo dois emojis e um deles sem animação.
- **Ícone de cada categoria** (`CATEGORY_PREMIUM_EMOJI_INDEX` em `player_categories.py`): Streaming e IPTV 🎥, Música 🎵, Jogos 🏀, Design 🔵, Contas Globais 🔵; IA, Microsoft e VPN usam o círculo de status (🔴/🟢), que também é premium. Se o pacote `service_emoji_ids` for trocado e o índice não existir, entra o ID de reserva em `CATEGORY_PREMIUM_EMOJI_FALLBACK` — nunca um emoji padrão.
- **Ícone dos produtos** casa o `service_emoji_map` por palavra inteira e sem acento (`service_emoji_id_for`). Antes era um `in` simples: chaves curtas como `SKY` casavam dentro de `dashboard` e aplicavam o ícone errado.
- `service_emoji_ids[38]` tinha o ID `5075765983608570K983` (um `K` no meio): o Telegram rejeita a mensagem inteira com “Invalid custom emoji identifier”. Corrigido para `5075765983608570983` em `settings/credenciais.json`.
- `contas_globais_page:<n>` continua funcionando para links antigos (abre o menu de categorias).
