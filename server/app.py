from flask import Flask, send_from_directory, request, jsonify
import ollama

app = Flask(__name__, static_folder='static')

# Serve landing page
@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

# Serve React app
@app.route('/chat/<path:path>')
def serve_chat(path):
    return send_from_directory(f'{app.static_folder}/chat', path)

@app.route('/chat/')
def serve_chat_index():
    return send_from_directory(f'{app.static_folder}/chat', 'index.html')

# API for chatting with Ollama
@app.route('/api/chat', methods=['POST'])
def chat_with_ollama():
    data = request.json
    messages = data.get('messages', [])
    try:
        response = ollama.chat(model='mistral', messages=messages)
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
