import React, { useState } from 'react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi, I’m PocketFreud. How are you feeling today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMessages = [...messages, { role: 'user', content: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: 'mistral',  // or whatever model you're using
          messages: [
            {
              role: "system",
              content: "You are PocketFreud, a kind, calm, and supportive AI trained to help people talk through their feelings and support their mental well-being. Speak in a gentle, understanding tone."
            },
            ...newMessages
          ],
        }),
      });

      const data = await response.json();

      if (!response.ok || !data?.message?.content) {
        const errorMsg = data?.error?.message || 'Something went wrong.';
        setMessages([...newMessages, { role: 'assistant', content: errorMsg }]);
      } else {
        const reply = data.message || data.choices?.[0]?.message || { role: 'assistant', content: 'Sorry, I didn’t understand that.' };
        setMessages([...newMessages, reply]);
      }
    } catch (err) {
      console.error('Fetch error:', err);
      setMessages([...newMessages, {
        role: 'assistant',
        content: "Oops! Network or server error. Please try again soon."
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') sendMessage();
  };

  return (
    <div className="chat-container">
      <h1>Welcome to PocketFreud</h1>

      <div className="chat-box">
        {messages.map((msg, index) => (
          <div key={index} className={`chat-msg ${msg.role}`}>
            <span>{msg.content}</span>
          </div>
        ))}
        {loading && <div className="chat-msg assistant">Typing...</div>}
      </div>

      <div className="input-box">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
        />
        <button onClick={sendMessage}>Send</button>
      </div>
    </div>
  );
}

export default App;

