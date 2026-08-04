# 导入必要的库
import os
import requests  # 用于发送HTTP请求到DeepSeek API
import json  # 用于处理JSON数据


class deepseek_chat:
    """==================================deepseek聊天类===================================
    提供与 DeepSeek Chat API 的交互能力。

    API_KEY 从环境变量 DEEPSEEK_API_KEY 读取，请在 .env 文件中配置。
    """
    # DeepSeek Chat API配置
    API_URL = "https://api.deepseek.com/v1/chat/completions"  # DeepSeek Chat API的端点URL
    API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

    # HTTP请求头配置
    headers = {
        "Authorization": f"Bearer {API_KEY}",  # 设置API认证信息
        "Content-Type": "application/json"  # 指定请求内容格式为JSON
    }

    # 直接调用DeepSeek API的函数
    """
        直接调用DeepSeek API进行聊天
        参数:
        message (str): 用户输入的消息内容
        返回:
        str: 模型返回的回复内容或错误信息
        
        这是向 DeepSeek API 发送请求时的对话消息格式，用于描述用户输入的内容，具体解析如下：
        messages：是一个列表，用于存储对话历史（包括用户和 AI 的消息）。
        列表元素结构：每个元素是一个字典，包含两个必填字段：
        role：标识消息的发送者角色，此处为"user"（用户）。
        content：消息的具体内容，此处通过变量message动态传入用户输入的文本。
        """
    def chat_with_deepseek(message):
        # 构建API请求数据
        data = {
            "model": "deepseek-chat",  # 指定使用的模型名称
            "messages": [
                {"role": "user", "content": message}  # 用户消息内容
            ]
        }
        # 发送POST请求到DeepSeek API
        response = requests.post(
            deepseek_chat.API_URL,
            headers=deepseek_chat.headers,
            json=data
        )

        # 处理API响应
        if response.status_code == 200:  # 检查请求是否成功(状态码200表示成功)
            # 从JSON响应中提取模型返回的回复内容
            return response.json()["choices"][0]["message"]["content"]
        else:
            # 请求失败时返回错误信息，包含状态码和错误详情
            return f"请求失败: {response.status_code}, {response.text}"

    @staticmethod
    def chat_with_deepseek_stream(message):
        """以流式（Server-Sent Events风格）获取模型输出，逐步产出内容片段。

        参数:
            message: str, 用户输入或提示词
        产出:
            str 片段，每次产出一小段文本，供调用方边到边转发给前端
        """
        # 构造带 stream=true 的请求体
        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": message}
            ],
            "stream": True
        }
        try:
            with requests.post(
                deepseek_chat.API_URL,
                headers=deepseek_chat.headers,
                json=data,
                stream=True,
                timeout=300
            ) as resp:
                # 若非 200，尝试读取错误体并抛出
                if resp.status_code != 200:
                    err_text = None
                    try:
                        err_text = resp.text
                    except Exception:
                        err_text = f"HTTP {resp.status_code}"
                    raise RuntimeError(f"DeepSeek 流式请求失败: {resp.status_code}, {err_text}")

                # 逐行读取 SSE 数据：以 data: 开头的 JSON，每个 JSON 包含增量片段
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if not raw_line:
                        continue
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    # 兼容性解析：尝试 OpenAI 风格 choices[0].delta.content
                    try:
                        obj = json.loads(payload)
                        choices = obj.get("choices", [])
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        content = delta.get("content")
                        # 有些实现可能直接在 message.content 返回最终整段
                        if content is None:
                            content = choices[0].get("message", {}).get("content")
                        if content:
                            yield content
                    except Exception:
                        # 非法 JSON，忽略该行
                        continue
        except Exception as e:
            # 发生异常时，将错误信息作为片段返回，避免前端长时间无响应
            yield f"[流式请求异常] {e}"


"""
message = input("你：")
result = deepseek_chat.chat_with_deepseek(message)
print(result)
"""