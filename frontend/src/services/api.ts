// API Service for Personal Finance App

import type {
  EntryListResponse,
  ChatRequest,
  ChatResponse,
  ErrorResponse,
  TranscriptionResponse,
  VoiceChatResponse,
} from "../types/api";

const API_BASE_URL = import.meta.env.PROD
  ? "https://agentic-personal-finance-app-2-production.up.railway.app/api/v1"
  : "http://localhost:8000/api/v1";

class ApiService {
  private getAuthHeaders(): HeadersInit {
    const session = localStorage.getItem("session");
    if (session) {
      try {
        const { access_token } = JSON.parse(session);
        return {
          Authorization: `Bearer ${access_token}`,
        };
      } catch (error) {
        console.error("Error parsing session:", error);
      }
    }
    return {};
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...this.getAuthHeaders(),
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        localStorage.removeItem("session");
        localStorage.removeItem("user");
        window.location.reload();
        throw new Error("Session expired. Please log in again.");
      }

      const errorData: ErrorResponse = await response.json();
      throw new Error(errorData.error?.message || "API request failed");
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

  async sendChatMessage(
    message: string,
    chatId?: string
  ): Promise<ChatResponse> {
    const request: ChatRequest = {
      text: message,
      ...(chatId && { chat_id: chatId }),
    };
    return this.request<ChatResponse>("/chat/", {
      method: "POST",
      body: JSON.stringify(request),
    });
  }

  async transcribeAudio(audioBlob: Blob): Promise<TranscriptionResponse> {
    const formData = new FormData();

    // Determine file extension based on MIME type
    let filename = "recording.webm";
    if (audioBlob.type.includes("mp4")) {
      filename = "recording.mp4";
    } else if (audioBlob.type.includes("webm")) {
      filename = "recording.webm";
    } else if (audioBlob.type.includes("wav")) {
      filename = "recording.wav";
    }

    formData.append("audio_file", audioBlob, filename);

    const url = `${API_BASE_URL}/chat/transcribe`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        ...this.getAuthHeaders(),
      },
      body: formData,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        localStorage.removeItem("session");
        localStorage.removeItem("user");
        window.location.reload();
        throw new Error("Session expired. Please log in again.");
      }

      const errorData: ErrorResponse = await response.json();
      throw new Error(errorData.error?.message || "Transcription failed");
    }

    return response.json();
  }

  async sendVoiceMessage(
    audioBlob: Blob,
    chatId?: string
  ): Promise<VoiceChatResponse> {
    const formData = new FormData();

    // Determine file extension based on MIME type
    let filename = "recording.webm";
    if (audioBlob.type.includes("mp4")) {
      filename = "recording.mp4";
    } else if (audioBlob.type.includes("webm")) {
      filename = "recording.webm";
    } else if (audioBlob.type.includes("wav")) {
      filename = "recording.wav";
    }

    formData.append("audio_file", audioBlob, filename);

    // Add chat_id if provided
    if (chatId) {
      formData.append("chat_id", chatId);
    }

    const url = `${API_BASE_URL}/chat/voice`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        ...this.getAuthHeaders(),
      },
      body: formData,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        localStorage.removeItem("session");
        localStorage.removeItem("user");
        window.location.reload();
        throw new Error("Session expired. Please log in again.");
      }

      const errorData: ErrorResponse = await response.json();
      throw new Error(errorData.error?.message || "Voice chat failed");
    }

    return response.json();
  }
}

export const apiService = new ApiService();
