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
  chat_id?: string;
}

export interface ChatResponse {
  message: string;
  entries: EntryResponse[];
  chat_id: string;
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

export interface TranscriptionResponse {
  text: string;
}

export interface VoiceChatResponse {
  transcription: string;
  chat_response: ChatResponse;
}
