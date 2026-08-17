"""
知识点映射服务 —— 星伴(StarPal) 资料内容自动关联知识点体系。

核心功能:
  1. 将文本块(Chunk)自动映射到已有的 71 个子知识点体系
  2. 映射算法: chunk向量 × 子知识点描述向量 → 余弦相似度 → top-N 匹配
  3. 子知识点描述向量预计算并内存缓存（避免每次映射重复计算）
  4. 生成用户级和文档级的知识点覆盖报告

用法:
    from server.knowledge_mapper import KnowledgeMapper

    mapper = KnowledgeMapper()
    # 对单个 chunk 做映射
    match = mapper.map_chunk_to_topics("TCP连接需要经过三次握手...")
    # match → [(sub_topic_id, sub_topic_name, similarity), ...]

    # 分析整个文档的覆盖
    report = mapper.analyze_document(doc_id)
    # 获取用户覆盖度
    coverage = mapper.get_user_coverage(user_id=1)
"""

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from AI_operate.embedding_service import EmbeddingService
from database.db_connector import get_connection

# 余弦相似度阈值：高于此值才认为匹配成功
SIMILARITY_THRESHOLD = 0.6
# 每个 chunk 返回的 top-N 候选知识点
TOP_N_CANDIDATES = 3


class KnowledgeMapper:
    """知识点自动映射器。

    工作原理:
      - 启动时从 MySQL 加载所有子知识点名称和描述
      - 预计算每个子知识点的描述向量（内存缓存）
      - 对输入的文本块，生成向量后与所有子知识点向量计算余弦相似度
      - 返回超过阈值的 top-N 匹配结果
    """

    def __init__(self):
        """初始化映射器，预加载子知识点并缓存向量。"""
        self._topics: List[Dict[str, Any]] = []  # 子知识点列表
        self._topic_vectors: Optional[np.ndarray] = None  # 预计算的向量矩阵 (N_topics × 384)
        self._embedding = EmbeddingService()
        self._loaded = False

    # ================================================================
    # 公开方法
    # ================================================================

    def ensure_loaded(self) -> None:
        """确保子知识点数据已加载（懒加载，首次调用时触发）。"""
        if not self._loaded:
            self._load_topics()
            self._precompute_topic_vectors()
            self._loaded = True

    def map_chunk_to_topics(
        self, text: str, top_n: int = TOP_N_CANDIDATES
    ) -> List[Dict[str, Any]]:
        """将单个文本块映射到知识点。

        Args:
            text: 文本块内容。
            top_n: 返回的候选知识点数量。

        Returns:
            匹配结果列表，按相似度降序排列:
            [{sub_topic_id, sub_topic_name, parent_kp, similarity}, ...]
            仅返回相似度 > SIMILARITY_THRESHOLD 的结果。
        """
        self.ensure_loaded()

        if not text or not text.strip():
            return []

        if self._topic_vectors is None or len(self._topics) == 0:
            print("[KnowledgeMapper] 子知识点为空，跳过映射")
            return []

        # 生成文本块向量
        chunk_vec = self._embedding.embed_single(text.strip())
        if chunk_vec is None:
            print("[KnowledgeMapper] 文本块嵌入生成失败")
            return []

        # 计算与所有子知识点的余弦相似度
        chunk_arr = np.array(chunk_vec)
        chunk_norm = np.linalg.norm(chunk_arr)
        if chunk_norm == 0:
            return []

        # 批量余弦相似度计算
        similarities = np.dot(self._topic_vectors, chunk_arr) / (
            np.linalg.norm(self._topic_vectors, axis=1) * chunk_norm
        )

        # 筛选超过阈值的 top-N
        results = []
        for idx in np.argsort(similarities)[::-1]:
            sim = float(similarities[idx])
            if sim < SIMILARITY_THRESHOLD:
                break
            topic = self._topics[idx]
            results.append({
                "sub_topic_id": topic["sub_topic_id"],
                "sub_topic_name": topic["sub_topic_name"],
                "parent_kp": topic["parent_kp"],
                "similarity": round(sim, 4),
            })
            if len(results) >= top_n:
                break

        return results

    def analyze_document(self, doc_id: int) -> Dict[str, Any]:
        """分析单个文档的知识点覆盖情况。

        遍历文档下所有 chunk，对每个 chunk 做映射，
        汇总得到文档级和知识点级的覆盖报告。

        Args:
            doc_id: 文档 ID。

        Returns:
            {
                doc_id, doc_title,
                mapped_chunks: int,       # 成功映射的 chunk 数
                total_chunks: int,        # 总 chunk 数
                covered_topics: [...],    # 覆盖到的知识点列表
            }
        """
        self.ensure_loaded()

        conn = get_connection()
        if not conn:
            return {"doc_id": doc_id, "error": "数据库连接失败"}

        try:
            cursor = conn.cursor(dictionary=True)

            # 获取文档信息
            cursor.execute(
                "SELECT doc_id, title FROM knowledge_documents WHERE doc_id = %s",
                (doc_id,),
            )
            doc = cursor.fetchone()
            if not doc:
                return {"doc_id": doc_id, "error": "文档不存在"}

            # 获取文档所有 chunk
            cursor.execute(
                "SELECT chunk_id, content FROM knowledge_chunks WHERE doc_id = %s ORDER BY chunk_index",
                (doc_id,),
            )
            chunks = cursor.fetchall() or []

            # 逐 chunk 映射
            topic_hits: Dict[int, Dict[str, Any]] = {}  # sub_topic_id → 聚合信息
            mapped_count = 0

            for chunk in chunks:
                matches = self.map_chunk_to_topics(chunk["content"])
                if not matches:
                    continue

                mapped_count += 1
                best_match = matches[0]  # 最强匹配作为主关联

                # 更新 MySQL 中 chunk 的 sub_topic_id
                cursor.execute(
                    "UPDATE knowledge_chunks SET sub_topic_id = %s WHERE chunk_id = %s",
                    (best_match["sub_topic_id"], chunk["chunk_id"]),
                )
                conn.commit()

                # 聚合到知识点
                tid = best_match["sub_topic_id"]
                if tid not in topic_hits:
                    topic_hits[tid] = {
                        "sub_topic_id": tid,
                        "sub_topic_name": best_match["sub_topic_name"],
                        "parent_kp": best_match["parent_kp"],
                        "chunk_count": 0,
                        "max_similarity": 0.0,
                    }
                topic_hits[tid]["chunk_count"] += 1
                topic_hits[tid]["max_similarity"] = max(
                    topic_hits[tid]["max_similarity"],
                    best_match["similarity"],
                )

            # 文档映射更新 → 标记关联的卡片失效
            if topic_hits:
                try:
                    from server.learning_card_service import LearningCardService
                    card_svc = LearningCardService()
                    card_svc.invalidate_cards_for_document(doc_id)
                except Exception as e:
                    print(f"[KnowledgeMapper] 卡片失效调用失败: {e}")

            return {
                "doc_id": doc_id,
                "doc_title": doc["title"],
                "mapped_chunks": mapped_count,
                "total_chunks": len(chunks),
                "coverage_pct": round(len(topic_hits) / max(len(self._topics), 1) * 100, 1),
                "covered_topics": sorted(
                    topic_hits.values(),
                    key=lambda x: x["chunk_count"],
                    reverse=True,
                ),
            }

        except Exception as e:
            print(f"[KnowledgeMapper] 分析文档失败: {e}")
            return {"doc_id": doc_id, "error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def get_user_coverage(
        self, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取用户（或系统）的知识点覆盖度。

        汇总 knowledge_chunks 中所有关联了 sub_topic_id 的记录，
        按知识点聚合，生成覆盖度摘要。

        Args:
            user_id: 用户 ID。
                     None → 系统知识库（knowledge_documents.user_id IS NULL）
                     具体值 → 个人资料库。

        Returns:
            {
                total_sub_topics: 71,
                covered_count: 23,
                coverage_pct: 32.4,
                details: [{sub_topic_id, sub_topic_name, parent_kp,
                           status: "covered"|"uncovered",
                           chunk_count, doc_count}, ...]
            }
        """
        self.ensure_loaded()

        conn = get_connection()
        if not conn:
            return {"error": "数据库连接失败"}

        try:
            cursor = conn.cursor(dictionary=True)

            # 查询该范围内已关联知识点的情况
            if user_id is None:
                # 系统知识库
                where_clause = "kd.user_id IS NULL"
            else:
                where_clause = "kd.user_id = %s"

            sql = f"""
                SELECT
                    kc.sub_topic_id,
                    COUNT(DISTINCT kc.chunk_id) AS chunk_count,
                    COUNT(DISTINCT kc.doc_id) AS doc_count
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.doc_id = kd.doc_id
                WHERE kc.sub_topic_id IS NOT NULL
                  AND {where_clause}
                GROUP BY kc.sub_topic_id
            """

            params = (user_id,) if user_id is not None else ()
            cursor.execute(sql, params)
            coverage_rows = {r["sub_topic_id"]: r for r in (cursor.fetchall() or [])}

            # 构建完整的 71 个子知识点覆盖详情
            details = []
            covered_count = 0
            for topic in self._topics:
                tid = topic["sub_topic_id"]
                row = coverage_rows.get(tid)
                if row:
                    covered_count += 1
                    details.append({
                        "sub_topic_id": tid,
                        "sub_topic_name": topic["sub_topic_name"],
                        "parent_kp": topic["parent_kp"],
                        "status": "covered",
                        "chunk_count": row["chunk_count"],
                        "doc_count": row["doc_count"],
                    })
                else:
                    details.append({
                        "sub_topic_id": tid,
                        "sub_topic_name": topic["sub_topic_name"],
                        "parent_kp": topic["parent_kp"],
                        "status": "uncovered",
                        "chunk_count": 0,
                        "doc_count": 0,
                    })

            return {
                "total_sub_topics": len(self._topics),
                "covered_count": covered_count,
                "coverage_pct": round(
                    covered_count / max(len(self._topics), 1) * 100, 1
                ),
                "details": details,
            }

        except Exception as e:
            print(f"[KnowledgeMapper] 获取覆盖度失败: {e}")
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def get_node_detail(
        self, sub_topic_id: int, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取知识图谱节点的下钻详情。

        返回该知识点关联的所有文档及知识块内容摘要。

        Args:
            sub_topic_id: 子知识点 ID。
            user_id: 同 get_user_coverage。

        Returns:
            {
                sub_topic_name, parent_kp,
                documents: [{doc_id, title, doc_type, chunk_count,
                             chunks_preview: [{chunk_id, content(截断)}, ...]}]
            }
        """
        self.ensure_loaded()

        conn = get_connection()
        if not conn:
            return {"error": "数据库连接失败"}

        try:
            cursor = conn.cursor(dictionary=True)

            # 知识点信息
            topic_info = None
            for t in self._topics:
                if t["sub_topic_id"] == sub_topic_id:
                    topic_info = t
                    break
            if not topic_info:
                return {"error": "子知识点不存在"}

            # 构建用户过滤条件
            if user_id is None:
                where_clause = "kd.user_id IS NULL"
                params = (sub_topic_id,)
            else:
                where_clause = "kd.user_id = %s"
                params = (sub_topic_id, user_id)

            # 查询关联文档
            sql = f"""
                SELECT
                    kd.doc_id, kd.title, kd.doc_type,
                    COUNT(kc.chunk_id) AS chunk_count
                FROM knowledge_chunks kc
                JOIN knowledge_documents kd ON kc.doc_id = kd.doc_id
                WHERE kc.sub_topic_id = %s AND {where_clause}
                GROUP BY kd.doc_id, kd.title, kd.doc_type
                ORDER BY chunk_count DESC
            """
            cursor.execute(sql, params)
            doc_rows = cursor.fetchall() or []

            documents = []
            for doc_row in doc_rows:
                # 取该文档下该知识点的前 3 个 chunk 内容预览
                cursor.execute(
                    """SELECT chunk_id, content FROM knowledge_chunks
                       WHERE doc_id = %s AND sub_topic_id = %s
                       ORDER BY chunk_index LIMIT 3""",
                    (doc_row["doc_id"], sub_topic_id),
                )
                chunk_rows = cursor.fetchall() or []
                chunks_preview = []
                for cr in chunk_rows:
                    content = cr["content"]
                    if len(content) > 200:
                        content = content[:200] + "..."
                    chunks_preview.append({
                        "chunk_id": cr["chunk_id"],
                        "content": content,
                    })

                documents.append({
                    "doc_id": doc_row["doc_id"],
                    "title": doc_row["title"],
                    "doc_type": doc_row["doc_type"],
                    "chunk_count": doc_row["chunk_count"],
                    "chunks_preview": chunks_preview,
                })

            return {
                "sub_topic_id": sub_topic_id,
                "sub_topic_name": topic_info["sub_topic_name"],
                "parent_kp": topic_info["parent_kp"],
                "documents": documents,
            }

        except Exception as e:
            print(f"[KnowledgeMapper] 获取节点详情失败: {e}")
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()

    def get_knowledge_graph(
        self, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取知识图谱数据（节点 + 连线 + 覆盖度）。

        返回 ECharts 力导向图所需的数据结构。
        所有同轨资料合并为一张图。

        Args:
            user_id: 同 get_user_coverage。

        Returns:
            {nodes: [...], links: [...], categories: [...]}
        """
        conn = get_connection()
        if not conn:
            return {"error": "数据库连接失败"}

        try:
            cursor = conn.cursor(dictionary=True)

            # 获取知识关系（连线）
            cursor.execute(
                "SELECT source_kp, target_kp, relation_type, description "
                "FROM knowledge_relations"
            )
            relations = cursor.fetchall() or []

            # 获取覆盖度数据
            coverage = self.get_user_coverage(user_id=user_id)
            if "error" in coverage:
                return coverage

            # 构建节点列表
            # 使用粗粒度知识点（parent_kp）作为图节点
            # 节点大小 = 该粗粒度下被覆盖的子知识点数量
            kp_coverage: Dict[str, Dict[str, Any]] = {}
            for detail in coverage.get("details", []):
                pkp = detail["parent_kp"]
                if pkp not in kp_coverage:
                    kp_coverage[pkp] = {
                        "name": pkp,
                        "total": 0,
                        "covered": 0,
                        "chunk_count": 0,
                        "doc_count": 0,
                    }
                kp_coverage[pkp]["total"] += 1
                kp_coverage[pkp]["chunk_count"] += detail.get("chunk_count", 0)
                kp_coverage[pkp]["doc_count"] += detail.get("doc_count", 0)
                if detail["status"] == "covered":
                    kp_coverage[pkp]["covered"] += 1

            nodes = []
            links = []
            seen_kps = set()

            for name, info in kp_coverage.items():
                coverage_ratio = info["covered"] / max(info["total"], 1)
                # 节点颜色: 绿色(>=0.5), 黄色(>0 & <0.5), 灰色(=0)
                if coverage_ratio >= 0.5:
                    category = 0  # 已覆盖
                elif coverage_ratio > 0:
                    category = 1  # 部分覆盖
                else:
                    category = 2  # 未覆盖

                symbol_size = max(20, min(80, 20 + info["chunk_count"] * 3))

                nodes.append({
                    "id": name,
                    "name": name,
                    "category": category,
                    "symbolSize": symbol_size,
                    "coverage": round(coverage_ratio, 2),
                    "value": info["chunk_count"],
                })
                seen_kps.add(name)

            # 构建连线（只保留两端节点都存在的）
            for rel in relations:
                src = rel["source_kp"]
                tgt = rel["target_kp"]
                if src in seen_kps and tgt in seen_kps:
                    link = {
                        "source": src,
                        "target": tgt,
                        "label": rel.get("relation_type", ""),
                    }
                    # 去重
                    if link not in links:
                        links.append(link)

            return {
                "nodes": nodes,
                "links": links,
                "categories": [
                    {"name": "已覆盖", "itemStyle": {"color": "#22C55E"}},
                    {"name": "部分覆盖", "itemStyle": {"color": "#F59E0B"}},
                    {"name": "未覆盖", "itemStyle": {"color": "#9CA3AF"}},
                ],
            }

        except Exception as e:
            print(f"[KnowledgeMapper] 获取知识图谱失败: {e}")
            return {"error": str(e)}
        finally:
            cursor.close()
            conn.close()

    # ================================================================
    # 内部方法
    # ================================================================

    def _load_topics(self) -> None:
        """从 MySQL 加载所有子知识点。"""
        conn = get_connection()
        if not conn:
            print("[KnowledgeMapper] 数据库连接失败，无法加载子知识点")
            self._topics = []
            return

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """SELECT sub_topic_id, sub_topic_name, parent_kp, description
                   FROM knowledge_sub_topics ORDER BY sub_topic_id"""
            )
            rows = cursor.fetchall() or []
            self._topics = [
                {
                    "sub_topic_id": r["sub_topic_id"],
                    "sub_topic_name": r["sub_topic_name"],
                    "parent_kp": r["parent_kp"],
                    "description": r.get("description") or r["sub_topic_name"],
                }
                for r in rows
            ]
            print(f"[KnowledgeMapper] 已加载 {len(self._topics)} 个子知识点")
        except Exception as e:
            print(f"[KnowledgeMapper] 加载子知识点失败: {e}")
            self._topics = []
        finally:
            cursor.close()
            conn.close()

    def _precompute_topic_vectors(self) -> None:
        """预计算所有子知识点描述文本的嵌入向量，并缓存为矩阵。"""
        if not self._topics:
            self._topic_vectors = None
            return

        # 构造描述文本：名称 + 简介
        descriptions = [
            f"{t['sub_topic_name']}：{t['description']}" for t in self._topics
        ]

        print(f"[KnowledgeMapper] 正在预计算 {len(descriptions)} 个子知识点向量...")
        embeddings = self._embedding.embed_batch(descriptions)

        if embeddings and len(embeddings) == len(descriptions):
            self._topic_vectors = np.array(embeddings)
            print(f"[KnowledgeMapper] 向量预计算完成 ({self._topic_vectors.shape})")
        else:
            print("[KnowledgeMapper] 向量预计算失败")
            self._topic_vectors = None


# 模块独立测试
if __name__ == "__main__":
    mapper = KnowledgeMapper()

    print("=== 知识点映射测试 ===\n")

    # 测试单个 chunk 映射
    test_chunks = [
        "TCP 连接建立需要经过三次握手过程。首先客户端发送 SYN 包...",
        "UDP 是无连接的传输层协议，不保证可靠交付...",
    ]

    for i, text in enumerate(test_chunks, 1):
        print(f"\n--- Chunk {i}: {text[:50]}... ---")
        matches = mapper.map_chunk_to_topics(text)
        for m in matches:
            print(f"  {m['sub_topic_name']} ({m['parent_kp']}): {m['similarity']:.3f}")
        if not matches:
            print("  (无匹配)")

    # 测试覆盖度
    print("\n--- 系统知识库覆盖度 ---")
    coverage = mapper.get_user_coverage(user_id=None)
    if "error" not in coverage:
        print(f"  总知识点: {coverage['total_sub_topics']}")
        print(f"  已覆盖: {coverage['covered_count']} ({coverage['coverage_pct']}%)")
