import { useEffect, useState } from "react";
import type { EntryResponse } from "../types/api";
import { apiService } from "../services/api";

interface EntriesTableProps {
  refreshTrigger?: number;
}

export default function EntriesTable({ refreshTrigger }: EntriesTableProps) {
  const [entries, setEntries] = useState<EntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [paginationLoading, setPaginationLoading] = useState(false);
  const [todayLoading, setTodayLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalEntries, setTotalEntries] = useState(0);
  const [todayPage, setTodayPage] = useState(1);
  const [hasInitialized, setHasInitialized] = useState(false);
  const [isTodayPage, setIsTodayPage] = useState(false);
  const entriesPerPage = 5;

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

        // Find today's page on first load only
        if (!hasInitialized && totalPagesCount > 0) {
          await findTodayPage();
          setHasInitialized(true);
        }

        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch entries"
        );
      } finally {
        setLoading(false);
      }
    };

    // Only fetch on initial load
    if (!hasInitialized) {
      fetchEntries();
    }
  }, [hasInitialized, entriesPerPage]);

  // Jump to today's page when it's found (only on initial load)
  useEffect(() => {
    if (todayPage !== 1 && currentPage === 1 && !hasInitialized) {
      setCurrentPage(todayPage);
    }
  }, [todayPage, currentPage, hasInitialized]);

  const refreshEntries = async () => {
    try {
      setLoading(true);
      const offset = (currentPage - 1) * entriesPerPage;
      const response = await apiService.getEntries(entriesPerPage, offset);
      setEntries(response.items);
      setTotalEntries(response.page.total);
      const totalPagesCount = Math.ceil(response.page.total / entriesPerPage);
      setTotalPages(totalPagesCount);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch entries");
    } finally {
      setLoading(false);
    }
  };

  const fetchPageEntries = async (page: number) => {
    try {
      setPaginationLoading(true);
      const offset = (page - 1) * entriesPerPage;
      const response = await apiService.getEntries(entriesPerPage, offset);
      setEntries(response.items);
      setError(null);

      // Check if current page contains today's entries
      checkIfTodayPage(response.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch entries");
    } finally {
      setPaginationLoading(false);
    }
  };

  const checkIfTodayPage = (entries: EntryResponse[]) => {
    // Use local date instead of UTC to match user's timezone
    const today = new Date();
    const todayLocal = `${today.getFullYear()}-${String(
      today.getMonth() + 1
    ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    const hasTodayEntry = entries.some((entry) =>
      entry.entry_date.startsWith(todayLocal)
    );
    setIsTodayPage(hasTodayEntry);
  };

  // Refresh entries when refreshTrigger changes
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0) {
      refreshEntries();
    }
  }, [refreshTrigger]);

  const formatAmount = (amount: number | string, direction: string) => {
    const numAmount = typeof amount === "string" ? parseFloat(amount) : amount;
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

  const findTodayPage = async () => {
    try {
      // Use local date instead of UTC to match user's timezone
      const today = new Date();
      const todayLocal = `${today.getFullYear()}-${String(
        today.getMonth() + 1
      ).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
      let page = 1;
      let found = false;

      console.log("Searching for today's entries:", todayLocal);

      // Search through pages to find today's entries
      while (page <= totalPages && !found) {
        const offset = (page - 1) * entriesPerPage;
        const response = await apiService.getEntries(entriesPerPage, offset);

        console.log(
          `Checking page ${page}:`,
          response.items.map((e) => e.entry_date)
        );

        // Check if any entry is from today
        const hasTodayEntry = response.items.some((entry) =>
          entry.entry_date.startsWith(todayLocal)
        );

        if (hasTodayEntry) {
          found = true;
          setTodayPage(page);
          console.log(`Found today's entries on page ${page}`);
        } else {
          page++;
        }
      }

      // If no today entries found, set to page 1 (closest date)
      if (!found) {
        console.log("No today entries found, defaulting to page 1");
        setTodayPage(1);
      }
    } catch (error) {
      console.error("Error finding today page:", error);
      setTodayPage(1);
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-gray-700/50 p-8 flex items-center justify-center h-64">
        <div className="flex items-center space-x-3">
          <div className="animate-spin rounded-full h-6 w-6 border-2 border-blue-500 border-t-transparent"></div>
          <div className="text-gray-300 font-medium">Loading entries...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-red-500/50 p-8 flex items-center justify-center h-64">
        <div className="text-center">
          <div className="text-red-400 text-lg font-medium mb-2">⚠️ Error</div>
          <div className="text-gray-300">{error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/50 backdrop-blur-sm rounded-2xl border border-gray-700/50 shadow-xl flex flex-col">
      <div className="p-6 border-b border-gray-700/50">
        <div className="flex items-center justify-between">
          <h2 className="text-2xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
            Recent Entries
          </h2>
          <div className="text-sm text-gray-400">
            {totalEntries} {totalEntries === 1 ? "entry" : "entries"} total
          </div>
        </div>
        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div
                className={`text-sm ${
                  isTodayPage ? "text-blue-300" : "text-gray-400"
                }`}
              >
                {isTodayPage && <span className="text-blue-400 mr-2">📅</span>}
                Page {currentPage} of {totalPages}
                {isTodayPage && (
                  <span className="ml-2 text-blue-400 font-medium">
                    (Today)
                  </span>
                )}
                {paginationLoading && (
                  <span className="ml-2 text-gray-400">
                    <div className="inline-block animate-spin rounded-full h-3 w-3 border border-gray-400 border-t-transparent mr-1"></div>
                    Loading...
                  </span>
                )}
              </div>
              <button
                onClick={async () => {
                  try {
                    setTodayLoading(true);
                    // Use local date instead of UTC to match user's timezone
                    const today = new Date();
                    const todayLocal = `${today.getFullYear()}-${String(
                      today.getMonth() + 1
                    ).padStart(2, "0")}-${String(today.getDate()).padStart(
                      2,
                      "0"
                    )}`;
                    let page = 1;
                    let found = false;

                    // Search through pages to find today's entries
                    while (page <= totalPages && !found) {
                      const offset = (page - 1) * entriesPerPage;
                      const response = await apiService.getEntries(
                        entriesPerPage,
                        offset
                      );

                      // Check if any entry is from today
                      const hasTodayEntry = response.items.some((entry) =>
                        entry.entry_date.startsWith(todayLocal)
                      );

                      if (hasTodayEntry) {
                        found = true;
                        setCurrentPage(page);
                        await fetchPageEntries(page);
                      } else {
                        page++;
                      }
                    }

                    // If no today entries found, go to page 1
                    if (!found) {
                      setCurrentPage(1);
                      await fetchPageEntries(1);
                    }
                  } catch (error) {
                    console.error("Error finding today page:", error);
                    setCurrentPage(1);
                    await fetchPageEntries(1);
                  } finally {
                    setTodayLoading(false);
                  }
                }}
                disabled={todayLoading}
                className={`w-20 px-3 py-1.5 text-sm rounded-lg transition-all duration-200 flex items-center justify-center space-x-1 ${
                  isTodayPage
                    ? "bg-blue-500 hover:bg-blue-600 text-white shadow-lg shadow-blue-500/25"
                    : "bg-blue-600 hover:bg-blue-700 text-white"
                } ${todayLoading ? "opacity-75 cursor-not-allowed" : ""}`}
                title={
                  isTodayPage
                    ? "Currently viewing today's entries"
                    : "Jump to today's entries"
                }
              >
                <span>📅</span>
                <span>Today</span>
                {todayLoading && (
                  <div className="animate-spin rounded-full h-3 w-3 border border-white border-t-transparent ml-1"></div>
                )}
              </button>
            </div>
            <div className="flex space-x-2">
              <button
                onClick={async () => {
                  const newPage = Math.max(1, currentPage - 1);
                  setCurrentPage(newPage);
                  await fetchPageEntries(newPage);
                }}
                disabled={currentPage === 1 || paginationLoading}
                className="w-20 px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Previous
              </button>
              <button
                onClick={async () => {
                  const newPage = Math.min(totalPages, currentPage + 1);
                  setCurrentPage(newPage);
                  await fetchPageEntries(newPage);
                }}
                disabled={currentPage === totalPages || paginationLoading}
                className="w-20 px-3 py-1.5 text-sm bg-gray-700 hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-hidden">
        {entries.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="text-6xl mb-4">💰</div>
              <div className="text-gray-400 text-lg font-medium">
                No entries found
              </div>
              <div className="text-gray-500 text-sm mt-2">
                Start by adding some transactions!
              </div>
            </div>
          </div>
        ) : (
          <div className="scrollbar-thin">
            <div className="p-6 space-y-3">
              {entries.map((entry) => {
                // Use local date instead of UTC to match user's timezone
                const today = new Date();
                const todayLocal = `${today.getFullYear()}-${String(
                  today.getMonth() + 1
                ).padStart(2, "0")}-${String(today.getDate()).padStart(
                  2,
                  "0"
                )}`;
                const isTodayEntry = entry.entry_date.startsWith(todayLocal);
                return (
                  <div
                    key={entry.id}
                    className={`rounded-xl p-4 border transition-all duration-200 group ${
                      isTodayEntry
                        ? "bg-blue-900/20 border-blue-500/30 hover:border-blue-400/50 hover:bg-blue-900/30"
                        : "bg-gray-800/50 border-gray-700/30 hover:border-gray-600/50 hover:bg-gray-800/70"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-4">
                        <div
                          className={`w-12 h-12 rounded-full flex items-center justify-center ${
                            entry.direction === "expense"
                              ? "bg-red-500/20 text-red-400"
                              : "bg-green-500/20 text-green-400"
                          }`}
                        >
                          <span className="text-lg font-bold">
                            {entry.direction === "expense" ? "−" : "+"}
                          </span>
                        </div>
                        <div>
                          <div className="flex items-center space-x-2">
                            <span
                              className={`text-xl font-bold ${
                                entry.direction === "expense"
                                  ? "text-red-400"
                                  : "text-green-400"
                              }`}
                            >
                              {formatAmount(entry.amount, entry.direction)}
                            </span>
                          </div>
                          <div className="text-gray-300 text-sm mt-1">
                            {entry.description || "No description"}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-gray-400 text-sm">
                          {formatDate(entry.entry_date)}
                        </div>
                        {entry.category && (
                          <div className="text-gray-500 text-xs mt-1">
                            {entry.category.name}
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
