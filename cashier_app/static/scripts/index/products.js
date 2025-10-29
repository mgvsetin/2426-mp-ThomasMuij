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

const productSide = document.querySelector('#product-side');
const productGridContainer = productSide.querySelector('#product-grid-container');


async function getProducts() {
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

    return data;

  } catch (error) {
    return 'unexpected_error';
  }
}

export async function renderProducts() {
  const products = await getProducts();

  if (products === 'event_or_booth_not_selected') {
    productGridContainer.innerHTML = `
      <div id="no-products-message">
        K načtení produktů vyberte stánek.
      </div>
    `;
    renderEventPicker(productSide);
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

  let productsHTML = '';

  products.forEach((product) => {
    let imageHTML;

    if (product['image_path'] && product['filename']) {
      imageHTML = `
        <div class="image-container">
          <img class="product-image" src="${product['image_path']}/${product['filename']}">
        </div>
      `;
    } else {
      imageHTML = '';
    }

    productsHTML += `
      <div class="product-container">
        ${imageHTML}
        <div class="product-info">
          <div class="product-name">${product['name']}</div>
          <div class="product-info-bottom-row">
            <div class="product-price">${product['price']} Kč</div>
            <div class="number-selector">
              <button class="minus-button">-</button>
              <input type="number" min="0" max="999" class="number-of-products" value="0">
              <button class="plus-button">+</button>
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