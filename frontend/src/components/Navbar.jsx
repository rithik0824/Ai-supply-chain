// Classification: Public
import { Link, useLocation } from 'react-router-dom';
import { Package, LayoutDashboard, LogOut, Activity } from 'lucide-react';

export default function Navbar({ username, onLogout }) {
  const location = useLocation();

  return (
    <nav className="navbar glass-panel">
      <div className="nav-brand">
        <Activity color="var(--accent-primary)" />
        <span style={{ background: 'var(--accent-gradient)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          AI Supply Chain
        </span>
      </div>

      <div className="nav-links">
        <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
          <LayoutDashboard size={18} style={{ marginRight: '0.5rem', display: 'inline', verticalAlign: 'text-bottom' }} />
          Dashboard
        </Link>

        <Link to="/inventory" className={`nav-link ${location.pathname === '/inventory' ? 'active' : ''}`}>
          <Package size={18} style={{ marginRight: '0.5rem', display: 'inline', verticalAlign: 'text-bottom' }} />
          Inventory
        </Link>

        {username && (
          <div className="nav-username" style={{ color: 'var(--text-secondary)', marginRight: '1rem', display: 'flex', alignItems: 'center', fontSize: '0.95rem' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}>
              Signed in: <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{username}</span>
            </span>
          </div>
        )}

        <button onClick={onLogout} className="btn btn-danger" style={{ padding: '0.5rem 1rem' }}>
          <LogOut size={16} /> Logout
        </button>
      </div>
    </nav>
  );
}
