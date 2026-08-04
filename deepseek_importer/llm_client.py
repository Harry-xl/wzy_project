# llm_client.py
import json
import time
import requests
from config import LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME

def call_deepseek(prompt: str, max_retries: int = 5) -> dict:
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "stream": False,
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                LLM_API_URL,
                headers=headers,
                json=payload,
                timeout=60
            )

            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                content = content.replace("```json", "").replace("```", "").strip()
                return json.loads(content)

            wait_s = min(2 ** attempt, 20)
            time.sleep(wait_s)

        except Exception:
            wait_s = min(2 ** attempt, 20)
            time.sleep(wait_s)

    return {
        "difficulty": "中等",
        "knowledge_point": "计算机网络概述",
        "osi_layer": None
    }
