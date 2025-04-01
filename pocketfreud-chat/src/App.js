// PocketFreud: Minimal React Chat App with ChatGPT API

import React, { useState } from 'react';
import './App.css';

const OPENAI_API_KEY = process.env.REACT_APP_OPENAI_API_KEY;
console.log("API Key in use:", OPENAI_API_KEY);


function App() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi, I’m PocketFreud. How are you feeling today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

const sendMessage = async () => {
  if (!input.trim()) return;

  console.log("Sending a message:", input);


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
        model: 'gpt-3.5-turbo',
        messages: newMessages,
      }),
    });

    const data = await response.json();

    // Log full response for debugging
    console.log("OpenAI response:", data);

    if (!response.ok) {
      let errorMessage = "Something went wrong.";
      if (response.status === 429) {
        errorMessage = "I'm being rate-limited right now. Please wait a few seconds and try again.";
      } else if (data?.error?.message) {
        errorMessage = data.error.message;
      }

      setMessages([...newMessages, { role: 'assistant', content: errorMessage }]);
    } else if (data?.choices?.[0]?.message) {
      setMessages([...newMessages, data.choices[0].message]);
    } else {
      setMessages([...newMessages, { role: 'assistant', content: "Unexpected response format." }]);
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
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="chat-container">
      <h1>PocketFreud</h1>
      <div className="chat-box">
        {messages.map((msg, index) => (
          <div key={index} className={`chat-msg ${msg.role}`}>
            <span>{msg.content}</span>
          </div>
        ))}
        {loading && <div className="chat-msg assistant">Typing...</div>}
      </div>
      <div className="input-box">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={3}
          style={{
            width: '100%',
            padding: '10px',
            borderRadius: '8px',
            border: '1px solid #ccc',
            fontSize: '1rem',
            resize: 'vertical'
          }}
        />
        <div style={{ textAlign: 'right', marginTop: '0.5rem' }}>
          <button
            onClick={sendMessage}
            style={{
              padding: '8px 16px',
              backgroundColor: '#6a5acd',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 'bold'
            }}
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;

