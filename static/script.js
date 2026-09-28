const CART_KEY = 'coffee-shop-cart';

function readCart() {
    try {
        const saved = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
        return Array.isArray(saved) ? saved : [];
    } catch {
        return [];
    }
}

let cart = readCart();

function saveCart() {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

document.querySelectorAll('.add-to-cart').forEach(function(button) {
    button.addEventListener('click', function() {
        const item = button.closest('.menu-item');
        const id = Number(button.dataset.id);
        const name = item.querySelector('h3').textContent.trim();
        const price = Number.parseInt(item.querySelector('p').textContent, 10) || 0;
        const existing = cart.find(function(product) { return product.id === id; });

        if (existing) {
            existing.quantity += 1;
        } else {
            cart.push({ id: id, name: name, price: price, quantity: 1 });
        }

        saveCart();
        renderCart();
    });
});

function renderCart() {
    const list = document.getElementById('cart-items');
    const totalElement = document.getElementById('cart-total');
    if (!list || !totalElement) return;

    list.replaceChildren();
    let total = 0;

    cart.forEach(function(product, index) {
        const lineTotal = product.price * product.quantity;
        const li = document.createElement('li');
        li.textContent = `${product.name} — ${product.quantity} × ${product.price} грн. = ${lineTotal} грн. `;

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'Убрать';
        remove.addEventListener('click', function() {
            cart.splice(index, 1);
            saveCart();
            renderCart();
        });
        li.appendChild(remove);
        list.appendChild(li);
        total += lineTotal;
    });

    totalElement.textContent = total;
}

const checkoutButton = document.getElementById('checkout');
if (checkoutButton) {
    checkoutButton.addEventListener('click', function() {
        if (cart.length === 0) {
            alert('Добавьте товары в корзину перед оформлением заказа.');
            return;
        }

        document.getElementById('cart-data').value = JSON.stringify(
            cart.map(function(product) { return { id: product.id, quantity: product.quantity }; })
        );
        document.getElementById('checkout-form').submit();
    });
}

const searchInput = document.getElementById('search');
if (searchInput) {
    searchInput.addEventListener('input', function() {
        const query = searchInput.value.toLowerCase();
        document.querySelectorAll('#menu .menu-item').forEach(function(item) {
            const name = item.querySelector('h3').textContent.toLowerCase();
            item.style.display = name.includes(query) ? '' : 'none';
        });
    });
}

renderCart();
