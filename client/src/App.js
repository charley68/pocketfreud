
import React, { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';
import './App.css';

function App() {
  const [email, setEmail] = useState('');
  const [user, setUser] = useState(null);
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi, I’m PocketFreud. How are you feeling today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const checkSession = async () => {
      const { data: { user } } = await supabase.auth.getUser();
      setUser(user);
    };
    checkSession();
  }, []);

  const handleLogin = async () => {
    const { data, error } = await supabase.auth.signInWithOtp({ email });
    if (error) alert(error.message);
    else alert("Magic link sent! Check your inbox.");
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    setUser(null);
  };

  const sendMessage = async () => {
    if (!input.trim()) return;

    const newMessages = [...messages, { role: 'user', content: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);

    const OPENAI_API_KEY = process.env.REACT_APP_OPENAI_API_KEY;

    try {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: 'gpt-3.5-turbo',
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

      if (!response.ok || !data?.choices?.[0]?.message) {
        const errorMsg = data?.error?.message || 'Something went wrong.';
        setMessages([...newMessages, { role: 'assistant', content: errorMsg }]);
      } else {
        setMessages([...newMessages, data.choices[0].message]);
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

  if (!user) {
    return (
      <div className="login-box">
        <h2>Login to PocketFreud</h2>
        <input
          type="email"
          placeholder="Your email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <button onClick={handleLogin}>Send Magic Link</button>
      </div>
    );
  }

  return (
    <div className="chat-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h1>Welcome back, {user.email}</h1>
        <button onClick={handleLogout}>Logout</button>
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
