"""
学习卡片服务 —— 星伴(StarPal) 知识库学习呈现核心引擎。

提供知识点学习卡片的生成、缓存、失效管理。

核心功能:
  1. 逐级展开卡片：精简版（同步，~5-10s）+ 完整版（SSE流式，~20-40s）
  2. MySQL 持久化缓存，按(sub_topic_id, user_id)粒度
  3. 卡片失效：源文档变更时自动标记 is_regenerating=1
  4. 懒生成：首次访问时生成，后续从缓存读取

架构:
  LearningCardService (本文件)
    ├── generate_slim_card()      → 同步调用 DeepSeek → 精简版（200-400字）
    ├── generate_full_card()      → SSE 流式调用 DeepSeek → 完整版（800-1500字）
    ├── get_card()                → 读缓存（未命中则触发生成）
    ├── invalidate_cards_for_document()  → 文档变更 → 标记相关卡片失效
    └── invalidate_cards_for_sub_topic() → 知识点重新映射 → 标记卡片失效

用法:
    from server.learning_card_service import LearningCardService

    svc = LearningCardService()
    card = svc.get_card(sub_topic_id=5, user_id=1)
    # card → {slim_content, full_content, source_doc_ids, ...}
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from AI_operate.deepseek_chat import deepseek_chat
# get_connection 在方法内部懒加载，避免模块导入时触发 MySQL 连接池初始化


class LearningCardService:
    """知识点学习卡片服务。

    卡片内容结构:
      - 精简版 (slim):
        * 定义（一句话概括该知识点）
        * 核心要点（3-5条，每条一行）
        * 来源（涉及的文档名称列表）

      - 完整版 (full):
        * 详细讲解（含原理、工作机制等，3-5段）
        * 常见误区（1-3个典型错误理解及纠正）
        * 记忆口诀（便于记忆的技巧或口诀）
        * 关联概念（相关知识点及关系说明）
        * 例题链接（相关题库中的题目编号，可直接跳转练习）
    """

    # 精简版 prompt 模板
    SLIM_PROMPT = """你是一位计算机网络讲师。请根据以下资料，为知识点「{topic_name}」生成一份精简学习卡片。

## 知识点信息
- 知识点名称: {topic_name}
- 所属分类: {parent_kp}
- 知识点描述: {description}

## 相关资料内容
{source_content}

## 要求
请严格按以下格式输出（不要使用markdown代码块标记，直接输出内容）：

【定义】
一句话概括该知识点（不超过80字）。

【核心要点】
- 要点1
- 要点2
- 要点3
- 要点4
- 要点5

【来源】
- 文档A
- 文档B
"""

    # 完整版 prompt 模板
    FULL_PROMPT = """你是一位资深的计算机网络教授。请根据以下资料，为知识点「{topic_name}」生成一份完整的学习讲义。

## 知识点信息
- 知识点名称: {topic_name}
- 所属分类: {parent_kp}
- 知识点描述: {description}

## 相关资料内容
{source_content}

## 要求
请严格按以下格式输出（不要使用markdown代码块标记）：

【详细讲解】
用3-5个自然段详细讲解该知识点，包括：
- 基本概念与背景
- 工作原理与机制
- 实际应用场景
- 与其他知识点的联系

每段之间空一行。

【常见误区】
列出1-3个学生常见的错误理解，并给出正确解释。

【记忆口诀】
提供一个简洁的记忆技巧或口诀（如果没有合适的，可以说"暂无"）。

【关联概念】
- 前置知识: xxx（学习本知识点前需要掌握的内容）
- 后继知识: xxx（学完本知识点后可以继续学习的内容）
- 对比概念: xxx（容易混淆的相关概念及区别）

【相关题目】
如果有相关题目，列出题目编号和简要描述，方便学生去题库练习。
"""

    def __init__(self):
        """初始化服务。"""

    @staticmethod
    def _get_conn():
        """懒加载数据库连接（避免模块导入时触发连接池初始化）。"""
        from database.db_connector import get_connection
        return get_connection()

    # ================================================================
    # 公开方法: 卡片获取与生成
    # ================================================================

    def get_card(
        self,
        sub_topic_id: int,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """获取知识点学习卡片（优先从缓存读取）。

        Args:
            sub_topic_id: 子知识点 ID。
            user_id: None=系统知识库，具体值=个人资料库。

        Returns:
            {
                sub_topic_id, sub_topic_name, parent_kp,
                slim_content, full_content, source_doc_ids,
                is_regenerating, generated_at, from_cache
            }
        """
        # 1. 尝试从缓存读取
        cached = self._get_cached_card(sub_topic_id, user_id)
        if cached and not cached.get("is_regenerating"):
            cached["from_cache"] = True
            return cached

        # 2. 获取知识点基础信息
        topic_info = self._get_topic_info(sub_topic_id)
        if not topic_info:
            return {"error": "知识点不存在", "sub_topic_id": sub_topic_id}

        # 3. 收集来源资料
        sources = self._collect_source_content(sub_topic_id, user_id)

        # 4. 生成精简版（同步）
        slim = self._generate_slim(topic_info, sources)

        # 5. 写入缓存
        self._save_card(sub_topic_id, user_id, slim, None, sources.get("doc_ids", []))

        result = {
            "sub_topic_id": sub_topic_id,
            "sub_topic_name": topic_info["sub_topic_name"],
            "parent_kp": topic_info["parent_kp"],
            "slim_content": slim,
            "full_content": None,
            "source_doc_ids": sources.get("doc_ids", []),
            "is_regenerating": False,
            "from_cache": False,
        }
        return result

    def generate_full_card_stream(
        self,
        sub_topic_id: int,
        user_id: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """SSE 流式生成完整版学习卡片。

        先确保精简版已生成（如未生成则同步生成），
        然后流式生成完整版内容。

        Args:
            sub_topic_id: 子知识点 ID。
            user_id: None=系统知识库，具体值=个人资料库。

        Yields:
            SSE 格式字符串: 'data: <chunk>\\n\\n'
            结束时: 'data: [DONE]\\n\\n'
        """
        topic_info = self._get_topic_info(sub_topic_id)
        if not topic_info:
            yield f"data: {json.dumps({'error': '知识点不存在'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 确保精简版存在
        card = self.get_card(sub_topic_id, user_id)
        if "error" in card:
            yield f"data: {json.dumps({'error': card['error']}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 如果已经缓存完整版，直接返回
        if card.get("full_content"):
            yield f"data: {json.dumps({'cached': True, 'full_content': card['full_content']}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 标记正在生成
        self._set_regenerating(sub_topic_id, user_id, True)

        # 收集来源资料
        sources = self._collect_source_content(sub_topic_id, user_id)

        # 构建 prompt
        prompt = self.FULL_PROMPT.format(
            topic_name=topic_info["sub_topic_name"],
            parent_kp=topic_info["parent_kp"],
            description=topic_info.get("description", topic_info["sub_topic_name"]),
            source_content=sources.get("text", "暂无相关资料"),
        )

        # 流式调用 AI
        full_content_parts = []
        try:
            for chunk in deepseek_chat.chat_with_deepseek_stream(prompt):
                full_content_parts.append(chunk)
                yield f"data: {json.dumps({'chunk': chunk}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'AI 生成失败: {str(e)}'}, ensure_ascii=False)}\n\n"
            self._set_regenerating(sub_topic_id, user_id, False)
            yield "data: [DONE]\n\n"
            return

        # 保存完整版到缓存
        full_content = "".join(full_content_parts)
        self._save_full_content(sub_topic_id, user_id, full_content)
        self._set_regenerating(sub_topic_id, user_id, False)

        yield "data: [DONE]\n\n"

    # ================================================================
    # 公开方法: 卡片失效管理
    # ================================================================

    def invalidate_cards_for_document(self, doc_id: int) -> int:
        """当文档内容变更时，标记关联的所有卡片为待重新生成。

        在文档重新处理（映射更新）后调用。

        Args:
            doc_id: 文档 ID。

        Returns:
            失效的卡片数量。
        """
        conn = self._get_conn()
        if not conn:
            return 0

        try:
            cursor = conn.cursor()
            # 找到该文档覆盖的所有 sub_topic_id
            cursor.execute(
                "SELECT DISTINCT sub_topic_id FROM knowledge_chunks "
                "WHERE doc_id = %s AND sub_topic_id IS NOT NULL",
                (doc_id,),
            )
            topic_ids = [r[0] for r in (cursor.fetchall() or [])]

            if not topic_ids:
                return 0

            # 标记这些知识点 + 所有 user_id 组合的卡片为待重新生成
            count = 0
            for tid in topic_ids:
                cursor.execute(
                    """UPDATE knowledge_learning_cards
                       SET is_regenerating = 1
                       WHERE sub_topic_id = %s""",
                    (tid,),
                )
                count += cursor.rowcount

            conn.commit()
            if count > 0:
                print(
                    f"[LearningCardService] 文档 {doc_id} 变更，"
                    f"已标记 {count} 张卡片待重新生成"
                )
            return count

        except Exception as e:
            print(f"[LearningCardService] 失效卡片失败: {e}")
            return 0
        finally:
            cursor.close()
            conn.close()

    def invalidate_cards_for_sub_topic(self, sub_topic_id: int) -> bool:
        """标记指定子知识点的所有卡片为待重新生成。

        Args:
            sub_topic_id: 子知识点 ID。

        Returns:
            是否成功。
        """
        conn = self._get_conn()
        if not conn:
            return False

        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE knowledge_learning_cards
                   SET is_regenerating = 1
                   WHERE sub_topic_id = %s""",
                (sub_topic_id,),
            )
            conn.commit()
            return True
        except Exception as e:
            print(f"[LearningCardService] 失效卡片失败(sub_topic={sub_topic_id}): {e}")
            return False
        finally:
            cursor.close()
            conn.close()

    # ================================================================
    # 内部方法: AI 生成
    # ================================================================

    def _generate_slim(
        self,
        topic_info: Dict[str, Any],
        sources: Dict[str, Any],
    ) -> str:
        """同步生成精简版卡片内容。

        Args:
            topic_info: {sub_topic_name, parent_kp, description}
            sources: {text, doc_ids}

        Returns:
            格式化的精简版内容文本。
        """
        prompt = self.SLIM_PROMPT.format(
            topic_name=topic_info["sub_topic_name"],
            parent_kp=topic_info["parent_kp"],
            description=topic_info.get("description", topic_info["sub_topic_name"]),
            source_content=sources.get("text", "暂无相关资料"),
        )

        try:
            content = deepseek_chat.chat_with_deepseek(prompt)
            return content.strip() if content else ""
        except Exception as e:
            print(f"[LearningCardService] 精简版生成失败: {e}")
            return self._fallback_slim(topic_info, sources)

    def _fallback_slim(
        self,
        topic_info: Dict[str, Any],
        sources: Dict[str, Any],
    ) -> str:
        """精简版生成失败时的降级内容。"""
        doc_names = sources.get("doc_names", [])
        source_lines = "\n".join(f"- {n}" for n in doc_names) if doc_names else "- 暂无来源"
        return (
            f"【定义】\n"
            f"{topic_info.get('description', topic_info['sub_topic_name'])}\n\n"
            f"【核心要点】\n"
            f"- 该知识点属于{topic_info['parent_kp']}分类\n"
            f"- 详情请查看下方来源文档\n\n"
            f"【来源】\n{source_lines}"
        )

    # ================================================================
    # 内部方法: 数据访问
    # ================================================================

    def _get_cached_card(
        self,
        sub_topic_id: int,
        user_id: Optional[int],
    ) -> Optional[Dict[str, Any]]:
        """从缓存读取卡片。"""
        conn = self._get_conn()
        if not conn:
            return None

        try:
            cursor = conn.cursor(dictionary=True)
            if user_id is not None:
                cursor.execute(
                    """SELECT kc.*, kst.sub_topic_name, kst.parent_kp
                       FROM knowledge_learning_cards kc
                       JOIN knowledge_sub_topics kst ON kc.sub_topic_id = kst.sub_topic_id
                       WHERE kc.sub_topic_id = %s AND kc.user_id = %s""",
                    (sub_topic_id, user_id),
                )
            else:
                cursor.execute(
                    """SELECT kc.*, kst.sub_topic_name, kst.parent_kp
                       FROM knowledge_learning_cards kc
                       JOIN knowledge_sub_topics kst ON kc.sub_topic_id = kst.sub_topic_id
                       WHERE kc.sub_topic_id = %s AND kc.user_id IS NULL""",
                    (sub_topic_id,),
                )
            row = cursor.fetchone()
            if not row:
                return None

            source_doc_ids = []
            if row.get("source_doc_ids"):
                try:
                    source_doc_ids = json.loads(row["source_doc_ids"])
                except (json.JSONDecodeError, TypeError):
                    source_doc_ids = []

            return {
                "sub_topic_id": row["sub_topic_id"],
                "sub_topic_name": row["sub_topic_name"],
                "parent_kp": row["parent_kp"],
                "slim_content": row["slim_content"],
                "full_content": row.get("full_content"),
                "source_doc_ids": source_doc_ids,
                "is_regenerating": bool(row.get("is_regenerating", 0)),
                "generated_at": str(row["generated_at"]) if row.get("generated_at") else "",
            }
        except Exception as e:
            print(f"[LearningCardService] 读取缓存失败: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def _get_topic_info(self, sub_topic_id: int) -> Optional[Dict[str, Any]]:
        """获取知识点基本信息。"""
        conn = self._get_conn()
        if not conn:
            return None

        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                "SELECT sub_topic_id, sub_topic_name, parent_kp, description "
                "FROM knowledge_sub_topics WHERE sub_topic_id = %s",
                (sub_topic_id,),
            )
            row = cursor.fetchone()
            return row if row else None
        except Exception as e:
            print(f"[LearningCardService] 获取知识点信息失败: {e}")
            return None
        finally:
            cursor.close()
            conn.close()

    def _collect_source_content(
        self,
        sub_topic_id: int,
        user_id: Optional[int],
        max_chars: int = 3000,
    ) -> Dict[str, Any]:
        """收集该知识点关联的所有资料内容。

        Args:
            sub_topic_id: 子知识点 ID。
            user_id: None=系统，具体值=个人。
            max_chars: 拼接后的最大字符数。

        Returns:
            {text: 拼接的文本内容, doc_ids: [1,2,3], doc_names: [...], problem_nums: [...]}
        """
        conn = self._get_conn()
        if not conn:
            return {"text": "暂无相关资料", "doc_ids": [], "doc_names": [], "problem_nums": []}

        try:
            cursor = conn.cursor(dictionary=True)

            # 查询关联的知识块
            if user_id is not None:
                where = "kc.sub_topic_id = %s AND kd.user_id = %s"
                params = (sub_topic_id, user_id)
            else:
                where = "kc.sub_topic_id = %s AND kd.user_id IS NULL"
                params = (sub_topic_id,)

            cursor.execute(
                f"""SELECT kc.content, kd.title AS doc_title, kd.doc_id
                    FROM knowledge_chunks kc
                    JOIN knowledge_documents kd ON kc.doc_id = kd.doc_id
                    WHERE {where}
                    ORDER BY kc.chunk_index LIMIT 20""",
                params,
            )
            chunks = cursor.fetchall() or []

            # 拼接文本（限制总长度）
            doc_ids = []
            doc_names = []
            text_parts = []
            total_chars = 0

            for ch in chunks:
                if total_chars >= max_chars:
                    break
                content = ch["content"]
                text_parts.append(content)
                total_chars += len(content)
                if ch["doc_id"] not in doc_ids:
                    doc_ids.append(ch["doc_id"])
                    doc_names.append(ch["doc_title"])

            # 查询相关题目
            parent_kp = None
            cursor.execute(
                "SELECT parent_kp FROM knowledge_sub_topics WHERE sub_topic_id = %s",
                (sub_topic_id,),
            )
            kp_row = cursor.fetchone()
            if kp_row:
                parent_kp = kp_row["parent_kp"]
                cursor.execute(
                    "SELECT problem_num, problem FROM problems "
                    "WHERE knowledge_point = %s LIMIT 5",
                    (parent_kp,),
                )
                problems = cursor.fetchall() or []
                problem_nums = [
                    {"num": p["problem_num"], "title": p["problem"][:50]}
                    for p in problems
                ]
            else:
                problem_nums = []

            return {
                "text": "\n\n".join(text_parts) if text_parts else "暂无相关资料",
                "doc_ids": doc_ids,
                "doc_names": doc_names,
                "problem_nums": problem_nums,
            }

        except Exception as e:
            print(f"[LearningCardService] 收集来源内容失败: {e}")
            return {"text": "暂无相关资料", "doc_ids": [], "doc_names": [], "problem_nums": []}
        finally:
            cursor.close()
            conn.close()

    def _save_card(
        self,
        sub_topic_id: int,
        user_id: Optional[int],
        slim_content: str,
        full_content: Optional[str],
        source_doc_ids: List[int],
    ) -> None:
        """保存（或更新）学习卡片到缓存。"""
        conn = self._get_conn()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            source_json = json.dumps(source_doc_ids, ensure_ascii=False)
            cursor.execute(
                """INSERT INTO knowledge_learning_cards
                   (sub_topic_id, user_id, slim_content, full_content,
                    source_doc_ids, is_regenerating)
                   VALUES (%s, %s, %s, %s, %s, 0)
                   ON DUPLICATE KEY UPDATE
                   slim_content = VALUES(slim_content),
                   source_doc_ids = VALUES(source_doc_ids),
                   is_regenerating = 0""",
                (sub_topic_id, user_id, slim_content, full_content, source_json),
            )
            conn.commit()
        except Exception as e:
            print(f"[LearningCardService] 保存卡片失败: {e}")
        finally:
            cursor.close()
            conn.close()

    def _save_full_content(
        self,
        sub_topic_id: int,
        user_id: Optional[int],
        full_content: str,
    ) -> None:
        """保存完整版卡片内容。"""
        conn = self._get_conn()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE knowledge_learning_cards
                   SET full_content = %s, is_regenerating = 0
                   WHERE sub_topic_id = %s
                     AND (user_id = %s OR (user_id IS NULL AND %s IS NULL))""",
                (full_content, sub_topic_id, user_id, user_id),
            )
            conn.commit()
        except Exception as e:
            print(f"[LearningCardService] 保存完整版失败: {e}")
        finally:
            cursor.close()
            conn.close()

    def _set_regenerating(
        self,
        sub_topic_id: int,
        user_id: Optional[int],
        value: bool,
    ) -> None:
        """设置卡片的重新生成标记。"""
        conn = self._get_conn()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE knowledge_learning_cards
                   SET is_regenerating = %s
                   WHERE sub_topic_id = %s
                     AND (user_id = %s OR (user_id IS NULL AND %s IS NULL))""",
                (1 if value else 0, sub_topic_id, user_id, user_id),
            )
            conn.commit()
        except Exception as e:
            print(f"[LearningCardService] 设置再生标记失败: {e}")
        finally:
            cursor.close()
            conn.close()


# 模块独立测试
if __name__ == "__main__":
    svc = LearningCardService()
    print("LearningCardService 已初始化")

    # 测试获取卡片
    print("\n=== 测试: 获取学习卡片 ===")
    card = svc.get_card(sub_topic_id=1, user_id=None)
    if "error" in card:
        print(f"  错误: {card['error']}")
    else:
        print(f"  知识点: {card['sub_topic_name']} ({card['parent_kp']})")
        print(f"  精简版: {card['slim_content'][:100]}...")
        print(f"  来源文档: {card['source_doc_ids']}")
        print(f"  来自缓存: {card['from_cache']}")