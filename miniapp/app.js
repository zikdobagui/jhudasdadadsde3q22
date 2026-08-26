const tg = window.Telegram?.WebApp;
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
const botUsername = 'vendasdoramon_bot';
const defaultProductImage = 'assets/store-banner.png';
const state = { products: [], cart: new Map(), filter: 'todos', query: '' };

const list = document.querySelector('#productList');
const count = document.querySelector('#resultCount');
const cartCount = document.querySelector('#cartCount');
const cartSheet = document.querySelector('#cartSheet');
const cartItems = document.querySelector('#cartItems');
const cartTotal = document.querySelector('#cartTotal');
const checkout = document.querySelector('#checkoutButton');
const toast = document.querySelector('#toast');

tg?.ready();
tg?.expand();
tg?.setHeaderColor?.('#080b10');
tg?.setBackgroundColor?.('#080b10');

function category(name) {
  const value = name.toLocaleLowerCase('pt-BR');
  if (value.includes('conta')) return 'conta';
  if (value.includes('tela')) return 'tela';
  return 'outros';
}

function cleanName(name) {
  return name.replace(/^[^\p{L}\p{N}]+/u, '').replace(/\s+/g, ' ').trim();
}

function imageFor(product) {
  const source = product.image || defaultProductImage;
  const separator = source.includes('?') ? '&' : '?';
  return `${source}${separator}v=${encodeURIComponent(product.updated_at || 'default')}`;
}

function visibleProducts() {
  return state.products.filter((product) => {
    const matchesFilter = state.filter === 'todos' || category(product.name) === state.filter;
    const matchesQuery = product.name.toLocaleLowerCase('pt-BR').includes(state.query);
    return matchesFilter && matchesQuery;
  });
}

function renderProducts() {
  const products = visibleProducts();
  count.textContent = `${products.length} produto${products.length === 1 ? '' : 's'}`;
  if (!products.length) {
    list.innerHTML = '<div class="empty">Nenhum produto encontrado.</div>';
    return;
  }
  list.innerHTML = products.map((product) => `
    <article class="product">
      <img class="product-image" src="${escapeHtml(imageFor(product))}" alt="${escapeHtml(cleanName(product.name))}" loading="lazy" onerror="this.onerror=null;this.src='${defaultProductImage}'">
      <h3>${escapeHtml(cleanName(product.name))}</h3>
      <p class="stock">${product.stock} unidade${product.stock === 1 ? '' : 's'} disponível${product.stock === 1 ? '' : 'is'}</p>
      <div class="product-bottom">
        <strong class="price">${money.format(product.price)}</strong>
        <button class="add-button" type="button" data-add="${escapeHtml(product.name)}" aria-label="Adicionar ao carrinho">+</button>
      </div>
    </article>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]);
}

function updateCart() {
  const entries = [...state.cart.entries()];
  const quantity = entries.reduce((sum, [, amount]) => sum + amount, 0);
  const total = entries.reduce((sum, [name, amount]) => {
    const product = state.products.find((item) => item.name === name);
    return sum + (product?.price || 0) * amount;
  }, 0);
  cartCount.textContent = quantity;
  cartTotal.textContent = money.format(total);
  checkout.disabled = quantity === 0;
  cartItems.innerHTML = entries.length ? entries.map(([name, amount]) => {
    const product = state.products.find((item) => item.name === name);
    return `<div class="cart-item">
      <div><strong>${escapeHtml(cleanName(name))}</strong><p>${money.format((product?.price || 0) * amount)}</p></div>
      <div class="stepper"><button data-change="${escapeHtml(name)}" data-delta="-1" type="button">−</button><span>${amount}</span><button data-change="${escapeHtml(name)}" data-delta="1" type="button">+</button></div>
    </div>`;
  }).join('') : '<div class="empty">Seu carrinho está vazio.</div>';
}

function showCart(open) {
  cartSheet.classList.toggle('open', open);
  cartSheet.setAttribute('aria-hidden', String(!open));
}

function showToast(text) {
  toast.textContent = text;
  toast.classList.add('show');
  window.setTimeout(() => toast.classList.remove('show'), 1800);
}

list.addEventListener('click', (event) => {
  const button = event.target.closest('[data-add]');
  if (!button) return;
  const product = state.products.find((item) => item.name === button.dataset.add);
  const current = state.cart.get(product.name) || 0;
  if (current >= Math.min(product.stock, 10)) return showToast('Limite disponível atingido');
  state.cart.set(product.name, current + 1);
  updateCart();
  tg?.HapticFeedback?.impactOccurred('light');
  showToast('Adicionado ao carrinho');
});

cartItems.addEventListener('click', (event) => {
  const button = event.target.closest('[data-change]');
  if (!button) return;
  const name = button.dataset.change;
  const product = state.products.find((item) => item.name === name);
  const next = (state.cart.get(name) || 0) + Number(button.dataset.delta);
  if (next <= 0) state.cart.delete(name);
  else if (next <= Math.min(product.stock, 10)) state.cart.set(name, next);
  updateCart();
});

document.querySelector('#searchInput').addEventListener('input', (event) => {
  state.query = event.target.value.trim().toLocaleLowerCase('pt-BR');
  renderProducts();
});
document.querySelector('#segments').addEventListener('click', (event) => {
  const button = event.target.closest('[data-filter]');
  if (!button) return;
  document.querySelectorAll('[data-filter]').forEach((item) => item.classList.toggle('active', item === button));
  state.filter = button.dataset.filter;
  renderProducts();
});
document.querySelector('#cartButton').addEventListener('click', () => showCart(true));
document.querySelector('#closeCart').addEventListener('click', () => showCart(false));
document.querySelector('#closeCartIcon').addEventListener('click', () => showCart(false));
checkout.addEventListener('click', () => {
  const items = [...state.cart.entries()].map(([servico, quantidade]) => {
    const idx = state.products.findIndex((product) => product.name === servico);
    return `${idx}x${quantidade}`;
  });
  if (!items.length) return;
  if (items.some((item) => item.startsWith('-1x'))) {
    return showToast('Atualize a loja e tente novamente');
  }
  const startPayload = `mc_${items.join('_')}`;
  if (startPayload.length > 64) {
    checkout.disabled = false;
    return showToast('Envie menos itens por vez para abrir no bot');
  }
  const link = `https://t.me/${botUsername}?start=${encodeURIComponent(startPayload)}`;
  checkout.disabled = true;
  checkout.textContent = 'Abrindo pagamento no bot...';
  tg.HapticFeedback?.notificationOccurred('success');
  if (tg?.openTelegramLink) tg.openTelegramLink(link);
  else window.location.href = link;
  window.setTimeout(() => tg?.close?.(), 500);
});

// URL da API de catálogo em tempo real (SquareCloud)
const catalogApiUrl = (window.APP_CONFIG && window.APP_CONFIG.catalogApiUrl)
  || 'https://ramonatualiza.squareweb.app/catalog.json';

fetch(`${catalogApiUrl}?v=${Date.now()}`, { cache: 'no-store' })
  .then((response) => {
    if (!response.ok) throw new Error('Falha ao carregar estoque');
    return response.json();
  })
  .then((products) => {
    state.products = products;
    renderProducts();
    updateCart();
  })
  .catch(() => { list.innerHTML = '<div class="empty">Não foi possível carregar o catálogo.</div>'; });
