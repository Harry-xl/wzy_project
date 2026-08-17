"""
检索增强生成 (RAG) 服务 —— 星伴(StarPal) 知识检索与 Prompt 增强引擎。

核心流水线:
  用户查询 → 嵌入生成 → ChromaDB 向量检索 → MySQL 内容查询 → Prompt 组装

架构:
  ChromaDB: 仅存储嵌入向量 + chunk_id（快速相似度检索）
  MySQL:   存储完整文本内容 + 元数据（知识块内容、来源、知识点）
  两者通过 chunk_id 关联。
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

import chromadb
from chromadb.config import Settings as ChromaSettings

from AI_operate.embedding_service import EmbeddingService
from database.db_connector import get_connection
from server.config import (
    CHROMADB_COLLECTION_NAME,
    CHROMADB_PERSIST_DIR,
    RAG_DEFAULT_TOP_K,
    RAG_MAX_TOP_K,
    RAG_SIMILARITY_THRESHOLD,
)


class RAGService:
    """检索增强生成服务。

    协调 ChromaDB 向量检索和 MySQL 内容查询，
    将相关知识块注入 LLM Prompt 以提高回答质量。

    用法:
        rag = RAGService()
        chunks = rag.search("TCP 三次握手的过程", top_k=3)
        prompt = rag.augment_prompt("TCP 三次握手的过程", chunks)
    """

    def __init__(self, persist_dir: Optional[str] = None):
        """初始化 RAG 服务。

        Args:
            persist_dir: ChromaDB 持久化目录，默认使用配置中的路径。
        """
        self._persist_dir = persist_dir or CHROMADB_PERSIST_DIR

        # 确保持久化目录存在
        os.makedirs(self._persist_dir, exist_ok=True)

        # 初始化 ChromaDB 客户端（嵌入式，无需额外服务）
        self._chroma_client = chromadb.PersistentClient(
            path=self._persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # 获取或创建集合（使用余弦相似度）
        self._collection = self._chroma_client.get_or_create_collection(
            name=CHROMADB_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        # 嵌入服务
        self._embedding = EmbeddingService()

    # ================================================================
    # 检索接口
    # ================================================================

    def search(
        self,
        query: str,
        top_k: int = RAG_DEFAULT_TOP_K,
        doc_type: Optional[str] = None,
        similarity_threshold: float = RAG_SIMILARITY_THRESHOLD,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """混合检索相关知识块。

        流程:
          1. 将查询嵌入为向量
          2. ChromaDB 向量语义检索（取 top_k * 2 候选）
             - user_id=None: 检索系统知识库（metadata user_id="system" 或不存在）
             - user_id=int: 检索个人资料库（metadata user_id="<user_id>"）
          3. MySQL 关键词辅助检索
          4. 合并去重，按相似度排序
          5. 过滤低于阈值的结果
          6. 从 MySQL 查询完整内容 + 元数据

        Args:
            query: 用户查询文本。
            top_k: 返回的最大结果数。
            doc_type: 可选，限定文档类型（textbook/rfc/knowledge_entry/...）。
            similarity_threshold: 相似度阈值（0.0-1.0），低于此值的结果被过滤。
            user_id: 可选，限定检索范围。
                     None → 系统知识库（knowledge_documents.user_id IS NULL）
                     具体值 → 个人资料库。

        Returns:
            知识块列表，每项包含:
              chunk_id, content, doc_title, doc_type, source,
              source_page, knowledge_points, sub_topic_name, score, source_type
        """
        if not query or not query.strip():
            return []

        # 限制 top_k 范围
        top_k = max(1, min(top_k, RAG_MAX_TOP_K))

        # Step 1: 嵌入查询
        query_vector = self._embedding.embed_single(query.strip())
        if query_vector is None:
            print("[RAGService] 查询嵌入生成失败，回退到关键词检索")
            return self._keyword_search(query, top_k, doc_type, user_id=user_id)

        # Step 2: ChromaDB 向量检索
        chroma_k = min(top_k * 2, RAG_MAX_TOP_K)  # 多取一些候选用于重排序
        try:
            query_kwargs = {
                "query_embeddings": [query_vector],
                "n_results": chroma_k,
                "include": ["distances"],
            }
            # user_id 过滤：限定检索范围
            # user_id=None → 不过滤（返回所有：旧占位数据 + 新系统资料）
            # user_id=int  → 仅检索该用户的个人资料
            if user_id is not None:
                query_kwargs["where"] = {"user_id": str(user_id)}
            # user_id=None 时不加 where 条件，兼容旧数据（无 metadata）

            chroma_results = self._collection.query(**query_kwargs)
        except Exception as e:
            print(f"[RAGService] ChromaDB 检索失败: {e}")
            return self._keyword_search(query, top_k, doc_type, user_id=user_id)

        chroma_ids = chroma_results.get("ids", [[]])[0]
        chroma_distances = chroma_results.get("distances", [[]])[0]

        if not chroma_ids:
            # 向量检索无结果，回退到关键词检索
            return self._keyword_search(query, top_k, doc_type, user_id=user_id)

        # Step 3: 从 MySQL 查询完整内容
        chunks = self._fetch_chunks_by_ids(chroma_ids, chroma_distances, doc_type, user_id=user_id)

        # Step 4: 合并关键词检索结果（混合检索）
        keyword_chunks = self._keyword_search(query, top_k, doc_type, user_id=user_id)
        chunk_map = {c["chunk_id"]: c for c in chunks}

        for kc in keyword_chunks:
            kid = kc["chunk_id"]
            if kid not in chunk_map:
                kc["score"] = 0.3  # 关键词匹配的基础分
                chunk_map[kid] = kc
            else:
                # 提升同时被向量和关键词命中的结果
                chunk_map[kid]["score"] = min(1.0, chunk_map[kid]["score"] + 0.1)

        # Step 5: 排序 + 过滤 + 截断
        merged = sorted(
            chunk_map.values(),
            key=lambda x: x.get("score", 0),
            reverse=True,
        )
        filtered = [c for c in merged if c.get("score", 0) >= similarity_threshold]

        return filtered[:top_k]

    # ================================================================
    # Prompt 增强
    # ================================================================

    def augment_prompt(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        knowledge_chunks: Optional[List[Dict[str, Any]]] = None,
        top_k: int = RAG_DEFAULT_TOP_K,
        context_type: str = "chat",
        user_id: Optional[int] = None,
    ) -> tuple:
        """构建 RAG 增强的 Prompt。

        将检索到的知识块组装为结构化 Prompt，注入给 LLM。

        Args:
            user_message: 用户消息。
            system_prompt: 系统提示词（如未提供，使用默认教学助手）。
            knowledge_chunks: 预检索的知识块列表（如为 None 则自动检索）。
            top_k: 自动检索时的结果数。
            context_type: 上下文类型 ("chat" 聊天 / "explain" 讲解)。
            user_id: 可选，限定检索范围（None=系统，具体值=个人）。

        Returns:
            (final_prompt, sources) 元组，其中 sources 是来源引用列表。
        """
        # 自动检索（如果未提供预检索结果）
        if knowledge_chunks is None:
            knowledge_chunks = self.search(user_message, top_k=top_k, user_id=user_id)

        # 构建知识上下文块
        context_block, sources = self.build_context_block(knowledge_chunks)

        # 构建 RAG 增强后的完整 Prompt
        default_system = (
            "你是星伴（StarPal）的计算机网络专业助教，"
            "擅长用通俗且结构化的方式讲解计算机网络概念与原理。"
        )

        base_system = system_prompt or default_system

        # RAG 引用规则
        if context_block:
            rag_instructions = (
                "\n\n【重要：知识引用规则】\n"
                "1. 你必须基于以下【参考资料】回答用户问题。\n"
                "2. 在回答中引用资料时使用编号标注，例如 [1]、[2]。\n"
                "3. 如果参考资料不充分，可以基于你的专业知识补充，"
                "但必须明确标注「以下内容基于通用知识，非参考资料」。\n"
                "4. 在回答末尾，列出【📚 参考来源】区块，列出所有引用的来源编号、"
                "书名/标准编号、章节和标题。"
            )
            full_system = base_system + rag_instructions
            # 组装最终 Prompt
            final_prompt = (
                f"{full_system}\n\n"
                f"{context_block}\n\n"
                f"【用户问题】\n{user_message}"
            )
        else:
            final_prompt = f"{base_system}\n\n{user_message}"

        return final_prompt, sources

    def build_context_block(
        self, chunks: List[Dict[str, Any]]
    ) -> tuple:
        """将知识块列表格式化为 Prompt 中的参考资料区块。

        Args:
            chunks: 知识块列表。

        Returns:
            (context_block_text, sources_list) 元组。
            context_block_text: 格式化的参考资料文本。
            sources_list: 来源引用列表（用于前端展示）。
        """
        if not chunks:
            return "", []

        lines = ["【参考资料】（来自星伴知识库检索）", ""]
        sources = []

        for i, chunk in enumerate(chunks, 1):
            source_title = chunk.get("source", "未知来源")
            doc_title = chunk.get("doc_title", "未知文档")
            source_page = chunk.get("source_page", "")
            doc_type = chunk.get("doc_type", "")

            # 构建来源描述
            if source_page:
                source_desc = f"{source_title} · {doc_title} · {source_page}"
            else:
                source_desc = f"{source_title} · {doc_title}"

            # 来源引用
            sources.append({
                "index": i,
                "title": doc_title,
                "source": source_title,
                "source_page": source_page,
                "chunk_id": chunk.get("chunk_id"),
                "score": round(chunk.get("score", 0), 3),
                "source_type": chunk.get("source_type", "system"),
            })

            # 知识块内容（截断过长内容）
            content = chunk.get("content", "")
            if len(content) > 600:
                content = content[:600] + "..."

            lines.append(f"[{i}] {source_desc}")
            lines.append(f"    {content}")
            lines.append("")

        return "\n".join(lines), sources

    # ================================================================
    # 索引管理
    # ================================================================

    def index_chunks(
        self, doc_id: int, chunks_data: List[Dict[str, Any]],
        user_id: Optional[int] = None,
    ) -> int:
        """将知识块索引到 ChromaDB。

        先插入 MySQL knowledge_chunks 表，再生成嵌入向量并写入 ChromaDB。

        Args:
            doc_id: 所属文档 ID。
            chunks_data: 块数据列表，每项包含:
              chunk_index, content, sub_topic_id (可选)
            user_id: 可选，关联的用户 ID。
                     None → 系统知识库（ChromaDB metadata: user_id="system"）
                     具体值 → 个人资料库（ChromaDB metadata: user_id="<user_id>"）

        Returns:
            成功索引的块数量。
        """
        if not chunks_data:
            return 0

        conn = get_connection()
        if not conn:
            print("[RAGService] 数据库连接失败，无法索引块")
            return 0

        # ChromaDB metadata 中的 user_id 标记
        metadata_user_id = "system" if user_id is None else str(user_id)

        indexed = 0
        try:
            cursor = conn.cursor()

            # 收集待嵌入的文本和已分配的 chunk_id
            pending_embeddings = []  # [(chunk_id, content), ...]

            for chunk in chunks_data:
                content = chunk.get("content", "")
                chunk_index = chunk.get("chunk_index", 0)
                sub_topic_id = chunk.get("sub_topic_id")

                if not content.strip():
                    continue

                content_hash = EmbeddingService.compute_content_hash(content)
                token_count = EmbeddingService.estimate_tokens(content)

                # 检查是否已存在（通过 content_hash 去重）
                cursor.execute(
                    """SELECT chunk_id FROM knowledge_chunks
                       WHERE doc_id = %s AND content_hash = %s""",
                    (doc_id, content_hash),
                )
                existing = cursor.fetchone()
                if existing:
                    pending_embeddings.append((existing[0], content))
                    continue

                # 插入 MySQL
                cursor.execute(
                    """INSERT INTO knowledge_chunks
                       (doc_id, chunk_index, content, content_hash, token_count, sub_topic_id)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (doc_id, chunk_index, content, content_hash, token_count, sub_topic_id),
                )
                conn.commit()
                chunk_id = cursor.lastrowid
                pending_embeddings.append((chunk_id, content))

            # 批量生成嵌入并写入 ChromaDB
            if pending_embeddings:
                texts = [t for _, t in pending_embeddings]
                embeddings = self._embedding.embed_batch(texts)

                if embeddings and len(embeddings) == len(pending_embeddings):
                    chroma_ids = [str(cid) for cid, _ in pending_embeddings]
                    metadatas = [{"user_id": metadata_user_id} for _ in pending_embeddings]
                    self._collection.add(
                        ids=chroma_ids,
                        embeddings=embeddings,
                        metadatas=metadatas,
                    )
                    indexed = len(pending_embeddings)
                    print(f"[RAGService] 已索引 {indexed} 个块到 ChromaDB (user_id={metadata_user_id})")
                else:
                    print("[RAGService] 嵌入生成失败，块已存入 MySQL 但未索引到 ChromaDB")

        except Exception as e:
            print(f"[RAGService] 索引块失败: {e}")
        finally:
            cursor.close()
            conn.close()

        return indexed

    def delete_chunks(self, chunk_ids: List[int]) -> int:
        """从 ChromaDB 中删除知识块。

        Args:
            chunk_ids: 要删除的块 ID 列表。

        Returns:
            成功删除的数量。
        """
        if not chunk_ids:
            return 0

        try:
            str_ids = [str(cid) for cid in chunk_ids]
            self._collection.delete(ids=str_ids)
            return len(str_ids)
        except Exception as e:
            print(f"[RAGService] 删除 ChromaDB 块失败: {e}")
            return 0

    # ================================================================
    # 内部方法
    # ================================================================

    def _fetch_chunks_by_ids(
        self,
        chroma_ids: List[str],
        distances: List[float],
        doc_type: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """从 MySQL 查询知识块的完整内容和元数据。

        Args:
            chroma_ids: ChromaDB 返回的 chunk_id 列表（字符串格式）。
            distances: ChromaDB 返回的距离值列表（余弦距离）。
            doc_type: 可选，过滤文档类型。
            user_id: 可选，过滤用户范围。

        Returns:
            知识块列表，score 由余弦距离转换而来 (1.0 - distance)。
        """
        if not chroma_ids:
            return []

        conn = get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)

            # 构建 IN 查询
            int_ids = [int(cid) for cid in chroma_ids if cid.isdigit()]
            if not int_ids:
                return []

            placeholders = ",".join(["%s"] * len(int_ids))
            sql = """
                SELECT
                    kc.chunk_id,
                    kc.content,
                    kc.chunk_index,
                    kd.title AS doc_title,
                    kd.doc_type,
                    kd.source,
                    kd.source_page,
                    kd.knowledge_points,
                    kd.user_id,
                    kst.sub_topic_name
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.doc_id = kd.doc_id
                LEFT JOIN knowledge_sub_topics kst ON kc.sub_topic_id = kst.sub_topic_id
                WHERE kc.chunk_id IN ({})
            """.format(placeholders)

            params = list(int_ids)
            if doc_type:
                sql += " AND kd.doc_type = %s"
                params.append(doc_type)

            cursor.execute(sql, params)

            rows = cursor.fetchall() or []

            # 构建 id → distance 映射
            id_dist_map = {}
            for cid, dist in zip(chroma_ids, distances):
                if cid.isdigit():
                    id_dist_map[int(cid)] = dist

            # 组装结果
            chunks = []
            for row in rows:
                cid = row["chunk_id"]
                cosine_dist = id_dist_map.get(cid, 1.0)
                # 余弦距离 [0, 2] → 相似度 [0, 1]
                score = max(0.0, min(1.0, 1.0 - cosine_dist / 2.0))

                # 解析知识点 JSON 数组
                kps_raw = row.get("knowledge_points", "")
                knowledge_points = []
                if kps_raw and isinstance(kps_raw, str):
                    try:
                        knowledge_points = json.loads(kps_raw)
                    except json.JSONDecodeError:
                        knowledge_points = [kps_raw]

                user_id_val = row.get("user_id")
                source_type = "system" if user_id_val is None else "personal"

                chunks.append({
                    "chunk_id": cid,
                    "content": row["content"],
                    "chunk_index": row["chunk_index"],
                    "doc_title": row["doc_title"],
                    "doc_type": row["doc_type"],
                    "source": row["source"],
                    "source_page": row.get("source_page", ""),
                    "knowledge_points": knowledge_points,
                    "sub_topic_name": row.get("sub_topic_name", ""),
                    "score": round(score, 4),
                    "source_type": source_type,
                })

            return chunks

        except Exception as e:
            print(f"[RAGService] MySQL 查询块失败: {e}")
            return []
        finally:
            cursor.close()
            conn.close()

    def _keyword_search(
        self,
        query: str,
        top_k: int = RAG_DEFAULT_TOP_K,
        doc_type: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """MySQL 关键词搜索（RAG 回退方案）。

        当向量检索失败或无结果时，使用 MySQL LIKE 进行关键词匹配。

        Args:
            query: 搜索关键词。
            top_k: 返回结果数。
            doc_type: 可选，文档类型过滤。
            user_id: 可选，限定用户范围（None=系统，具体值=个人）。

        Returns:
            知识块列表。
        """
        conn = get_connection()
        if not conn:
            return []

        try:
            cursor = conn.cursor(dictionary=True)

            # 构造 LIKE 条件
            keywords = [kw.strip() for kw in query.split() if len(kw.strip()) >= 2]
            if not keywords:
                return []

            like_clauses = " OR ".join(["kc.content LIKE %s"] * len(keywords))
            like_params = [f"%{kw}%" for kw in keywords]

            sql = f"""
                SELECT
                    kc.chunk_id,
                    kc.content,
                    kc.chunk_index,
                    kd.title AS doc_title,
                    kd.doc_type,
                    kd.source,
                    kd.source_page,
                    kd.knowledge_points,
                    kd.user_id,
                    kst.sub_topic_name
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.doc_id = kd.doc_id
                LEFT JOIN knowledge_sub_topics kst ON kc.sub_topic_id = kst.sub_topic_id
                WHERE ({like_clauses})
                  AND kd.status = 'published'
            """

            params = like_params
            if doc_type:
                sql += " AND kd.doc_type = %s"
                params.append(doc_type)

            if user_id is not None:
                sql += " AND kd.user_id = %s"
                params.append(user_id)
            else:
                sql += " AND kd.user_id IS NULL"

            sql += " LIMIT %s"
            params.append(top_k * 2)

            cursor.execute(sql, params)
            rows = cursor.fetchall() or []

            chunks = []
            for row in rows:
                kps_raw = row.get("knowledge_points", "")
                knowledge_points = []
                if kps_raw and isinstance(kps_raw, str):
                    try:
                        knowledge_points = json.loads(kps_raw)
                    except json.JSONDecodeError:
                        knowledge_points = [kps_raw]

                user_id_val = row.get("user_id")
                source_type = "system" if user_id_val is None else "personal"

                chunks.append({
                    "chunk_id": row["chunk_id"],
                    "content": row["content"],
                    "chunk_index": row["chunk_index"],
                    "doc_title": row["doc_title"],
                    "doc_type": row["doc_type"],
                    "source": row["source"],
                    "source_page": row.get("source_page", ""),
                    "knowledge_points": knowledge_points,
                    "sub_topic_name": row.get("sub_topic_name", ""),
                    "score": 0.25,  # 关键词匹配的基准分
                    "source_type": source_type,
                })

            return chunks[:top_k]

        except Exception as e:
            print(f"[RAGService] 关键词搜索失败: {e}")
            return []
        finally:
            cursor.close()
            conn.close()


# ================================================================
# 模块独立测试
# ================================================================
if __name__ == "__main__":
    print("=== RAG Service 模块测试 ===\n")

    rag = RAGService()
    print(f"ChromaDB 持久化目录: {rag._persist_dir}")
    print(f"集合名称: {CHROMADB_COLLECTION_NAME}")
    print(f"集合内已有块数: {rag._collection.count()}")

    # 测试检索（需要先有数据）
    if rag._collection.count() > 0:
        print("\n--- 测试检索: 'TCP三次握手' ---")
        results = rag.search("TCP三次握手的过程", top_k=3)
        for r in results:
            print(f"  [{r['score']:.3f}] {r['doc_title']}: {r['content'][:80]}...")
    else:
        print("\n（知识库为空，跳过检索测试。请先运行 seed_knowledge.py 导入数据。）")
