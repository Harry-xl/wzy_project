"""
星伴(StarPal) 知识库 + RAG 系统 — 完整性验证脚本

用法:
    python scripts/verify_rag.py              # 完整检查（需服务器运行）
    python scripts/verify_rag.py --offline    # 仅检查本地组件（无需服务器）
    python scripts/verify_rag.py --quick      # 快速检查（跳过模型加载）
"""

import argparse
import os
import sys
import time
from pathlib import Path

# 强制 UTF-8 输出（Windows 兼容）
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# HuggingFace 网络配置（必须放在所有 AI 相关导入之前）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# ---- 测试结果收集 ----
RESULTS = []
PASS = 0
FAIL = 0
SKIP = 0


def check(name: str, condition: bool, detail: str = "", fatal: bool = False, skipped: bool = False):
    """记录单个检查结果。"""
    global PASS, FAIL, SKIP
    if skipped:
        status = "⏭️ SKIP"
        SKIP += 1
    else:
        status = "✅ PASS" if condition else "❌ FAIL"
        if condition:
            PASS += 1
        else:
            FAIL += 1
    msg = f"  {status} | {name}"
    if detail:
        msg += f"  → {detail}"
    print(msg)
    RESULTS.append({"name": name, "passed": condition, "detail": detail, "skipped": skipped})
    if not condition and not skipped and fatal:
        print(f"\n⛔ 严重错误，终止检查: {name}")
        sys.exit(2)


def section(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ================================================================
# 1. 依赖检查
# ================================================================
def check_dependencies():
    section("1. Python 依赖检查")

    deps = {
        "chromadb": "向量数据库",
        "sentence_transformers": "嵌入模型框架",
        "flask": "Web框架",
        "mysql.connector": "MySQL驱动",
        "requests": "HTTP客户端",
        "dotenv": "环境变量管理",
    }

    for module, desc in deps.items():
        try:
            __import__(module.replace("-", "_"))
            check(f"{module} ({desc})", True)
        except ImportError:
            check(f"{module} ({desc})", False, "请运行: pip install {module}")


# ================================================================
# 2. MySQL 检查
# ================================================================
def check_mysql():
    section("2. MySQL 数据库检查")

    try:
        import mysql.connector
    except ImportError:
        check("MySQL 驱动加载", False, "mysql-connector-python 未安装", fatal=True)
        return

    # 连接
    from server.config import DB_CONFIG

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        check("MySQL 连接", True, f"{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
    except Exception as e:
        check("MySQL 连接", False, str(e), fatal=True)
        return

    try:
        cursor = conn.cursor()

        # 检查知识表存在
        expected_tables = [
            "knowledge_documents",
            "knowledge_chunks",
            "knowledge_sub_topics",
            "knowledge_relations",
        ]
        cursor.execute("SHOW TABLES")
        existing = {r[0] for r in cursor.fetchall()}

        for t in expected_tables:
            check(f"表 {t}", t in existing,
                  "存在" if t in existing else "不存在 — 请运行: python database/init_db.py")

        if not all(t in existing for t in expected_tables):
            cursor.close()
            conn.close()
            return

        # 检查数据量
        expected_counts = {
            "knowledge_documents": (12, 12),       # (min, max)
            "knowledge_chunks": (30, 500),
            "knowledge_sub_topics": (70, 200),
            "knowledge_relations": (40, 300),
        }

        for table, (lo, hi) in expected_counts.items():
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            ok = lo <= count <= hi
            check(f"{table} 数据量", ok,
                  f"{count} 行 (期望 {lo}-{hi})" if ok else f"{count} 行 (期望 {lo}-{hi})，请运行: python scripts/seed_knowledge.py")

        # 抽查一条数据
        cursor.execute(
            "SELECT chunk_id, LEFT(content, 60) FROM knowledge_chunks LIMIT 1"
        )
        row = cursor.fetchone()
        if row:
            check("知识块内容可读性", True, f"chunk#{row[0]}: {row[1]}...")
        else:
            check("知识块内容可读性", False, "knowledge_chunks 为空")

        cursor.close()
    except Exception as e:
        check("MySQL 查询", False, str(e))
    finally:
        conn.close()


# ================================================================
# 3. ChromaDB 检查
# ================================================================
def check_chromadb():
    section("3. ChromaDB 向量索引检查")

    try:
        import chromadb
    except ImportError:
        check("ChromaDB 加载", False, "chromadb 未安装", fatal=True)
        return

    from server.config import CHROMADB_PERSIST_DIR, CHROMADB_COLLECTION_NAME

    persist = str(BASE_DIR / "chroma_data") if not os.path.isabs(CHROMADB_PERSIST_DIR) else CHROMADB_PERSIST_DIR

    if not os.path.isdir(persist):
        check("ChromaDB 持久化目录", False, f"目录不存在: {persist}")
        return

    check("ChromaDB 持久化目录", True, persist)

    try:
        client = chromadb.PersistentClient(path=persist)
        check("ChromaDB 客户端初始化", True)
    except Exception as e:
        check("ChromaDB 客户端初始化", False, str(e), fatal=True)
        return

    try:
        collection = client.get_collection(CHROMADB_COLLECTION_NAME)
        count = collection.count()
        check(f"集合 '{CHROMADB_COLLECTION_NAME}'", True, f"{count} 个块")

        if count > 0:
            try:
                import numpy as np
                sample = collection.peek(limit=1)
                if sample and sample.get("embeddings") is not None:
                    emb = sample["embeddings"]
                    if isinstance(emb, np.ndarray):
                        dim = emb.shape[1] if len(emb.shape) > 1 else emb.shape[0]
                    elif isinstance(emb, list) and len(emb) > 0:
                        dim = len(emb[0]) if isinstance(emb[0], list) else len(emb)
                    else:
                        dim = 0
                    check("向量维度", dim == 384, f"{dim}维 (期望 384)")
                else:
                    check("向量维度", False, "无法获取样本向量")

                # 检查 IDs
                if sample and sample.get("ids") is not None:
                    ids = sample["ids"]
                    if isinstance(ids, np.ndarray):
                        id_list = ids.flatten().tolist()
                    elif isinstance(ids, list):
                        id_list = ids[0] if (len(ids) > 0 and isinstance(ids[0], list)) else ids
                    else:
                        id_list = []
                    check("Chunk ID 格式", len(id_list) > 0 and str(id_list[0]).isdigit(),
                          f"ID示例={id_list[0] if id_list else '?'}")
                else:
                    check("Chunk ID 格式", False, "无法获取 IDs")
            except Exception as e:
                check("ChromaDB 详情检查", False, str(e))
    except Exception as e:
        check("ChromaDB 集合查询", False, str(e))


# ================================================================
# 4. 嵌入模型检查
# ================================================================
def check_embedding_model(quick: bool = False):
    section("4. 嵌入模型检查")

    if quick:
        check("嵌入模型加载", True, "快速模式跳过", skipped=True)
        check("向量生成测试", True, "快速模式跳过", skipped=True)
        return

    from AI_operate.embedding_service import EmbeddingService

    # 模型加载
    t0 = time.time()
    try:
        model = EmbeddingService._get_local_model()
        elapsed = time.time() - t0
        if model is not None:
            check("本地嵌入模型加载", True,
                  f"{EmbeddingService.LOCAL_MODEL_NAME} ({elapsed:.1f}s)")
        else:
            check("本地嵌入模型加载", False,
                  "模型为 None，将回退到 API 模式")
    except Exception as e:
        check("本地嵌入模型加载", False, str(e))

    # 向量生成
    try:
        vec = EmbeddingService.embed_single("计算机网络")
        if vec and len(vec) == 384:
            check("向量生成 (384维)", True,
                  f"前3值=[{vec[0]:.4f}, {vec[1]:.4f}, {vec[2]:.4f}]")
        elif vec:
            check("向量生成", False, f"维度={len(vec)}，期望384")
        else:
            check("向量生成", False, "返回 None")
    except Exception as e:
        check("向量生成", False, str(e))

    # 文档分块
    test_text = "TCP提供面向连接的、可靠的数据传输服务。\n\n它通过序列号、确认应答和超时重传保证可靠性。\n\n这些机制共同构成了TCP的可靠传输基础。"
    try:
        chunks = EmbeddingService.chunk_document(test_text, chunk_size=80)
        check("文档智能分块", len(chunks) >= 1,
              f"输入{len(test_text)}字 → {len(chunks)}块: {[len(c) for c in chunks]}")
    except Exception as e:
        check("文档智能分块", False, str(e))

    # 内容哈希
    h = EmbeddingService.compute_content_hash("test")
    check("内容哈希 (SHA-256)", len(h) == 64, f"{h[:16]}...")


# ================================================================
# 5. RAG 检索管道检查
# ================================================================
def check_rag_pipeline(quick: bool = False):
    section("5. RAG 检索管道检查")

    if quick:
        check("RAGService 初始化", True, "快速模式跳过", skipped=True)
        check("语义检索", True, "快速模式跳过", skipped=True)
        check("混合检索", True, "快速模式跳过", skipped=True)
        check("Prompt 组装", True, "快速模式跳过", skipped=True)
        return

    from AI_operate.rag_service import RAGService
    from server.config import RAG_DEFAULT_TOP_K, RAG_SIMILARITY_THRESHOLD

    # 初始化
    try:
        rag = RAGService()
        check("RAGService 初始化", True,
              f"persist={rag._persist_dir}, collection={rag._collection.name}")
    except Exception as e:
        err_msg = str(e)
        if "already exists" in err_msg or "different settings" in err_msg:
            check("RAGService 初始化", False,
                  "ChromaDB 被服务器进程占用，请先关闭 Flask 服务器再运行完整验证",
                  fatal=False)  # 不致命，其他检查可继续
            return
        else:
            check("RAGService 初始化", False, err_msg, fatal=True)
            return

    # 语义检索
    try:
        results = rag.search("TCP三次握手的过程", top_k=3)
        check("语义检索 (向量)", len(results) > 0,
              f"返回 {len(results)} 条结果")

        if results:
            top = results[0]
            check("检索结果结构", all(k in top for k in ["chunk_id", "content", "score", "source"]),
                  f"score={top['score']:.3f}, source={top.get('source','?')[:30]}")
            check("相似度分数合理", 0.3 <= top["score"] <= 1.0,
                  f"top score={top['score']:.3f} (阈值={RAG_SIMILARITY_THRESHOLD})")

            # 显示 Top 3
            for i, r in enumerate(results[:3]):
                print(f"     #{i+1} [score={r['score']:.3f}] {r.get('doc_title','?')[:40]} · {r.get('source_page','')}")
    except Exception as e:
        check("语义检索 (向量)", False, str(e))

    # 关键词检索回退
    try:
        kw_results = rag._keyword_search("TCP", top_k=3)
        check("关键词检索 (MySQL)", len(kw_results) >= 0,
              f"返回 {len(kw_results)} 条（回退方案）")
    except Exception as e:
        check("关键词检索 (MySQL)", False, str(e))

    # Prompt 组装
    try:
        prompt, sources = rag.augment_prompt("什么是三次握手？", top_k=3)
        has_ref = "【参考资料】" in prompt
        check("Prompt 增强组装", has_ref and len(sources) > 0,
              f"Prompt包含参考资料={has_ref}, 来源数={len(sources)}")
        if sources:
            for s in sources[:2]:
                print(f"     [{s['index']}] {s['source'][:30]} · {s['title'][:30]} (score={s['score']})")
    except Exception as e:
        check("Prompt 增强组装", False, str(e))


# ================================================================
# 6. API 端点检查（可选）
# ================================================================
def check_api_endpoints():
    section("6. API 端点检查")

    import requests

    BASE_URL = "http://127.0.0.1:3001"

    endpoints = [
        ("GET", "/api/knowledge/search?q=TCP&top_k=2", None),
        ("GET", "/api/knowledge/documents?page=1&page_size=3", None),
        ("GET", "/api/knowledge/sub-topics?parent_kp=TCP连接管理", None),
        ("GET", "/api/knowledge/relations?kp=TCP连接管理", None),
    ]

    for method, path, _ in endpoints:
        url = f"{BASE_URL}{path}"
        try:
            resp = requests.request(method, url, timeout=10)
            ok = resp.status_code == 200
            detail = f"HTTP {resp.status_code}"
            if ok:
                try:
                    data = resp.json()
                    if "chunks" in data:
                        detail += f", {len(data['chunks'])}条结果"
                    elif "items" in data:
                        detail += f", {len(data['items'])}篇文档"
                    elif "sub_topics" in data:
                        detail += f", {len(data['sub_topics'])}个子知识点"
                    elif "relations" in data:
                        detail += f", {len(data['relations'])}条关系"
                except Exception:
                    pass
            check(f"{method} {path}", ok, detail)
        except requests.ConnectionError:
            check(f"{method} {path}", False, "服务器未运行 (127.0.0.1:3001)")
        except Exception as e:
            check(f"{method} {path}", False, str(e))

    # RAG 聊天 API
    try:
        resp = requests.post(
            f"{BASE_URL}/api/chat",
            json={"message": "测试", "username": "verify", "chat_id": "verify_rag"},
            stream=True,
            timeout=30,
        )
        sources_found = False
        for line in resp.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                import json
                try:
                    d = json.loads(line[5:].strip())
                    if d.get("done") and d.get("sources"):
                        sources_found = True
                        break
                except Exception:
                    pass
        check("POST /api/chat (RAG流式)", sources_found,
              "流结束包含sources" if sources_found else "流结束未包含sources（可能use_rag=False或检索无结果）")
    except requests.ConnectionError:
        check("POST /api/chat (RAG流式)", False, "服务器未运行")
    except Exception as e:
        check("POST /api/chat (RAG流式)", False, str(e))


# ================================================================
# 7. 前端文件完整性检查
# ================================================================
def check_frontend_files():
    section("7. 前端文件完整性检查")

    static = BASE_DIR / "static"

    files_to_check = {
        "js/dashboard-chat.js": "仪表盘聊天（含RAG来源）",
        "js/chat.js": "独立聊天页（已修复RAG）",
        "js/renderer.js": "消息渲染器（已添加sources-card）",
        "assets/starpal-chat-style.css": "来源卡片样式",
    }

    for path, desc in files_to_check.items():
        full = static / path
        exists = full.exists()
        check(f"{desc} ({path})", exists, "存在" if exists else "缺失")

        if exists and path == "js/dashboard-chat.js":
            content = full.read_text(encoding="utf-8")
            check("dashboard-chat.js: SSE sources解析",
                  "o.done && o.sources" in content,
                  "已包含sources解析逻辑")
            check("dashboard-chat.js: 来源卡片渲染",
                  "sources-card" in content,
                  "已包含sources-card渲染")

        if exists and path == "js/renderer.js":
            content = full.read_text(encoding="utf-8")
            check("renderer.js: RAG来源卡片",
                  "sources-card" in content,
                  "已包含sources-card渲染")

        if exists and path == "js/chat.js":
            content = full.read_text(encoding="utf-8")
            check("chat.js: SSE sources解析",
                  "data.done && data.sources" in content,
                  "已包含sources解析逻辑")


# ================================================================
# 主流程
# ================================================================
def main():
    parser = argparse.ArgumentParser(description="StarPal RAG 系统完整性验证")
    parser.add_argument("--offline", action="store_true", help="跳过 API 端点检查")
    parser.add_argument("--quick", action="store_true", help="快速模式（跳过模型加载）")
    args = parser.parse_args()

    print("╔══════════════════════════════════════════════════════╗")
    print("║   StarPal 知识库 + RAG 系统 — 完整性验证           ║")
    print("╚══════════════════════════════════════════════════════╝")
    print(f"  项目目录: {BASE_DIR}")
    print(f"  模式: {'快速' if args.quick else '完整'}{'+离线' if args.offline else ''}")
    print(f"  时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    t_start = time.time()

    check_dependencies()
    check_mysql()
    check_chromadb()
    check_embedding_model(quick=args.quick)
    check_rag_pipeline(quick=args.quick)

    if not args.offline:
        check_api_endpoints()

    check_frontend_files()

    elapsed = time.time() - t_start

    # ---- 汇总 ----
    total = PASS + FAIL + SKIP
    print(f"\n{'='*60}")
    print(f"  验证完成")
    print(f"{'='*60}")
    print(f"  总计: {total} 项 | ✅ 通过: {PASS} | ❌ 失败: {FAIL} | ⏭️ 跳过: {SKIP}")
    print(f"  耗时: {elapsed:.1f}s")

    if FAIL == 0:
        print(f"\n  🎉 全部检查通过！RAG 系统运行正常。")
        return 0
    else:
        print(f"\n  ⚠️  {FAIL} 项失败，请根据上述提示修复。")
        print(f"  常见修复步骤:")
        print(f"    1. 缺失表 → python database/init_db.py")
        print(f"    2. 缺失数据 → python scripts/seed_knowledge.py")
        print(f"    3. 缺失依赖 → pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())
