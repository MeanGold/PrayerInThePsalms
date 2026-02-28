import { useState, useRef, useEffect } from 'react'
import './App.css'

interface Message {
  id: number
  text: string
  sender: 'user' | 'bot'
  timestamp: Date
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [theme, setTheme] = useState<'editorial' | 'sacred-night'>('editorial')
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
      // const recommendation = "It warms my heart to hear about your upbeat and positive spirit as you work on your project. In this joyous season of your life, I’d love to share a few psalms that can enrich your gratitude and confidence as you move forward. **Psalm 92**: This psalm beautifully embodies a spirit of thanksgiving and joy. It begins with the declaration, \"It is a good thing to give thanks to Yahweh\" (92:1), which resonates with your uplifting mood. The verses that follow express how God’s works bring gladness and triumph to our hearts. As you see your project flourishing, you might find comfort in verse 12, which says, \"The righteous shall flourish like the palm tree.\" This imagery can remind you that your hard work, coupled with faith, can lead to beautiful growth and success. Embracing this psalm can deepen your sense of gratitude for the positive outcomes you are experiencing. **Psalm 108**: This psalm exudes confidence and determination, reflecting a heart ready to sing praises and trust in God’s guidance. You might find encouragement in verse 1, \"My heart is steadfast, God. I will sing and I will make music with my soul.\" As you work on your project, this reminder of steadfastness can inspire you to keep pursuing your goals with passion. The assurance in verse 13, \"Through God, we will do valiantly,\" can uplift you, reinforcing your faith that your efforts are supported by a greater power. Let this psalm be a source of motivation as you continue your journey. **Psalm 112**: This psalm speaks of blessings and stability, celebrating the life of one who delights in righteousness. It begins with \"Praise Yah! Blessed is the man who fears Yahweh\" (112:1), inviting you to reflect on the blessings in your own life. As you experience success, you might resonate with verse 7, \"His heart is steadfast, trusting in Yahweh,\" which encourages you to maintain that positive and confident outlook. The reminder that \"wealth and riches are in his house\" (112:3) can serve as a metaphor for the richness of experiences and achievements you’re gaining through your project. May these psalms bring you even more joy and affirmation in this wonderful chapter of your life!"
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

  const handleHintClick = (hint: string) => {
    setInputValue(hint)
    const inputElement = document.getElementById('chatInput') as HTMLInputElement
    if (inputElement) inputElement.focus()
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
            <h1 className="sidebar-title">{theme === 'editorial' ? 'Psalm' : <span>PSALM<span style={{color: '#d4a843'}}>AI</span></span>}</h1>
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
            <div className="nav-link active" onClick={() => setMenuOpen(false)}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
              Chat
            </div>
            <div className="nav-link" onClick={() => setMenuOpen(false)}>
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

          {/* Header */}
          <div className="chat-header">
            {theme === 'editorial' ? (
              <>
                <div>
                  <div className="header-title">Scripture Chat</div>
                  <div className="header-sub">Ask anything about the Psalms</div>
                </div>
                <div className="header-tags">
                  <div className="tag active">Psalms</div>
                  <div className="tag">Hebrew</div>
                  <div className="tag">History</div>
                </div>
              </>
            ) : (
              <>
                <div className="header-left">
                  <svg className="logo-mark" viewBox="0 0 34 34" fill="none">
                    <circle cx="17" cy="17" r="15" stroke="#d4a843" strokeWidth="1" opacity="0.4"/>
                    <circle cx="17" cy="17" r="9" stroke="#d4a843" strokeWidth="1" opacity="0.6"/>
                    <circle cx="17" cy="17" r="2.5" fill="#d4a843" opacity="0.8"/>
                    <line x1="17" y1="2" x2="17" y2="32" stroke="#d4a843" strokeWidth="0.75" opacity="0.3"/>
                    <line x1="2" y1="17" x2="32" y2="17" stroke="#d4a843" strokeWidth="0.75" opacity="0.3"/>
                  </svg>
                  <div className="header-title-sacred">
                    PSALM<span style={{color: '#d4a843'}}>AI</span>
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
                  <div className="msg-label">{message.sender === 'bot' ? 'Scripture' : 'You'}</div>
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
            {theme === 'editorial' && (
              <div className="hint-chips">
                <div className="hint-chip" onClick={() => handleHintClick("Psalms for anxiety")}>
                  Psalms for anxiety
                </div>
                <div className="hint-chip" onClick={() => handleHintClick("What is selah?")}>
                  What is selah?
                </div>
                <div className="hint-chip" onClick={() => handleHintClick("Psalm 23 in depth")}>
                  Psalm 23 in depth
                </div>
                <div className="hint-chip" onClick={() => handleHintClick("Psalms of ascent")}>
                  Psalms of ascent
                </div>
              </div>
            )}
            {theme === 'sacred-night' && (
              <div className="footer-note">meditatio · lectio · oratio</div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}

export default App
