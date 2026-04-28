// src/frontend/src/components/Login.jsx
import { useState } from "react";
import { api } from "../api";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true); 
    setError("");
    try {
      const data = await api.login(username, password);
      onLogin(data.access_token);
    } catch {
      setError("Invalid username or password");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-layout">
      
      {/* ── Left Panel: Branding & Stats ── */}
      <div className="brand-panel">
        <div className="brand-header">
          <div className="brand-logo">📦</div>
          <span className="brand-name">Inventory AI</span>
        </div>

        <div className="brand-content">
          <div className="brand-badge">
            <span>ML-Powered Forecasting</span>
          </div>
          <h1 className="brand-title">
            Smart Inventory Management System
          </h1>
          <p className="brand-description">
            Demand forecasting, inventory optimization, and real-time alerts — all powered by XGBoost ML models.
          </p>

          <div className="brand-stats">
            {[["50", "Products"], ["36K+", "Data Points"], ["~25%", "Avg MAPE"]].map(([val, label]) => (
              <div key={label} className="stat-item">
                <p className="stat-value">{val}</p>
                <p className="stat-label">{label}</p>
              </div>
            ))}
          </div>
        </div>

        <p className="brand-footer">
          Built with Python · XGBoost · FastAPI · React
        </p>
      </div>

      {/* ── Right Panel: Login Form ── */}
      <div className="form-panel">
        <div className="form-wrapper">
          <h2 className="form-title">Welcome back</h2>
          <p className="form-subtitle">Sign in to your dashboard</p>

          <form onSubmit={handleSubmit}>
            <div className="input-group">
              <label className="input-label">Username</label>
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="Enter username"
                autoFocus
                className="text-input"
              />
            </div>

            <div className="input-group">
              <label className="input-label">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="Enter password"
                className="text-input"
              />
            </div>

            {error && (
              <div className="error-alert">
                <p className="error-text">⚠ {error}</p>
              </div>
            )}

            <button 
              type="submit" 
              disabled={loading} 
              className={`submit-btn ${loading ? 'loading' : ''}`}
            >
              {loading ? "Signing in..." : "Sign in →"}
            </button>
          </form>

          <div className="demo-credentials">
            <p className="demo-title">Demo credentials</p>
            <p className="demo-text">admin / admin123</p>
          </div>
        </div>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        * { box-sizing: border-box; }
        
        /* Force reset on any parent containers */
        html, body, #root { 
          margin: 0; 
          padding: 0; 
          width: 100%; 
          height: 100%;
        }

        body { font-family: 'Inter', sans-serif; background: #f9fafb; overflow-x: hidden; }

        /* Layout - Using fixed to guarantee it breaks out of padded #root divs */
        .login-layout {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          display: flex;
          flex-direction: column;
          overflow: hidden; 
          z-index: 1;
        }

        /* ── Left Panel (Brand) ── */
        .brand-panel {
          background: #111827;
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          padding: 32px 24px;
          color: white;
          overflow-y: auto; 
        }

        .brand-header {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 40px;
        }

        .brand-logo {
          width: 36px;
          height: 36px;
          background: #fff;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 18px;
          color: #111827;
        }

        .brand-name { font-weight: 700; font-size: 16px; }
        .brand-content { margin-bottom: 40px; }

        .brand-badge {
          display: inline-flex;
          background: rgba(255,255,255,0.08);
          border-radius: 6px;
          padding: 6px 12px;
          margin-bottom: 24px;
        }

        .brand-badge span {
          color: rgba(255,255,255,0.7);
          font-size: 12px;
          font-weight: 600;
          letter-spacing: 0.05em;
          text-transform: uppercase;
        }

        .brand-title {
          font-size: clamp(28px, 5vw, 40px);
          font-weight: 700;
          line-height: 1.15;
          margin: 0 0 16px;
          letter-spacing: -0.02em;
        }

        .brand-description {
          color: rgba(255,255,255,0.6);
          font-size: clamp(14px, 2vw, 16px);
          line-height: 1.6;
          margin: 0 0 40px;
          max-width: 440px;
        }

        .brand-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(110px, 1fr)); gap: 24px; }
        .stat-item { border-left: 2px solid rgba(255,255,255,0.1); padding-left: 16px; }
        .stat-value { margin: 0 0 4px; font-size: clamp(20px, 4vw, 24px); font-weight: 700; }
        .stat-label { margin: 0; font-size: 13px; color: rgba(255,255,255,0.5); font-weight: 500; }
        .brand-footer { color: rgba(255,255,255,0.3); font-size: 12px; margin: 0; font-weight: 500; }

        /* ── Right Panel (Form) ── */
        .form-panel {
          background: #fff;
          display: flex;
          flex-direction: column;
          justify-content: center;
          padding: 40px 24px;
          flex: 1;
          overflow-y: auto;
        }

        .form-wrapper { width: 100%; max-width: 400px; margin: 0 auto; }
        .form-title { margin: 0 0 8px; font-size: clamp(24px, 4vw, 28px); font-weight: 700; color: #111827; letter-spacing: -0.01em; }
        .form-subtitle { margin: 0 0 40px; color: #6b7280; font-size: 15px; }

        .input-group { margin-bottom: 20px; }
        .input-label { display: block; font-size: 13px; font-weight: 600; color: #374151; margin-bottom: 8px; }

        .text-input {
          width: 100%;
          padding: 12px 16px;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          font-size: 14px;
          color: #111827;
          background: #fff;
          outline: none;
          transition: all 0.2s ease;
        }

        .text-input:focus { border-color: #4f46e5; box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1); }
        .text-input::placeholder { color: #9ca3af; }

        .error-alert { background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; }
        .error-text { margin: 0; color: #dc2626; font-size: 13px; font-weight: 500; }

        .submit-btn {
          width: 100%; padding: 14px; background: #111827; color: #fff; border: none; border-radius: 8px;
          font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s ease; margin-top: 8px;
        }

        .submit-btn:hover:not(:disabled) { background: #1f2937; transform: translateY(-1px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); }
        .submit-btn:active:not(:disabled) { transform: translateY(0); }
        .submit-btn.loading { background: #6b7280; cursor: not-allowed; }

        .demo-credentials { margin-top: 40px; padding: 16px; background: #f9fafb; border-radius: 8px; border: 1px dashed #d1d5db; text-align: center; }
        .demo-title { margin: 0 0 6px; font-size: 12px; font-weight: 600; color: #4b5563; text-transform: uppercase; letter-spacing: 0.05em; }
        .demo-text { margin: 0; font-size: 13px; color: #6b7280; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; font-weight: 500; }

        /* ── Responsive Breakpoints ── */
        @media (min-width: 768px) {
          .login-layout { flex-direction: row; }
          .brand-panel { flex: 1; padding: 48px; }
          .form-panel { flex: 1; padding: 60px 56px; }
        }

        @media (min-width: 1024px) {
          .brand-panel { flex: 1.2; padding: 64px 80px; }
          .form-panel { flex: 1; }
        }
      `}</style>
    </div>
  );
}