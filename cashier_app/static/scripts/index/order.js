let _orderCache = null;
let _orderInitPromise = null;


export class Order {
  constructor(key) {
    this._key = key;
    this.items = [];
    this._loadOrderFromStorage();
  }

  static async _makeStorageKey() {
    try {
      const response = await fetch('/api/session');

      if (!response.ok) {
        throw new Error('unexpected_error');
      }
      const data = await response.json();

      return `order:${data.employee.id}:${data.booth.id}`

    } catch (error) {
      return 'order:anonymous';
    }
  }

  static async _makeOrder() {
    const storageKey = await Order._makeStorageKey();
    return new Order(storageKey);
  }

  static async getOrder() {
    if (_orderCache) return _orderCache;

    if (!_orderInitPromise) {
      _orderInitPromise = this._makeOrder()
        .then(order => {
          _orderCache = order;
          _orderInitPromise = null;
          return order;
        })
    }
    return _orderInitPromise;
  }

  _loadOrderFromStorage() {
    try {
      const raw = sessionStorage.getItem(this._key);
      this.items = raw ? JSON.parse(raw) : [
        { productId: '20000000-0000-0000-0000-000000000001', quantity: 2 },
        { productId: '20000000-0000-0000-0000-000000000003', quantity: 1 }
      ];
    } catch (error) {
      this.items = [
        { productId: '20000000-0000-0000-0000-000000000001', quantity: 2 },
        { productId: '20000000-0000-0000-0000-000000000003', quantity: 1 }
      ];
      this._saveOrderToStorage();
    }
  }

  _saveOrderToStorage() {
    try {
      sessionStorage.setItem(this._key, JSON.stringify(this.items));
    } catch (error) {
      
    }
  }

  resetAndRemoveFromStorage() {
    this.items = [];
    sessionStorage.removeItem(this._key);
    _orderCache = null;
    _orderInitPromise = null;
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

  updateQuantity(productId, quantity=1) {
    const item = this.getItem(productId);

    if (item) {
      this.setQuantity(productId, item.quantity + quantity);
      return;
    }

    this.setQuantity(productId, quantity);
    return;
  }
}