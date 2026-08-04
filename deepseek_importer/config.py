# config.py
import os

LLM_API_URL = "https://api.deepseek.com/v1/chat/completions"
LLM_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
LLM_MODEL_NAME = "deepseek-chat"

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "wzyProjectDb"),
    "charset": "utf8mb4",
}

STANDARD_KNOWLEDGE_POINTS = [
    "计算机网络概述",
    "网络体系结构",
    "物理层基础",
    "数据链路层基础",
    "滑动窗口与可靠传输",
    "MAC子层与以太网",
    "ARP协议",
    "IPv4与IPv6",
    "IP地址与子网划分",
    "路由算法与协议",
    "ICMP协议",
    "NAT与DHCP",
    "多播与移动IP",
    "UDP协议",
    "TCP连接管理",
    "TCP可靠传输与流量控制",
    "TCP拥塞控制",
    "DNS系统",
    "HTTP与HTTPS",
    "高级Web协议",
    "FTP与电子邮件",
    "CDN与负载均衡",
    "零拷贝与传输优化",
    "QoS与流量管理",
    "网络安全与防火墙"
]

OSI_LAYERS = [
    "应用层",
    "表示层",
    "会话层",
    "传输层",
    "网络层",
    "数据链路层",
    "物理层"
]

MAX_WORKERS = 8
BATCH_SIZE = 100
CHECKPOINT_FILE = "import_checkpoint.json"
FAILED_FILE = "failed_questions.json"

def build_prompt(q: dict) -> str:
    stem = q["stem"].strip()
    if q.get("options"):
        opts = "\n".join([f"{k}. {v}" for k, v in q["options"].items()])
        full_q = f"{stem}\n{opts}"
    else:
        full_q = stem

    q_type_map = {
        "single_choice": "单选题",
        "multi_choice": "多选题",
        "blank": "填空题",
        "judge": "判断题"
    }
    q_type = q_type_map.get(q.get("type"), "未知题型")

    kp_text = "\n".join([f"{i+1}. {kp}" for i, kp in enumerate(STANDARD_KNOWLEDGE_POINTS)])

    return f"""
你是计算机网络课程的题目标注专家。

请对下面题目做结构化标注。

【题型】
{q_type}

【题目内容】
{full_q}

【标准答案】
{q.get("raw_answer", "").strip()}

【知识点候选列表】
{kp_text}

【OSI层可选值】
应用层、表示层、会话层、传输层、网络层、数据链路层、物理层、null

【要求】
1. difficulty 只能是：简单 / 中等 / 困难
2. knowledge_point 必须且只能从知识点候选列表中选一个，原样输出
3. osi_layer 必须从给定 OSI 层中选一个，或者输出 null
4. 只输出 JSON，不要输出解释，不要输出 markdown

输出格式：
{{
  "difficulty": "中等",
  "knowledge_point": "TCP连接管理",
  "osi_layer": "传输层"
}}
""".strip()
