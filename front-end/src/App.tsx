import { useState, useRef, useEffect } from 'react'
import TypeIt from "typeit"
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
  const [isLoading, setIsLoading] = useState(false)         // NEW
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
  // Add the first welcome message AFTER mount
  const welcomeMessage: Message = {
    id: 1,
    text: "Welcome to Prayer in the Psalms! Share how you're feeling and I'll suggest psalms to pray through.",
    sender: "bot",
    timestamp: new Date(),
  }

  setMessages([welcomeMessage])
}, []);

  useEffect(() => {
    scrollToBottom()
     }, [messages])

     useEffect(() => {
      
     })

useEffect(() => {
  const lastMessage = messages[messages.length - 1];
  if (!lastMessage || lastMessage.sender !== "bot") return;

  const element = document.getElementById(`bot-${lastMessage.id}`);
  if (!element) return;

  const text = lastMessage.text;
  let index = 0;
  let lastTick = Date.now();
  const CHAR_INTERVAL = 15; // ms per character

  const tick = () => {
    const now = Date.now();
    const elapsed = now - lastTick;
    lastTick = now;

    // Calculate how many characters should have been written by now
    const charsToCatchUp = Math.floor(elapsed / CHAR_INTERVAL);
    const charsToAdd = Math.max(1, charsToCatchUp);

    const slice = text.slice(index, index + charsToAdd);
    element.textContent += slice;
    index += charsToAdd;

    if (index >= text.length) {
      clearInterval(interval);
    }
  };

  const interval = setInterval(tick, CHAR_INTERVAL);

  return () => clearInterval(interval);
}, [messages]);

  const fetchRecommendation = async (userMessage: string): Promise<string> => {
    const response = await fetch(`${API_URL}/recommend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userMessage })
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
      let recommendation = "It warms my heart to hear about your upbeat and positive spirit as you work on your project. In this joyous season of your life, I’d love to share a few psalms that can enrich your gratitude and confidence as you move forward. **Psalm 92**: This psalm beautifully embodies a spirit of thanksgiving and joy. It begins with the declaration, \"It is a good thing to give thanks to Yahweh\" (92:1), which resonates with your uplifting mood. The verses that follow express how God’s works bring gladness and triumph to our hearts. As you see your project flourishing, you might find comfort in verse 12, which says, \"The righteous shall flourish like the palm tree.\" This imagery can remind you that your hard work, coupled with faith, can lead to beautiful growth and success. Embracing this psalm can deepen your sense of gratitude for the positive outcomes you are experiencing. **Psalm 108**: This psalm exudes confidence and determination, reflecting a heart ready to sing praises and trust in God’s guidance. You might find encouragement in verse 1, \"My heart is steadfast, God. I will sing and I will make music with my soul.\" As you work on your project, this reminder of steadfastness can inspire you to keep pursuing your goals with passion. The assurance in verse 13, \"Through God, we will do valiantly,\" can uplift you, reinforcing your faith that your efforts are supported by a greater power. Let this psalm be a source of motivation as you continue your journey. **Psalm 112**: This psalm speaks of blessings and stability, celebrating the life of one who delights in righteousness. It begins with \"Praise Yah! Blessed is the man who fears Yahweh\" (112:1), inviting you to reflect on the blessings in your own life. As you experience success, you might resonate with verse 7, \"His heart is steadfast, trusting in Yahweh,\" which encourages you to maintain that positive and confident outlook. The reminder that \"wealth and riches are in his house\" (112:3) can serve as a metaphor for the richness of experiences and achievements you’re gaining through your project. May these psalms bring you even more joy and affirmation in this wonderful chapter of your life!"
      recommendation = recommendation.replaceAll("**Psalm", "\n\n**Psalm")

      // await fetchRecommendation(userText)

      const botMessage: Message = {
        id: messages.length + 2,
        text: recommendation,
        sender: 'bot',
        timestamp: new Date()
      }

      setMessages(prev => [...prev, botMessage])

    } catch (error) {
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
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage(e as unknown as React.FormEvent)
    }
  }

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h1>Prayer in the Psalms</h1>
        <p>Explore and reflect on the Book of Psalms</p>
      </div>

      <div className="chat-messages">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`message ${message.sender === 'user' ? 'message-user' : 'message-bot'}`}
          >
            <div className="message-content">
              <p
                id={message.sender === 'bot' ? `bot-${message.id}` : undefined}
                style={{ whiteSpace: "pre-line" }}
              >
                {message.sender === 'user' ? message.text : null}
              </p>
              <span className="message-time">
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
          </div>
        ))}

        {/* Loading indicator while waiting for the API */}
        {isLoading && (
          <div className="message message-bot">
            <div className="message-content">
              <p className="loading-dots">Finding psalms for you<span>.</span><span>.</span><span>.</span></p>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="chat-input-container" onSubmit={handleSendMessage}>
        <input
          type="text"
          className="chat-input"
          placeholder="Share how you're feeling..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
        />
        <button
          type="submit"
          className="chat-send-button"
          disabled={inputValue.trim() === '' || isLoading}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>
      </form>
    </div>
  )
}

export default App