import { useState } from "react";
import type { ChatResponse, EntryResponse } from "../types/api";
import { apiService } from "../services/api";

interface Message {
  id: string;
  type: "user" | "assistant" | "thinking";
  content: string;
  entries?: EntryResponse[];
}

interface ChatInterfaceProps {
  onEntryCreated?: () => void;
}

export default function ChatInterface({ onEntryCreated }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const examplePrompts = [
    "spent $20 on coffee",
    "show my expenses",
    "earned $100",
    "what did I spend this month",
    "add expense for groceries $50",
  ];

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      type: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    // Add thinking message
    const thinkingMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: "thinking",
      content: "Processing your request...",
    };
    setMessages((prev) => [...prev, thinkingMessage]);

    try {
      const response: ChatResponse = await apiService.sendChatMessage(
        input.trim()
      );

      // Remove thinking message
      setMessages((prev) => prev.filter((msg) => msg.type !== "thinking"));

      // Add assistant response
      const assistantMessage: Message = {
        id: (Date.now() + 2).toString(),
        type: "assistant",
        content: response.message,
        entries:
          response.result &&
          Array.isArray(response.result) &&
          response.result.length > 0
            ? response.result
            : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Trigger refresh if data was mutated (write operation creates an entry)
      if (response.operation === "write" && response.result && onEntryCreated) {
        onEntryCreated();
      }
    } catch (error) {
      // Remove thinking message
      setMessages((prev) => prev.filter((msg) => msg.type !== "thinking"));

      // Add error message
      const errorMessage: Message = {
        id: (Date.now() + 2).toString(),
        type: "assistant",
        content: `Error: ${
          error instanceof Error ? error.message : "Something went wrong"
        }`,
      };

      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatAmount = (
    amount: number | string | undefined,
    direction: string
  ) => {
    // Handle undefined, null, or invalid amounts
    if (amount === undefined || amount === null || amount === "") {
      return direction === "expense" ? "-$0.00" : "+$0.00";
    }

    const numAmount = typeof amount === "string" ? parseFloat(amount) : amount;

    // Handle NaN case
    if (isNaN(numAmount)) {
      return direction === "expense" ? "-$0.00" : "+$0.00";
    }

    const sign = direction === "expense" ? "-" : "+";
    return `${sign}$${numAmount.toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const day = date.getDate().toString().padStart(2, "0");
    const month = (date.getMonth() + 1).toString().padStart(2, "0");
    const year = date.getFullYear();
    return `${day}/${month}/${year}`;
  };

  return (
    <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-gray-700/50 shadow-xl flex flex-col">
      <div className="p-6 border-b border-gray-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 bg-gradient-to-r from-purple-500 to-pink-500 rounded-full flex items-center justify-center">
              <span className="text-white text-sm">🤖</span>
            </div>
            <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
              AI Assistant
            </h2>
          </div>
          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white rounded-lg transition-colors flex items-center space-x-1"
              title="Clear conversation"
            >
              <span>🔄</span>
              <span>Reset</span>
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 scrollbar-thin">
        {messages.length === 0 && (
          <div className="text-center py-4">
            <div className="text-4xl mb-3">💬</div>
            <div className="text-gray-400 text-lg font-medium mb-3">
              Start a conversation
            </div>
            <div className="text-gray-500 text-sm mb-4">
              Try these examples:
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {examplePrompts.map((prompt, index) => (
                <button
                  key={index}
                  onClick={() => setInput(prompt)}
                  className="text-left p-2.5 bg-gray-800/50 hover:bg-gray-800/70 rounded-lg border border-gray-700/30 hover:border-gray-600/50 transition-all duration-200 group"
                >
                  <div className="flex items-center space-x-2">
                    <span className="text-blue-400 group-hover:text-blue-300 text-sm">
                      💡
                    </span>
                    <span className="text-gray-300 group-hover:text-white text-sm">
                      {prompt}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex ${
              message.type === "user" ? "justify-end" : "justify-start"
            }`}
          >
            <div
              className={`max-w-xs lg:max-w-md px-4 py-3 rounded-2xl ${
                message.type === "user"
                  ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white"
                  : message.type === "thinking"
                  ? "bg-gray-700/50 text-gray-300 border border-gray-600/30"
                  : "bg-gray-800/50 text-white border border-gray-700/30"
              }`}
            >
              <div className="flex items-start space-x-2">
                {message.type === "user" ? (
                  <span className="text-sm">👤</span>
                ) : message.type === "thinking" ? (
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-gray-400 border-t-transparent mt-0.5"></div>
                ) : (
                  <span className="text-sm">🤖</span>
                )}
                <p className="text-sm flex-1">{message.content}</p>
              </div>

              {/* Show entries if present */}
              {message.entries && message.entries.length > 0 && (
                <div className="mt-3 space-y-2">
                  {message.entries.map((entry) => (
                    <div
                      key={entry.id}
                      className="bg-gray-900/50 p-3 rounded-xl border border-gray-700/30"
                    >
                      <div className="flex justify-between items-start">
                        <div className="flex items-center space-x-2">
                          <span
                            className={`font-bold text-lg ${
                              entry.direction === "expense"
                                ? "text-red-400"
                                : "text-green-400"
                            }`}
                          >
                            {formatAmount(entry.amount, entry.direction)}
                          </span>
                          <span className="text-gray-400 text-xs">
                            {formatDate(entry.entry_date)}
                          </span>
                        </div>
                      </div>
                      {entry.description && (
                        <div className="text-gray-300 text-xs mt-2">
                          {entry.description}
                        </div>
                      )}
                      {entry.category && (
                        <div className="text-gray-400 text-xs mt-1">
                          📁 {entry.category.name}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-700/50">
        <div className="flex space-x-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Ask about your finances..."
              className="w-full bg-gray-800/50 text-white px-4 py-3 rounded-xl border border-gray-700/50 focus:outline-none focus:border-blue-500/50 focus:ring-2 focus:ring-blue-500/20 transition-all duration-200 placeholder-gray-400"
              disabled={isLoading}
            />
            {isLoading && (
              <div className="absolute right-3 top-1/2 transform -translate-y-1/2">
                <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-500 border-t-transparent"></div>
              </div>
            )}
          </div>
          <button
            onClick={handleSend}
            disabled={!input.trim() || isLoading}
            className="bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 disabled:from-gray-600 disabled:to-gray-700 disabled:cursor-not-allowed text-white px-6 py-3 rounded-xl font-medium transition-all duration-200 shadow-lg hover:shadow-xl disabled:shadow-none"
          >
            {isLoading ? "..." : "Send"}
          </button>
        </div>
      </div>
    </div>
  );
}
