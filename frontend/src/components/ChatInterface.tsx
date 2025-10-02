import { useState } from "react";
import { ChatResponse, EntryResponse } from "../types/api";
import { apiService } from "../services/api";

interface Message {
  id: string;
  type: "user" | "assistant" | "thinking";
  content: string;
  entries?: EntryResponse[];
}

export default function ChatInterface() {
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
        entries: Array.isArray(response.result)
          ? response.result
          : [response.result],
      };

      setMessages((prev) => [...prev, assistantMessage]);
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

  const formatAmount = (amount: number, direction: string) => {
    const sign = direction === "expense" ? "-" : "+";
    return `${sign}$${amount.toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  return (
    <div className="bg-gray-900 rounded-lg p-6 h-full flex flex-col">
      <h2 className="text-xl font-bold text-white mb-4">Chat Assistant</h2>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto mb-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-gray-400 text-sm">
            <p className="mb-2">Try these examples:</p>
            <div className="space-y-1">
              {examplePrompts.map((prompt, index) => (
                <button
                  key={index}
                  onClick={() => setInput(prompt)}
                  className="block text-left text-blue-400 hover:text-blue-300 text-xs"
                >
                  • {prompt}
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
              className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                message.type === "user"
                  ? "bg-blue-600 text-white"
                  : message.type === "thinking"
                  ? "bg-gray-700 text-gray-300"
                  : "bg-gray-700 text-white"
              }`}
            >
              <p className="text-sm">{message.content}</p>

              {/* Show entries if present */}
              {message.entries && message.entries.length > 0 && (
                <div className="mt-2 space-y-1">
                  {message.entries.map((entry) => (
                    <div
                      key={entry.id}
                      className="text-xs bg-gray-800 p-2 rounded"
                    >
                      <div className="flex justify-between">
                        <span
                          className={`font-medium ${
                            entry.direction === "expense"
                              ? "text-red-400"
                              : "text-green-400"
                          }`}
                        >
                          {formatAmount(entry.amount, entry.direction)}
                        </span>
                        <span className="text-gray-400">
                          {formatDate(entry.entry_date)}
                        </span>
                      </div>
                      {entry.description && (
                        <div className="text-gray-300 mt-1">
                          {entry.description}
                        </div>
                      )}
                      {entry.category && (
                        <div className="text-gray-400 mt-1">
                          {entry.category.name}
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
      <div className="flex space-x-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Ask about your finances..."
          className="flex-1 bg-gray-800 text-white px-3 py-2 rounded-lg border border-gray-700 focus:outline-none focus:border-blue-500"
          disabled={isLoading}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || isLoading}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg"
        >
          Send
        </button>
      </div>
    </div>
  );
}
