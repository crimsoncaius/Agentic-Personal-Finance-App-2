import { useState } from "react";
import EntriesTable from "./components/EntriesTable";
import ChatInterface from "./components/ChatInterface";

function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);

  const handleEntryCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black">
      {/* Header */}
      <div className="bg-gray-900/80 backdrop-blur-sm border-b border-gray-700/50 shadow-lg">
        <div className="max-w-7xl mx-auto px-6 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-lg">$</span>
              </div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
                Personal Finance App
              </h1>
            </div>
            <div className="text-sm text-gray-400">
              AI-Powered Financial Management
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Left Side - Entries Table */}
          <div className="flex flex-col">
            <EntriesTable refreshTrigger={refreshTrigger} />
          </div>

          {/* Right Side - Chat Interface */}
          <div className="flex flex-col">
            <ChatInterface onEntryCreated={handleEntryCreated} />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
