import { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, BarChart, Bar, Legend } from 'recharts'
import api from '../api/client'

const WMO_CODES = {
  0: '☀️ Clear', 1: '🌤 Mainly clear', 2: '⛅ Partly cloudy', 3: '☁️ Overcast',
  45: '🌫 Fog', 61: '🌧 Light rain', 63: '🌧 Rain', 65: '🌧 Heavy rain',
  80: '🌦 Showers', 95: '⛈ Thunderstorm'
}

export default function Forecast() {
  const [location, setLocation] = useState('')
  const [forecast, setForecast] = useState(null)
  const [current, setCurrent] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const fetchForecast = async () => {
    if (!location.trim()) return
    setLoading(true)
    setError('')
    try {
      const [forecastRes, currentRes] = await Promise.all([
        api.get(`/weather/forecast?location=${encodeURIComponent(location)}&days=7`),
        api.get(`/weather/current?location=${encodeURIComponent(location)}`)
      ])
      setForecast(forecastRes.data)
      setCurrent(currentRes.data)
    } catch (err) {
      setError('Could not fetch forecast. Check the location and try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <h1 className="page-title">📅 Weather Forecast</h1>
      <div className="search-row">
        <input
          className="search-input"
          placeholder="Enter city or location..."
          value={location}
          onChange={e => setLocation(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && fetchForecast()}
        />
        <button className="btn-primary" onClick={fetchForecast} disabled={loading}>
          {loading ? 'Loading...' : 'Get Forecast'}
        </button>
      </div>

      {error && <p className="error-msg">{error}</p>}

      {current && (
        <div className="current-card">
          <h2>{current.location}</h2>
          <div className="current-grid">
            <div className="metric"><span className="metric-val">{current.temperature}°C</span><span>Temperature</span></div>
            <div className="metric"><span className="metric-val">{current.humidity}%</span><span>Humidity</span></div>
            <div className="metric"><span className="metric-val">{current.wind_speed} m/s</span><span>Wind</span></div>
            <div className="metric"><span className="metric-val">{current.pressure} hPa</span><span>Pressure</span></div>
          </div>
          <p className="condition">{current.description}</p>
        </div>
      )}

      {forecast && (
        <>
          <div className="forecast-cards">
            {forecast.forecast.map((day, i) => (
              <div key={i} className="forecast-day-card">
                <p className="day-date">{new Date(day.date).toLocaleDateString('en-IN', { weekday: 'short', month: 'short', day: 'numeric' })}</p>
                <p className="day-icon">{WMO_CODES[day.weather_code]?.split(' ')[0] || '🌡'}</p>
                <p className="day-temp">{day.temp_max}° / {day.temp_min}°</p>
                <p className="day-rain">💧 {day.precipitation} mm</p>
              </div>
            ))}
          </div>

          <div className="chart-section">
            <h3>Temperature Trend (°C)</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={forecast.forecast}>
                <XAxis dataKey="date" tickFormatter={d => d.slice(5)} />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="temp_max" stroke="#ff7043" name="Max" />
                <Line type="monotone" dataKey="temp_min" stroke="#42a5f5" name="Min" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="chart-section">
            <h3>Rainfall (mm)</h3>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={forecast.forecast}>
                <XAxis dataKey="date" tickFormatter={d => d.slice(5)} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="precipitation" fill="#42a5f5" name="Rain (mm)" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <p className="source-note">Source: {forecast.source}</p>
        </>
      )}
    </div>
  )
}
