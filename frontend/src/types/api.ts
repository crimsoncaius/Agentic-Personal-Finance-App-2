// API Types for Personal Finance App

export interface CategoryResponse {
  id: string;
  name: string;
  type: "expense" | "income";
}

export interface EntryResponse {
  id: string;
  amount: number | string;
  direction: "expense" | "income";
  entry_date: string;
  category?: CategoryResponse;
  description?: string;
  source: "manual" | "nlp";
  parse_confidence?: number;
  created_at: string;
}

export interface EntryListResponse {
  items: EntryResponse[];
  page: {
    limit: number;
    offset: number;
    total: number;
  };
}

export interface ChatRequest {
  text: string;
}

export interface ChatResponse {
  operation: "read" | "write" | "unsure";
  result: EntryResponse | EntryResponse[] | string[];
  message: string;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: {
      missing_fields?: string[];
      suggestions?: string[];
    };
  };
}
