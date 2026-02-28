import { useState, useRef, useEffect } from 'react'
import './App.css'
import { BookOpen } from 'lucide-react'

interface Message {
  id: number
  text: string
  sender: 'user' | 'bot'
  timestamp: Date
}

type View = 'chat' | 'psalms' | 'psalm-detail'

interface PsalmMetadata {
  psalm_id: string
  themes: string[]
  emotional_context: string[]
}

interface Psalm {
  psalm_number: number
  psalm_id: string
  text: string[]
  themes: string[]
  emotional_context: string[]
  historical_usage: string
  key_verses: string[]
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState<'editorial' | 'sacred-night'>('editorial')
  const [currentView, setCurrentView] = useState<View>('chat')
  const [psalms, setPsalms] = useState<PsalmMetadata[]>([])
  const [selectedPsalm, setSelectedPsalm] = useState<Psalm | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  const typingIntervalRef = useRef<number | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Welcome message on mount
  useEffect(() => {
    const welcomeMessage: Message = {
      id: 1,
      text: "Welcome to Prayer in the Psalms. Share what's on your heart, and I'll guide you to psalms that speak to your moment.",
      sender: "bot",
      timestamp: new Date(),
    }
    setMessages([welcomeMessage])
  }, [])

  // Auto-scroll when messages change
  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Typing animation effect
  useEffect(() => {
    const lastMessage = messages[messages.length - 1]

    if (!lastMessage || lastMessage.sender !== "bot") return

    const element = document.getElementById(`bot-${lastMessage.id}`)
    if (!element) return

    let index = 0
    const text = lastMessage.text

    // Clear any existing typing animation
    if (typingIntervalRef.current) {
      clearInterval(typingIntervalRef.current)
    }

    typingIntervalRef.current = window.setInterval(() => {
      element.textContent += text[index]
      index++
      if (index >= text.length) {
        if (typingIntervalRef.current) {
          clearInterval(typingIntervalRef.current)
          typingIntervalRef.current = null
        }
      }
    }, 15)

    return () => {
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
        typingIntervalRef.current = null
      }
    }
  }, [messages])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
      if (typingIntervalRef.current) {
        clearInterval(typingIntervalRef.current)
      }
    }
  }, [])

  const fetchRecommendation = async (userMessage: string, signal: AbortSignal): Promise<string> => {
    const response = await fetch(`${API_URL}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage }),
      signal
    })

    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`)
    }

    const data = await response.json()
    return data.recommendation
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()

    if (inputValue.trim() === '' || isLoading) return

    // Cancel any ongoing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }

    // Create new abort controller for this request
    const abortController = new AbortController()
    abortControllerRef.current = abortController

    const userText = inputValue.trim()

    const userMessage: Message = {
      id: messages.length + 1,
      text: userText,
      sender: 'user',
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setInputValue('')
    setIsLoading(true)

    try {
      const recommendation = await fetchRecommendation(userText, abortController.signal)
      const formattedRecommendation = recommendation.replaceAll("**Psalm", "\n\n**Psalm")

      // Check if request was aborted
      if (abortController.signal.aborted) {
        return
      }

      const botMessage: Message = {
        id: messages.length + 2,
        text: formattedRecommendation,
        sender: 'bot',
        timestamp: new Date()
      }

      setMessages(prev => [...prev, botMessage])

    } catch (error) {
      // Don't show error if request was aborted
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Request was cancelled')
        return
      }

      const errorMessage: Message = {
        id: messages.length + 2,
        text: "Something went wrong connecting to the server. Please try again.",
        sender: 'bot',
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
      console.error('Failed to fetch recommendation:', error)

    } finally {
      setIsLoading(false)
      abortControllerRef.current = null
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage(e as unknown as React.FormEvent)
    }
  }


  const fetchAllPsalms = async () => {
    try {
      const response = await fetch(`${API_URL}/psalms`)
      const data = await response.json()
      setPsalms(data.psalms)
    } catch (error) {
      console.error('Failed to fetch psalms:', error)
    }
  }

  const fetchPsalm = async (psalmNumber: number) => {
    try {
      const response = await fetch(`${API_URL}/psalms/${psalmNumber}`)
      const data = await response.json()
      setSelectedPsalm(data)
      setCurrentView('psalm-detail')
    } catch (error) {
      console.error('Failed to fetch psalm:', error)
    }
  }

  const handleViewChange = (view: View) => {
    setCurrentView(view)
    setMenuOpen(false)
    if (view === 'psalms' && psalms.length === 0) {
      fetchAllPsalms()
    }
  }

  return (
    <div className={`page ${theme}`} data-theme={theme}>
      
      {/* Theme Switcher */}
      <div className="theme-switcher">
        <button 
          className={`switcher-btn ${theme === 'editorial' ? 'active' : ''}`}
          onClick={() => setTheme('editorial')}
        >
          <span className="num">I</span> Editorial
        </button>
        <button 
          className={`switcher-btn ${theme === 'sacred-night' ? 'active' : ''}`}
          onClick={() => setTheme('sacred-night')}
        >
          <span className="num">II</span> Sacred Night
        </button>
      </div>

      {/* Sacred Night geometry background */}
      {theme === 'sacred-night' && (
        <div className="geo-bg">
          <svg width="600" height="600" viewBox="0 0 600 600" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="300" cy="300" r="280" stroke="#d4a843" strokeWidth="0.5"/>
            <circle cx="300" cy="300" r="200" stroke="#d4a843" strokeWidth="0.5"/>
            <circle cx="300" cy="300" r="120" stroke="#d4a843" strokeWidth="0.5"/>
            <line x1="300" y1="20" x2="300" y2="580" stroke="#d4a843" strokeWidth="0.5"/>
            <line x1="20" y1="300" x2="580" y2="300" stroke="#d4a843" strokeWidth="0.5"/>
            <line x1="60" y1="60" x2="540" y2="540" stroke="#d4a843" strokeWidth="0.5"/>
            <line x1="540" y1="60" x2="60" y2="540" stroke="#d4a843" strokeWidth="0.5"/>
            <polygon points="300,60 540,420 60,420" stroke="#d4a843" strokeWidth="0.5" fill="none"/>
            <polygon points="300,540 60,180 540,180" stroke="#d4a843" strokeWidth="0.5" fill="none"/>
          </svg>
        </div>
      )}

      <div className="chat-shell">
        
        {/* Sacred Night geo bar */}
        {theme === 'sacred-night' && <div className="geo-bar"></div>}
        
        {/* Hamburger Button (top left of container) */}
        <button 
          className={`hamburger-btn ${menuOpen ? 'open' : ''}`}
          onClick={() => setMenuOpen(!menuOpen)}
          aria-label="Toggle sidebar"
        >
          <span></span>
          <span></span>
          <span></span>
        </button>

        {/* Sidebar backdrop */}
        <div 
          className={`sidebar-backdrop ${menuOpen ? 'visible' : ''}`}
          onClick={() => setMenuOpen(false)}
        />

        {/* Sidebar */}
        <div className={`sidebar ${menuOpen ? 'open' : ''}`}>
          <div className="sidebar-logo">
            <h1 className="sidebar-title">{theme === 'editorial' ? 'Psalm' : <span>PSALMS</span>}</h1>
            <p>{theme === 'editorial' ? 'Daily Scripture Companion' : 'Ancient Wisdom'}</p>
          </div>
          <div className="sidebar-divider"></div>
          {theme === 'editorial' && (
            <div>
              <div className="sidebar-section-label">Today's Psalm</div>
              <div className="psalm-of-day">
                <div className="psalm-number">119</div>
                <div className="psalm-title">Psalm of the Day</div>
                <p className="psalm-excerpt">"Thy word is a lamp unto my feet, and a light unto my path."</p>
              </div>
            </div>
          )}
          <div className="nav-links">
            <div className={`nav-link ${currentView === 'chat' ? 'active' : ''}`} onClick={() => handleViewChange('chat')}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              Chat
            </div>
            <div className={`nav-link ${currentView === 'psalms' || currentView === 'psalm-detail' ? 'active' : ''}`} onClick={() => handleViewChange('psalms')}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
              </svg>
              All Psalms
            </div>
          </div>
        </div>

        {/* Main Column */}
        <div className="main-col">

          {currentView === 'chat' && (
            <>
              {/* Header */}
              <div className="chat-header">
                {theme === 'editorial' ? (
                  <>
                    <div>
                      <div className="header-title">Prayer Companion</div>
                      <div className="header-sub">Ask anything about the Psalms</div>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="header-left">
                      <BookOpen className='logo-mark' color="#d4a843"/>
                      <div className="header-title-sacred">
                        PRAYER<span style={{color: '#d4a843'}}>COMPANION</span>
                      </div>
                    </div>
                    <div className="header-right">
                      <div className="pulse-dot"></div>
                      <span className="header-status">Listening</span>
                    </div>
                  </>
                )}
              </div>

              {/* Messages */}
              <div className="chat-messages">
            {messages.map((message) => (
              <div key={message.id} className={`msg msg-${message.sender}`}>
                {theme === 'sacred-night' && (
                  <div className="msg-label">{message.sender === 'bot' ? 'Prayer Companion' : 'You'}</div>
                )}
                <div className="msg-row">
                  <div className={`avatar avatar-${message.sender}`}>
                    {message.sender === 'bot' ? '✦' : 'Me'}
                  </div>
                  <div className="msg-bubble">
                    <p
                      id={message.sender === 'bot' ? `bot-${message.id}` : undefined}
                      style={{ whiteSpace: "pre-line" }}
                    >
                      {message.sender === 'user' ? message.text : null}
                    </p>
                  </div>
                </div>
                <span className="msg-time">
                  {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>
            ))}

            {isLoading && (
              <div className="msg msg-bot">
                <div className="msg-row">
                  <div className="avatar avatar-bot">✦</div>
                  <div className="msg-bubble">
                    <p style={{ fontStyle: 'italic' }}>Searching the Psalms...</p>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input */}
          <div className="input-zone">
            <form onSubmit={handleSendMessage}>
              <div className="input-row">
                <input
                  className="chat-input"
                  type="text"
                  placeholder="Ask about a psalm, a verse, or seek understanding…"
                  id="chatInput"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyDown={handleKeyDown}
                  disabled={isLoading}
                />
                <button
                  className="send-btn"
                  type="submit"
                  disabled={inputValue.trim() === '' || isLoading}
                  aria-label="Send"
                >
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13"/>
                    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
                  </svg>
                </button>
              </div>
            </form>
            {theme === 'sacred-night' && (
              <div className="footer-note">meditatio · lectio · oratio</div>
            )}
          </div>
            </>
          )}

          {currentView === 'psalms' && (
            <div className="psalms-grid-container">
              <div className="psalms-grid-header">
                <h2>All Psalms</h2>
                <p>Browse the complete collection of 150 Psalms</p>
              </div>
              <div className="psalms-grid">
                {psalms.map((psalm) => {
                  const psalmNum = parseInt(psalm.psalm_id.replace('Psalm ', ''))
                  return (
                    <div 
                      key={psalm.psalm_id} 
                      className="psalm-card"
                      onClick={() => fetchPsalm(psalmNum)}
                    >
                      <div className="psalm-card-number">{psalmNum}</div>
                      <div className="psalm-card-themes">
                        {psalm.themes.slice(0, 2).map((theme, idx) => (
                          <span key={idx} className="psalm-card-tag">{theme}</span>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          {currentView === 'psalm-detail' && selectedPsalm && (
            <div className="psalm-detail-container">
              <button className="back-btn" onClick={() => setCurrentView('psalms')}>
                ← Back to All Psalms
              </button>
              <div className="psalm-detail">
                <h1 className="psalm-detail-title">{selectedPsalm.psalm_id}</h1>
                
                <div className="psalm-detail-meta">
                  <div className="psalm-detail-themes">
                    {selectedPsalm.themes.map((theme, idx) => (
                      <span key={idx} className="psalm-detail-tag">{theme}</span>
                    ))}
                  </div>
                  <div className="psalm-detail-context">
                    <strong>Emotional Context:</strong> {selectedPsalm.emotional_context.join(', ')}
                  </div>
                </div>

                <div className="psalm-detail-text">
                  {selectedPsalm.text.map((verse, idx) => (
                    <p key={idx} className="psalm-verse">{verse}</p>
                  ))}
                </div>

                {selectedPsalm.historical_usage && (
                  <div className="psalm-detail-usage">
                    <strong>Historical Usage:</strong> {selectedPsalm.historical_usage}
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}

export default App
