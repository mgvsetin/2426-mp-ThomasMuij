/**
 * @file Vykreslení souhrnu objednávky a celkové ceny.
 */
import { order } from "./order.js";
import { fetchProductsAndCategories, findProduct } from "./products.js";


const orderSummary = document.querySelector('#order-summary');
const orderPrice = document.querySelector('#order-cost');
const payButton = document.querySelector('#pay-button');

/**
 * Vykreslí souhrn objednávky a celkovou cenu do příslušných prvků na stránce.
 * Pokud nejsou produkty nebo položky v objednávce, zobrazí prázdný souhrn a deaktivuje tlačítko platby.
 * @returns {Promise<void>}
 */
export async function renderSummary() {

  // přidat zůstatek a zůstatek po platbě nebo něco podobného

  const result = await fetchProductsAndCategories().catch(() => { });
  if (!result) return;

  const products = result.products;

  if (products.length === 0
    || order.items.length === 0) {
    orderSummary.innerHTML = '';
    orderPrice.innerHTML = '0 Kč';
    payButton.disabled = true;
    return;
  }

  let orderSummaryHTML = '';
  let totalCost = 0;

  order.items.forEach((item) => {
    const matchingProduct = findProduct(products, item.productId);

    totalCost += matchingProduct.price * item.quantity;

    let imageHTML;

    if (matchingProduct.image_path) {
      imageHTML = `
        <div class="summary-image-container">
          <img class="product-image" src="${matchingProduct.image_path}">
        </div>
      `;
    } else {
      imageHTML = '';
    }

    orderSummaryHTML += `
      <div class="summary-item-container selected-product">        
        ${imageHTML}
        <div class="summary-product-info">
          <div class="summary-product-info-top-row">
            <div class="summary-product-name">
              ${matchingProduct.name}
            </div>
            <button class="remove-item-button" data-product-id="${matchingProduct.id}">
              <img class="remove-item-icon" src="/static/images/icons/trash_icon.png">
            </button>
          </div>

          <div class="summary-product-info-bottom-row">
            <div class="summary-product-price">
              ${matchingProduct.price} Kč
            </div>
            <div class="summary-number-selector">
              <button class="summary-minus-button" data-product-id="${matchingProduct.id}">-</button>
              <input class="summary-productQuantity" name="summary-productQuantity" type="number" min="0" value="${item.quantity}" data-product-id="${matchingProduct.id}">
              <button class="summary-plus-button" data-product-id="${matchingProduct.id}">+</button>
            </div>
          </div>
        </div>
      </div>
    `;
  });

  orderSummary.innerHTML = orderSummaryHTML;
  orderPrice.innerHTML = `${totalCost} Kč`;

  payButton.disabled = false;
}
