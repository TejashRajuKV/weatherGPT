import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="app-shell">
      <nav className="sidebar">
        <div className="sidebar-logo">
          <span className="logo-icon">🌦</span>
          <span className="logo-text">WeatherGPT</span>
        </div>
        <div className="nav-links">
          <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            💬 Chat
          </NavLink>
          <NavLink to="/forecast" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            📅 Forecast
          </NavLink>
          <NavLink to="/alerts" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            🚨 Alerts
          </NavLink>
          <NavLink to="/climate" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
            📊 Climate
          </NavLink>
          {user?.role === 'admin' && (
            <NavLink to="/admin" className={({ isActive }) => isActive ? 'nav-item active' : 'nav-item'}>
              ⚙️ Admin
            </NavLink>
          )}
        </div>
        <div className="sidebar-user">
          <span className="user-name">{user?.name}</span>
          <span className="user-role">{user?.role}</span>
          <button className="logout-btn" onClick={handleLogout}>Sign out</button>
        </div>
      </nav>
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}
