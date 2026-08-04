import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.deepseek_chat import deepseek_chat

class AbilityProfile:
    def __init__(self, user_id):
        self.user_id = user_id
    
    def _load_profile(self):
        """
        从数据库加载用户能力画像
        """
        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT knowledge_point, proficiency_level 
                FROM ability_profile 
                WHERE user_id = %s
            """, (self.user_id,))
            results = cursor.fetchall()
            
            # 转换为字典格式
            profile_data = {}
            for row in results:
                profile_data[row['knowledge_point']] = row['proficiency_level']
            
            return profile_data
        finally:
            if conn:
                conn.close()
    
    def _calculate_user_strength(self):
        """
        计算用户整体实力水平
        基于所有知识点的平均熟练度
        """
        profile_data = self._load_profile()
        if not profile_data:
            return 0.5  # 默认中等实力
        
        # 计算平均熟练度作为用户实力
        avg_proficiency = sum(profile_data.values()) / len(profile_data)
        return round(avg_proficiency, 2)
    
    def _update_user_strength(self):
        """
        更新用户实力到数据库
        """
        strength = self._calculate_user_strength()
        
        conn = get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user SET user_strength = %s WHERE user_id = %s
            """, (strength, self.user_id))
            conn.commit()
        finally:
            if conn:
                conn.close()
        
        return strength
    
    def get_user_strength(self):
        """
        获取用户实力水平
        """
        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT user_strength FROM user WHERE user_id = %s
            """, (self.user_id,))
            result = cursor.fetchone()
            
            if result and result['user_strength'] is not None:
                return result['user_strength']
            else:
                # 如果没有实力数据，计算并更新
                return self._update_user_strength()
        finally:
            if conn:
                conn.close()
    
    def analyze_answer(self, problem_id, user_answer, is_correct):
        """
        分析用户答题情况并更新能力画像和用户实力
        - 先安全写入 user_answers（立刻提交，避免后续步骤异常导致整笔事务回滚）
        - 尝试更新/插入 ability_profile（失败不影响答题记录）
        - 尝试聚合学习会话（learning_sessions），失败不影响前两步
        - 最后更新 user 表中的 user_strength（在独立连接中执行）
        """
        conn = get_connection()
        if not conn:
            raise Exception('数据库连接失败：无法获取连接')
        try:
            cursor = conn.cursor(dictionary=True)

            # 1) 写入用户答题记录（最关键步骤）
            try:
                cursor.execute(
                    """
                    INSERT INTO user_answers (user_id, problem_id, user_answer, is_correct)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (self.user_id, problem_id, user_answer, is_correct)
                )
                # 立刻提交，避免后续非关键步骤异常导致本条答题记录丢失
                conn.commit()
            except Exception as e:
                # 答题记录是核心数据，如失败直接抛出
                raise

            # 2) 更新能力画像（非核心，失败时仅记录日志并继续执行）
            try:
                # 获取题目的知识点
                cursor.execute(
                    """
                    SELECT knowledge_point FROM problems WHERE problem_id = %s
                    """,
                    (problem_id,)
                )
                result = cursor.fetchone()

                if result:
                    knowledge_point = result['knowledge_point']

                    # 查询当前熟练度，若不存在则使用默认 0.5
                    cursor.execute(
                        """
                        SELECT proficiency_level FROM ability_profile 
                        WHERE user_id = %s AND knowledge_point = %s
                        """,
                        (self.user_id, knowledge_point)
                    )
                    current_result = cursor.fetchone()
                    current_level = current_result['proficiency_level'] if current_result else 0.5

                    # 基于答题结果调整熟练度
                    if is_correct:
                        new_level = min(1.0, current_level + 0.1)
                    else:
                        new_level = max(0.0, current_level - 0.05)

                    # UPSERT 能力画像
                    cursor.execute(
                        """
                        INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level)
                        VALUES (%s, %s, %s)
                        ON DUPLICATE KEY UPDATE proficiency_level = %s
                        """,
                        (self.user_id, knowledge_point, new_level, new_level)
                    )
                    conn.commit()  # 提交画像更新
            except Exception as e:
                # 画像更新失败不影响流程，打印日志便于排查
                try:
                    print('[analyze_answer] 更新能力画像失败:', e)
                except Exception:
                    pass

            # 3) 聚合学习会话（非核心，失败不影响前两步）
            try:
                cursor.execute(
                    """
                    SELECT session_id, start_time, end_time, total_problems, correct_problems
                    FROM learning_sessions
                    WHERE user_id = %s
                    ORDER BY end_time DESC
                    LIMIT 1
                    """,
                    (self.user_id,)
                )
                last_session = cursor.fetchone()
                import datetime
                now = datetime.datetime.now()
                if last_session and last_session.get('end_time'):
                    delta = now - last_session['end_time']
                    within_window = (delta.total_seconds() <= 24* 60* 60)# 2分钟内;注意；需更改

                else:
                    within_window = False

                add_correct = 1 if is_correct else 0
                if last_session and within_window:
                    # 更新现有会话
                    cursor.execute(
                        """
                        UPDATE learning_sessions
                        SET end_time = NOW(),
                            total_problems = total_problems + 1,
                            correct_problems = correct_problems + %s
                        WHERE session_id = %s
                        """,
                        (add_correct, last_session['session_id'])
                    )
                else:
                    # 创建新会话
                    cursor.execute(
                        """
                        INSERT INTO learning_sessions (user_id, start_time, end_time, total_problems, correct_problems)
                        VALUES (%s, NOW(), NOW(), %s, %s)
                        """,
                        (self.user_id, 1, add_correct)
                    )
                conn.commit()  # 提交会话更新
            except Exception as e:
                # 仅记录错误，不中断流程
                try:
                    print('[analyze_answer] 聚合学习会话失败:', e)
                except Exception:
                    pass

            # 4) 更新用户整体实力（单独连接中执行，内部已 commit）
            try:
                self._update_user_strength()
            except Exception as e:
                try:
                    print('[analyze_answer] 更新用户实力失败:', e)
                except Exception:
                    pass

        finally:
            # 清理资源
            try:
                if 'cursor' in locals():
                    cursor.close()
            except Exception:
                pass
            if conn:
                conn.close()
    
    def get_ai_analysis(self):
        """
        获取AI分析报告
        """
        profile_data = self._load_profile()
        
        if not profile_data:
            return "暂无足够数据进行分析，请继续答题。"
        
        # 获取最近的答题记录
        conn = get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT p.problem, p.knowledge_point, ua.user_answer, p.answer, ua.is_correct
                FROM user_answers ua
                JOIN problems p ON ua.problem_id = p.problem_id
                WHERE ua.user_id = %s
                ORDER BY ua.answer_time DESC
                LIMIT 10
            """, (self.user_id,))
            recent_answers = cursor.fetchall()
        finally:
            if conn:
                conn.close()
        
        # 先定义换行符变量
        newline = '\n'
        
        prompt = f"""作为一个教育分析AI，请分析以下学生的答题情况和能力画像，并给出学习建议：
                    
                    学生能力画像：
                    {', '.join([f'{k}: {v:.2f}' for k, v in profile_data.items()])}
                    
                    最近答题记录：
                    {newline.join([f'题目：{a["problem"]}{newline}知识点：{a["knowledge_point"]}{newline}学生答案：{a["user_answer"]}{newline}正确答案：{a["answer"]}{newline}是否正确：{"是" if a["is_correct"] else "否"}' for a in recent_answers])}
                    
                    请分析：
                    简洁表达,快速生成，
                    1. 学生的强项和弱项知识点
                    2. 学生的学习进展
                    3. 列出相关知识点的学习资源。按照平台名称、资源标题、创作者/频道来输出 
                    4. 推荐应该加强哪些知识点的学习
                    """
        
        try:
            analysis = deepseek_chat.chat_with_deepseek(prompt)
            return analysis
        except Exception as e:
            return f"AI分析暂时不可用：{str(e)}"