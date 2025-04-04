from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    messages = data.get('messages', [])

    # Send request to Ollama
    response = requests.post(
        "http://localhost:11434/api/chat",
        json={
            "model": "mistral",
            "messages": messages
        }
    )

    if response.status_code == 200:
        return jsonify(response.json())
    else:
        return jsonify({"error": "Failed to get response from Ollama."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
 
