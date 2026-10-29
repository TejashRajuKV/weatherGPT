import { useState, useEffect } from 'react'
import api from '../api/client'

const HAZARDS = ['Heavy Rain', 'Cyclone', 'Heatwave', 'Cold Wave', 'Flood', 'Thunderstorm', 'Lightning', 'High Winds']

export default function Admin() {
  const [alerts, setAlerts] = useState([])
  const [users, setUsers] = useState([])
  const [tab, setTab] = useState('alerts')
  const [form, setForm] = useState({ hazard_type: 'Heavy Rain', severity: 'medium', message: '', source: 'Admin', status: 'active' })
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    api.get('/admin/alerts').then(r => setAlerts(r.data)).catch(() => {})
    api.get('/admin/users').then(r => setUsers(r.data)).catch(() => {})
  }, [])

  const createAlert = async (e) => {
    e.preventDefault()
    setCreating(true)
    try {
      const res = await api.post('/admin/alerts', form)
      setAlerts(prev => [res.data, ...prev])
      setForm({ hazard_type: 'Heavy Rain', severity: 'medium', message: '', source: 'Admin', status: 'active' })
    } catch (err) {
      alert(err.response?.data?.error || 'Failed to create alert')
    } finally {
      setCreating(false)
    }
  }

  const updateAlertStatus = async (id, status) => {
    await api.patch(`/admin/alerts/${id}`, { status })
    setAlerts(prev => prev.map(a => a._id === id ? { ...a, status } : a))
  }

  return (
    <div className="page">
      <h1 className="page-title">⚙️ Admin Dashboard</h1>
      <div className="tab-row">
        <button className={`tab-btn ${tab === 'alerts' ? 'active' : ''}`} onClick={() => setTab('alerts')}>Alerts</button>
        <button className={`tab-btn ${tab === 'users' ? 'active' : ''}`} onClick={() => setTab('users')}>Users</button>
        <button className={`tab-btn ${tab === 'create' ? 'active' : ''}`} onClick={() => setTab('create')}>Create Alert</button>
      </div>

      {tab === 'create' && (
        <form className="admin-form" onSubmit={createAlert}>
          <select value={form.hazard_type} onChange={e => setForm({ ...form, hazard_type: e.target.value })}>
            {HAZARDS.map(h => <option key={h}>{h}</option>)}
          </select>
          <select value={form.severity} onChange={e => setForm({ ...form, severity: e.target.value })}>
            {['low', 'medium', 'high', 'extreme'].map(s => <option key={s}>{s}</option>)}
          </select>
          <textarea
            placeholder="Alert message..."
            required value={form.message}
            onChange={e => setForm({ ...form, message: e.target.value })}
          />
          <input placeholder="Source (e.g. IMD)" value={form.source} onChange={e => setForm({ ...form, source: e.target.value })} />
          <button type="submit" className="btn-primary" disabled={creating}>
            {creating ? 'Creating...' : 'Broadcast Alert'}
          </button>
        </form>
      )}

      {tab === 'alerts' && (
        <table className="admin-table">
          <thead>
            <tr><th>Type</th><th>Severity</th><th>Message</th><th>Status</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {alerts.map(a => (
              <tr key={a._id}>
                <td>{a.hazard_type}</td>
                <td>{a.severity}</td>
                <td>{a.message.substring(0, 60)}...</td>
                <td>{a.status}</td>
                <td>
                  {a.status !== 'expired' && (
                    <button onClick={() => updateAlertStatus(a._id, 'expired')} className="btn-small">Expire</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === 'users' && (
        <table className="admin-table">
          <thead>
            <tr><th>Name</th><th>Email</th><th>Role</th><th>Language</th></tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u._id}><td>{u.name}</td><td>{u.email}</td><td>{u.role}</td><td>{u.language}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
