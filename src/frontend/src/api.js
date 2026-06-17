// src/frontend/src/api.js
// Centralized API calls to FastAPI backend

const DEFAULT_API_URL = "https://inventory-api-uyqy.onrender.com";
const configuredApiUrl = import.meta.env.VITE_API_URL;
const BASE_URL = configuredApiUrl && configuredApiUrl !== "https://inventory-api.onrender.com"
  ? configuredApiUrl
  : DEFAULT_API_URL;

console.info("Inventory API URL:", BASE_URL);

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
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: form,
    });
    if (!res.ok) {
      let detail = "";
      try {
        const data = await res.json();
        detail = data.detail ? `: ${data.detail}` : "";
      } catch {
        detail = `: ${await res.text()}`;
      }
      throw new Error(`Login failed (${res.status})${detail}`);
    }
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
