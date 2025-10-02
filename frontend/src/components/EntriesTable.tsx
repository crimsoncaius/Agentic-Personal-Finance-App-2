import { useEffect, useState } from "react";
import { EntryResponse } from "../types/api";
import { apiService } from "../services/api";

export default function EntriesTable() {
  const [entries, setEntries] = useState<EntryResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchEntries = async () => {
      try {
        setLoading(true);
        const response = await apiService.getEntries();
        setEntries(response.items);
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch entries"
        );
      } finally {
        setLoading(false);
      }
    };

    fetchEntries();
  }, []);

  const formatAmount = (amount: number, direction: string) => {
    const sign = direction === "expense" ? "-" : "+";
    return `${sign}$${amount.toFixed(2)}`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-white">Loading entries...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-red-400">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 rounded-lg p-6">
      <h2 className="text-xl font-bold text-white mb-4">Recent Entries</h2>

      {entries.length === 0 ? (
        <div className="text-gray-400 text-center py-8">No entries found</div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-300 py-2">Amount</th>
                <th className="text-left text-gray-300 py-2">Date</th>
                <th className="text-left text-gray-300 py-2">Category</th>
                <th className="text-left text-gray-300 py-2">Description</th>
                <th className="text-left text-gray-300 py-2">Source</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id} className="border-b border-gray-800">
                  <td className="py-3">
                    <span
                      className={`font-medium ${
                        entry.direction === "expense"
                          ? "text-red-400"
                          : "text-green-400"
                      }`}
                    >
                      {formatAmount(entry.amount, entry.direction)}
                    </span>
                  </td>
                  <td className="text-gray-300 py-3">
                    {formatDate(entry.entry_date)}
                  </td>
                  <td className="text-gray-300 py-3">
                    {entry.category?.name || "-"}
                  </td>
                  <td className="text-gray-300 py-3">
                    {entry.description || "-"}
                  </td>
                  <td className="py-3">
                    <span
                      className={`px-2 py-1 rounded text-xs ${
                        entry.source === "nlp"
                          ? "bg-blue-900 text-blue-300"
                          : "bg-gray-700 text-gray-300"
                      }`}
                    >
                      {entry.source.toUpperCase()}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
