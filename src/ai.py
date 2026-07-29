from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"]
)


def analyse(article, playbook):
    prompt = f"""
You are an event-driven investing analyst.

Playbook:

{playbook}

Article:

{article}

Return ONLY:

Score: 0-100

Reason:

2-5 concise bullet points.
"""

    response = client.responses.create(
        model="gpt-5",
        input=prompt,
    )

    return response.output_text
