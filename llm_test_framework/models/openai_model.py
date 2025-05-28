from openai import OpenAI
from config import OPENAI_API_KEY, PRICES, PROMPT

client = OpenAI(api_key=OPENAI_API_KEY)

def query_openai_conversation(user_turns, model="gpt-4o", system_msg=None):
    full_history = [{"role": "system", "content": system_msg or PROMPT}]
    replies = []
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0

    for user_msg in user_turns:
        full_history.append(user_msg)
        response = client.chat.completions.create(
            model=model,
            messages=full_history,
            temperature=0.7
        )
        assistant_msg = response.choices[0].message
        full_history.append(assistant_msg)

        usage = response.usage
        cost = (usage.prompt_tokens / 1000) * PRICES[model]["input"] + (usage.completion_tokens / 1000) * PRICES[model]["output"]

        total_prompt += usage.prompt_tokens
        total_completion += usage.completion_tokens
        total_cost += cost

        replies.append(assistant_msg.content)

    return replies, total_prompt, total_completion, total_cost
