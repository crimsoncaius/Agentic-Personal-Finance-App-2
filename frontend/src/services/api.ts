// API Service for Personal Finance App

import type {
  EntryListResponse,
  ChatRequest,
  ChatResponse,
  ErrorResponse,
} from "../types/api";

const API_BASE_URL = process.env.NODE_ENV === 'production' 
  ? 'https://agentic-personal-finance-app-2-production.up.railway.app/api/v1'
  : 'http://localhost:8000/api/v1';

class ApiService {
  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorData: ErrorResponse = await response.json();
      throw new Error(errorData.error.message || "API request failed");
    }

    return response.json();
  }

  async getEntries(
    limit: number = 10,
    offset: number = 0
  ): Promise<EntryListResponse> {
    return this.request<EntryListResponse>(
      `/entries/?limit=${limit}&offset=${offset}`
    );
  }

  async sendChatMessage(message: string): Promise<ChatResponse> {
    const request: ChatRequest = { text: message };
    return this.request<ChatResponse>("/chat/", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }
}

export const apiService = new ApiService();
