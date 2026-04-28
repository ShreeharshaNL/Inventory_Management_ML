// src/frontend/src/components/Dashboard.jsx
import { useState, useEffect } from "react";
import {
  AreaChart, Area, BarChart, Bar,
  LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import { api } from "../api";

const ALERT_CONFIG = {
  critical: { color: "#ef4444", bg: "#fef2f2", label: "Critical", icon: "⚠️" },
  high:     { color: "#f97316", bg: "#fff7ed", label: "High",     icon: "↑"  },
  medium:   { color: "#eab308", bg: "#fefce8", label: "Medium",   icon: "→"  },
  low:      { color: "#22c55e", bg: "#f0fdf4", label: "Healthy",  icon: "✓"  },
};

const NAV_ITEMS = [
  { id: "overview", label: "Overview", icon: "▦" },
  { id: "forecast", label: "Forecast", icon: "∿" },
  { id: "alerts",   label: "Alerts",   icon: "◎" },
  { id: "products", label: "Products", icon: "≡" },
];

const CustomTooltip = ({ active, payload, label, prefix = "" }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <p className="tooltip-label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} style={{ color: p.color }} className="tooltip-data">
          {p.name}: {prefix}{typeof p.value === "number" ? p.value.toLocaleString() : p.value}
        </p>
      ))}
    </div>
  );
};

export default function Dashboard({ token, onLogout }) {
  const [kpis, setKpis] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [trends, setTrends] = useState([]);
  const [products, setProducts] = useState([]);
  const [forecast, setForecast] = useState([]);
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [updating, setUpdating] = useState(null);
  const [updateVal, setUpdateVal] = useState("");
  const [alertFilter, setAlertFilter] = useState("all");

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [k, a, t, p] = await Promise.all([
        api.getKPIs(token),
        api.getAlerts(token),
        api.getTrends(token, 60),
        api.getProducts(token),
      ]);
      setKpis(k);
      setAlerts(a);
      setTrends(t.slice(-30));
      setProducts(p);
      if (p.length > 0) { 
        setSelectedProduct(p[0].id); 
        loadForecast(p[0].id); 
      }
    } catch (e) { console.error(e); }
    finally { setLoading(false); }
  };

  const loadForecast = async (id) => {
    try {
      const data = await api.getForecast(token, id, 30);
      setForecast(data.map(d => ({
        date: d.forecast_date?.slice(5),
        demand: Math.round(d.predicted_demand),
        lower: Math.round(d.lower_bound || 0),
        upper: Math.round(d.upper_bound || 0),
      })));
    } catch { setForecast([]); }
  };

  const handleStockSave = async (productId) => {
    const val = parseInt(updateVal);
    if (isNaN(val) || val < 0) return;
    await api.updateStock(token, productId, val);
    setUpdating(null); 
    setUpdateVal(""); 
    loadAll();
  };

  const filteredAlerts = alertFilter === "all"
    ? alerts : alerts.filter(a => a.alert_level === alertFilter);

  const urgentCount = alerts.filter(a => ["critical","high"].includes(a.alert_level)).length;

  const handleNav = (tab) => {
    setActiveTab(tab);
    setSidebarOpen(false);
  };

  if (loading) return (
    <div className="loader-container">
      <div className="loader-spinner">
        <div className="spinner" />
        <p>Loading dashboard...</p>
      </div>
    </div>
  );

  return (
    <div className="dashboard-layout">
      {/* Mobile Overlay */}
      <div 
        className={`sidebar-overlay ${sidebarOpen ? 'open' : ''}`} 
        onClick={() => setSidebarOpen(false)} 
      />

      {/* Sidebar */}
      <aside className={`sidebar ${sidebarOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="logo-section">
            <div className="logo-icon">📦</div>
            <div>
              <p className="logo-title">Inventory AI</p>
              <p className="logo-subtitle">Forecasting System</p>
            </div>
          </div>
          <button className="close-mobile-btn" onClick={() => setSidebarOpen(false)}>✕</button>
        </div>

        <nav className="sidebar-nav">
          <p className="nav-heading">Menu</p>
          {NAV_ITEMS.map(item => (
            <button 
              key={item.id} 
              onClick={() => handleNav(item.id)} 
              className={`nav-btn ${activeTab === item.id ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              {item.label}
              {item.id === "alerts" && urgentCount > 0 && (
                <span className="alert-badge">{urgentCount}</span>
              )}
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="avatar">A</div>
            <div className="user-details">
              <p className="user-name">Admin</p>
              <p className="user-role">Administrator</p>
            </div>
          </div>
          <button onClick={onLogout} className="signout-btn">Sign out</button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="main-wrapper">
        <header className="top-header">
          <div className="header-left">
            <button className="menu-toggle-btn" onClick={() => setSidebarOpen(true)}>☰</button>
            <div>
              <h1 className="page-title">{NAV_ITEMS.find(n => n.id === activeTab)?.label}</h1>
              <p className="page-date">{new Date().toLocaleDateString("en-IN", { weekday:"long", year:"numeric", month:"long", day:"numeric" })}</p>
            </div>
          </div>
          <button onClick={loadAll} className="refresh-btn">
            ↻ <span className="refresh-text">Refresh</span>
          </button>
        </header>

        <main className="main-content">
          {/* ── OVERVIEW ── */}
          {activeTab === "overview" && (
            <div className="tab-content fade-in">
              <div className="kpi-grid">
                {[
                  { label:"Total Products",  value: kpis?.total_products,                      sub:"Active SKUs",        color:"#6366f1" },
                  { label:"Critical Alerts", value: kpis?.critical_alerts,                     sub:"Immediate action",   color:"#ef4444" },
                  { label:"High Risk",       value: kpis?.high_alerts,                         sub:"Below safety stock", color:"#f97316" },
                  { label:"Stock Units",     value: kpis?.total_stock_units?.toLocaleString(), sub:"All products",       color:"#22c55e" },
                ].map((kpi, i) => (
                  <div key={i} className="card kpi-card">
                    <p className="kpi-label">{kpi.label}</p>
                    <p className="kpi-value">{kpi.value ?? "—"}</p>
                    <p className="kpi-sub" style={{ color: kpi.color }}>{kpi.sub}</p>
                  </div>
                ))}
              </div>

              <div className="card chart-card">
                <p className="card-title">Revenue Trend</p>
                <p className="card-subtitle">Last 30 days</p>
                <div className="chart-wrapper">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={trends}>
                      <defs>
                        <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15}/>
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f9fafb" vertical={false} />
                      <XAxis dataKey="date" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} tickFormatter={d => d?.slice(5)} minTickGap={20}/>
                      <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} tickFormatter={v => `₹${(v/1000000).toFixed(1)}M`} width={60}/>
                      <Tooltip content={<CustomTooltip prefix="₹"/>}/>
                      <Area type="monotone" dataKey="total_revenue" stroke="#6366f1" strokeWidth={3} fill="url(#revGrad)" name="Revenue"/>
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="split-grid">
                <div className="card">
                  <p className="card-title">Stock Health</p>
                  <p className="card-subtitle">By alert level</p>
                  <div className="health-bars">
                    {Object.entries(ALERT_CONFIG).map(([level, cfg]) => {
                      const count = alerts.filter(a => a.alert_level === level).length;
                      const pct = alerts.length > 0 ? (count / alerts.length) * 100 : 0;
                      return (
                        <div key={level} className="health-bar-row">
                          <div className="health-bar-labels">
                            <span>{cfg.label}</span>
                            <span style={{ color: cfg.color }}>{count}</span>
                          </div>
                          <div className="progress-track">
                            <div className="progress-fill" style={{ width: `${pct}%`, background: cfg.color }}/>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                <div className="card">
                  <p className="card-title">Units Sold</p>
                  <p className="card-subtitle">Daily volume</p>
                  <div className="chart-wrapper">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={trends} barSize={6}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#f9fafb" vertical={false}/>
                        <XAxis dataKey="date" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} tickFormatter={d => d?.slice(5)} minTickGap={20}/>
                        <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} width={40}/>
                        <Tooltip content={<CustomTooltip/>}/>
                        <Bar dataKey="total_units" fill="#111827" radius={[4,4,0,0]} name="Units" animationDuration={1000}/>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ── FORECAST ── */}
          {activeTab === "forecast" && (
            <div className="tab-content fade-in">
              <div className="card">
                <p className="input-label">Select Product</p>
                <select
                  value={selectedProduct || ""}
                  onChange={e => { const id = Number(e.target.value); setSelectedProduct(id); loadForecast(id); }}
                  className="product-select"
                >
                  {products.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>

              {forecast.length > 0 ? (
                <>
                  <div className="card">
                    <p className="card-title">30-Day Demand Forecast</p>
                    <p className="card-subtitle">XGBoost predictions with 95% confidence interval</p>
                    <div className="chart-wrapper forecast-chart">
                      <ResponsiveContainer width="100%" height="100%">
                        <AreaChart data={forecast}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#f9fafb" vertical={false}/>
                          <XAxis dataKey="date" tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} minTickGap={20}/>
                          <YAxis tick={{ fontSize:11, fill:"#9ca3af" }} axisLine={false} tickLine={false} width={40}/>
                          <Tooltip content={<CustomTooltip/>}/>
                          <Area type="monotone" dataKey="upper" stroke="none" fill="#e0e7ff" name="Upper"/>
                          <Area type="monotone" dataKey="lower" stroke="none" fill="#fff" name="Lower"/>
                          <Line type="monotone" dataKey="demand" stroke="#6366f1" strokeWidth={3} dot={false} name="Predicted"/>
                        </AreaChart>
                      </ResponsiveContainer>
                    </div>
                  </div>

                  <div className="card no-padding">
                    <div className="table-header">
                      <p className="card-title m-0">Forecast Details</p>
                    </div>
                    <div className="table-responsive">
                      <table className="data-table">
                        <thead>
                          <tr>
                            {["Date","Predicted","Lower","Upper","Range"].map(h => <th key={h}>{h}</th>)}
                          </tr>
                        </thead>
                        <tbody>
                          {forecast.slice(0, 14).map((row, i) => (
                            <tr key={i}>
                              <td className="font-medium text-dark">{row.date}</td>
                              <td className="font-bold text-primary">{row.demand}</td>
                              <td className="text-muted">{row.lower}</td>
                              <td className="text-muted">{row.upper}</td>
                              <td><span className="badge badge-primary">±{Math.round((row.upper - row.lower) / 2)}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              ) : (
                <div className="empty-state">
                  <p className="empty-icon">📊</p>
                  <p className="empty-title">No forecast data</p>
                  <p className="empty-sub">Run train_models.py to generate predictions</p>
                </div>
              )}
            </div>
          )}

          {/* ── ALERTS ── */}
          {activeTab === "alerts" && (
            <div className="tab-content fade-in">
              <div className="filter-scroll">
                {["all","critical","high","medium","low"].map(f => (
                  <button 
                    key={f} 
                    onClick={() => setAlertFilter(f)} 
                    className={`filter-pill ${alertFilter === f ? 'active' : ''}`}
                  >
                    {f === "all" ? `All (${alerts.length})` : `${ALERT_CONFIG[f]?.label} (${alerts.filter(a => a.alert_level === f).length})`}
                  </button>
                ))}
              </div>

              <div className="card no-padding mobile-cards-container">
                <div className="table-responsive desktop-only-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {["Product","Category","Stock","ROP","EOQ","Days Left","Status","Action"].map(h => <th key={h}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredAlerts.map(alert => {
                        const cfg = ALERT_CONFIG[alert.alert_level] || ALERT_CONFIG.low;
                        return (
                          <tr key={alert.product_id}>
                            <td className="font-medium text-dark truncate-cell">{alert.product_name}</td>
                            <td className="text-muted">{alert.category}</td>
                            <td className="font-bold text-dark">{alert.current_stock?.toLocaleString()}</td>
                            <td className="text-muted">{alert.reorder_point?.toFixed(0)}</td>
                            <td className="text-muted">{alert.optimal_order_qty?.toFixed(0)}</td>
                            <td><span className={`font-semibold ${alert.days_remaining < 10 ? 'text-danger' : 'text-dark'}`}>{alert.days_remaining}d</span></td>
                            <td>
                              <span className="status-badge" style={{ background: cfg.bg, color: cfg.color }}>
                                {cfg.icon} {cfg.label}
                              </span>
                            </td>
                            <td>
                              {updating === alert.product_id ? (
                                <div className="action-row">
                                  <input type="number" value={updateVal} onChange={e => setUpdateVal(e.target.value)} placeholder="Stock" className="sm-input"/>
                                  <button onClick={() => handleStockSave(alert.product_id)} className="btn-save">✓</button>
                                  <button onClick={() => setUpdating(null)} className="btn-cancel">✕</button>
                                </div>
                              ) : (
                                <button onClick={() => { setUpdating(alert.product_id); setUpdateVal(""); }} className="btn-outline">Update</button>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile view for Alerts */}
                <div className="mobile-cards">
                  {filteredAlerts.map(alert => {
                    const cfg = ALERT_CONFIG[alert.alert_level] || ALERT_CONFIG.low;
                    return (
                      <div key={alert.product_id} className="mobile-card" style={{ borderLeftColor: cfg.color }}>
                        <div className="mobile-card-header">
                          <p className="mobile-card-title">{alert.product_name}</p>
                          <span className="status-badge" style={{ background: cfg.bg, color: cfg.color }}>{cfg.icon} {cfg.label}</span>
                        </div>
                        <div className="mobile-card-grid">
                          {[["Stock", alert.current_stock], ["ROP", alert.reorder_point?.toFixed(0)], ["EOQ", alert.optimal_order_qty?.toFixed(0)], ["Days Left", `${alert.days_remaining}d`]].map(([l, v]) => (
                            <div key={l} className="metric-box">
                              <p className="metric-label">{l}</p>
                              <p className="metric-value">{v}</p>
                            </div>
                          ))}
                        </div>
                        {updating === alert.product_id ? (
                          <div className="action-row mt-3">
                            <input type="number" value={updateVal} onChange={e => setUpdateVal(e.target.value)} placeholder="New stock" className="sm-input flex-1"/>
                            <button onClick={() => handleStockSave(alert.product_id)} className="btn-save px-3">Save</button>
                            <button onClick={() => setUpdating(null)} className="btn-cancel px-3">✕</button>
                          </div>
                        ) : (
                          <button onClick={() => { setUpdating(alert.product_id); setUpdateVal(""); }} className="btn-block mt-3">Update Stock</button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {/* ── PRODUCTS ── */}
          {activeTab === "products" && (
            <div className="tab-content fade-in">
              <div className="card no-padding mobile-cards-container">
                <div className="table-header desktop-only-table">
                  <p className="card-title m-0">Product Catalog <span className="font-normal text-muted">({products.length} SKUs)</span></p>
                </div>
                <div className="table-responsive desktop-only-table">
                  <table className="data-table">
                    <thead>
                      <tr>
                        {["SKU","Product Name","Category","Unit Cost","Price","Margin","Lead Time"].map(h => <th key={h}>{h}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {products.map(p => {
                        const margin = ((p.selling_price - p.unit_cost) / p.selling_price * 100).toFixed(1);
                        return (
                          <tr key={p.id}>
                            <td><code className="sku-badge">{p.sku}</code></td>
                            <td className="font-medium text-dark">{p.name}</td>
                            <td><span className="category-badge">{p.category}</span></td>
                            <td className="text-muted">₹{p.unit_cost?.toLocaleString()}</td>
                            <td className="font-semibold text-dark">₹{p.selling_price?.toLocaleString()}</td>
                            <td><span className="text-success font-bold">{margin}%</span></td>
                            <td className="text-muted">{p.lead_time_days}d</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Mobile view for Products */}
                <div className="mobile-cards">
                  {products.map(p => {
                    const margin = ((p.selling_price - p.unit_cost) / p.selling_price * 100).toFixed(1);
                    return (
                      <div key={p.id} className="mobile-card">
                        <div className="mobile-card-header">
                          <p className="mobile-card-title">{p.name}</p>
                          <code className="sku-badge">{p.sku}</code>
                        </div>
                        <div className="mobile-card-grid">
                          {[["Category", p.category], ["Cost", `₹${p.unit_cost?.toLocaleString()}`], ["Price", `₹${p.selling_price?.toLocaleString()}`], ["Margin", `${margin}%`]].map(([l, v]) => (
                            <div key={l} className="metric-box">
                              <p className="metric-label">{l}</p>
                              <p className={`metric-value ${l === "Margin" ? "text-success" : ""}`}>{v}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}
        </main>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        :root {
          --bg-main: #f9fafb;
          --bg-card: #ffffff;
          --border: #f3f4f6;
          --border-dark: #e5e7eb;
          --text-dark: #111827;
          --text-muted: #9ca3af;
          --text-gray: #6b7280;
          --primary: #4f46e5;      /* Updated to match your screenshot */
          --primary-bg: #eef2ff;   /* Updated to match your screenshot */
          --danger: #ef4444;
          --success: #22c55e;
          --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
          --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
          --radius-md: 12px;
          --radius-sm: 8px;
        }

        * { box-sizing: border-box; }
        
        /* Force reset on any parent containers */
        html, body, #root { 
          margin: 0; 
          padding: 0; 
          width: 100%; 
          height: 100%;
        }
        
        body { 
          font-family: 'Inter', sans-serif; 
          background: var(--bg-main); 
          color: var(--text-dark); 
        }
        
        /* Layouts - Using fixed to guarantee it breaks out of padded #root divs */
        .dashboard-layout { 
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          display: flex; 
          overflow: hidden; 
          background: var(--bg-main);
          z-index: 1;
        }
        
        .main-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
        
        .main-content { 
          flex: 1; 
          overflow-x: hidden;
          overflow-y: auto;
          padding: 24px 32px; 
          scroll-behavior: smooth; 
        }
        
        /* Sidebar */
        .sidebar { width: 260px; background: var(--bg-card); border-right: 1px solid var(--border); display: flex; flex-direction: column; flex-shrink: 0; transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1); z-index: 50; }
        .sidebar-header { padding: 28px 24px 24px; display: flex; justify-content: space-between; align-items: center; }
        .logo-section { display: flex; align-items: center; gap: 12px; }
        .logo-icon { width: 40px; height: 40px; background: var(--text-dark); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-size: 18px; }
        .logo-title { margin: 0; font-weight: 700; font-size: 15px; }
        .logo-subtitle { margin: 0; font-size: 12px; color: var(--text-muted); }
        .close-mobile-btn { display: none; background: none; border: none; font-size: 20px; color: var(--text-gray); cursor: pointer; }
        .sidebar-overlay { display: none; position: fixed; inset: 0; background: rgba(17, 24, 39, 0.5); z-index: 40; backdrop-filter: blur(2px); transition: opacity 0.3s; opacity: 0; pointer-events: none; }
        .sidebar-overlay.open { opacity: 1; pointer-events: auto; }
        
        /* Navigation */
        .sidebar-nav { padding: 10px 16px; flex: 1; overflow-y: auto; }
        .nav-heading { font-size: 12px; font-weight: 600; color: var(--text-muted); letter-spacing: 0.08em; margin: 0 0 16px 12px; text-transform: uppercase; }
        .nav-btn { width: 100%; display: flex; align-items: center; gap: 12px; padding: 12px 16px; border-radius: var(--radius-sm); border: none; cursor: pointer; background: transparent; color: var(--text-gray); font-weight: 500; font-size: 14px; margin-bottom: 6px; text-align: left; transition: all 0.2s; }
        .nav-btn:hover { background: var(--bg-main); color: var(--text-dark); }
        
        /* Active nav styling matching your screenshot */
        .nav-btn.active { background: var(--primary-bg); color: var(--primary); font-weight: 600; }
        
        .nav-icon { font-size: 18px; width: 24px; text-align: center; }
        .alert-badge { margin-left: auto; background: var(--danger); color: white; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 20px; }
        
        /* User Profile */
        .sidebar-footer { padding: 24px; border-top: 1px solid var(--border); }
        .user-info { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
        .avatar { width: 40px; height: 40px; background: var(--text-dark); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 15px; font-weight: 700; flex-shrink: 0; }
        .user-details { overflow: hidden; }
        .user-name { margin: 0; font-size: 14px; font-weight: 600; }
        .user-role { margin: 0; font-size: 12px; color: var(--text-muted); }
        .signout-btn { width: 100%; padding: 10px; background: white; border: 1px solid var(--border-dark); border-radius: var(--radius-sm); color: var(--text-dark); font-size: 13px; cursor: pointer; font-weight: 600; transition: all 0.2s; }
        .signout-btn:hover { background: var(--bg-main); }

        /* Top Header */
        .top-header { background: var(--bg-main); padding: 24px 32px 16px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 10; }
        .header-left { display: flex; align-items: center; gap: 16px; }
        .menu-toggle-btn { display: none; background: white; border: 1px solid var(--border-dark); border-radius: var(--radius-sm); padding: 8px 12px; cursor: pointer; font-size: 16px; transition: background 0.2s; }
        .menu-toggle-btn:hover { background: var(--bg-card); }
        .page-title { margin: 0; font-size: 24px; font-weight: 700; letter-spacing: -0.01em; color: var(--text-dark); }
        .page-date { margin: 4px 0 0; font-size: 14px; color: var(--text-muted); }
        .refresh-btn { display: flex; align-items: center; gap: 6px; padding: 10px 16px; background: var(--text-dark); color: white; border: none; border-radius: var(--radius-sm); font-size: 13px; cursor: pointer; font-weight: 600; transition: transform 0.1s, background 0.2s; }
        .refresh-btn:hover { background: #1f2937; }
        .refresh-btn:active { transform: scale(0.96); }

        /* Cards & Grids */
        .kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 24px; margin-bottom: 24px; }
        .card { background: var(--bg-card); border-radius: var(--radius-md); padding: 24px; border: 1px solid var(--border); box-shadow: var(--shadow-sm); transition: box-shadow 0.2s; }
        .card:hover { box-shadow: var(--shadow-md); }
        .card.no-padding { padding: 0; overflow: hidden; }
        .split-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 24px; }
        
        /* Typography Helpers */
        .kpi-label { margin: 0 0 10px; font-size: 13px; color: var(--text-muted); font-weight: 600; }
        .kpi-value { margin: 0 0 6px; font-size: 32px; font-weight: 700; letter-spacing: -0.02em; }
        .kpi-sub { margin: 0; font-size: 13px; font-weight: 600; }
        .card-title { margin: 0 0 6px; font-size: 18px; font-weight: 600; color: var(--text-dark); }
        .card-subtitle { margin: 0 0 24px; font-size: 14px; color: var(--text-muted); }
        .font-medium { font-weight: 500; } .font-bold { font-weight: 700; } .font-semibold { font-weight: 600; } .font-normal { font-weight: 400; }
        .text-dark { color: var(--text-dark); } .text-muted { color: var(--text-muted); } .text-primary { color: var(--primary); }
        .text-danger { color: var(--danger); } .text-success { color: var(--success); }
        .m-0 { margin: 0; } .mt-3 { margin-top: 12px; }

        /* Charts */
        .chart-wrapper { width: 100%; height: 260px; }
        .chart-card { margin-bottom: 24px; }
        .forecast-chart { height: 300px; }
        .custom-tooltip { background: rgba(255,255,255,0.95); border: 1px solid var(--border-dark); border-radius: var(--radius-sm); padding: 12px 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); font-size: 13px; backdrop-filter: blur(4px); }
        .tooltip-label { color: var(--text-gray); margin: 0 0 8px; font-weight: 600; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
        .tooltip-data { margin: 4px 0; font-weight: 700; }

        /* Progress Bars */
        .health-bars { display: flex; flex-direction: column; gap: 16px; }
        .health-bar-row { display: flex; flex-direction: column; gap: 8px; }
        .health-bar-labels { display: flex; justify-content: space-between; font-size: 14px; font-weight: 600; color: var(--text-gray); }
        .progress-track { height: 8px; background: var(--bg-main); border-radius: 4px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 1s ease-out; }

        /* Tables */
        .table-header { padding: 20px 24px; border-bottom: 1px solid var(--border); }
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .data-table { width: 100%; border-collapse: collapse; font-size: 14px; min-width: 700px; }
        .data-table th { padding: 14px 24px; text-align: left; font-weight: 600; color: var(--text-gray); font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; background: var(--bg-main); white-space: nowrap; }
        .data-table td { padding: 16px 24px; border-top: 1px solid var(--border); vertical-align: middle; }
        .data-table tr:hover { background: #fdfdfd; }
        .truncate-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        
        /* Badges & Inputs */
        .status-badge { padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; white-space: nowrap; display: inline-flex; align-items: center; gap: 4px; }
        .badge { padding: 3px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
        .badge-primary { background: var(--primary-bg); color: var(--primary); }
        .sku-badge { font-size: 12px; background: var(--bg-main); border: 1px solid var(--border-dark); padding: 3px 8px; border-radius: 6px; color: var(--primary); font-weight: 600; font-family: monospace; }
        .category-badge { background: var(--bg-main); color: var(--text-gray); padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        
        .product-select { width: 100%; padding: 12px 16px; border: 1px solid var(--border-dark); border-radius: var(--radius-sm); font-size: 15px; color: var(--text-dark); background: white; outline: none; cursor: pointer; transition: border-color 0.2s; }
        .product-select:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-bg); }
        .input-label { margin: 0 0 10px; font-size: 13px; font-weight: 600; color: var(--text-gray); }
        
        /* Actions & Filters */
        .filter-scroll { display: flex; gap: 10px; margin-bottom: 24px; overflow-x: auto; padding-bottom: 4px; scrollbar-width: none; -webkit-overflow-scrolling: touch; }
        .filter-scroll::-webkit-scrollbar { display: none; }
        .filter-pill { padding: 8px 16px; border-radius: 20px; border: 1px solid var(--border-dark); background: white; color: var(--text-gray); font-size: 13px; font-weight: 600; cursor: pointer; white-space: nowrap; transition: all 0.2s; }
        .filter-pill:hover { border-color: var(--text-dark); color: var(--text-dark); }
        .filter-pill.active { background: var(--text-dark); color: white; border-color: var(--text-dark); }
        
        .action-row { display: flex; gap: 6px; }
        .sm-input { width: 80px; padding: 6px 10px; border: 1px solid var(--border-dark); border-radius: 6px; font-size: 13px; outline: none; }
        .sm-input:focus { border-color: var(--primary); }
        .flex-1 { flex: 1; }
        .btn-save { background: var(--text-dark); color: white; border: none; border-radius: 6px; padding: 6px 12px; font-size: 13px; cursor: pointer; font-weight: 600; }
        .btn-cancel { background: var(--bg-main); color: var(--text-gray); border: none; border-radius: 6px; padding: 6px 12px; font-size: 13px; cursor: pointer; }
        .btn-outline { background: transparent; border: 1px solid var(--border-dark); border-radius: 6px; padding: 6px 16px; font-size: 13px; color: var(--text-dark); cursor: pointer; font-weight: 600; transition: background 0.2s; }
        .btn-outline:hover { background: var(--bg-main); }
        .btn-block { width: 100%; background: var(--bg-main); border: 1px solid var(--border-dark); border-radius: var(--radius-sm); padding: 10px; font-size: 13px; color: var(--text-dark); cursor: pointer; font-weight: 600; }
        .px-3 { padding-left: 16px; padding-right: 16px; }

        /* Utilities */
        .fade-in { animation: fadeIn 0.4s ease-out; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }
        .empty-state { background: white; border-radius: var(--radius-md); padding: 80px 20px; text-align: center; border: 1px dashed var(--border-dark); }
        .empty-icon { font-size: 40px; margin: 0 0 16px; opacity: 0.8; }
        .empty-title { color: var(--text-dark); font-weight: 700; font-size: 18px; margin: 0 0 8px; }
        .empty-sub { color: var(--text-muted); font-size: 14px; margin: 0; }
        
        .loader-container { display: flex; align-items: center; justify-content: center; height: 100%; width: 100%; background: var(--bg-main); position: fixed; inset: 0; z-index: 100; }
        .loader-spinner { text-align: center; color: var(--text-muted); font-size: 14px; font-weight: 500; }
        .spinner { width: 40px; height: 40px; border: 3px solid var(--border-dark); border-top: 3px solid var(--text-dark); border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 16px; }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #9ca3af; }

        /* Hide Mobile Specific Elements on Desktop */
        .mobile-cards { display: none; }

        /* =========================================
           Responsive Breakpoints
           ========================================= */
        @media (max-width: 1024px) {
          .split-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 768px) {
          /* Sidebar converts to off-canvas menu */
          .sidebar { position: fixed; top: 0; left: 0; height: 100%; transform: translateX(-100%); width: 280px; box-shadow: var(--shadow-md); }
          .sidebar.open { transform: translateX(0); }
          .close-mobile-btn { display: block; }
          .sidebar-overlay { display: block; }
          
          /* Header adjustments */
          .top-header { padding: 16px 20px; }
          .menu-toggle-btn { display: block; }
          .page-date { display: none; }
          .refresh-text { display: none; }
          
          /* Main Content spacing */
          .main-content { padding: 16px 20px; }
          .kpi-grid { grid-template-columns: repeat(2, 1fr); gap: 12px; }
          .card { padding: 16px; }
          .kpi-value { font-size: 24px; }
          .chart-wrapper { height: 200px; }
          .forecast-chart { height: 240px; }
          
          /* Table to Card conversion */
          .desktop-only-table { display: none; }
          .mobile-cards-container { background: transparent; border: none; box-shadow: none; }
          .mobile-cards { display: flex; flex-direction: column; gap: 12px; width: 100%; }
          .mobile-card { background: white; border-radius: var(--radius-md); padding: 16px; border: 1px solid var(--border); border-left: 4px solid var(--text-dark); box-shadow: var(--shadow-sm); width: 100%; }
          .mobile-card-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; gap: 12px; }
          .mobile-card-title { margin: 0; font-weight: 600; font-size: 14px; color: var(--text-dark); flex: 1; }
          .mobile-card-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
          .metric-box { background: var(--bg-main); border-radius: var(--radius-sm); padding: 10px 12px; }
          .metric-label { margin: 0 0 4px; font-size: 11px; color: var(--text-gray); font-weight: 500; }
          .metric-value { margin: 0; font-size: 15px; font-weight: 700; color: var(--text-dark); }
        }

        @media (max-width: 480px) {
          .kpi-grid { grid-template-columns: 1fr; }
        }
      `}</style>
    </div>
  );
}