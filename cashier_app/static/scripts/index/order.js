import { findProduct } from "./products.js";

// let _orderCache = null;
// let _orderInitPromise = null;


class Order {
  constructor(key = 'order') {
    this._key = key;
    this.items = [];
    this._loadOrderFromStorage();
  }

  // static async _makeStorageKey() {
  //   try {
  //     const response = await fetch('/api/session');

  //     if (!response.ok) {
  //       throw new Error('unexpected_error');
  //     }
  //     const data = await response.json();

  //     return `order-${data.employee.id}-${data.booth.id}`

  //   } catch (error) {
  //     return 'order-anonymous';
  //   }
  // }

  // static async _makeOrder() {
  //   const storageKey = await Order._makeStorageKey();
  //   return new Order(storageKey);
  // }

  // static async getOrder() {
  //   if (_orderCache) return _orderCache;

  //   if (!_orderInitPromise) {
  //     _orderInitPromise = this._makeOrder()
  //       .then(order => {
  //         _orderCache = order;
  //         _orderInitPromise = null;
  //         return order;
  //       })
  //   }
  //   return _orderInitPromise;
  // }

  _loadOrderFromStorage() {
    try {
      const raw = sessionStorage.getItem(this._key);
      this.items = raw ? JSON.parse(raw) : [];
    } catch (error) {
      // this.items = [];
      console.warn('Failed to load order from sessionStorage');
      this._saveOrderToStorage();
    }
  }

  _saveOrderToStorage() {
    try {
      sessionStorage.setItem(this._key, JSON.stringify(this.items));
    } catch (error) {
      console.warn('Failed to save order to sessionStorage');
    }
  }

  reset() {
    this.items = [];
    this._saveOrderToStorage();
    // sessionStorage.removeItem(this._key);
  }

  getTotalPrice(products) {
    let totalPrice = 0;
    for (const item of this.items) {
      const product = findProduct(products, item.productId);
      totalPrice += product.price * item.quantity;
    }
    return totalPrice;
  }

  getItem(productId) {
    for (const item of this.items) {
      if (item.productId === productId) {
        return item;
      }
    }
  }

  getQuantity(productId) {
    const item = this.getItem(productId);
    return item ? item.quantity : 0;
  }

  setQuantity(productId, quantity) {
    quantity = Number(quantity);
    if (Number.isNaN(quantity)) {
      throw new Error('Item quantity has to be a number')
    }

    let item = this.getItem(productId);

    if (item) {
      item.quantity = quantity;

      if (item.quantity <= 0) {
        const index = this.items.indexOf(item);
        if (index >= 0) this.items.splice(index, 1);
      }
      this._saveOrderToStorage();
      return;
    }

    if (quantity <= 0) {
      return;
    }

    this.items.push({
      productId: productId,
      quantity: quantity
    })
    this._saveOrderToStorage();
  }

  updateQuantity(productId, quantity = 1) {
    quantity = Number(quantity);
    if (Number.isNaN(quantity)) {
      throw new Error('Item quantity has to be a number')
    }
    const item = this.getItem(productId);

    if (item) {
      this.setQuantity(productId, item.quantity + quantity);
      return;
    }

    this.setQuantity(productId, quantity);
    return;
  }
}

export const order = new Order();