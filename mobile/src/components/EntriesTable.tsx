import React, { useEffect, useState } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  ActivityIndicator,
} from "react-native";
import type { EntryResponse } from "../../../shared/src/types/api";
import { formatAmount, formatDate } from "../../../shared/src/utils/formatters";
import { MobileStorage } from "../../../shared/src/services/storage";
import { ApiService } from "../../../shared/src/services/api";
import { API_BASE_URL } from "../config/api";
import { colors, spacing, borderRadius, typography } from "../styles/theme";
import * as SecureStore from "expo-secure-store";

interface EntriesTableProps {
  refreshTrigger?: number;
}

export default function EntriesTable({ refreshTrigger }: EntriesTableProps) {
  const [entries, setEntries] = useState<EntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEntries, setTotalEntries] = useState(0);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [isTodayPage, setIsTodayPage] = useState(false);
  const entriesPerPage = 10;

  // Create API service
  const storage = new MobileStorage(SecureStore);
  const apiService = new ApiService({
    baseUrl: API_BASE_URL,
    storage,
  });

  useEffect(() => {
    const fetchEntries = async () => {
      try {
        setLoading(true);
        const offset = (currentPage - 1) * entriesPerPage;
        const response = await apiService.getEntries(entriesPerPage, offset);
        setEntries(response.items);
        setTotalEntries(response.page.total);
        const totalPagesCount = Math.ceil(response.page.total / entriesPerPage);
        setTotalPages(totalPagesCount);

        // Check if current page contains today's entries
        checkIfTodayPage(response.items);

        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch entries"
        );
      } finally {
        setLoading(false);
      }
    };

    if (!hasInitialized) {
      fetchEntries();
      setHasInitialized(true);
    }
  }, [hasInitialized, currentPage]);

  // Refresh entries when refreshTrigger changes
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      onRefresh();
    }
  }, [refreshTrigger]);

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      const offset = (currentPage - 1) * entriesPerPage;
      const response = await apiService.getEntries(entriesPerPage, offset);
      setEntries(response.items);
      setTotalEntries(response.page.total);
      const totalPagesCount = Math.ceil(response.page.total / entriesPerPage);
      setTotalPages(totalPagesCount);
      checkIfTodayPage(response.items);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch entries");
    } finally {
      setRefreshing(false);
    }
  };

  const checkIfTodayPage = (entries: EntryResponse[]) => {
    const today = new Date();
    const todayLocal = `${today.getFullYear()}-${String(
      today.getMonth() + 1
    ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    const hasTodayEntry = entries.some((entry) =>
      entry.entry_date.startsWith(todayLocal)
    );
    setIsTodayPage(hasTodayEntry);
  };

  const goToToday = async () => {
    try {
      setLoading(true);
      const today = new Date();
      const todayLocal = `${today.getFullYear()}-${String(
        today.getMonth() + 1
      ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      let page = 1;
      let found = false;

      // Search through pages to find today's entries
      while (page <= totalPages && !found) {
        const offset = (page - 1) * entriesPerPage;
        const response = await apiService.getEntries(entriesPerPage, offset);

        const hasTodayEntry = response.items.some((entry) =>
          entry.entry_date.startsWith(todayLocal)
        );

        if (hasTodayEntry) {
          found = true;
          setCurrentPage(page);
          setEntries(response.items);
          checkIfTodayPage(response.items);
        } else {
          page++;
        }
      }

      // If no today entries found, go to page 1
      if (!found) {
        setCurrentPage(1);
        const response = await apiService.getEntries(entriesPerPage, 0);
        setEntries(response.items);
        checkIfTodayPage(response.items);
      }
    } catch (error) {
      console.error("Error finding today page:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderEntry = ({ item: entry }: { item: EntryResponse }) => {
    const today = new Date();
    const todayLocal = `${today.getFullYear()}-${String(
      today.getMonth() + 1
    ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    const isTodayEntry = entry.entry_date.startsWith(todayLocal);

    return (
      <View style={[styles.entryCard, isTodayEntry && styles.todayEntryCard]}>
        <View style={styles.entryContent}>
          <View style={styles.entryLeft}>
            <View
              style={[
                styles.entryIcon,
                entry.direction === "expense"
                  ? styles.expenseIcon
                  : styles.incomeIcon,
              ]}
            >
              <Text style={styles.entryIconText}>
                {entry.direction === "expense" ? "âˆ’" : "+"}
              </Text>
            </View>
            <View style={styles.entryDetails}>
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
              <Text style={styles.entryDescription}>
                {entry.description || "No description"}
              </Text>
            </View>
          </View>
          <View style={styles.entryRight}>
            <Text style={styles.entryDate}>{formatDate(entry.entry_date)}</Text>
            {entry.category && (
              <Text style={styles.entryCategory}>{entry.category.name}</Text>
            )}
          </View>
        </View>
      </View>
    );
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyEmoji}>ðŸ’°</Text>
      <Text style={styles.emptyTitle}>No entries found</Text>
      <Text style={styles.emptySubtitle}>
        Start by adding some transactions!
      </Text>
    </View>
  );

  if (loading && !refreshing) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color={colors.accent.blue} />
        <Text style={styles.loadingText}>Loading entries...</Text>
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorEmoji}>âš ï¸</Text>
        <Text style={styles.errorTitle}>Error</Text>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <Text style={styles.title}>Recent Entries</Text>
          <Text style={styles.count}>
            {totalEntries} {totalEntries === 1 ? "entry" : "entries"} total
          </Text>
        </View>
        {totalPages > 1 && (
          <View style={styles.pagination}>
            <View style={styles.paginationLeft}>
              <Text
                style={[styles.pageInfo, isTodayPage && styles.todayPageInfo]}
              >
                {isTodayPage && <Text style={styles.todayIcon}>ðŸ“… </Text>}
                Page {currentPage} of {totalPages}
                {isTodayPage && <Text style={styles.todayText}> (Today)</Text>}
              </Text>
              <TouchableOpacity
                style={[
                  styles.todayButton,
                  isTodayPage && styles.todayButtonActive,
                ]}
                onPress={goToToday}
                disabled={loading}
              >
                <Text style={styles.todayButtonText}>ðŸ“… Today</Text>
              </TouchableOpacity>
            </View>
            <View style={styles.paginationRight}>
              <TouchableOpacity
                style={[
                  styles.pageButton,
                  currentPage === 1 && styles.pageButtonDisabled,
                ]}
                onPress={() => setCurrentPage(Math.max(1, currentPage - 1))}
                disabled={currentPage === 1 || loading}
              >
                <Text
                  style={[
                    styles.pageButtonText,
                    currentPage === 1 && styles.pageButtonTextDisabled,
                  ]}
                >
                  Previous
                </Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.pageButton,
                  currentPage === totalPages && styles.pageButtonDisabled,
                ]}
                onPress={() =>
                  setCurrentPage(Math.min(totalPages, currentPage + 1))
                }
                disabled={currentPage === totalPages || loading}
              >
                <Text
                  style={[
                    styles.pageButtonText,
                    currentPage === totalPages && styles.pageButtonTextDisabled,
                  ]}
                >
                  Next
                </Text>
              </TouchableOpacity>
            </View>
          </View>
        )}
      </View>

      <FlatList
        data={entries}
        renderItem={renderEntry}
        keyExtractor={(item) => item.id}
        ListEmptyComponent={renderEmpty}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor={colors.accent.blue}
          />
        }
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
      />
    </View>
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
    padding: spacing.lg,
    borderBottomWidth: 1,
    borderBottomColor: colors.border.primary,
  },
  headerTop: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  title: {
    fontSize: typography["2xl"].fontSize,
    fontWeight: "bold",
    color: colors.text.primary,
  },
  count: {
    fontSize: typography.sm.fontSize,
    color: colors.text.tertiary,
  },
  pagination: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  paginationLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  pageInfo: {
    fontSize: typography.sm.fontSize,
    color: colors.text.tertiary,
    marginRight: spacing.md,
  },
  todayPageInfo: {
    color: colors.accent.blue,
  },
  todayIcon: {
    color: colors.accent.blue,
  },
  todayText: {
    color: colors.accent.blue,
    fontWeight: "500",
  },
  todayButton: {
    backgroundColor: colors.accent.blue,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  todayButtonActive: {
    backgroundColor: colors.accent.blueDark,
  },
  todayButtonText: {
    color: colors.text.primary,
    fontSize: typography.sm.fontSize,
    fontWeight: "500",
  },
  paginationRight: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  pageButton: {
    backgroundColor: colors.background.tertiary,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    minWidth: 80,
    alignItems: "center",
  },
  pageButtonDisabled: {
    backgroundColor: colors.background.secondary,
    opacity: 0.5,
  },
  pageButtonText: {
    color: colors.text.secondary,
    fontSize: typography.sm.fontSize,
  },
  pageButtonTextDisabled: {
    color: colors.text.muted,
  },
  listContent: {
    flexGrow: 1,
    padding: spacing.lg,
  },
  entryCard: {
    backgroundColor: colors.background.tertiary,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  todayEntryCard: {
    backgroundColor: colors.accent.blue + "20",
    borderColor: colors.accent.blue + "50",
  },
  entryContent: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  entryLeft: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
  },
  entryIcon: {
    width: 48,
    height: 48,
    borderRadius: 24,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  expenseIcon: {
    backgroundColor: colors.accent.red + "20",
  },
  incomeIcon: {
    backgroundColor: colors.accent.green + "20",
  },
  entryIconText: {
    fontSize: typography.lg.fontSize,
    fontWeight: "bold",
    color: colors.text.primary,
  },
  entryDetails: {
    flex: 1,
  },
  entryAmount: {
    fontSize: typography.xl.fontSize,
    fontWeight: "bold",
  },
  expenseAmount: {
    color: colors.accent.red,
  },
  incomeAmount: {
    color: colors.accent.green,
  },
  entryDescription: {
    fontSize: typography.sm.fontSize,
    color: colors.text.secondary,
    marginTop: spacing.xs,
  },
  entryRight: {
    alignItems: "flex-end",
  },
  entryDate: {
    fontSize: typography.sm.fontSize,
    color: colors.text.tertiary,
  },
  entryCategory: {
    fontSize: typography.xs.fontSize,
    color: colors.text.muted,
    marginTop: spacing.xs,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyEmoji: {
    fontSize: 64,
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
  },
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background.card,
    borderRadius: borderRadius.xl,
    borderWidth: 1,
    borderColor: colors.border.primary,
  },
  loadingText: {
    fontSize: typography.base.fontSize,
    color: colors.text.secondary,
    marginTop: spacing.md,
  },
  errorContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.background.card,
    borderRadius: borderRadius.xl,
    borderWidth: 1,
    borderColor: colors.accent.red + "50",
    padding: spacing.lg,
  },
  errorEmoji: {
    fontSize: 24,
    marginBottom: spacing.sm,
  },
  errorTitle: {
    fontSize: typography.lg.fontSize,
    fontWeight: "500",
    color: colors.accent.red,
    marginBottom: spacing.sm,
  },
  errorText: {
    fontSize: typography.base.fontSize,
    color: colors.text.secondary,
    textAlign: "center",
  },
});
