from flask import Flask, request, jsonify, send_from_directory
import requests
import os

USE_OLLAMA = os.getenv('USE_OLLAMA', 'false').lower() == 'true'



app = Flask(__name__, static_folder='static')

@app.route('/')
def serve_landing():
    return send_from_directory('static', 'index.html')

@app.route('/chat')
def serve_chat():
    return send_from_directory('static', 'chat.html')


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])

    try:
        if USE_OLLAMA:
            # Talk to Ollama locally
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "mistral",
                    "prompt": user_prompt
                }
            )
        else:
            # Talk to OpenAI API
            response = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [{"role": "user", "content": user_prompt}]
                }
        )


        response.raise_for_status()
        result = response.json()
        ai_message = result["message"]["content"]
        return jsonify({"response": ai_message})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

