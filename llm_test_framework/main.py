import json
from models.openai_model import query_openai_conversation
from models.claude_model import query_claude_conversation

models_to_test = ["gpt-3.5-turbo", "gpt-4-turbo", "gpt-4o"]

with open("prompts.json") as f:
    prompts = json.load(f)

results_md = "# LLM Conversation Simulation Comparison\n\n"

for prompt in prompts:
    user_turns = prompt['messages']
    results_md += f"## Prompt ID: {prompt['id']}\n\n"

    for model in models_to_test:
        replies, tokens_in, tokens_out, cost = query_openai_conversation(user_turns, model=model)
        results_md += f"### OpenAI {model}:\n"
        results_md += f"**Input Tokens**: {tokens_in}, **Output Tokens**: {tokens_out}, **Total Cost**: ${cost:.4f}\n"
        for i, reply in enumerate(replies):
            results_md += f"**Reply {i+1}:**\n```text\n{reply}\n```\n"
        results_md += "\n"

    #claude_replies = query_claude_conversation(user_turns)
    #results_md += f"### Claude Sonnet 4:\n"
    #results_md += f"_Token usage estimation not available_\n"
    #for i, reply in enumerate(claude_replies):
    #    results_md += f"**Reply {i+1}:**\n```text\n{reply}\n```\n"
    #results_md += "\n"

with open("results/latest_output.md", "w") as f:
    f.write(results_md)
