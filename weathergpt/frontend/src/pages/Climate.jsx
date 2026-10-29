import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts'
import api from '../api/client'

export default function Climate() {
  const [location, setLocation] = useState('')
  const [from, setFrom] = useState(() => {
    const d = new Date(); d.setMonth(d.getMonth() - 1); return d.toISOString().split('T')[0]
  })
  const [to, setTo] = useState(() => new Date().toISOString().split('T')[0])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchClimate = async () => {
    if (!location.trim()) return
    setLoading(true); setError('')
    try {
      const res = await api.get(`/climate/history?location=${encodeURIComponent(location)}&from=${from}&to=${to}`)
      setData(res.data)
    } catch {
      setError('Could not fetch climate data.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">📊 Climate & Historical Analysis</h1>
      <div className="search-row">
        <input className="search-input" placeholder="Location" value={location} onChange={e => setLocation(e.target.value)} />
        <input type="date" value={from} onChange={e => setFrom(e.target.value)} className="date-input" />
        <input type="date" value={to} onChange={e => setTo(e.target.value)} className="date-input" />
        <button className="btn-primary" onClick={fetchClimate} disabled={loading}>
          {loading ? 'Loading...' : 'Analyze'}
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      {data?.records?.length > 0 && (
        <>
          <div className="stats-row">
            <div className="stat-card">
              <span className="stat-val">{Math.max(...data.records.map(r => r.temp_max)).toFixed(1)}°C</span>
              <span>Max Temp</span>
            </div>
            <div className="stat-card">
              <span className="stat-val">{Math.min(...data.records.map(r => r.temp_min)).toFixed(1)}°C</span>
              <span>Min Temp</span>
            </div>
            <div className="stat-card">
              <span className="stat-val">{data.records.reduce((s, r) => s + (r.precipitation || 0), 0).toFixed(1)} mm</span>
              <span>Total Rainfall</span>
            </div>
          </div>

          <div className="chart-section">
            <h3>Temperature History</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={data.records}>
                <XAxis dataKey="date" tickFormatter={d => d.slice(5)} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="temp_max" stroke="#ff7043" name="Max °C" dot={false} />
                <Line type="monotone" dataKey="temp_min" stroke="#42a5f5" name="Min °C" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-section">
            <h3>Daily Rainfall (mm)</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={data.records}>
                <XAxis dataKey="date" tickFormatter={d => d.slice(5)} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="precipitation" fill="#1565c0" name="Rain mm" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="source-note">Source: {data.source}</p>
        </>
      )}
    </div>
  )
}
