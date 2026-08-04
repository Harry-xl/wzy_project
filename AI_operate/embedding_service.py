"""
文本嵌入服务 —— 调用 DeepSeek Embedding API 生成文本嵌入向量。
用于 RAG 知识检索的向量化环节。

支持:
- 单条文本嵌入
- 批量文本嵌入（减少 API 调用次数）
- 文档智能分块（按段落/句子边界）

注意: API_KEY 后续应从环境变量注入，当前保留回退值以兼容现有配置。
"""

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import List, Optional

import requests

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

# 导入 DeepSeek 配置
from AI_operate.deepseek_chat import deepseek_chat


class EmbeddingService:
    """文本嵌入服务。

    主要使用本地 sentence-transformers 模型生成嵌入向量（无需 API Key）。
    也可通过 DeepSeek Embedding API 生成（需配置正确的 API 端点）。

    同时提供文档分块功能，用于将长文档切分为适合检索的段落。
    """

    # 本地嵌入模型
    LOCAL_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
    _local_model = None  # 懒加载

    # HuggingFace 镜像（国内访问加速）
    # hf-mirror.com 是国内可用的 HuggingFace 镜像
    _HF_MIRROR = "https://hf-mirror.com"

    # DeepSeek Embedding API 端点（备用）
    API_URL = "https://api.deepseek.com/v1/embeddings"
    MODEL = "deepseek-chat"

    # 批量处理大小
    BATCH_SIZE = 16

    # 分块默认参数
    DEFAULT_CHUNK_SIZE = 512
    DEFAULT_CHUNK_OVERLAP = 64

    @classmethod
    def _get_local_model(cls):
        """懒加载本地嵌入模型。

        优先使用国内镜像 (hf-mirror.com) 下载模型。
        如镜像不可用，回退到 HuggingFace 官方源。
        """
        if cls._local_model is None:
            try:
                from sentence_transformers import SentenceTransformer

                # 尝试使用国内镜像
                import os
                os.environ.setdefault("HF_ENDPOINT", cls._HF_MIRROR)
                print(f"[EmbeddingService] 正在加载模型: {cls.LOCAL_MODEL_NAME}")
                print(f"[EmbeddingService] 使用镜像: {cls._HF_MIRROR}")

                cls._local_model = SentenceTransformer(cls.LOCAL_MODEL_NAME)
                print(f"[EmbeddingService] 本地模型已加载: {cls.LOCAL_MODEL_NAME}")
            except ImportError:
                print("[EmbeddingService] sentence-transformers 未安装，将使用 API 模式")
                return None
            except Exception as e:
                print(f"[EmbeddingService] 本地模型加载失败: {e}")
                print("[EmbeddingService] 请检查网络连接，或手动下载模型放置到本地")
                return None
        return cls._local_model

    @classmethod
    def _get_headers(cls) -> dict:
        """构建 API 请求头。"""
        api_key = os.getenv("DEEPSEEK_API_KEY", deepseek_chat.API_KEY)
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    def embed_single(cls, text: str) -> Optional[List[float]]:
        """生成单条文本的嵌入向量。

        优先使用本地模型，不可用时回退到 API。

        Args:
            text: 待嵌入的文本。

        Returns:
            嵌入向量（浮点数列表），失败时返回 None。
        """
        if not text or not text.strip():
            return None

        result = cls.embed_batch([text.strip()])
        if result and len(result) > 0:
            return result[0]
        return None

    @classmethod
    def embed_batch(cls, texts: List[str], max_retries: int = 3) -> Optional[List[List[float]]]:
        """批量生成嵌入向量。

        优先使用本地模型（sentence-transformers）。
        不可用时回退到 DeepSeek Embedding API。

        Args:
            texts: 文本列表。
            max_retries: API 模式下的最大重试次数。

        Returns:
            嵌入向量列表，与输入顺序一致。失败时返回 None。
        """
        if not texts:
            return []

        valid_texts = [t.strip() for t in texts if t and t.strip()]
        if not valid_texts:
            return []

        # 优先使用本地模型
        local_model = cls._get_local_model()
        if local_model is not None:
            try:
                embeddings = local_model.encode(
                    valid_texts,
                    batch_size=cls.BATCH_SIZE,
                    show_progress_bar=False,
                    normalize_embeddings=True,  # 归一化以支持余弦相似度
                )
                return embeddings.tolist()
            except Exception as e:
                print(f"[EmbeddingService] 本地模型编码失败: {e}，回退到 API")

        # 回退到 API
        return cls._embed_via_api(valid_texts, max_retries)

    @classmethod
    def _embed_via_api(cls, texts: List[str], max_retries: int = 3) -> Optional[List[List[float]]]:
        """通过 DeepSeek Embedding API 生成嵌入向量（备用方案）。"""
        all_embeddings = []

        # 分批处理
        for batch_start in range(0, len(texts), cls.BATCH_SIZE):
            batch = texts[batch_start:batch_start + cls.BATCH_SIZE]

            for attempt in range(max_retries):
                try:
                    payload = {
                        "model": cls.MODEL,
                        "input": batch,
                    }

                    response = requests.post(
                        cls.API_URL,
                        headers=cls._get_headers(),
                        json=payload,
                        timeout=60,
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # OpenAI-compatible 格式: data[].embedding
                        embeddings_data = data.get("data", [])
                        batch_embeddings = [
                            item["embedding"]
                            for item in sorted(embeddings_data, key=lambda x: x.get("index", 0))
                        ]
                        all_embeddings.extend(batch_embeddings)
                        break  # 成功，跳出重试循环
                    elif response.status_code == 429:
                        # Rate limit — 指数退避
                        wait = 2 ** attempt
                        print(f"[EmbeddingService] Rate limited, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(
                            f"[EmbeddingService] API 错误: HTTP {response.status_code}, "
                            f"{response.text[:200]}"
                        )
                        if attempt < max_retries - 1:
                            time.sleep(2 ** attempt)

                except requests.Timeout:
                    print(f"[EmbeddingService] 请求超时 (attempt {attempt + 1})")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                except Exception as e:
                    print(f"[EmbeddingService] 嵌入生成异常: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)

        if len(all_embeddings) != len(texts):
            print(
                f"[EmbeddingService] 警告: 请求 {len(texts)} 条, "
                f"仅获取 {len(all_embeddings)} 条嵌入"
            )
            return None

        return all_embeddings

    @classmethod
    def chunk_document(
        cls,
        text: str,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> List[str]:
        """将文档智能分块。

        分块策略:
        1. 优先按段落（\\n\\n）切分
        2. 超长段落按句子边界（。！？\\n）切分
        3. 每个块控制在 chunk_size 字符左右
        4. 块之间有 overlap 字符的重叠窗口，保持上下文连贯

        Args:
            text: 文档全文。
            chunk_size: 每块目标字符数（约等于 ~500 tokens）。
            overlap: 块间重叠字符数。

        Returns:
            文本块列表。
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # 第一步：按段落切分
        paragraphs = re.split(r"\n\s*\n", text)

        chunks = []
        current_chunk = ""
        current_length = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_length = len(para)

            # 如果当前段落本身超过 chunk_size，按句子切分
            if para_length > chunk_size:
                # 先把当前累积的块保存
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                    current_length = 0

                # 按句子边界切分长段落
                sentences = cls._split_by_sentence(para)
                for sentence in sentences:
                    sent_len = len(sentence)
                    if current_length + sent_len <= chunk_size:
                        current_chunk += sentence
                        current_length += sent_len
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        # 重叠处理：保留上一个块的尾部
                        if overlap > 0 and chunks:
                            prev_tail = chunks[-1][-overlap:] if len(chunks[-1]) > overlap else chunks[-1]
                            current_chunk = prev_tail + sentence
                            current_length = len(current_chunk)
                        else:
                            current_chunk = sentence
                            current_length = sent_len
            else:
                # 段落长度在 chunk_size 以内
                if current_length + para_length + 2 <= chunk_size:
                    if current_chunk:
                        current_chunk += "\n\n" + para
                    else:
                        current_chunk = para
                    current_length = len(current_chunk)
                else:
                    # 当前块已满，保存并开始新块
                    chunks.append(current_chunk.strip())
                    # 重叠处理
                    if overlap > 0:
                        prev_tail = chunks[-1][-overlap:] if len(chunks[-1]) > overlap else chunks[-1]
                        current_chunk = prev_tail + "\n\n" + para
                    else:
                        current_chunk = para
                    current_length = len(current_chunk)

        # 保存最后一块
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    @classmethod
    def _split_by_sentence(cls, text: str) -> List[str]:
        """按句子边界切分文本。

        识别中英文句子结束标记: 。！？! ? . 以及换行符。
        保留分隔符在所属句子末尾。
        """
        # 句子结束模式（中英文）
        pattern = r"(?<=[。！？!?.。\n])\s*"
        parts = re.split(pattern, text)
        return [p for p in parts if p.strip()]

    @classmethod
    def compute_content_hash(cls, text: str) -> str:
        """计算文本内容的 SHA-256 哈希，用于增量更新检测。

        Args:
            text: 文本内容。

        Returns:
            64 位十六进制哈希字符串。
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @classmethod
    def estimate_tokens(cls, text: str) -> int:
        """粗略估算文本的 Token 数量。

        中文: 约 1.5 字符/token
        英文: 约 4 字符/token
        混合时取保守估计: 字符数 / 2

        Args:
            text: 文本内容。

        Returns:
            估算的 token 数量。
        """
        if not text:
            return 0
        # 粗略估算: 对于中英混合文本，大约每 2 个字符 = 1 个 token
        return len(text) // 2


# 模块独立测试
if __name__ == "__main__":
    # 测试分块功能
    test_text = """
TCP 提供面向连接的、可靠的数据传输服务。它通过以下机制保证可靠性：

1. 序列号（Sequence Number）：TCP 将每个字节的数据都进行编号。
   序列号用于标识发送的数据字节在数据流中的位置。

2. 确认应答（ACK）：接收方收到数据后，会发送确认应答。
   确认号等于期望收到的下一个字节的序列号。

3. 超时重传：发送方在发送数据后会启动一个定时器。
   如果在超时之前没有收到确认，则重传数据。

这些机制共同构成了 TCP 的可靠传输基础，是理解 TCP 协议的关键。
"""

    print("=== 文档分块测试 ===")
    chunks = EmbeddingService.chunk_document(test_text, chunk_size=200, overlap=30)
    for i, chunk in enumerate(chunks):
        print(f"\n--- Chunk {i} (len={len(chunk)}, ~{EmbeddingService.estimate_tokens(chunk)} tokens) ---")
        print(chunk[:150] + "..." if len(chunk) > 150 else chunk)

    print(f"\n总块数: {len(chunks)}")
    print(f"内容哈希: {EmbeddingService.compute_content_hash(test_text)[:16]}...")

    # 测试嵌入生成（需要 API Key，默认注释）
    # vec = EmbeddingService.embed_single("TCP三次握手的过程")
    # if vec:
    #     print(f"嵌入维度: {len(vec)}")
