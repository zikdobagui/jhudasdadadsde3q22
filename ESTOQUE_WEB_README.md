# 🔄 Sistema de Sincronização de Estoque Web

## 📋 Problema Resolvido

O estoque web (miniapp) estava usando um arquivo estático `miniapp/catalog.json` que **não era atualizado automaticamente** quando o estoque real do bot (`database/acessos.json`) mudava. Isso causava:

- ❌ Estoque desatualizado no site
- ❌ Clientes vendo produtos esgotados como disponíveis
- ❌ Produtos disponíveis não aparecendo no site
- ❌ Preços desatualizados

## ✅ Solução Implementada

### 1. **Atualização Automática em Tempo Real**

O catálogo web agora é atualizado **automaticamente** sempre que:

- ➕ **Logins são adicionados** ao estoque (`/addlogin`)
- ➖ **Logins são removidos** (`remover_login`)
- 🗑️ **Plataforma inteira é removida** (`remover_por_plataforma`)
- 🔄 **Estoque é zerado** (`zerar_estoque`)
- 🛒 **Compras são finalizadas** (carrinho ou compra direta)

### 2. **Script Manual de Atualização**

Criado o arquivo `atualizar_catalogo_web.py` que pode ser executado:

```bash
python atualizar_catalogo_web.py
```

**Quando usar:**
- Se houver alguma inconsistência no estoque
- Após importação manual de dados
- Para forçar uma atualização completa

### 3. **Alterações no Código**

#### Arquivo: `bot.py`

**Função `adicionar_login()` (linha ~4088)**
```python
# Atualizar catálogo do miniapp após adicionar logins
if quantity > 0:
    try:
        atualizar_catalogo_miniapp()
        publicar_miniapp_no_git('atualizar estoque')
    except Exception as e:
        print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `remover_login()` (linha ~4153)**
```python
# Atualizar catálogo do miniapp após remover login
try:
    atualizar_catalogo_miniapp()
    publicar_miniapp_no_git('remover login do estoque')
except Exception as e:
    print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `remover_por_plataforma()` (linha ~4168)**
```python
# Atualizar catálogo do miniapp após remover logins
try:
    atualizar_catalogo_miniapp()
    publicar_miniapp_no_git('remover plataforma do estoque')
except Exception as e:
    print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `zerar_estoque()` (linha ~4267)**
```python
# Atualizar catálogo do miniapp após zerar estoque
try:
    atualizar_catalogo_miniapp()
    publicar_miniapp_no_git('zerar estoque')
except Exception as e:
    print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `executar_compra_quantidade()` (linha ~6808)**
```python
# Atualizar catálogo do miniapp após compra
if comprados > 0:
    try:
        atualizar_catalogo_miniapp()
        publicar_miniapp_no_git('atualizar estoque após compra')
    except Exception as e:
        print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `executar_compra_direta()` (linha ~6842)**
```python
# Atualizar catálogo do miniapp após compra
try:
    atualizar_catalogo_miniapp()
    publicar_miniapp_no_git('atualizar estoque após compra')
except Exception as e:
    print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

**Função `executar_compra_carrinho()` (linha ~6909)**
```python
# Atualizar catálogo do miniapp após compra do carrinho
if total_comprado > 0:
    try:
        atualizar_catalogo_miniapp()
        publicar_miniapp_no_git('atualizar estoque após compra carrinho')
    except Exception as e:
        print(f"[MINIAPP] Erro ao atualizar catálogo: {e}")
```

## 🔍 Como Funciona

### Fluxo de Atualização

```
┌─────────────────────┐
│ Ação no Bot         │
│ (add/remove/compra) │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────────┐
│ atualizar_catalogo_miniapp()│
│ - Lê database/acessos.json  │
│ - Agrupa por produto        │
│ - Conta estoque             │
│ - Gera catalog.json         │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ publicar_miniapp_no_git()   │
│ - git add catalog.json      │
│ - git commit                │
│ - git push                  │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ GitHub Actions Deploy       │
│ (se configurado)            │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│ Site Atualizado! ✅         │
└─────────────────────────────┘
```

### Estrutura do catalog.json

```json
[
  {
    "name": "🔴CONTA NETFLIX PREMIUM",
    "price": 26.0,
    "stock": 20,
    "image": "assets/service-images/auto-icons/contanetflixpcomanncio.jpg",
    "updated_at": 1787704548
  },
  {
    "name": "🔵CONTA DISNEY COM ANUNCIO",
    "price": 8.0,
    "stock": 5,
    "image": "assets/service-images/auto-icons/contadisneypadro.jpg",
    "updated_at": 1787704548
  }
]
```

## 🧪 Como Testar

1. **Teste de Adição:**
   ```
   Adicione um login via bot
   Verifique o catalog.json
   Confirme que o estoque aumentou
   ```

2. **Teste de Compra:**
   ```
   Faça uma compra de um produto
   Verifique o catalog.json
   Confirme que o estoque diminuiu
   ```

3. **Teste Manual:**
   ```bash
   python atualizar_catalogo_web.py
   ```
   Deve mostrar o resumo do estoque atualizado

## 📊 Monitoramento

Para verificar se as atualizações estão funcionando, observe nos logs do bot:

```
✅ Linhas indicando sucesso:
   [MINIAPP] Catálogo atualizado

❌ Linhas indicando erro:
   [MINIAPP] Erro ao atualizar catálogo: <mensagem>
```

## ⚙️ Configuração Adicional (Opcional)

### Atualização Periódica Automática

Para garantir que o estoque esteja sempre sincronizado, você pode:

**Opção 1: Cron Job (Linux/Mac)**
```bash
# Editar crontab
crontab -e

# Adicionar linha para atualizar a cada 5 minutos
*/5 * * * * cd /caminho/para/bot && python atualizar_catalogo_web.py >> logs/catalogo.log 2>&1
```

**Opção 2: Task Scheduler (Windows)**
```
1. Abrir "Agendador de Tarefas"
2. Criar nova tarefa
3. Gatilho: Repetir a cada 5 minutos
4. Ação: Executar atualizar_catalogo_web.py
```

**Opção 3: Loop no bot.py**
```python
import threading

def atualizar_catalogo_periodico():
    while True:
        try:
            atualizar_catalogo_miniapp()
            publicar_miniapp_no_git('atualização periódica')
        except Exception as e:
            print(f"[MINIAPP] Erro na atualização periódica: {e}")
        time.sleep(300)  # A cada 5 minutos

# Iniciar thread ao startar o bot
threading.Thread(target=atualizar_catalogo_periodico, daemon=True).start()
```

## 🐛 Solução de Problemas

### Estoque não atualiza no site

1. **Verifique os logs do bot** para mensagens `[MINIAPP]`
2. **Execute manualmente:** `python atualizar_catalogo_web.py`
3. **Verifique permissões** de escrita em `miniapp/catalog.json`
4. **Confirme que o Git está funcionando** (se usando deploy automático)

### Erro ao executar script manual

```bash
# Verifique se o módulo central está acessível
python -c "import central"

# Verifique se os arquivos existem
ls -la database/acessos.json
ls -la miniapp/catalog.json
```

## 📝 Notas Importantes

- ✅ As alterações **não afetam** o funcionamento normal do bot
- ✅ Se a atualização falhar, **uma mensagem de erro é registrada** mas o bot continua funcionando
- ✅ O estoque real (`database/acessos.json`) **sempre** é a fonte da verdade
- ✅ O `catalog.json` é **gerado automaticamente**, não edite manualmente

## 🎉 Resultado Final

Agora o estoque web está **sempre sincronizado** com o estoque real do bot, proporcionando:

- ✅ Informações precisas para os clientes
- ✅ Experiência de compra melhorada
- ✅ Menos suporte devido a inconsistências
- ✅ Sincronização automática em tempo real
