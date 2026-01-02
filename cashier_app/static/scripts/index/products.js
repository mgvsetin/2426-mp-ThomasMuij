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

import { cloneData } from "../general/cache.js";
import { BoothNotSelectedError, EventNotSelectedError, UnauthorizedRedirectError, UnexpectedError } from "../general/errors.js";
import { order } from "./order.js";

const productSide = document.querySelector('#product-side');
const productGridContainer = document.querySelector('#product-grid-container');
const categoriesEl = document.querySelector('#categories');
const productsSearchBar = document.querySelector('#products-search-bar');


const cache_time_ms = 60 * 1000; // 1 minuta
// maybe figure out cache max time so that the slow doenst have to happen

const _productsCache = {
  data: null,
  expiry: 0
};

let _getProductsPromise = null;

export function getProductsAndCategories() { // make sure that if this changes it also changes order
  if (_productsCache.data && _productsCache.expiry > Date.now()) {
    return Promise.resolve(cloneData(_productsCache.data));
  }

  if (_getProductsPromise) return _getProductsPromise;

  _getProductsPromise = (async () => {
    try {
      const response = await fetch('/api/events/booths/products-categories');

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        throw new UnauthorizedRedirectError(json.redirect_url);
      }

      const resData = await response.json();

      if (response.status === 400 && resData.error === 'no_selected_event') {
        throw new EventNotSelectedError();
      }

      if (response.status === 400 && resData.error === 'no_selected_booth') {
        throw new BoothNotSelectedError();
      }

      if (!response.ok) {
        throw new UnexpectedError();
      }

      const data = {
        products: resData.products,
        categories: resData.categories.map(category => category.name),
      }

      data.products.forEach(product => {
        product.categories = product.categories.map(category => category.name);
      })

      _productsCache.data = data;
      _productsCache.expiry = Date.now() + cache_time_ms;

      return cloneData(_productsCache.data);

    } finally {
      _getProductsPromise = null;
    }
  })();

  return _getProductsPromise;
}


export function resetProductsCache() {
  _productsCache.data = null;
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
  const result = await getProductsAndCategories().catch((error) => { // combine awaits here and everywhere else
    if ([EventNotSelectedError, BoothNotSelectedError].some((c) => error instanceof c)) {
      productGridContainer.innerHTML = `
      <div id="no-products-message">
        K načtení produktů vyberte stánek.
      </div>
    `;
      return;
    }

    productGridContainer.innerHTML = `
      <div id="no-products-message">
        Nepovedlo se načíst produkty.
      </div>
    `;
  });
  if (!result) {
    return;
  }
  const products = result.products;

  if (products.length === 0) {
    productGridContainer.innerHTML = `
      <div id="no-products-message">
        Stánek nemá přiřazené žádné produkty
      </div>
    `;
    return;
  }

  // const url = new URL(window.location);
  // const searchQuery = url.searchParams.get('search_query');
  const searchQuery = productsSearchBar.value; //.toLowerCase().trim();
  const selectedCategory = getSelectedCategory();

  let productsHTML = '';

  products.forEach((product) => {
    if (!isSearchedFor(product, searchQuery, selectedCategory)) {
      return;
    }

    let imageHTML;

    if (product.image_path) {
      imageHTML = `
        <div class="image-container">
          <img class="product-image" src="${product.image_path}">
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


function isSearchedFor(product, searchQuery, selectedCategory) {
  const productCategories = product.categories.map((category) => {
    return category.toLowerCase().trim();
  })

  if (selectedCategory) {
    if (!productCategories.includes(selectedCategory)) {
      return false;
    }
  }

  searchQuery = searchQuery.toLowerCase().trim();

  if (!searchQuery
    || product.name.toLowerCase().trim().includes(searchQuery)) {
    return true;
  }

  if (selectedCategory) {
    return false;
  }

  for (let category of productCategories) {
    if (category.includes(searchQuery)) {
      return true;
    }
  }

  return false;
}


function getSelectedCategory() {
  return sessionStorage.getItem('selectedCategory');
}


export function saveSelectedCategory(category) {
  if (!category) {
    sessionStorage.removeItem('selectedCategory');
  } else {
    sessionStorage.setItem('selectedCategory', category.toLowerCase().trim())
  }
}


export async function renderCategories() {
  const result = await getProductsAndCategories().catch(() => {
    categoriesEl.innerHTML = '';
  }); // combine awaits here and everywhere else
  if (!result) return;

  const categories = result.categories;

  let categoriesHTML = '';

  categories.forEach((category) => {
    categoriesHTML += `
    <button class="category" data-category="${category.toLowerCase().trim()}">
      ${category}
    </button>
    `;
  })

  categoriesEl.innerHTML = categoriesHTML;
  if (categoriesHTML === '') {
    categoriesEl.classList.remove('show');
  } else {
    categoriesEl.classList.add('show');
  }

  const saved = getSelectedCategory();
  if (saved) {
    const btn = categoriesEl.querySelector(`.category[data-category="${saved}"]`);
    if (btn) btn.classList.add('selected');
  }
}