import { useState, useEffect } from 'react'
import api from '../api/client'

const SEVERITY_COLOR = { low: '#4caf50', medium: '#ff9800', high: '#f44336', extreme: '#9c27b0' }

export default function Alerts() {
  const [alerts, setAlerts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/alerts').then(res => {
      setAlerts(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <h1 className="page-title">🚨 Weather Alerts</h1>
      {loading && <p>Loading alerts...</p>}
      {!loading && alerts.length === 0 && (
        <div className="empty-state">
          <p>✅ No active weather alerts at the moment.</p>
        </div>
      )}
      <div className="alerts-list">
        {alerts.map(alert => (
          <div key={alert._id} className="alert-card" style={{ borderLeft: `4px solid ${SEVERITY_COLOR[alert.severity]}` }}>
            <div className="alert-header">
              <span className="alert-type">{alert.hazard_type}</span>
              <span className="alert-severity" style={{ color: SEVERITY_COLOR[alert.severity] }}>
                {alert.severity.toUpperCase()}
              </span>
            </div>
            <p className="alert-message">{alert.message}</p>
            <div className="alert-meta">
              {alert.source && <span>Source: {alert.source}</span>}
              {alert.start && <span>From: {new Date(alert.start).toLocaleString()}</span>}
              {alert.end && <span>Until: {new Date(alert.end).toLocaleString()}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
