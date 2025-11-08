import React, { useState, useRef } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
} from "react-native";
import { Audio } from "expo-av";
import type {
  ChatResponse,
  EntryResponse,
} from "../../../shared/src/types/api";
import { formatAmount, formatDate } from "../../../shared/src/utils/formatters";
import { MobileStorage } from "../../../shared/src/services/storage";
import { ApiService } from "../../../shared/src/services/api";
import { API_BASE_URL } from "../config/api";
import { colors, spacing, borderRadius, typography } from "../styles/theme";
import * as SecureStore from "expo-secure-store";

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
  const [chatId, setChatId] = useState<string | undefined>();
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [recording, setRecording] = useState<Audio.Recording | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Create API service
  const storage = new MobileStorage(SecureStore);
  const apiService = new ApiService({
    baseUrl: API_BASE_URL,
    storage,
  });

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
        input.trim(),
        chatId
      );

      // Store chat_id from response for conversation continuity
      if (response.chat_id) {
        setChatId(response.chat_id);
      }

      // Remove thinking message
      setMessages((prev) => prev.filter((msg) => msg.type !== "thinking"));

      // Add assistant response
      const assistantMessage: Message = {
        id: (Date.now() + 2).toString(),
        type: "assistant",
        content: response.message,
        entries:
          response.entries && response.entries.length > 0
            ? response.entries
            : undefined,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Trigger refresh if entries were created/updated
      if (response.entries && response.entries.length > 0 && onEntryCreated) {
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

  const startRecording = async () => {
    try {
      const permission = await Audio.requestPermissionsAsync();
      if (permission.status !== "granted") {
        Alert.alert(
          "Permission Required",
          "Please grant microphone permission to record voice messages."
        );
        return;
      }

      await Audio.setAudioModeAsync({
        allowsRecordingIOS: true,
        playsInSilentModeIOS: true,
      });

      const { recording } = await Audio.Recording.createAsync(
        Audio.RecordingOptionsPresets.HIGH_QUALITY
      );
      setRecording(recording);
      setIsRecording(true);
      setError(null);
    } catch (error) {
      console.error("Failed to start recording:", error);
      setError("Failed to start recording");
    }
  };

  const stopRecording = async () => {
    if (!recording) return;

    try {
      setIsRecording(false);
      await recording.stopAndUnloadAsync();
      const uri = recording.getURI();
      setRecording(null);

      if (uri) {
        // Convert URI to blob for API
        const response = await fetch(uri);
        const blob = await response.blob();

        // Add user message with transcription
        setIsTranscribing(true);
        const transcriptionResult = await apiService.transcribeAudio(blob);

        const userMessage: Message = {
          id: Date.now().toString(),
          type: "user",
          content: transcriptionResult.text,
        };
        setMessages((prev) => [...prev, userMessage]);

        setIsTranscribing(false);
        setIsLoading(true);

        // Add thinking message for NLP processing
        const thinkingMessage: Message = {
          id: (Date.now() + 1).toString(),
          type: "thinking",
          content: "Processing your request...",
        };
        setMessages((prev) => [...prev, thinkingMessage]);

        // Process with chat API
        const chatResponse = await apiService.sendChatMessage(
          transcriptionResult.text,
          chatId
        );

        // Remove thinking message
        setMessages((prev) => prev.filter((msg) => msg.type !== "thinking"));

        // Store chat_id from response for conversation continuity
        if (chatResponse.chat_id) {
          setChatId(chatResponse.chat_id);
        }

        // Add assistant response
        const assistantMessage: Message = {
          id: (Date.now() + 2).toString(),
          type: "assistant",
          content: chatResponse.message,
          entries:
            chatResponse.entries && chatResponse.entries.length > 0
              ? chatResponse.entries
              : undefined,
        };

        setMessages((prev) => [...prev, assistantMessage]);

        // Trigger refresh if entries were created/updated
        if (
          chatResponse.entries &&
          chatResponse.entries.length > 0 &&
          onEntryCreated
        ) {
          onEntryCreated();
        }
      }
    } catch (error) {
      console.error("Failed to stop recording:", error);
      setError("Failed to process voice message");
    } finally {
      setIsLoading(false);
      setIsTranscribing(false);
    }
  };

  const clearConversation = () => {
    setMessages([]);
    setChatId(undefined);
  };

  const renderMessage = ({ item: message }: { item: Message }) => {
    const isUser = message.type === "user";
    const isThinking = message.type === "thinking";

    return (
      <View
        style={[styles.messageContainer, isUser && styles.userMessageContainer]}
      >
        <View
          style={[
            styles.messageBubble,
            isUser ? styles.userMessageBubble : styles.assistantMessageBubble,
            isThinking && styles.thinkingMessageBubble,
          ]}
        >
          <View style={styles.messageHeader}>
            <Text style={styles.messageIcon}>
              {isUser ? "ðŸ‘¤" : isThinking ? "ðŸ¤”" : "ðŸ¤–"}
            </Text>
            {isThinking && (
              <ActivityIndicator
                size="small"
                color={colors.text.secondary}
                style={styles.thinkingSpinner}
              />
            )}
          </View>
          <Text
            style={[
              styles.messageText,
              isUser ? styles.userMessageText : styles.assistantMessageText,
            ]}
          >
            {message.content}
          </Text>

          {/* Show entries if present */}
          {message.entries && message.entries.length > 0 && (
            <View style={styles.entriesContainer}>
              {message.entries.map((entry, index) => {
                const isFullEntry =
                  entry &&
                  typeof entry === "object" &&
                  "id" in entry &&
                  "direction" in entry;

                if (!isFullEntry) {
                  return null;
                }

                return (
                  <View
                    key={entry.id || `entry-${index}`}
                    style={styles.entryCard}
                  >
                    <View style={styles.entryHeader}>
                      <Text
                        style={[
                          styles.entryAmount,
                          entry.direction === "expense"
                            ? styles.expenseAmount
                            : styles.incomeAmount,
                        ]}
                      >
                        {formatAmount(entry.amount, entry.direction)}
                      </Text>
                      <Text style={styles.entryDate}>
                        {formatDate(entry.entry_date)}
                      </Text>
                    </View>
                    {entry.description && (
                      <Text style={styles.entryDescription}>
                        {entry.description}
                      </Text>
                    )}
                    {entry.category && entry.category.name && (
                      <Text style={styles.entryCategory}>
                        ðŸ“ {entry.category.name}
                      </Text>
                    )}
                  </View>
                );
              })}
            </View>
          )}
        </View>
      </View>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyEmoji}>ðŸ’¬</Text>
      <Text style={styles.emptyTitle}>Start a conversation</Text>
      <Text style={styles.emptySubtitle}>Try these examples:</Text>
      <View style={styles.examplesContainer}>
        {examplePrompts.map((prompt, index) => (
          <TouchableOpacity
            key={index}
            style={styles.exampleButton}
            onPress={() => setInput(prompt)}
          >
            <Text style={styles.exampleIcon}>ðŸ’¡</Text>
            <Text style={styles.exampleText}>{prompt}</Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.headerIcon}>ðŸ¤–</Text>
          <Text style={styles.headerTitle}>AI Assistant</Text>
        </View>
        {messages.length > 0 && (
          <TouchableOpacity
            style={styles.resetButton}
            onPress={clearConversation}
          >
            <Text style={styles.resetButtonText}>ðŸ”„ Reset</Text>
          </TouchableOpacity>
        )}
      </View>

      <FlatList
        data={messages}
        renderItem={renderMessage}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={renderEmpty}
        contentContainerStyle={styles.messagesContainer}
        showsVerticalScrollIndicator={false}
      />

      {/* Error Display */}
      {error && (
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>âš ï¸</Text>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={() => setError(null)}>
            <Text style={styles.errorClose}>âœ•</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Input */}
      <View style={styles.inputContainer}>
        <View style={styles.inputRow}>
          <TextInput
            style={styles.textInput}
            value={input}
            onChangeText={setInput}
            placeholder="Ask about your finances..."
            placeholderTextColor={colors.text.muted}
            editable={!isLoading && !isTranscribing}
            multiline
          />
          {(isLoading || isTranscribing) && (
            <ActivityIndicator
              size="small"
              color={colors.accent.blue}
              style={styles.inputSpinner}
            />
          )}
        </View>

        <View style={styles.buttonRow}>
          <TouchableOpacity
            style={[
              styles.voiceButton,
              isRecording && styles.voiceButtonRecording,
              (isLoading || isTranscribing) && styles.voiceButtonDisabled,
            ]}
            onPress={isRecording ? stopRecording : startRecording}
            disabled={isLoading || isTranscribing}
          >
            <Text style={styles.voiceButtonText}>
              {isRecording ? "ðŸŽ¤" : "ðŸŽ¤"}
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.sendButton,
              (!input.trim() || isLoading || isTranscribing) &&
                styles.sendButtonDisabled,
            ]}
            onPress={handleSend}
            disabled={!input.trim() || isLoading || isTranscribing}
          >
            <Text style={styles.sendButtonText}>
              {isLoading ? "..." : "Send"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background.card,
    borderRadius: borderRadius.xl,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.primary,
  },
  headerLeft: {
    flexDirection: "row",
    alignItems: "center",
  },
  headerIcon: {
    fontSize: 20,
    marginRight: spacing.sm,
  },
  headerTitle: {
    fontSize: typography["2xl"].fontSize,
    fontWeight: "bold",
    color: colors.text.primary,
  },
  resetButton: {
    backgroundColor: colors.background.tertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  resetButtonText: {
    color: colors.text.secondary,
    fontSize: typography.sm.fontSize,
  },
  messagesContainer: {
    flexGrow: 1,
    padding: spacing.md,
  },
  messageContainer: {
    marginBottom: spacing.md,
  },
  userMessageContainer: {
    alignItems: "flex-end",
  },
  messageBubble: {
    maxWidth: "80%",
    padding: spacing.md,
    borderRadius: borderRadius.lg,
  },
  userMessageBubble: {
    backgroundColor: colors.accent.blue,
  },
  assistantMessageBubble: {
    backgroundColor: colors.background.tertiary,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  thinkingMessageBubble: {
    backgroundColor: colors.background.secondary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
  },
  messageHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  messageIcon: {
    fontSize: 16,
    marginRight: spacing.sm,
  },
  thinkingSpinner: {
    marginLeft: spacing.sm,
  },
  messageText: {
    fontSize: typography.sm.fontSize,
  },
  userMessageText: {
    color: colors.text.primary,
  },
  assistantMessageText: {
    color: colors.text.primary,
  },
  entriesContainer: {
    marginTop: spacing.md,
  },
  entryCard: {
    backgroundColor: colors.background.secondary,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  entryHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  entryAmount: {
    fontSize: typography.lg.fontSize,
    fontWeight: "bold",
  },
  expenseAmount: {
    color: colors.accent.red,
  },
  incomeAmount: {
    color: colors.accent.green,
  },
  entryDate: {
    fontSize: typography.xs.fontSize,
    color: colors.text.tertiary,
  },
  entryDescription: {
    fontSize: typography.sm.fontSize,
    color: colors.text.secondary,
    marginBottom: spacing.xs,
  },
  entryCategory: {
    fontSize: typography.xs.fontSize,
    color: colors.text.tertiary,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyEmoji: {
    fontSize: 48,
    marginBottom: spacing.md,
  },
  emptyTitle: {
    fontSize: typography.lg.fontSize,
    fontWeight: "500",
    color: colors.text.tertiary,
    marginBottom: spacing.sm,
  },
  emptySubtitle: {
    fontSize: typography.sm.fontSize,
    color: colors.text.muted,
    marginBottom: spacing.md,
  },
  examplesContainer: {
    width: "100%",
  },
  exampleButton: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.background.tertiary,
    padding: spacing.md,
    borderRadius: borderRadius.lg,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  exampleIcon: {
    fontSize: 16,
    color: colors.accent.blue,
    marginRight: spacing.sm,
  },
  exampleText: {
    color: colors.text.secondary,
    fontSize: typography.sm.fontSize,
    flex: 1,
  },
  errorContainer: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.accent.red + "20",
    borderWidth: 1,
    borderColor: colors.accent.red + "50",
    padding: spacing.md,
    margin: spacing.md,
    borderRadius: borderRadius.lg,
  },
  errorIcon: {
    fontSize: 16,
    color: colors.accent.red,
    marginRight: spacing.sm,
  },
  errorText: {
    color: colors.accent.red,
    fontSize: typography.sm.fontSize,
    flex: 1,
  },
  errorClose: {
    color: colors.accent.red,
    fontSize: typography.sm.fontSize,
    fontWeight: "bold",
  },
  inputContainer: {
    padding: spacing.md,
    borderTopWidth: 1,
    borderTopColor: colors.border.primary,
  },
  inputRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  textInput: {
    flex: 1,
    backgroundColor: colors.background.tertiary,
    borderWidth: 1,
    borderColor: colors.border.secondary,
    borderRadius: borderRadius.lg,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: typography.base.fontSize,
    color: colors.text.primary,
    maxHeight: 100,
  },
  inputSpinner: {
    position: "absolute",
    right: spacing.md,
  },
  buttonRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  voiceButton: {
    backgroundColor: colors.background.tertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    justifyContent: "center",
    minWidth: 50,
  },
  voiceButtonRecording: {
    backgroundColor: colors.accent.red,
  },
  voiceButtonDisabled: {
    opacity: 0.5,
  },
  voiceButtonText: {
    fontSize: 20,
  },
  sendButton: {
    backgroundColor: colors.accent.blue,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.lg,
    alignItems: "center",
    justifyContent: "center",
    flex: 1,
  },
  sendButtonDisabled: {
    backgroundColor: colors.background.tertiary,
    opacity: 0.5,
  },
  sendButtonText: {
    color: colors.text.primary,
    fontSize: typography.base.fontSize,
    fontWeight: "500",
  },
});
