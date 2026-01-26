import { useState, useEffect } from 'react';
import { healthCheck } from './services/api';

function App() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await healthCheck();
        setHealth(response.data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    checkHealth();
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-2xl w-full">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-gray-900 mb-2">
            🎯 Smart Mapping Platform
          </h1>
          <p className="text-gray-600">
            AI-Powered Data Transformation
          </p>
        </div>

        <div className="space-y-4">
          {loading && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
              <p className="mt-4 text-gray-600">Checking backend connection...</p>
            </div>
          )}

          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-red-800 font-semibold">❌ Error</p>
              <p className="text-red-600 text-sm mt-1">{error}</p>
            </div>
          )}

          {health && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-6">
              <p className="text-green-800 font-semibold text-lg mb-4">
                ✅ Backend Connected Successfully!
              </p>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Status:</span>
                  <span className="font-semibold text-green-600">
                    {health.status}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Environment:</span>
                  <span className="font-semibold">
                    {health.environment}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Database:</span>
                  <span className={`font-semibold ${
                    health.database === 'connected' 
                      ? 'text-green-600' 
                      : 'text-yellow-600'
                  }`}>
                    {health.database}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">OpenAI:</span>
                  <span className={`font-semibold ${
                    health.openai === 'configured' 
                      ? 'text-green-600' 
                      : 'text-yellow-600'
                  }`}>
                    {health.openai}
                  </span>
                </div>
              </div>
            </div>
          )}

          <div className="mt-8 p-4 bg-blue-50 rounded-lg">
            <h2 className="font-semibold text-blue-900 mb-2">
              🚀 Sprint 1-2 Setup Complete!
            </h2>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>✅ Docker infrastructure configured</li>
              <li>✅ Backend (FastAPI) ready</li>
              <li>✅ Frontend (React + Vite) ready</li>
              <li>✅ PostgreSQL database ready</li>
              <li>⚠️  OpenAI API (add key later)</li>
            </ul>
          </div>

          <div className="text-center pt-4">
            <p className="text-gray-500 text-sm">
              Next: Sprint 3-4 - Authentication System
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;