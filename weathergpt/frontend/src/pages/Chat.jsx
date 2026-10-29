import { useState, useRef, useEffect } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const SUGGESTED = [
  "What's the weather in Mumbai today?",
  "Will it rain in Delhi this week?",
  "Should I spray pesticide tomorrow? (Pune)",
  "Is it safe to go fishing in Goa tomorrow?",
  "Cyclone warnings for coastal areas?",
]

const LANGUAGES = [
  { code: 'en', label: 'English' }, { code: 'hi', label: 'हिंदी' },
  { code: 'mr', label: 'मराठी' }, { code: 'ta', label: 'தமிழ்' },
  { code: 'te', label: 'తెలుగు' }, { code: 'bn', label: 'বাংলা' },
  { code: 'gu', label: 'ગુજરાતી' }, { code: 'ml', label: 'മലയാളം' },
  { code: 'kn', label: 'ಕನ್ನಡ' }, { code: 'pa', label: 'ਪੰਜਾਬੀ' },
]

export default function Chat() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([
    { role: 'assistant', content: `Hello ${user?.name || ''}! Ask me anything about weather, forecasts, or advisories.` }
  ])
  const [input, setInput] = useState('')
  const [location, setLocation] = useState('')
  const [language, setLanguage] = useState(user?.language || 'en')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [listening, setListening] = useState(false)
  const messagesEndRef = useRef(null)
  const recognitionRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const speak = (text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utt = new SpeechSynthesisUtterance(text)
    utt.lang = language === 'hi' ? 'hi-IN' : language === 'mr' ? 'mr-IN' :
               language === 'ta' ? 'ta-IN' : language === 'te' ? 'te-IN' : 'en-IN'
    window.speechSynthesis.speak(utt)
  }

  const sendMessage = async (query) => {
    if (!query.trim()) return
    const userMsg = { role: 'user', content: query }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)
    try {
      const res = await api.post('/chat', { query, location, language, conversationId })
      setConversationId(res.data.conversationId)
      const reply = res.data.response
      setMessages(prev => [...prev, { role: 'assistant', content: reply }])
      speak(reply)
    } catch (err) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I could not process your request. Please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  const startVoice = () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) return alert('Voice input not supported in this browser')
    const recognition = new SpeechRecognition()
    recognition.lang = language === 'hi' ? 'hi-IN' : language === 'mr' ? 'mr-IN' : 'en-IN'
    recognition.onresult = (e) => {
      const text = e.results[0][0].transcript
      setInput(text)
      setListening(false)
    }
    recognition.onerror = () => setListening(false)
    recognition.onend = () => setListening(false)
    recognition.start()
    recognitionRef.current = recognition
    setListening(true)
  }

  const stopVoice = () => {
    recognitionRef.current?.stop()
    setListening(false)
  }

  return (
    <div className="chat-page">
      <div className="chat-toolbar">
        <input
          className="location-input"
          placeholder="📍 Location (optional)"
          value={location}
          onChange={e => setLocation(e.target.value)}
        />
        <select className="lang-select" value={language} onChange={e => setLanguage(e.target.value)}>
          {LANGUAGES.map(l => <option key={l.code} value={l.code}>{l.label}</option>)}
        </select>
      </div>

      <div className="chat-messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-bubble">
              {msg.role === 'assistant' && <span className="msg-icon">🌦</span>}
              <p>{msg.content}</p>
            </div>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-bubble">
              <span className="msg-icon">🌦</span>
              <p className="typing">Thinking...</p>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {messages.length <= 1 && (
        <div className="suggestions">
          {SUGGESTED.map((s, i) => (
            <button key={i} className="suggestion-chip" onClick={() => sendMessage(s)}>{s}</button>
          ))}
        </div>
      )}

      <div className="chat-input-row">
        <button
          className={`voice-btn ${listening ? 'listening' : ''}`}
          onClick={listening ? stopVoice : startVoice}
          aria-label="Voice input"
        >
          {listening ? '⏹' : '🎤'}
        </button>
        <input
          className="chat-input"
          placeholder="Ask about weather, forecasts, alerts..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && sendMessage(input)}
        />
        <button className="send-btn" onClick={() => sendMessage(input)} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
