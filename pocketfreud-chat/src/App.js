import React, { useState } from 'react';
import './App.css';

const OPENAI_API_KEY = process.env.REACT_APP_OPENAI_API_KEY;

function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi, I’m PocketFreud. How are you feeling today?' }
  ]);
  const [input, setInput] = useState('');
  const [model, setModel] = useState('gpt-3.5-turbo'); // default
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMessages = [...messages, { role: 'user', content: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    try {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model,
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
      console.log("OpenAI response:", data);

      if (!response.ok) {
        const errorMessage = data?.error?.message || "Something went wrong.";
        setMessages([...newMessages, { role: 'assistant', content: errorMessage }]);
      } else {
        setMessages([...newMessages, data.choices[0].message]);
      }
    } catch (err) {
      console.error("Fetch error:", err);
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
      <h1>PocketFreud</h1>

      {/* Model selector */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontWeight: 'bold' }}>Model:</label>{' '}
        <select value={model} onChange={(e) => setModel(e.target.value)}>
          <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
          <option value="gpt-3.5-turbo-1106">gpt-3.5-turbo-1106</option>
          <option value="gpt-4">gpt-4 (if available)</option>
          <option value="text-davinci-003">text-davinci-003 (legacy)</option>
        </select>
      </div>

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

