import { useState } from "react";
import { useAuth } from "./contexts/AuthContext";
import EntriesTable from "./components/EntriesTable";
import ChatInterface from "./components/ChatInterface";
import LoginForm from "./components/LoginForm";
import RegisterForm from "./components/RegisterForm";
import ProtectedRoute from "./components/ProtectedRoute";

function App() {
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [showRegister, setShowRegister] = useState(false);
  const { user, logout } = useAuth();

  const handleEntryCreated = () => {
    setRefreshTrigger((prev) => prev + 1);
  };

  const authFallback = showRegister ? (
    <RegisterForm onSwitchToLogin={() => setShowRegister(false)} />
  ) : (
    <LoginForm onSwitchToRegister={() => setShowRegister(true)} />
  );

  return (
    <ProtectedRoute fallback={authFallback}>
      <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-800 to-black">
        {/* Header */}
        <div className="bg-gray-900/80 backdrop-blur-sm border-b border-gray-700/50 shadow-lg">
          <div className="max-w-7xl mx-auto px-6 py-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
                  <span className="text-white font-bold text-lg">$</span>
                </div>
                <h1 className="text-3xl font-bold text-white">
                  Personal Finance App
                </h1>
              </div>
              <div className="flex items-center space-x-4">
                <div className="text-sm text-gray-400">
                  Welcome,{" "}
                  <span className="text-white font-medium">
                    {user?.name || user?.email}
                  </span>
                </div>
                <button
                  onClick={logout}
                  className="px-4 py-2 bg-gray-700/50 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition text-sm font-medium border border-gray-600/50"
                >
                  Sign Out
                </button>
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
    </ProtectedRoute>
  );
}

export default App;
