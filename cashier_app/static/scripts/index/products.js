// make sure backend checks that product belongs to event/booth
// make sure to remove it from sessionstorage when logging in/out
// make the products in sessionstorage be stored behind a session id or employee id for safety
// order (not cart)


// class Product {
//   constructor(id, name, price, image_url) {
//     this.id = id;
//     this.name = name;
//     this.price = price;
//     this.image_url = image_url;
//   }
// }

import { renderEventPicker } from "./event_booth.js";
import { order } from "./order.js";

const productSide = document.querySelector('#product-side');
const productGridContainer = productSide.querySelector('#product-grid-container');


const cache_time_ms = 60 * 1000; // 1 minuta
// maybe figure out cache max time so that the slow doenst have to happen

const _productsCache = {
  products: null,
  expiry: 0
};

export async function getProducts() {
  if (_productsCache.products && _productsCache.expiry > Date.now()) {
    return _productsCache.products;
  }

  try {
    const response = await fetch('/api/employees/me/events/booths/products');

    if (response.status === 401) {
      const json = await response.json();
      window.location.href = json.redirect_url;
      return false;
    }

    const data = await response.json();

    if (response.status === 400 && ['no_selected_event', 'no_selected_booth'].includes(data.error)) {
      return 'event_or_booth_not_selected';
    }

    if (!response.ok) {
      throw new Error('unexpected_error')
    }

    _productsCache.products = data;
    _productsCache.expiry = Date.now() + cache_time_ms;

    return data;

  } catch (error) {
    return 'unexpected_error';
  }
}


export function resetProductsCache() {
  _productsCache.products = null;
  _productsCache.expiry = 0;
}


export function findProduct(products, productId) {
  for (const product of products) {
    if (product.id === productId) {
      return product;
    }
  }
}


export async function renderProducts() {
  const products = await getProducts(); // combine awaits here and everywhere else

  if (products === false) {
    return;
  }

  if (products === 'event_or_booth_not_selected') {
    productGridContainer.innerHTML = `
      <div id="no-products-message">
        K načtení produktů vyberte stánek.
      </div>
    `;
    renderEventPicker();
    return;
  }

  if (products === 'unexpected_error') {
    productGridContainer.innerHTML = `
      <div id="no-products-message">
        Nepovedlo se načíst produkty.
      </div>
    `;
    return;
  }

  if (products.length === 0) {
    productGridContainer.innerHTML = `
      <div id="no-products-message">
        Stánek nemá přiřazené žádné produkty
      </div>
    `;
    return;
  }

  const url = new URL(window.location);
  const searchQuery = url.searchParams.get('search_query');

  let productsHTML = '';

  products.forEach((product) => {
    if (searchQuery
      && !product.name.toLowerCase().trim().includes(searchQuery)) {
        return;
    }

    let imageHTML;

    if (product.image_path && product.filename) {
      imageHTML = `
        <div class="image-container">
          <img class="product-image" src="${product.image_path}/${product.filename}">
        </div>
      `;
    } else {
      imageHTML = '';
    }

    const quantity = order.getQuantity(product.id);
    const selectedClass = quantity ? 'selected-product' : ''

    productsHTML += `
      <div class="product-container ${selectedClass}">
        ${imageHTML}
        <div class="product-info">
          <div class="product-name">${product.name}</div>
          <div class="product-info-bottom-row">
            <div class="product-price">${product.price} Kč</div>
            <div class="number-selector">
              <button class="minus-button" data-product-id="${product.id}">-</button>
              <input class="productQuantity" name="productQuantity" type="number" min="0" value="${quantity}" data-product-id="${product.id}">
              <button class="plus-button" data-product-id="${product.id}">+</button>
            </div>
          </div>
        </div>
      </div>
    `;
  })

  productGridContainer.innerHTML = `
    <div id="product-grid">
      ${productsHTML}
    </div>
  `;
}