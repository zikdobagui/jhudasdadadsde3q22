const tg = window.Telegram?.WebApp;
const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
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

function iconFor(name) {
  const value = name.toLocaleLowerCase('pt-BR');
  if (value.includes('music') || value.includes('spotify') || value.includes('deezer') || value.includes('tidal')) return '🎧';
  if (value.includes('canva') || value.includes('capcut')) return '🎨';
  if (value.includes('youtube') || value.includes('video')) return '▶️';
  if (value.includes('tela')) return '📺';
  if (value.includes('conta')) return '🔐';
  return '📦';
}

function cleanName(name) {
  return name.replace(/^[^\p{L}\p{N}]+/u, '').replace(/\s+/g, ' ').trim();
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
      <div class="product-icon" aria-hidden="true">${iconFor(product.name)}</div>
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
  const items = [...state.cart.entries()].map(([servico, quantidade]) => ({ servico, quantidade }));
  if (!items.length) return;
  const payload = JSON.stringify({ action: 'miniapp_cart', items });
  if (!tg?.initData || typeof tg.sendData !== 'function') {
    return showToast('Abra a loja dentro do Telegram para enviar');
  }
  checkout.disabled = true;
  checkout.textContent = 'Enviando para o bot...';
  tg.sendData(payload);
  tg.HapticFeedback?.notificationOccurred('success');
  window.setTimeout(() => tg.close(), 350);
});

fetch('catalog.json', { cache: 'no-store' })
  .then((response) => response.json())
  .then((products) => {
    state.products = products;
    renderProducts();
    updateCart();
  })
  .catch(() => { list.innerHTML = '<div class="empty">Não foi possível carregar o catálogo.</div>'; });
