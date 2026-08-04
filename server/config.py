"""
星伴(StarPal) 全局配置模块。
所有配置优先从环境变量读取，提供合理的默认值作为回退。

用法:
    from server.config import DB_CONFIG, DEEPSEEK_API_KEY, CHROMADB_PERSIST_DIR
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

# ============================================================
# MySQL 数据库配置
# ============================================================
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": os.getenv("MYSQL_DATABASE", "wzyProjectDb"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
}

# ============================================================
# DeepSeek API 配置
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions"
)
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ============================================================
# ChromaDB 向量数据库配置
# ============================================================
CHROMADB_PERSIST_DIR = os.getenv(
    "CHROMADB_PERSIST_DIR", str(BASE_DIR / "chroma_data")
)
CHROMADB_COLLECTION_NAME = os.getenv(
    "CHROMADB_COLLECTION_NAME", "knowledge_chunks"
)

# ============================================================
# RAG 检索增强生成配置
# ============================================================
RAG_DEFAULT_TOP_K = int(os.getenv("RAG_DEFAULT_TOP_K", "5"))
RAG_MAX_TOP_K = int(os.getenv("RAG_MAX_TOP_K", "20"))
RAG_SIMILARITY_THRESHOLD = float(os.getenv("RAG_SIMILARITY_THRESHOLD", "0.3"))

# ============================================================
# 数据清理配置
# ============================================================
CLEANUP_ENABLED = os.getenv("CLEANUP_ENABLED", "true").lower() in ("true", "1", "yes")
CLEANUP_INTERVAL_SECONDS = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "3600"))
RETAIN_DAYS_ANSWERS = int(os.getenv("RETAIN_DAYS_ANSWERS", "60"))
RETAIN_DAYS_SESSIONS = int(os.getenv("RETAIN_DAYS_SESSIONS", "180"))


def print_config():
    """打印当前配置摘要（隐藏密钥）。"""
    print(f"[config] MySQL: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    print(f"[config] DeepSeek API: {DEEPSEEK_API_URL} (model={DEEPSEEK_MODEL})")
    print(f"[config] ChromaDB: {CHROMADB_PERSIST_DIR}")
    print(f"[config] RAG: top_k={RAG_DEFAULT_TOP_K}, threshold={RAG_SIMILARITY_THRESHOLD}")
    print(f"[config] Cleanup: enabled={CLEANUP_ENABLED}, interval={CLEANUP_INTERVAL_SECONDS}s")
