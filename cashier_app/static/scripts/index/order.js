class Order {
  constructor(key = this._makeStorageKey()) {
    this._key = key;
    this.items = [];
    this._loadOrderFromStorage();
  }

  async _makeStorageKey() {
    try {
      const response = await fetch('/api/session/employee');

      if (!response.ok) {
        throw new Error('unexpected_error');
      }
      const data = await response.json();

      return `order:${data['id']}`

    } catch (error) {
      return 'order:anonymous';
    }
  }

  _loadOrderFromStorage() {
    this.items = JSON.parse(sessionStorage.getItem(this._key)) || [
      {
        productId: '20000000000000000000000000000001',
        quantity: 2
      },
      {
        productId: '20000000000000000000000000000003',
        quantity: 1
      }
    ];
  }

  _saveOrderToStorage() {
    sessionStorage.setItem(this._key, JSON.stringify(this.items));
  }

  resetAndRemoveFromStorage() {
    this.items = [];
    sessionStorage.removeItem(this._key);
  }
}

export let order = new Order();
