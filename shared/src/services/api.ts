// Platform-agnostic API Service for Personal Finance App

import type {
  EntryListResponse,
  ChatRequest,
  ChatResponse,
  ErrorResponse,
  TranscriptionResponse,
  VoiceChatResponse,
} from "../types/api";
import type { StorageInterface } from "./storage";

export interface ApiConfig {
  baseUrl: string;
  storage: StorageInterface;
}

class ApiService {
  private config: ApiConfig;

  constructor(config: ApiConfig) {
    this.config = config;
  }

  private async getAuthHeaders(): Promise<Record<string, string>> {
    const session = await this.config.storage.getItem("session");
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
    const url = `${this.config.baseUrl}${endpoint}`;

    const response = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...(await this.getAuthHeaders()),
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        await this.config.storage.removeItem("session");
        await this.config.storage.removeItem("user");

        // For web, reload the page
        if (typeof window !== "undefined") {
          (window as any).location.reload();
        }

        throw new Error("Session expired. Please log in again.");
      }

      const errorData = (await response.json()) as ErrorResponse;
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

    const url = `${this.config.baseUrl}/chat/transcribe`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        ...(await this.getAuthHeaders()),
      },
      body: formData,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        await this.config.storage.removeItem("session");
        await this.config.storage.removeItem("user");

        // For web, reload the page
        if (typeof window !== "undefined") {
          (window as any).location.reload();
        }

        throw new Error("Session expired. Please log in again.");
      }

      const errorData = (await response.json()) as ErrorResponse;
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

    const url = `${this.config.baseUrl}/chat/voice`;
    const response = await fetch(url, {
      method: "POST",
      headers: {
        ...(await this.getAuthHeaders()),
      },
      body: formData,
    });

    if (!response.ok) {
      // Handle 401 Unauthorized - token expired
      if (response.status === 401 || response.status === 403) {
        // Clear session and reload to show login
        await this.config.storage.removeItem("session");
        await this.config.storage.removeItem("user");

        // For web, reload the page
        if (typeof window !== "undefined") {
          (window as any).location.reload();
        }

        throw new Error("Session expired. Please log in again.");
      }

      const errorData = (await response.json()) as ErrorResponse;
      throw new Error(errorData.error?.message || "Voice chat failed");
    }

    return response.json();
  }
}

export { ApiService };
