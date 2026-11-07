# 🌍 INTEGRAÇÃO PLAYER REVENDAS

## 📋 Sobre

A integração com o **Player Revendas** permite que seu bot ofereça contas globais (ChatGPT, Spotify, Canva, etc.) diretamente no menu principal, com entrega automática via API.

## ✨ Funcionalidades

- 🛍️ **Catálogo completo** - Contas, telas, servidores e produtos globais
- ⚡ **Entrega automática** - Pagou, recebeu instantaneamente
- 🏷️ **Seu preço, sua marca** - Configure a margem de lucro
- 💰 **Seus gateways** - O dinheiro cai na SUA conta
- 📊 **Painel completo** - Controle total via painel admin
- 🔒 **Fornecedor oculto** - 100% white label

## 🚀 Como Configurar

### 1. Criar Conta no Player

1. Acesse: https://playertv.sbs
2. Clique em **"Criar minha loja"**
3. Cadastre seu e-mail e senha (24h grátis)
4. Faça login no painel

### 2. Criar Bot no Telegram

1. Converse com o @BotFather
2. Envie `/newbot`
3. Escolha o nome do bot
4. Copie o **token** fornecido

### 3. Conectar o Bot no Player

1. No painel do Player, vá em **Início**
2. Cole o token do bot em **"Token do bot"**
3. Clique em **Salvar**

### 4. Gerar Token de API

1. Ainda no painel do Player, vá em **API & Docs** ou **Início**
2. Clique em **"Gerar Token de API"**
3. Confirme a operação (pode pedir uma soma)
4. **COPIE O TOKEN** - você precisará dele no próximo passo

### 5. Configurar no Bot Ramon

1. No bot, envie `/admin`
2. Clique em **"🌍 Configurar Player API"**
3. Clique em **"🔑 Configurar API Key"**
4. **Cole o token** que você copiou no passo 4
5. O sistema testará automaticamente a conexão

### 6. Definir Preços

1. No painel do Player, vá em **Produtos**
2. Defina sua **margem de lucro** para cada produto
3. Ative o bot no painel do Player

## 🎯 Como Usar

### Para Clientes

1. No menu principal do bot, clique em **"🌍 CONTAS GLOBAIS"**
2. Navegue pelas categorias de produtos
3. Escolha o produto desejado
4. Clique em **"🛒 Comprar Agora"**
5. Receba os dados instantaneamente!

### Para Admin

#### Ver Status da Integração
- `/admin` → **"🌍 Configurar Player API"**
- Veja: Status, saldo, conexão

#### Ativar/Desativar
- No menu de configuração, clique em:
  - **"✅ Ativar"** para habilitar
  - **"❌ Desativar"** para desabilitar

#### Testar Conexão
- Clique em **"🔄 Testar Conexão"**
- Verifica se a API está funcionando

#### Alterar API Key
- Clique em **"🔑 Configurar API Key"**
- Cole o novo token

## 💰 Planos e Preços

- **Teste Grátis**: 24 horas sem cartão
- **Plano Mensal**: R$ 49,90/mês após o teste
- **Seus produtos**: Estoque e clientes 100% seus
- **Sem taxa por venda**: Só a mensalidade

## 📞 Suporte

### Player Revendas
- **Suporte**: @PLAYERSUPORTE01
- **Site**: https://playertv.sbs
- **Documentação**: https://playertv.sbs/api/v1/docs

### Bot Ramon
- Use o botão **"SUPORTE"** no menu principal
- Ou entre em contato com seu administrador

## ⚙️ Arquivos Técnicos

### Novos Arquivos Criados

1. **`player_api.py`**
   - Módulo de integração com a API
   - Funções para produtos, pedidos, saldo

2. **`settings/player_config.json`**
   - Armazena a API Key e status
   - Criado automaticamente na primeira configuração

### Modificações

1. **`bot.py`**
   - Novo botão "CONTAS GLOBAIS" no menu principal
   - Handlers para navegação e compra
   - Configuração no painel admin

## 🔐 Segurança

- ⚠️ **Nunca compartilhe sua API Key**
- 🔒 O token fica armazenado localmente em `settings/player_config.json`
- 🛡️ Use o 2FA no painel do Player para maior segurança

## 🐛 Problemas Comuns

### "API Key não configurada"
- Gere o token no painel do Player
- Configure no bot usando `/admin`

### "API Key inválida"
- Verifique se copiou o token completo
- Gere um novo token no painel do Player

### "Erro ao conectar"
- Verifique sua conexão com a internet
- Confirme que o Player está online

### "Sem estoque"
- O produto está temporariamente indisponível
- Escolha outro produto ou aguarde reabastecimento

## 📊 Estatísticas

As vendas de contas globais são registradas automaticamente:
- Aparecem no histórico do cliente
- Contam para a receita total
- Notificações enviadas ao grupo de vendas

## 🎁 Benefícios

✅ **Aumente seu catálogo** sem gerenciar estoque
✅ **Entrega automática** 24/7
✅ **Fornecedor confiável** com suporte
✅ **Seus clientes** permanecem seus
✅ **Sua marca** em todas as interações

---

**Desenvolvido para Ramon Store Bot** 🚀
**Integração Player Revendas** 🌍
