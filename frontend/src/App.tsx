import EntriesTable from "./components/EntriesTable";
import ChatInterface from "./components/ChatInterface";

function App() {
  return (
    <div className="min-h-screen bg-black">
      {/* Header */}
      <div className="bg-gray-900 border-b border-gray-800">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-white">
            Personal Finance App
          </h1>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 h-[calc(100vh-120px)]">
          {/* Left Side - Entries Table */}
          <div className="h-full">
            <EntriesTable />
          </div>

          {/* Right Side - Chat Interface */}
          <div className="h-full">
            <ChatInterface />
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
