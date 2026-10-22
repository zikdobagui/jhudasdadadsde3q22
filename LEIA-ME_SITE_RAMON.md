# Site + Painel no Ramon (vendasdoramon.squareweb.app)

## Como instalar
1. Faça um backup do Ramon.
2. Extraia este zip **por cima** da pasta do Ramon (substitui só os arquivos listados abaixo; `database/` e `settings/credenciais.json` não são tocados).
3. Reinicie a aplicação na SquareCloud. O `requirements.txt` novo instala `Pillow` e `qrcode`.
4. Abra https://vendasdoramon.squareweb.app — esse é o link do site.
5. No Telegram, como admin, envie **/painel**: o bot responde com o link permanente do painel (`/painel novo` troca o link).

## Arquivos novos
site_ponte.py, site_espelho.py, webapp.py, admin_painel.py, webapp_imagens.py, eventos_admin.py,
rl_maintenance.py, sistema_favoritos.py, fotos_produtos.py, Oferta_relampago.py, premium_emojis.py,
entretenimento*.py, fotos_menus.py, webapp_entretenimento.py, webapp_static/ (site, painel e ícones do app),
assets/icones/ (imagens de reserva), settings/webapp.json (URL e porta do site)

## Arquivos alterados
- bot.py: 5 linhas antes do `bot.infinity_polling()` que ligam o site (se o site falhar, o bot segue normal).
- database.py: ao salvar um cliente, também atualiza o espelho do site.
- start.py: não inicia mais o api_catalogo.py (mini app antigo) porque o site agora usa a porta 80.
- requirements.txt: + Pillow, qrcode.

## Como funciona
- O site roda dentro do bot e usa o mesmo estoque, saldo, PIX (gateway selecionado: MisticPay, Mercado Pago ou PushinPay) e entrega do Ramon.
- `database/site_espelho.db` é criado sozinho na 1ª vez (copia os clientes para o painel listar vendas/clientes). Pode apagar: ele se refaz.
- Painel: Resumo, Estoque, Imagens, Clientes, Vendas, Pagamentos (lê/grava as configurações de PIX do Ramon), Ofertas, Gift cards, Admins, Ajustes.
- Imagens dos produtos: painel > `database/miniapp_images.json` (as do mini app antigo) > /setfoto > ícones de reserva.

## Não incluído / diferente do bot da RL
- Aba Diversão (filmes/jogos), VIP/cashback e indicações no site: ficam ocultos.
- Backup e grupo obrigatório pelo painel: indisponíveis (o Ramon continua fazendo pelo bot).
- Manutenção do painel vale só para o site.
- Se o Ramon for atualizado por git (auto_update), faça commit dos arquivos novos/alterados.

## Teste recomendado
Crie uma conta no site, faça um PIX pequeno e uma compra. Conferido só com bot simulado (sem Telegram/gateway reais).
