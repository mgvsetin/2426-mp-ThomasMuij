import { Order } from "./order.js";
import { getProducts, findProduct } from "./products.js";


const orderSummary = document.querySelector('#order-summary');
const orderPrice = document.querySelector('#order-cost');
const payButton = document.querySelector('#pay-button');

export async function renderSummary() {

  // add the zustatek stuff, add zustatek po platbe nebo neco takoveho

  const order = await Order.getOrder();
  const products = await getProducts();

  if ([false, 'event_or_booth_not_selected', 'unexpected_error'].includes(products)
  || products.length === 0
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

    if (matchingProduct.image_path && matchingProduct.filename) {
      imageHTML = `
        <div class="summary-image-container">
          <img class="product-image" src="${matchingProduct.image_path}/${matchingProduct.filename}">
        </div>
      `;
    } else {
      imageHTML = '';
    }

    orderSummaryHTML += `
      <div class="summary-item-container">        
        ${imageHTML}
        <div class="summary-product-info">
          <div class="summary-product-name">
            ${matchingProduct.name}
          </div>
          <div class="summary-product-info-bottom-row">
            <div class="summary-product-price">
              ${matchingProduct.price} Kč
            </div>
            <div class="summary-number-selector">
              <button class="summary-minus-button" data-product-id="${matchingProduct.id}">-</button>
              <input class="summary-number-of-products" type="number" min="0" value="${item.quantity}">
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
