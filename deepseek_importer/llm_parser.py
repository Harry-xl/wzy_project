# llm_parser.py
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from config import LLM_API_URL, LLM_API_KEY, LLM_MODEL_NAME

FAILED_CHUNKS_FILE = "failed_chunks.json"
MAX_WORKERS = 5  # 提取阶段的并发线程数，不要设太大以免触发 API 限流

SYSTEM_PROMPT = """
你是一个专业的题库整理工具，负责从原始文本中识别并提取所有题目。

任务要求：
1. 识别文本中的每一道题目，过滤掉所有非题目内容，例如课程说明、预习提示、章节标题、说明语句。
2. 只保留以下题型：
   - single_choice：单选题
   - multi_choice：多选题
   - blank：填空题
   - judge：判断题
3. 忽略简答题、论述题、计算题、案例分析题、开放题等主观题。
4. 完整提取题干、选项、答案。
5. 如果是多选题，answer 形如 "ABD"。
6. 如果是填空题且有多个空，stem 保留完整题干，answer 用 "；" 分隔多个答案。
7. 如果选项跨行，必须合并成完整选项。
8. 如果某段文字不是题目，绝对不要输出。

只输出 JSON 数组，不要输出解释，不要输出 markdown，不要输出额外文字。
""".strip()

# 配置更强大的底层的会话和重试机制
session = requests.Session()
retry_strategy = Retry(
    total=5,  # 最大重试次数
    backoff_factor=2,  # 重试间隔：2, 4, 8, 16秒...
    status_forcelist=[429, 500, 502, 503, 504], # 遇到这些状态码自动重试
    allowed_methods=["POST"]
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS)
session.mount("https://", adapter)
session.mount("http://", adapter)

session.headers.update({
    "Authorization": f"Bearer {LLM_API_KEY}",
    "Content-Type": "application/json",
})


def append_failed_chunk(chunk_index: int, text_chunk: str, error_msg: str):
    failed = []
    try:
        with open(FAILED_CHUNKS_FILE, "r", encoding="utf-8") as f:
            failed = json.load(f)
    except Exception:
        failed = []

    failed.append({
        "chunk_index": chunk_index,
        "error": error_msg,
        "text_chunk": text_chunk[:5000]
    })

    with open(FAILED_CHUNKS_FILE, "w", encoding="utf-8") as f:
        json.dump(failed, f, ensure_ascii=False, indent=2)


def split_text_into_chunks(raw_text: str, lines_per_chunk: int = 40, max_chars: int = 2500) -> list:
    lines = raw_text.split("\n")
    chunks = []
    current = []
    current_chars = 0

    for line in lines:
        line_len = len(line)
        if current and (current_chars + line_len > max_chars):
            chunks.append("\n".join(current))
            current = []
            current_chars = 0
        current.append(line)
        current_chars += line_len
        if len(current) >= lines_per_chunk and not line.strip():
            chunks.append("\n".join(current))
            current = []
            current_chars = 0
    if current:
        chunks.append("\n".join(current))
    return chunks


def _extract_json_array(text: str):
    text = text.replace("```json", "").replace("```", "").strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    json_part = text[start:end + 1]
    try:
        data = json.loads(json_part)
        if isinstance(data, list):
            return data
    except Exception:
        return []
    return []


def process_single_chunk(args):
    chunk_index, text_chunk = args
    payload = {
        "model": LLM_MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"请从下面文本中提取所有题目：\n\n{text_chunk}"}
        ],
        "temperature": 0.1,
        "stream": False
    }

    try:
        # 这里底层的 retry_strategy 已经处理了大部分的网络报错和超时
        resp = session.post(LLM_API_URL, json=payload, timeout=(15, 180))
        
        if resp.status_code != 200:
            error_msg = f"HTTP {resp.status_code}: {resp.text[:500]}"
            append_failed_chunk(chunk_index, text_chunk, error_msg)
            return chunk_index, []

        content = resp.json()["choices"][0]["message"]["content"]
        parsed = _extract_json_array(content)

        cleaned = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            q_type = (item.get("type") or "").strip()
            stem = (item.get("stem") or "").strip()
            options = item.get("options")
            answer = (item.get("answer") or "").strip()

            if q_type not in {"single_choice", "multi_choice", "blank", "judge"}:
                continue
            if not stem:
                continue
            if q_type in {"single_choice", "multi_choice"} and not isinstance(options, dict):
                continue

            cleaned.append({
                "type": q_type,
                "stem": stem,
                "options": options if isinstance(options, dict) else None,
                "answer": answer
            })

        return chunk_index, cleaned

    except Exception as e:
        # 捕捉所有未被 adapter 拦住的异常 (如极端超时)
        error_msg = str(e)
        append_failed_chunk(chunk_index, text_chunk, error_msg)
        return chunk_index, []


def parse_docx_with_llm(docx_path: str) -> list:
    from docx_reader import extract_raw_text

    print("\n" + "=" * 55)
    print("  【阶段 1/2】 正在用 LLM 提取题目 (多线程并发加速)...")
    print("=" * 55)

    print("正在读取文档原始文本...")
    raw_text = extract_raw_text(docx_path)

    chunks = split_text_into_chunks(raw_text, lines_per_chunk=40, max_chars=2500)
    print(f"文档共分为 {len(chunks)} 个批次")

    # 准备任务
    tasks = [(idx, chunk) for idx, chunk in enumerate(chunks, start=1)]
    results_map = {}
    total_extracted = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_task = {executor.submit(process_single_chunk, task): task for task in tasks}
        
        with tqdm(total=len(chunks), desc="📄 提取题目", unit="批", ncols=90) as pbar:
            for future in as_completed(future_to_task):
                chunk_index, extracted_questions = future.result()
                results_map[chunk_index] = extracted_questions
                total_extracted += len(extracted_questions)
                
                pbar.set_postfix({"已提取题目": total_extracted})
                pbar.update(1)

    # 按原始 chunk 顺序重组题目，确保题目顺序不乱
    all_questions = []
    for idx in range(1, len(chunks) + 1):
        if idx in results_map:
            all_questions.extend(results_map[idx])

    print(f"\n✅ 阶段1完成：共提取到 {len(all_questions)} 道有效题目")
    print(f"若有失败批次，请检查 {FAILED_CHUNKS_FILE}\n")
    return all_questions
