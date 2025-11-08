// API Service for Personal Finance App - Web

import { ApiService, WebStorage } from "@finance-app/shared";

const API_BASE_URL = import.meta.env.PROD
  ? "https://agentic-personal-finance-app-2-production.up.railway.app/api/v1"
  : "http://localhost:8000/api/v1";

// Create API service with web storage
const storage = new WebStorage();
export const apiService = new ApiService({
  baseUrl: API_BASE_URL,
  storage,
});
