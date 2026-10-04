import React from 'react';
import { BrowserRouter, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import { ShieldCheck, LayoutDashboard, ScrollText, MessageSquare, Sliders } from 'lucide-react';
import Home from './pages/Home';
import Dashboard from './pages/Dashboard';
import AuditLog from './pages/AuditLog';
import PolicyEditor from './pages/PolicyEditor';

// ── Navbar ─────────────────────────────────────────────────────────────────

const NAV_LINKS = [
  { to: '/', label: 'Chat', icon: MessageSquare, exact: true },
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard, exact: false },
  { to: '/audit', label: 'Audit Log', icon: ScrollText, exact: false },
  { to: '/policies', label: 'Policy Rules', icon: Sliders, exact: false },
];

const Navbar: React.FC = () => {
  return (
    <header className="h-12 border-b border-industrial-border bg-industrial-surface/90 backdrop-blur-sm flex items-center px-4 gap-6 flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-2 mr-4">
        <ShieldCheck size={18} className="text-accent" />
        <span className="font-semibold text-sm tracking-tight text-industrial-text">
          AP <span className="text-accent">Auditor</span>
        </span>
      </div>

      {/* Nav links */}
      <nav className="flex items-center gap-1">
        {NAV_LINKS.map(({ to, label, icon: Icon, exact }) => (
          <NavLink
            key={to}
            to={to}
            end={exact}
            className={({ isActive }) =>
              `flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'text-accent bg-accent/10 border border-accent/30'
                  : 'text-industrial-text-muted hover:text-industrial-text border border-transparent'
              }`
            }
          >
            <Icon size={12} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Right: status indicator */}
      <div className="ml-auto flex items-center gap-2 text-[10px] text-industrial-text-dim">
        <span className="w-1.5 h-1.5 rounded-full bg-nominal-bright animate-pulse" />
        <span>API: localhost:8000</span>
      </div>
    </header>
  );
};

// ── Layout ─────────────────────────────────────────────────────────────────

const Layout: React.FC = () => {
  const { pathname } = useLocation();
  const isChat = pathname === '/';

  return (
    <div className="flex flex-col h-screen bg-industrial-bg overflow-hidden">
      <Navbar />
      <main className={`flex-1 min-h-0 ${isChat ? 'flex flex-col' : 'overflow-y-auto'}`}>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/audit" element={<AuditLog />} />
          <Route path="/policies" element={<PolicyEditor />} />
        </Routes>
      </main>
    </div>
  );
};

// ── App ────────────────────────────────────────────────────────────────────

const App: React.FC = () => (
  <BrowserRouter>
    <Layout />
  </BrowserRouter>
);

export default App;
