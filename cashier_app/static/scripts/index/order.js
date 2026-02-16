/**
 * @file Správa objednávky - přidávání, odebírání a ukládání položek.
 */
import { findProduct } from "./products.js";

// let _orderCache = null;
// let _orderInitPromise = null;


class Order {
  /**
   * Vytvoří novou instanci objednávky a načte položky ze sessionStorage.
   * @param {string} [key='order'] Klíč pro uložení objednávky v sessionStorage.
   */
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

  /**
   * Načte objednávku ze sessionStorage.
   * Pokud se načtení nezdaří, uloží prázdnou objednávku.
   * @private
   */
  _loadOrderFromStorage() {
    try {
      const raw = sessionStorage.getItem(this._key);
      this.items = raw ? JSON.parse(raw) : [];
    } catch (error) {
      // this.items = [];
      console.warn('Nepodařilo se načíst objednávku ze sessionStorage');
      this._saveOrderToStorage();
    }
  }

  /**
   * Uloží aktuální objednávku do sessionStorage.
   * @private
   */
  _saveOrderToStorage() {
    try {
      sessionStorage.setItem(this._key, JSON.stringify(this.items));
    } catch (error) {
      console.warn('Nepodařilo se uložit objednávku do sessionStorage');
    }
  }

  /**
   * Resetuje objednávku (vymaže všechny položky) a uloží změnu do sessionStorage.
   */
  reset() {
    this.items = [];
    this._saveOrderToStorage();
    // sessionStorage.removeItem(this._key);
  }

  /**
   * Vrátí celkovou cenu objednávky.
   * @param {Array} products Pole produktů pro výpočet ceny.
   * @returns {number} Celková cena objednávky.
   */
  getTotalPrice(products) {
    let totalPrice = 0;
    for (const item of this.items) {
      const product = findProduct(products, item.productId);
      totalPrice += product.price * item.quantity;
    }
    return totalPrice;
  }

  /**
   * Vrátí položku objednávky podle ID produktu.
   * @param {number|string} productId ID produktu.
   * @returns {Object|undefined} Položka objednávky nebo undefined, pokud neexistuje.
   */
  getItem(productId) {
    for (const item of this.items) {
      if (item.productId === productId) {
        return item;
      }
    }
  }

  /**
   * Vrátí množství daného produktu v objednávce.
   * @param {number|string} productId ID produktu.
   * @returns {number} Množství produktu v objednávce.
   */
  getQuantity(productId) {
    const item = this.getItem(productId);
    return item ? item.quantity : 0;
  }

  /**
   * Nastaví množství produktu v objednávce.
   * Pokud je množství 0 nebo menší, položka se odstraní.
   * @param {number|string} productId ID produktu.
   * @param {number} quantity Požadované množství.
   * @throws {Error} Pokud množství není číslo.
   */
  setQuantity(productId, quantity) {
    quantity = Number(quantity);
    if (Number.isNaN(quantity)) {
      throw new Error('Množství položky musí být číslo')
    }

    quantity = Math.min(quantity, 999);

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

  /**
   * Aktualizuje množství produktu v objednávce (přičte nebo odečte).
   * Pokud položka neexistuje, přidá ji.
   * @param {number|string} productId ID produktu.
   * @param {number} [quantity=1] Změna množství (kladné nebo záporné číslo).
   * @throws {Error} Pokud množství není číslo.
   */
  updateQuantity(productId, quantity = 1) {
    quantity = Number(quantity);
    if (Number.isNaN(quantity)) {
      throw new Error('Množství položky musí být číslo')
    }
    const item = this.getItem(productId);

    if (item) {
      this.setQuantity(productId, item.quantity + quantity);
      return;
    }

    this.setQuantity(productId, quantity);
    return;
  }

  /**
   * Odstraní z objednávky položky, které nemají odpovídající produkt v seznamu produktů.
   * @param {Array} products Pole aktuálních produktů.
   */
  removeItemsWithNoMatchingProduct(products) {
    this.items = this.items.filter((item) => {
      const product = findProduct(products, item.productId);
      if (!product) {
        return false;
      }
      return true;
    });
    this._saveOrderToStorage();
  }
}

export const order = new Order();