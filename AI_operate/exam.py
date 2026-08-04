import sys
from pathlib import Path
import random

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.Ability_Profile import AbilityProfile

def get_random_problems(num_problems=5):
    """
    获取随机题目
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT problem_id, problem_num, problem, answer, difficulty, knowledge_point
            FROM problems
            ORDER BY RAND()
            LIMIT %s
        """, (num_problems,))
        problems = cursor.fetchall()
        return problems
    finally:
        if conn:
            conn.close()

def _fetch_ranked_candidates(conn, user_id, knowledge_points=None, difficulties=None, limit=10, stale_days=30, exclude_ids=None):
    """
    从数据库拉取候选题，并按“未做/久未做优先”进行排序。
    排序优先级：
    1) 从未做过（last_time IS NULL）
    2) 久未做（last_time < NOW() - INTERVAL stale_days DAY）
    3) 最近做过（其余）
    同级内按 last_time 升序，再加少量 RAND() 以增加多样性。
    参数：
    - knowledge_points: 可选，限定知识点集合
    - difficulties: 可选，限定难度集合（'简单'/'中等'/'困难'）
    - exclude_ids: 可选，排除这些 problem_id
    返回：dict 列表，每项包含题目信息。
    """
    params = []

    # 子查询：用户最近一次作答时间
    sub_sql = """
        SELECT problem_id, MAX(answer_time) AS last_time
        FROM user_answers
        WHERE user_id = %s
        GROUP BY problem_id
    """
    params.append(user_id)

    # 主查询
    sql = [
        "SELECT p.problem_id, p.problem_num, p.problem, p.answer, p.difficulty, p.knowledge_point, ua.last_time",
        "FROM problems p",
        "LEFT JOIN (" + sub_sql + ") ua ON ua.problem_id = p.problem_id",
        "WHERE 1=1"
    ]

    # 过滤条件
    if knowledge_points:
        placeholders = ", ".join(["%s"] * len(knowledge_points))
        sql.append(f"AND p.knowledge_point IN ({placeholders})")
        params.extend(list(knowledge_points))
    if difficulties:
        placeholders = ", ".join(["%s"] * len(difficulties))
        sql.append(f"AND p.difficulty IN ({placeholders})")
        params.extend(list(difficulties))
    if exclude_ids:
        placeholders = ", ".join(["%s"] * len(exclude_ids))
        sql.append(f"AND p.problem_id NOT IN ({placeholders})")
        params.extend(list(exclude_ids))

    # 排序 + 限制数量
    sql.append(
        """
        ORDER BY
          CASE
            WHEN ua.last_time IS NULL THEN 0
            WHEN ua.last_time < (NOW() - INTERVAL %s DAY) THEN 1
            ELSE 2
          END ASC,
          ua.last_time ASC,
          RAND()
        LIMIT %s
        """
    )
    params.extend([stale_days, int(limit)])

    cursor = conn.cursor(dictionary=True)
    cursor.execute("\n".join(sql), tuple(params))
    rows = cursor.fetchall() or []
    cursor.close()
    return rows

def get_filtered_problems(userid, num_problems=5, knowledge_points=None, difficulties=None, stale_days=30):
    """
    获取按条件筛选的题目列表（支持知识点与难度过滤），并结合“未做/久未做优先”的排序。
    - user_id: 当前用户ID（用于结合 user_answers 计算 last_time 排序）
    - num_problems: 返回题目数量
    - knowledge_points: 可选，限定知识点集合（list/tuple/set of str）
    - difficulties: 可选，限定难度集合（['简单','中等','困难'] 的子集）
    - stale_days: 久未做阈值（天）
    返回：长度不超过 num_problems 的题目列表（dict 列表）
    """
    conn = get_connection()
    try:
        # 归一化参数
        kps = list(knowledge_points) if knowledge_points else None
        diffs = list(difficulties) if difficulties else None
        # 从候选集中按优先规则获取更多，再截断
        candidates = _fetch_ranked_candidates(
            conn,
            userid,
            knowledge_points=kps,
            difficulties=diffs,
            limit=max(3 * int(num_problems), 20),
            stale_days=stale_days,
        )
        return candidates[: int(num_problems)]
    finally:
        if conn:
            conn.close()

def get_personalized_problems(user_id, num_problems=5, stale_days=30):
    """
    根据用户能力画像获取个性化题目（后端完整方案）
    核心策略：
    1) 以用户“未做过/久未做”为优先级进行排序和选择；
    2) 70% 来自弱点知识点（熟练度 < 0.6），30% 来自强点（>= 0.6）；
    3) 强点部分根据用户整体实力优先筛选中等/困难（或简单/中等）；
    4) 若候选不足，则在全量题库中继续按上述优先级补齐；
    5) 全过程完全在后端完成，依赖 user_answers 表；
    6) stale_days 控制“久未做”的阈值（默认 30 天）。
    返回：长度为 num_problems 的题目列表（不保证顺序随机，但优先级满足需求）。
    """
    conn = get_connection()
    try:
        # 获取用户能力画像和整体实力
        profile = AbilityProfile(user_id)
        profile_data = profile._load_profile()
        user_strength = profile.get_user_strength()

        # 若没有能力画像，仍按“未做/久未做优先”在全量题库选择
        if not profile_data:
            candidates = _fetch_ranked_candidates(conn, user_id, limit=max(3 * num_problems, 20), stale_days=stale_days)
            return candidates[:num_problems]

        # 计算强弱点
        sorted_knowledge = sorted(profile_data.items(), key=lambda x: x[1])
        weak_points = [kp for kp, level in sorted_knowledge if level < 0.6]
        strong_points = [kp for kp, level in sorted_knowledge if level >= 0.6]
        if not weak_points:
            weak_points = [kp for kp, _ in sorted_knowledge[: max(1, len(sorted_knowledge) // 2)]]
        if not strong_points:
            strong_points = [kp for kp, _ in sorted_knowledge[max(1, len(sorted_knowledge) // 2):]]

        # 强点偏好难度
        strong_difficulties = ['中等', '困难'] if user_strength >= 0.6 else ['简单', '中等']

        selected = []
        used_ids = set()

        def _take(items, need):
            taken = []
            for it in items:
                pid = it['problem_id']
                if pid in used_ids:
                    continue
                used_ids.add(pid)
                taken.append(it)
                if len(taken) >= need:
                    break
            return taken

        # 70% 弱点
        weak_need = max(0, int(num_problems * 0.7))
        if weak_need > 0 and weak_points:
            weak_candidates = _fetch_ranked_candidates(
                conn, user_id,
                knowledge_points=weak_points,
                difficulties=None,
                limit=max(weak_need * 3, 15),
                stale_days=stale_days,
            )
            selected.extend(_take(weak_candidates, weak_need))

        # 30% 强点
        remain = num_problems - len(selected)
        if remain > 0 and strong_points:
            strong_candidates = _fetch_ranked_candidates(
                conn, user_id,
                knowledge_points=strong_points,
                difficulties=strong_difficulties,
                limit=max(remain * 3, 10),
                stale_days=stale_days,
                exclude_ids=list(used_ids) if used_ids else None,
            )
            selected.extend(_take(strong_candidates, remain))

        # 若仍不足，面向全量题库补齐（仍按优先级排序）
        remain = num_problems - len(selected)
        if remain > 0:
            more = _fetch_ranked_candidates(
                conn, user_id,
                knowledge_points=None,
                difficulties=None,
                limit=max(remain * 3, 10),
                stale_days=stale_days,
                exclude_ids=list(used_ids) if used_ids else None,
            )
            selected.extend(_take(more, remain))

        return selected[:num_problems]

    finally:
        if conn:
            conn.close()