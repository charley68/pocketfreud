from flask import Flask, request, jsonify, send_from_directory
import requests

app = Flask(__name__, static_folder='static')

# Serve the landing page
@app.route('/')
def serve_landing():
    return send_from_directory('static', 'index.html')

# Serve the chat page
@app.route('/chat')
def serve_chat():
    return send_from_directory('static', 'chat.html')

# API endpoint to chat
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    messages = data.get('messages', [])

    try:
        response = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": "mistral",
                "messages": messages,
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

