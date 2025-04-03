// server.js
const express = require('express');
const fetch = require('node-fetch'); // Ensure version 2 is installed
const bodyParser = require('body-parser');
const cors = require('cors');

const app = express();
const PORT = 3000;

app.use(cors());
app.use(bodyParser.json());

app.post('/api/chat', async (req, res) => {
  const messages = req.body.messages;

  try {
    const response = await fetch('http://localhost:11434/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: 'mistral',
        prompt: messages.map(m => m.content).join('\n'),
        stream: false
      })
    });

    const data = await response.json();
    res.json({
      role: 'assistant',
      content: data.response
    });
  } catch (err) {
    console.error('Error communicating with Ollama:', err);
    res.status(500).json({ error: 'Ollama request failed.' });
  }
});

app.listen(PORT, () => {
  console.log(`PocketFreud API listening on port ${PORT}`);
});

