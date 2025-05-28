import anthropic
from config import CLAUDE_API_KEY, PROMPT

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

def query_claude_conversation(user_turns, model="claude-3-sonnet-20240229", system_msg=None):
    history = []
    replies = []

    for user_msg in user_turns:
        history.append(user_msg)
        response = client.messages.create(
            model=model,
            max_tokens=1000,
            temperature=0.7,
            system=system_msg or PROMPT,
            messages=history
        )
        assistant_msg = {"role": "assistant", "content": response.content[0].text}
        history.append(assistant_msg)
        replies.append(assistant_msg["content"])

    return replies
