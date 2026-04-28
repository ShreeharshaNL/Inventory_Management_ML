// src/frontend/src/api.js
// Centralized API calls to FastAPI backend

const BASE_URL = "http://localhost:8000";

async function request(path, token, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  login: async (username, password) => {
    const form = new URLSearchParams({ username, password });
    const res = await fetch(`${BASE_URL}/api/auth/login`, {
      method: "POST",
      body: form,
    });
    if (!res.ok) throw new Error("Invalid credentials");
    return res.json();
  },

  getProducts:  (token)            => request("/api/products", token),
  getForecast:  (token, id, days=30) => request(`/api/forecast/${id}?days=${days}`, token),
  getAlerts:    (token)            => request("/api/inventory/alerts", token),
  getTrends:    (token, days=60)   => request(`/api/analytics/trends?days=${days}`, token),
  getKPIs:      (token)            => request("/api/analytics/kpis", token),

  updateStock: (token, productId, newStock) =>
    request("/api/inventory/update", token, {
      method: "POST",
      body: JSON.stringify({ product_id: productId, new_stock: newStock }),
    }),
};