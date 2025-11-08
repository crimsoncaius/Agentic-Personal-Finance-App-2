// Platform-agnostic storage interface

export interface StorageInterface {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
  removeItem(key: string): Promise<void>;
}

// Web storage implementation (for React web)
export class WebStorage implements StorageInterface {
  async getItem(key: string): Promise<string | null> {
    return localStorage.getItem(key);
  }

  async setItem(key: string, value: string): Promise<void> {
    localStorage.setItem(key, value);
  }

  async removeItem(key: string): Promise<void> {
    localStorage.removeItem(key);
  }
}

// Mobile storage implementation (for React Native)
export class MobileStorage implements StorageInterface {
  private secureStore: any;

  constructor(secureStore: any) {
    this.secureStore = secureStore;
  }

  async getItem(key: string): Promise<string | null> {
    try {
      return await this.secureStore.getItemAsync(key);
    } catch (error) {
      console.error("Error getting item from secure store:", error);
      return null;
    }
  }

  async setItem(key: string, value: string): Promise<void> {
    try {
      await this.secureStore.setItemAsync(key, value);
    } catch (error) {
      console.error("Error setting item in secure store:", error);
    }
  }

  async removeItem(key: string): Promise<void> {
    try {
      await this.secureStore.deleteItemAsync(key);
    } catch (error) {
      console.error("Error removing item from secure store:", error);
    }
  }
}
