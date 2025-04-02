// server/server.js

const express = require('express');
const cors = require('cors');
const fetch = require('node-fetch');
require('dotenv').config(); // Optional if using .env

const app = express();
const PORT = process.env.PORT || 3000;

// Which model provider to use: 'ollama' or 'openai'
const LLM_PROVIDER = process.env.LLM_PROVIDER || 'ollama';
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

app.use(cors());
app.use(express.json());

app.post('/api/chat', async (req, res) => {
  const { messages, model = 'mistral' } = req.body;

  try {
    if (LLM_PROVIDER === 'ollama') {
      const response = await fetch('http://localhost:11434/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model, messages }),
      });

      const data = await response.json();
      return res.json(data);
    }

    if (LLM_PROVIDER === 'openai') {
      const response = await fetch('https://api.openai.com/v1/chat/completions', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: model || 'gpt-3.5-turbo',
          messages,
        }),
      });

      const data = await response.json();
      return res.json(data);
    }

    return res.status(400).json({ error: 'Unsupported LLM provider' });
  } catch (err) {
    console.error('Chat error:', err);
    return res.status(500).json({ error: 'Something went wrong' });
  }
});

app.get('/', (req, res) => {
  res.send('PocketFreud backend is running.');
});

app.listen(PORT, () => {
  console.log(`PocketFreud backend listening on port ${PORT}`);
});

