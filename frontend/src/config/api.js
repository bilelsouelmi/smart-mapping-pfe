// src/config/api.js
// All API calls must use this base URL — never hardcode localhost:8000 directly.
// In development: VITE_API_URL=http://localhost:8000
// In Docker:      VITE_API_URL=http://backend:8000  (service name)

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export default API_BASE_URL;