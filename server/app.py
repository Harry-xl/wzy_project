import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载项目根目录下的 .env 文件
load_dotenv(Path(__file__).parent.parent / ".env")

from flask import Flask, request, jsonify, Response, redirect, url_for
from flask_cors import CORS
import mysql.connector
import sys
from werkzeug.security import generate_password_hash, check_password_hash
# 新增: 清理调度所需
import threading
import time
import json

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

# HuggingFace 国内镜像（必须在导入嵌入模型前设置）
import os as _os
_os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')

from AI_operate.exam import get_personalized_problems, get_random_problems, get_filtered_problems

from AI_operate.Ability_Profile import AbilityProfile
# 新增：引入 DeepSeek 调用封装
from AI_operate.deepseek_chat import deepseek_chat
# 新增：RAG 检索增强生成
from AI_operate.rag_service import RAGService

# RAG 服务懒加载单例（避免每次请求重新加载嵌入模型）
_rag_service_instance = None


def _get_rag_service():
    """获取 RAG 服务单例（懒加载）。"""
    global _rag_service_instance
    if _rag_service_instance is None:
        _rag_service_instance = RAGService()
    return _rag_service_instance

# 配置静态文件路径，指向上级目录的static文件夹
app = Flask(__name__, static_folder='../static', static_url_path='/static')
CORS(app)

# MySQL配置
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'wzyProjectDb')
}

# ---------------- 清理任务配置（可按需调整）----------------
# 是否启用后台定期清理
CLEANUP_ENABLED = True
# 清理间隔（秒），默认每小时清理一次
CLEANUP_INTERVAL_SECONDS = 3600
# user_answers 保留天数（超出会被删除）
RETAIN_DAYS_ANSWERS = 60
# learning_sessions 保留天数（超出会被删除）
RETAIN_DAYS_SESSIONS = 180
_cleanup_thread_started = False

# 根路由 - 重定向到登录页面
@app.route('/')
def index():
    """根路由，重定向到登录页面"""
    return redirect('/static/login.html')

def cleanup_old_data():
    """
    定期清理旧数据，避免数据量无限增长。
    - 删除 user_answers 中早于 RETAIN_DAYS_ANSWERS 的记录（按 answer_time）
    - 删除 learning_sessions 中早于 RETAIN_DAYS_SESSIONS 的记录（按 end_time；为空则按 start_time）
    注意：该函数会在独立线程中循环执行。
    """
    while True:
        try:
            conn = mysql.connector.connect(**db_config)
            cur = conn.cursor()
            # 清理 user_answers
            cur.execute(
                """
                DELETE FROM user_answers
                WHERE answer_time < (NOW() - INTERVAL %s DAY)
                """,
                (RETAIN_DAYS_ANSWERS,)
            )
            ua_deleted = cur.rowcount
            # 清理 learning_sessions（end_time 有值按 end_time，无值按 start_time）
            # 两步删除：先删 end_time 超期，再删 start_time 超期且 end_time 为空的
            cur.execute(
                """
                DELETE FROM learning_sessions
                WHERE end_time IS NOT NULL AND end_time < (NOW() - INTERVAL %s DAY)
                """,
                (RETAIN_DAYS_SESSIONS,)
            )
            ls_deleted1 = cur.rowcount
            cur.execute(
                """
                DELETE FROM learning_sessions
                WHERE end_time IS NULL AND start_time < (NOW() - INTERVAL %s DAY)
                """,
                (RETAIN_DAYS_SESSIONS,)
            )
            ls_deleted2 = cur.rowcount
            conn.commit()
            print(f"[cleanup] user_answers 删除 {ua_deleted} 条；learning_sessions 删除 {ls_deleted1 + ls_deleted2} 条")
        except Exception as e:
            print('[cleanup] 清理任务执行异常:', e)
        finally:
            try:
                if 'cur' in locals(): cur.close()
                if 'conn' in locals(): conn.close()
            except Exception:
                pass
        # 等待下次执行
        time.sleep(CLEANUP_INTERVAL_SECONDS)


def start_cleanup_scheduler():
    """
    启动清理任务调度线程（仅启动一次）。
    """
    global _cleanup_thread_started
    if _cleanup_thread_started or not CLEANUP_ENABLED:
        return
    t = threading.Thread(target=cleanup_old_data, name='cleanup_scheduler', daemon=True)
    t.start()
    _cleanup_thread_started = True
    print('[cleanup] 清理调度线程已启动')


# 注册接口
@app.route('/api/signup', methods=['POST'])
def signup():
    """
    用户注册接口：
    - 接收 name、email、password
    - 使用 PBKDF2-SHA256 对密码进行哈希后入库
    - 返回 { success: True } 或失败信息
    安全：不在日志中打印明文密码
    """
    try:
        data = request.get_json()
        # 避免打印包含明文密码的请求体
        print('收到注册请求:', { 'name': data.get('name'), 'email': data.get('email') })
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        if not all([name, email, password]):
            print('字段缺失:', {'name': name, 'email': email, 'password': bool(password)})
            return jsonify({'success': False, 'message': '请填写所有字段'})
        # 生成哈希密码
        hashed_password = generate_password_hash(password)
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO user (email, name, password) VALUES (%s, %s, %s)', (email, name, hashed_password))
            conn.commit()
            print('注册成功:', email)
            return jsonify({'success': True})
        except mysql.connector.Error as err:
            print('注册数据库错误:', err)
            if err.errno == 1062:
                return jsonify({'success': False, 'message': '邮箱已注册'})
            return jsonify({'success': False, 'message': '注册失败', 'error': str(err)})
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        print('注册接口异常:', e)
        return jsonify({'success': False, 'message': '服务器异常', 'error': str(e)})

# 登录接口
@app.route('/api/login', methods=['POST'])
def login():
    """
    用户登录接口：
    - 按邮箱查询用户
    - 使用哈希校验密码；如检测到历史明文密码，首次登录时自动迁移为哈希
    - 返回 { success: True, user_id, name } 或失败信息
    """
    try:
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 先按邮箱查询
        cursor.execute('SELECT * FROM user WHERE email=%s', (email,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '邮箱或密码错误'})

        stored_pwd = user.get('password') or ''
        verified = False
        try:
            # 优先按哈希进行校验
            verified = check_password_hash(stored_pwd, password)
        except Exception:
            # stored_pwd 不是哈希格式
            verified = False
        
        # 兼容历史明文密码（仅当哈希校验失败时）
        if not verified and stored_pwd and stored_pwd == password:
            verified = True
            try:
                # 检测到为明文密码，自动迁移为哈希
                new_hashed = generate_password_hash(password)
                cursor2 = conn.cursor()
                cursor2.execute('UPDATE user SET password=%s WHERE user_id=%s', (new_hashed, user['user_id']))
                conn.commit()
                cursor2.close()
                print(f"已将用户 {email} 的明文密码自动迁移为哈希")
            except Exception as _m_err:
                print('明文迁移为哈希时出错:', _m_err)
        
        if verified:
            return jsonify({'success': True, 'user_id': user['user_id'], 'name': user['name']})
        return jsonify({'success': False, 'message': '邮箱或密码错误'})
    except Exception as e:
        return jsonify({'success': False, 'message': '登录失败', 'error': str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# 获取题目接口
@app.route('/api/problems/filter', methods=['GET'])
def get_problems_by_filter():
    """按知识点 / 难度筛选题目"""
    try:
        # 注意：和前端 api.js 发出的参数名完全对齐
        user_id_raw = request.args.get('user_id')
        count_raw = request.args.get('count', '5')
        kp_raw = request.args.get('knowledge_points', '').strip()
        diff_raw = request.args.get('difficulties', '').strip()
        stale_days_raw = request.args.get('stale_days')

        print(f"[server] /api/problems/filter 参数: user_id={user_id_raw}, count={count_raw}, kp={kp_raw}, diff={diff_raw}, stale_days={stale_days_raw}")

        # userid 解析
        try:
            user_id = int(user_id_raw)
        except Exception:
            return jsonify(success=False, message='user_id 必须是有效整数'), 400

        # count 解析
        try:
            count = int(count_raw)
        except Exception:
            count = 5
        if count <= 0:
            count = 5
        if count > 50:
            count = 50

        # stale_days 解析
        try:
            stale_days = int(stale_days_raw) if stale_days_raw is not None else 30
            if stale_days <= 0:
                stale_days = 30
        except Exception:
            stale_days = 30

        # 解析知识点 / 难度（逗号分隔转列表）
        knowledge_points = [s.strip() for s in kp_raw.split(',') if s.strip()] if kp_raw else None
        difficulties = [s.strip() for s in diff_raw.split(',') if s.strip()] if diff_raw else None

        print(f"[server] 调用 get_filtered_problems: userid={user_id}, num_problems={count}, knowledgepoints={knowledge_points}, difficulties={difficulties}, staledays={stale_days}")

        # 调用 exam.py 中的函数（注意参数名完全匹配函数签名）
        problems = get_filtered_problems(
            userid=user_id,             # 对应定义里的 userid
            num_problems=count,         # 对应定义里的 num_problems
            knowledge_points=knowledge_points, # 对应定义里的 knowledge_points
            difficulties=difficulties,  # 对应定义里的 difficulties
            stale_days=stale_days       # 对应定义里的 stale_days
        )


        print(f"[server] get_filtered_problems 返回题目数: {len(problems)}")

        # JSON 安全化
        safe_problems = []
        for p in problems:
            safep = dict(p)
            if 'problemid' in safep:
                safep['problemid'] = int(safep['problemid'])
            safe_problems.append(safep)

        return jsonify(success=True, problems=safe_problems)

    except Exception as e:
        print('[server] /api/problems/filter 详细错误:', e)
        import traceback
        traceback.print_exc()  # 打印完整堆栈，方便调试
        return jsonify(success=False, message='服务器内部错误', error=str(e)), 500

@app.route('/api/knowledge_points', methods=['GET'])
def get_knowledge_points():
    """
    获取全量知识点列表（用于前端筛选）
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT knowledge_point
            FROM problems
            WHERE knowledge_point IS NOT NULL AND knowledge_point != ''
            ORDER BY knowledge_point ASC
            """
        )
        rows = cursor.fetchall() or []
        items = [r[0] for r in rows if r and r[0]]
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取知识点失败', 'error': str(e)})
    finally:
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass

@app.route('/api/problems', methods=['GET']) 
def get_problems():
    """
    获取题目接口：
    - 支持游客随机与登录用户个性化两种模式
    - 新增：可选查询参数 stale_days，用于个性化推荐中"久未做"的阈值天数（默认30）
    """
    try:
        # 更详细的请求调试信息
        try:
            print('[server] 请求URL:', request.url)
            print('[server] full_path:', getattr(request, 'full_path', 'N/A'))
            print('[server] query_string(raw):', request.query_string)
            print('[server] args(dict):', request.args.to_dict(flat=False))
        except Exception as _dbg_err:
            print('[server] 调试信息打印异常:', _dbg_err)

        user_id = request.args.get('user_id')
        count_raw = request.args.get('count', '5')
        stale_days_raw = request.args.get('stale_days')
        # 解析参数
        try:
            count = int(count_raw)
        except Exception:
            count = 5
        try:
            stale_days = int(stale_days_raw) if stale_days_raw is not None else 30
            if stale_days <= 0:
                stale_days = 30
        except Exception:
            stale_days = 30
        print(f"[server] 收到 /api/problems 请求, user_id={user_id}, count={count}, stale_days={stale_days}")
        
        if user_id and user_id.isdigit() and int(user_id) > 0:
            problems = get_personalized_problems(int(user_id), count, stale_days=stale_days)
        else:
            problems = get_random_problems(count)
        
        # 转换为JSON安全格式
        safe_problems = []
        for p in problems:
            safe_p = dict(p)
            safe_p['problem_id'] = int(safe_p['problem_id'])  # 确保ID是整数
            safe_problems.append(safe_p)
        
        print(f"[server] 本次返回题目数量: {len(safe_problems)}")
        return jsonify({'success': True, 'problems': safe_problems})
    except Exception as e:
        print('[server] /api/problems 处理异常:', e)
        return jsonify({'success': False, 'message': '获取题目失败', 'error': str(e)})

# 提交答案接口
@app.route('/api/submit_answer', methods=['POST'])
def submit_answer():
    """
    提交答案接口：判题并更新用户画像/学习会话。
    - 登录用户（user_id > 0）：写入 user_answers、更新 ability_profile、聚合 learning_sessions，并刷新用户整体实力。
    - 游客（user_id <= 0 或缺失）：仅返回判题结果，不进行数据库写入。
    返回：{ success, is_correct, correct_answer, guest? }
    """
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id')
        problem_id = data.get('problem_id')
        user_answer = (data.get('user_answer') or '').strip()

        if user_id is None or problem_id is None or not user_answer:
            return jsonify({'success': False, 'message': '缺少必要参数'})

        # 参数类型校验与转换
        try:
            user_id = int(user_id)
            problem_id = int(problem_id)
        except Exception:
            return jsonify({'success': False, 'message': '参数格式错误'})

        # 获取正确答案
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT answer FROM problems WHERE problem_id = %s', (problem_id,))
        problem = cursor.fetchone()
        if not problem:
            return jsonify({'success': False, 'message': '题目不存在'})

        is_correct = user_answer == (problem['answer'] or '').strip()

        # 游客模式：不落库，仅返回判题结果
        if user_id <= 0:
            return jsonify({
                'success': True,
                'is_correct': is_correct,
                'correct_answer': problem['answer'],
                'guest': True
            })

        # 登录用户：写入答题与画像/会话
        profile = AbilityProfile(user_id)
        profile.analyze_answer(problem_id, user_answer, is_correct)

        return jsonify({
            'success': True,
            'is_correct': is_correct,
            'correct_answer': problem['answer']
        })
    except Exception as e:
        print('[server] /api/submit_answer 异常:', e)
        return jsonify({'success': False, 'message': '提交答案失败', 'error': str(e)})
    finally:
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

# 获取用户能力画像接口
@app.route('/api/user_profile/<int:user_id>', methods=['GET'])
def get_user_profile(user_id):
    """
    获取指定用户的能力画像：
    - 返回用户基本信息（name、email）
    - 返回用户整体实力（user_strength，0.0-1.0）
    - 返回能力画像（abilities: { 知识点: 熟练度 }）
    - 返回 AI 分析文本（analysis）
    兼容性：若数据库暂未包含 user_strength 列，自动回退为根据 ability_profile 计算平均熟练度。
    """
    def _compute_strength_avg(conn_, uid):
        """从 ability_profile 计算平均熟练度，范围 [0,1]。"""
        cur2 = conn_.cursor(dictionary=True)
        try:
            cur2.execute('SELECT proficiency_level FROM ability_profile WHERE user_id=%s', (uid,))
            rows = cur2.fetchall() or []
        finally:
            cur2.close()
        if not rows:
            return 0.5
        avg = sum(float(r.get('proficiency_level') or 0.0) for r in rows) / max(1, len(rows))
        return max(0.0, min(1.0, round(avg, 2)))

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        missing_strength_column = False
        user_info = None
        try:
            cursor.execute('SELECT name, email, user_strength FROM user WHERE user_id=%s', (user_id,))
            user_info = cursor.fetchone()
        except Exception as e:
            # 兼容数据库缺失 user_strength 列的情况
            if 'Unknown column' in str(e) or '1054' in str(e):
                missing_strength_column = True
                cursor.close()
                cursor = conn.cursor(dictionary=True)
                cursor.execute('SELECT name, email FROM user WHERE user_id=%s', (user_id,))
                user_info = cursor.fetchone()
            else:
                raise

        if not user_info:
            return jsonify({'success': False, 'message': '用户不存在'})

        # 计算/获取用户实力
        if missing_strength_column or (user_info.get('user_strength') is None):
            user_strength = _compute_strength_avg(conn, user_id)
        else:
            try:
                user_strength = float(user_info.get('user_strength'))
            except Exception:
                user_strength = _compute_strength_avg(conn, user_id)

        cursor.close()
        conn.close()

        # 获取能力画像
        profile = AbilityProfile(user_id)
        profile_data = profile._load_profile()
        # 获取AI分析
        ai_analysis = profile.get_ai_analysis()

        # 合并用户基本信息和能力画像
        result_profile = {
            'name': user_info['name'],
            'email': user_info['email'],
            'user_strength': float(user_strength),
            'abilities': profile_data
        }

        return jsonify({
            'success': True,
            'profile': result_profile,
            'analysis': ai_analysis
        })
    except Exception as e:
        return jsonify({'success': False, 'message': '获取用户画像失败', 'error': str(e)})

# 用户实力趋势（基于学习会话正确率的时间序列）
@app.route('/api/user_strength_trend/<int:user_id>', methods=['GET'])
def get_user_strength_trend(user_id):
    """
    返回用户实力趋势时间序列数据（mini 折线图数据源）。
    - 数据来源：learning_sessions 表，每次会话的正确率作为一个点。
    - 返回字段：
      [
        {"t": ISO8601时间字符串, "value": 0.0~1.0正确率}
      ]（按时间升序）
    - 若没有数据，返回空列表。
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cur = conn.cursor(dictionary=True)
        cur.execute(
            """
            SELECT start_time, total_problems, correct_problems
            FROM learning_sessions
            WHERE user_id=%s
            ORDER BY start_time ASC
            """,
            (user_id,)
        )
        rows = cur.fetchall() or []
        cur.close()
        conn.close()

        trend = []
        for r in rows:
            total = r.get('total_problems') or 0
            correct = r.get('correct_problems') or 0
            if total and total > 0:
                val = max(0.0, min(1.0, float(correct) / float(total)))
                # MySQL connector 返回 datetime 对象
                t = r.get('start_time')
                try:
                    t_str = t.isoformat(sep=' ', timespec='seconds') if hasattr(t, 'isoformat') else str(t)
                except Exception:
                    t_str = str(t)
                trend.append({
                    't': t_str,
                    'value': val
                })
        return jsonify({'success': True, 'trend': trend})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取实力趋势失败', 'error': str(e)})

# 获取用户错题列表
@app.route('/api/wrong_answers/<int:user_id>', methods=['GET'])
def get_wrong_answers(user_id: int):
    """
    获取指定用户的错题记录（仅返回做错的题），按时间倒序，支持可选 limit、offset 参数。
    返回字段包含题目基本信息与用户作答信息，便于前端展示与"同维度重练"。
    安全：limit 做上限约束，offset 做非负约束，SQL 使用参数化，时间字段转字符串。
    """
    try:
        # 解析并约束 limit
        try:
            limit = int(request.args.get('limit', 50))
        except Exception:
            limit = 50
        if limit < 1:
            limit = 1
        if limit > 200:
            limit = 200
        # 解析并约束 offset
        try:
            offset = int(request.args.get('offset', 0))
        except Exception:
            offset = 0
        if offset < 0:
            offset = 0
        if offset > 100000:
            offset = 100000

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        sort_by = (request.args.get('sort_by') or 'time').strip().lower()
        if sort_by == 'knowledge_point':
            order_sql = "ORDER BY p.knowledge_point ASC, ua.answer_time DESC"
        else:
            order_sql = "ORDER BY ua.answer_time DESC"
        cursor.execute(
            f"""
            SELECT ua.answer_id, ua.user_id, ua.problem_id, ua.user_answer, ua.is_correct, ua.answer_time,
                   p.problem_num, p.problem, p.answer, p.difficulty, p.knowledge_point,
                   COALESCE(wc.wrong_count, 0) AS wrong_count,
                   wc.last_wrong_time
            FROM user_answers ua
            JOIN problems p ON ua.problem_id = p.problem_id
            JOIN (
                SELECT problem_id, MAX(answer_time) AS last_time
                FROM user_answers
                WHERE user_id = %s
                GROUP BY problem_id
            ) last_ans ON last_ans.problem_id = ua.problem_id AND last_ans.last_time = ua.answer_time
            LEFT JOIN (
                SELECT problem_id, COUNT(*) AS wrong_count, MAX(answer_time) AS last_wrong_time
                FROM user_answers
                WHERE user_id = %s AND is_correct = 0
                GROUP BY problem_id
            ) wc ON wc.problem_id = ua.problem_id
            WHERE ua.user_id = %s AND ua.is_correct = 0
            {order_sql}
            LIMIT %s OFFSET %s
            """,
            (user_id, user_id, user_id, limit, offset)
        )
        rows = cursor.fetchall() or []
        items = []
        for r in rows:
            t = r.get('answer_time')
            try:
                t_str = t.isoformat(sep=' ', timespec='seconds') if hasattr(t, 'isoformat') else str(t)
            except Exception:
                t_str = str(t)
            wrong_count = r.get('wrong_count') or 0
            try:
                wrong_count = int(wrong_count)
            except Exception:
                wrong_count = 0
            redo_wrong_count = max(0, wrong_count - 1)
            items.append({
                'answer_id': r.get('answer_id'),
                'user_id': r.get('user_id'),
                'problem_id': r.get('problem_id'),
                'problem_num': r.get('problem_num'),
                'problem': r.get('problem'),
                'answer': r.get('answer'),
                'difficulty': r.get('difficulty'),
                'knowledge_point': r.get('knowledge_point'),
                'user_answer': r.get('user_answer'),
                'is_correct': bool(r.get('is_correct')),
                'answer_time': t_str,
                'redo_wrong_count': redo_wrong_count
            })
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取错题失败', 'error': str(e)})
    finally:
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass

@app.route('/api/wrong_redo/<int:user_id>', methods=['GET'])
def get_wrong_redo(user_id: int):
    try:
        try:
            count = int(request.args.get('count', 10))
        except Exception:
            count = 10
        if count < 1:
            count = 1
        if count > 200:
            count = 200

        mode = (request.args.get('mode') or 'time').strip().lower()
        kp_raw = (request.args.get('knowledge_points') or request.args.get('knowledge_point') or '').strip()
        knowledge_points = [s.strip() for s in kp_raw.split(',') if s.strip()] if kp_raw else []

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        params = [user_id, user_id, user_id]
        where_parts = []
        if mode == 'knowledge_point' and knowledge_points:
            placeholders = ", ".join(["%s"] * len(knowledge_points))
            where_parts.append(f"p.knowledge_point IN ({placeholders})")
            params.extend(list(knowledge_points))

        if mode == 'knowledge_point':
            order_sql = "ORDER BY COALESCE(wc.wrong_count, 0) DESC, ua.answer_time DESC"
        else:
            order_sql = "ORDER BY ua.answer_time DESC, COALESCE(wc.wrong_count, 0) DESC"

        where_extra = (" AND " + " AND ".join(where_parts)) if where_parts else ""

        cursor.execute(
            f"""
            SELECT ua.answer_id, ua.user_id, ua.problem_id, ua.user_answer, ua.is_correct, ua.answer_time,
                   p.problem_num, p.problem, p.answer, p.difficulty, p.knowledge_point,
                   COALESCE(wc.wrong_count, 0) AS wrong_count
            FROM user_answers ua
            JOIN problems p ON ua.problem_id = p.problem_id
            JOIN (
                SELECT problem_id, MAX(answer_time) AS last_time
                FROM user_answers
                WHERE user_id = %s
                GROUP BY problem_id
            ) last_ans ON last_ans.problem_id = ua.problem_id AND last_ans.last_time = ua.answer_time
            LEFT JOIN (
                SELECT problem_id, COUNT(*) AS wrong_count, MAX(answer_time) AS last_wrong_time
                FROM user_answers
                WHERE user_id = %s AND is_correct = 0
                GROUP BY problem_id
            ) wc ON wc.problem_id = ua.problem_id
            WHERE ua.user_id = %s AND ua.is_correct = 0
            {where_extra}
            {order_sql}
            LIMIT %s
            """,
            tuple(params + [count])
        )
        rows = cursor.fetchall() or []
        items = []
        for r in rows:
            wrong_count = r.get('wrong_count') or 0
            try:
                wrong_count = int(wrong_count)
            except Exception:
                wrong_count = 0
            redo_wrong_count = max(0, wrong_count - 1)
            items.append({
                'problem_id': r.get('problem_id'),
                'problem_num': r.get('problem_num'),
                'problem': r.get('problem'),
                'answer': r.get('answer'),
                'difficulty': r.get('difficulty'),
                'knowledge_point': r.get('knowledge_point'),
                'redo_wrong_count': redo_wrong_count
            })
        return jsonify({'success': True, 'items': items})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取错题重做题目失败', 'error': str(e)})
    finally:
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except Exception:
            pass

# 启动清理任务（在模块导入时尝试启动，避免重复启动）
start_cleanup_scheduler()

# 同步预热 RAG 服务（加载嵌入模型，避免首次请求超时）
print('[warmup] 正在预热 RAG 服务（加载嵌入模型）...')
try:
    _rag = _get_rag_service()
    _rag.search('warmup query', top_k=1)  # 触发模型加载
    print('[warmup] RAG 服务预热完成')
except Exception as e:
    print(f'[warmup] RAG 预热失败（将在首次请求时加载）: {e}')

# 新增：AI 讲解接口
@app.route('/api/explain', methods=['POST'])
def explain_problem():
    """
    题目 AI 讲解接口
    - 入参（JSON）：
      problem_text: 题干文本
      knowledge_point: 知识点（可选）
      difficulty: 难度（可选）
      user_answer: 学生作答（可选）
      correct_answer: 正确答案（可选）
    - 返回：{ success: bool, explanation?: str, message?: str }
    """
    try:
        data = request.get_json(force=True) or {}
        problem_text = (data.get('problem_text') or data.get('problem') or '').strip()
        knowledge_point = (data.get('knowledge_point') or '')
        difficulty = (data.get('difficulty') or '')
        user_answer = (data.get('user_answer') or '')
        correct_answer = (data.get('correct_answer') or data.get('answer') or '')

        if not problem_text:
            return jsonify({'success': False, 'message': '缺少题目内容 problem_text'}), 400

        # RAG 增强：检索题目相关知识
        knowledge_context = ''
        try:
            rag = _get_rag_service()
            search_query = f'{knowledge_point} {problem_text[:200]}'
            chunks = rag.search(search_query, top_k=3)
            if chunks:
                knowledge_context, _ = rag.build_context_block(chunks)
        except Exception as e:
            print(f'[/api/explain] RAG 检索失败: {e}')

        # 组装提示词（尽量结构化，便于前端展示）
        prompt_parts = [
            '你是一位资深学科辅导老师，请用清晰、分步骤的方式讲解下面这道题。',
            '请包含以下小节：',
            '1) 考查知识点与思路',
            '2) 详细解题步骤（逐步推导）',
            '3) 常见易错点与纠正',
            '4) 若学生作答有误，请指出错误原因',
            '5) 总结与举一反三',
        ]
        if knowledge_context:
            prompt_parts.insert(1, '请基于以下参考资料进行讲解，并在讲解中标注引用来源：\n' + knowledge_context)
        prompt_parts.append(
            f'题目：{problem_text}\n'
            f'知识点：{knowledge_point}\n'
            f'难度：{difficulty}\n'
            f'正确答案：{correct_answer}\n'
            f'学生作答：{user_answer}'
        )
        prompt = '\n\n'.join(prompt_parts)

        explanation = deepseek_chat.chat_with_deepseek(prompt)
        return jsonify({'success': True, 'explanation': explanation})
    except Exception as e:
        print('[/api/explain] 生成讲解失败:', e)
        return jsonify({'success': False, 'message': '生成讲解失败', 'error': str(e)}), 500

# 流式传输：AI 讲解（Chunked Text Streaming）
# 说明：
# - 接收与 /api/explain 相同的参数，但以分块文本形式实时返回内容，便于前端边到边渲染。
# - 为兼容性选择纯文本分块（非 SSE），前端通过 fetch 的 ReadableStream 读取。
# #前端把"题目 +（可选）作答信息"发过来，这个接口一边调用大模型生成讲解，一边通过 SSE 流式推给前端，
# 前端就能看到"打字机一样、逐步出来的题目讲解"。
@app.route('/api/explain/stream', methods=['POST'])

def explain_problem_stream():
    """流式讲解：将 DeepSeek 的增量内容以 SSE 文本流返回给前端。

    支持两种请求体：
    A) { problem_text, knowledge_point?, difficulty?, user_answer?, correct_answer? }
    B) { problem_id, user_answer? }  // 按题目ID在后端查询题干

    返回:
      text/event-stream 数据流（形如多条 "data: <chunk>\n\n"），前端按 SSE data: 解析。
    """
    data = request.get_json(force=True) or {}

    # 解析两类入参
    problem_text = str(data.get('problem_text') or '').strip()
    knowledge_point = str(data.get('knowledge_point') or '').strip()
    difficulty = str(data.get('difficulty') or '').strip()
    user_answer = str(data.get('user_answer') or '').strip()
    correct_answer = str(data.get('correct_answer') or '').strip()
    problem_id = data.get('problem_id')

    # 若未直接提供题干，尝试通过 problem_id 查询
    if not problem_text and problem_id:
        try:
            conn = mysql.connector.connect(**db_config)
            cur = conn.cursor(dictionary=True)
            cur.execute(
                "SELECT problem, knowledge_point, difficulty FROM problems WHERE problem_id = %s",
                (int(problem_id),)
            )
            prob = cur.fetchone()
            if prob:
                problem_text = str(prob.get('problem') or '').strip()
                knowledge_point = knowledge_point or str(prob.get('knowledge_point') or '')
                difficulty = difficulty or str(prob.get('difficulty') or '')
            cur.close()
            conn.close()
        except Exception:
            pass

    # 最低要求：必须有题干文本
    if not problem_text:
        return jsonify({"success": False, "message": "problem_text 不能为空（或提供 problem_id）"}), 400

    # RAG 增强：检索题目相关知识
    knowledge_context = ''
    try:
        rag = _get_rag_service()
        search_query = f'{knowledge_point} {problem_text[:200]}'
        chunks = rag.search(search_query, top_k=3)
        if chunks:
            knowledge_context, _ = rag.build_context_block(chunks)
    except Exception as e:
        print(f'[/api/explain/stream] RAG 检索失败: {e}')

    # 统一构造提示词（与同步接口保持一致风格）
    prompt_parts = [
        '你是一名资深教师，请对下面的题目进行详细的讲解，包括：思路分析、关键知识点、常见陷阱、逐步推导、以及给出举一反三的小练习。',
    ]
    if knowledge_context:
        prompt_parts.append('请基于以下参考资料进行讲解，并在讲解中标注引用来源：\n' + knowledge_context)
    prompt_parts.append(
        f'题目：{problem_text}\n'
        f'知识点：{knowledge_point or "未知"}\n'
        f'难度：{difficulty or "未知"}\n'
        f'学生的作答：{user_answer or "（未提供）"}\n'
        f'标准答案：{correct_answer or "（未提供）"}\n'
        '请用清晰的结构化格式输出。'
    )
    prompt = '\n\n'.join(prompt_parts)

    def generate():
        """后端流生成器：
        - 先立即发送一个很短的提示帧，确保前端尽快进入"正在生成"状态；
        - 将上游 DeepSeek 的 chunk 按更细粒度切片，提升前端流式打字机的顺滑度。
        """
        # 立即推送一个很短的引导帧，加速首包可见
        yield "data: 正在生成讲解…\n\n"

        # 从上游逐步获取内容
        for chunk in deepseek_chat.chat_with_deepseek_stream(prompt):
            if not chunk:
                continue
            # 将较长的片段切成更小的段，提升前端打字机连贯性
            step = 48  # 每帧约 48 个字符，可根据体验调整
            for i in range(0, len(chunk), step):
                sub = chunk[i:i+step]
                yield f"data: {sub}\n\n"

        # 结束标记（便于前端做收尾）
        yield "data: [DONE]\n\n"

    headers = {
        'Content-Type': 'text/event-stream; charset=utf-8',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Access-Control-Allow-Origin': '*',  # 如部署时有独立前端域名，请改成具体域
    }
    return Response(generate(), headers=headers)

# ======================= 新增：AI 智能对话（SSE JSON）接口 =======================
@app.route('/api/chat', methods=['POST'])
def chat_stream():
    """
    AI 智能对话流式接口（与前端 chat.js 协议对齐）。

    前端约定：
    - 使用 fetch ReadableStream 读取后端返回的 text/event-stream。
    - 每条事件以 "data: {\"reply\": "..."}\n\n" 的 JSON 形式发送。
    - 结束时发送一条包含 {"done": true} 的事件，便于前端收尾。

    请求(JSON)：
    - message: 本次用户消息（必填）
    - username: 发起用户（可选，仅用于日志/鉴权）
    - chat_id: 当前对话ID（可选，仅用于日志）
    - system_prompt: 系统提示词（可选，若提供将与 message 合并发送给上游）

    默认系统提示词：若未提供 system_prompt，将使用"计算机网络学习助手"角色提示词，专注 TCP/IP、HTTP/HTTPS、DNS、路由与交换、子网划分与CIDR、可靠传输与拥塞控制、网络安全与故障排查等主题，提供循序渐进讲解与示例，必要时给出图表/表格/对比与练习题。
    """
    try:
        payload = request.get_json(force=True) or {}
        message = str(payload.get('message') or '').strip()
        username = str(payload.get('username') or '')
        chat_id = str(payload.get('chat_id') or '')
        system_prompt = payload.get('system_prompt')

        # RAG 开关（默认开启）
        use_rag = payload.get('use_rag', True)
        if isinstance(use_rag, str):
            use_rag = use_rag.lower() in ('true', '1', 'yes')

        # 若未提供系统提示词，使用默认计算机网络学习助手角色设定
        default_system_prompt = (
            '你是一位计算机网络的专业学习助教，擅长用通俗且结构化的方式讲解概念与原理。\n'
            '教学范围包括但不限于：OSI 与 TCP/IP 分层模型、以太网与链路层、IP/子网划分/CIDR、\n'
            'ARP 与 ICMP、路由与交换（RIP/OSPF/BGP/ACL）、NAT、TCP 可靠传输与拥塞控制、\n'
            'UDP 特性、应用层协议（HTTP/HTTPS/DNS/SMTP/FTP 等）、TLS/证书、常见网络安全与排错。\n\n'
            '请遵循以下风格：\n'
            '1) 先给出要点纲要，再逐步展开；\n'
            '2) 结合小例子、对比表或简单 ASCII 图帮助理解；\n'
            '3) 回答尽量具体、避免空话，必要时给出命令或抓包思路；\n'
            '4) 若用户提出考试/面试需求，可提供高频题与解题思路；\n'
            '5) 若问题不清晰，先澄清再解答；如果涉及风险操作，提醒注意事项。\n\n'
            '当用户没有特别指定深度时，默认从概念->原理->实践的层次化方式来讲解，并在结尾给出1-2个\n'
            '简短练习或思考题以促进记忆。'
        )
        if not system_prompt or not str(system_prompt).strip():
            system_prompt = default_system_prompt

        if not message:
            return jsonify({'success': False, 'message': '缺少消息内容 message'}), 400

        # RAG 检索增强
        knowledge_context = ''
        sources = []
        if use_rag:
            try:
                rag = _get_rag_service()
                chunks = rag.search(message, top_k=5)
                if chunks:
                    knowledge_context, sources = rag.build_context_block(chunks)
            except Exception as e:
                print(f'[server] RAG 检索失败，回退到纯对话模式: {e}')

        # 组装最终提示词
        prompt_parts = []
        if system_prompt and str(system_prompt).strip():
            prompt_parts.append(str(system_prompt).strip())
        if knowledge_context:
            prompt_parts.append(knowledge_context)
        prompt_parts.append(message)
        final_prompt = "\n\n".join(prompt_parts)

        def generate():
            """服务端生成器：SSE 流式推送。"""
            try:
                yield f"data: {json.dumps({'reply': ''})}\n\n"
            except Exception:
                pass

            try:
                for chunk in deepseek_chat.chat_with_deepseek_stream(final_prompt):
                    if not chunk:
                        continue
                    step = 64
                    for i in range(0, len(chunk), step):
                        sub = chunk[i:i+step]
                        yield f"data: {json.dumps({'reply': sub})}\n\n"
            except Exception as e:
                err_text = f"[服务异常] {e}"
                yield f"data: {json.dumps({'reply': err_text})}\n\n"
            finally:
                # 结束标识（含来源引用）
                done_msg = {'reply': '', 'done': True}
                if sources:
                    done_msg['sources'] = sources
                yield f"data: {json.dumps(done_msg)}\n\n"

        headers = {
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
        return Response(generate(), headers=headers)
    except Exception as e:
        print('[server] /api/chat 异常:', e)
        return jsonify({'success': False, 'message': '聊天接口异常', 'error': str(e)}), 500

# 全局 CORS 处理：为所有响应追加必要的跨域头，并允许预检通过
@app.after_request
def apply_cors_headers(resp: Response):
    """全局 after_request 钩子：
    为所有响应追加跨域相关响应头，允许来自任意源的 GET/POST/PUT/DELETE/OPTIONS 访问，
    并暴露 Content-Type 以便前端正确处理流式/SSE 响应。
    """
    try:
        resp.headers['Access-Control-Allow-Origin'] = '*'
        resp.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
        resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        resp.headers['Access-Control-Expose-Headers'] = 'Content-Type'
        resp.headers['Vary'] = 'Origin'
    except Exception:
        pass
    return resp
@app.route('/<path:any_path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def fallback_handler(any_path):
    """
    兜底路由处理：
    - OPTIONS: 返回 204 (CORS预检)
    - 其他: 返回 404 (未找到)
    避免因为只有 OPTIONS 路由而导致未定义的 URL 返回 405。
    """
    if request.method == 'OPTIONS':
        return ('', 204)
    return jsonify({'success': False, 'message': 'Not Found'}), 404

# ======================= 知识库 API 接口 =======================

@app.route('/api/knowledge/search', methods=['GET'])
def knowledge_search():
    """
    知识库检索接口。
    参数: q (查询文本), top_k (默认5, 最大20), doc_type (可选过滤)
    返回: { success, chunks: [{chunk_id, content, doc_title, source, source_page, score}] }
    """
    try:
        query = request.args.get('q', '').strip()
        if not query:
            return jsonify({'success': False, 'message': '缺少搜索关键词 q'}), 400

        try:
            top_k = int(request.args.get('top_k', 5))
        except Exception:
            top_k = 5
        top_k = max(1, min(top_k, 20))

        doc_type = request.args.get('doc_type', '').strip() or None

        rag = _get_rag_service()
        chunks = rag.search(query, top_k=top_k, doc_type=doc_type)

        return jsonify({
            'success': True,
            'chunks': chunks,
            'total': len(chunks),
            'query': query,
        })
    except Exception as e:
        print('[server] /api/knowledge/search 异常:', e)
        return jsonify({'success': False, 'message': '知识检索失败', 'error': str(e)}), 500


@app.route('/api/knowledge/documents', methods=['GET'])
def knowledge_documents_list():
    """知识文档列表（分页）。"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        doc_type = request.args.get('doc_type', '').strip() or None

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        where = "WHERE status = 'published'"
        params = []
        if doc_type:
            where += " AND doc_type = %s"
            params.append(doc_type)

        cursor.execute(f"SELECT COUNT(*) AS cnt FROM knowledge_documents {where}", params)
        total = cursor.fetchone()['cnt']

        offset = (page - 1) * page_size
        cursor.execute(
            f"""SELECT doc_id, title, doc_type, source, source_page, difficulty,
                       knowledge_points, osi_layer, created_at
                FROM knowledge_documents {where}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s""",
            params + [page_size, offset]
        )
        rows = cursor.fetchall() or []
        documents = []
        for r in rows:
            kps_raw = r.get('knowledge_points', '')
            kps = json.loads(kps_raw) if kps_raw and isinstance(kps_raw, str) else []
            documents.append({
                'doc_id': r['doc_id'],
                'title': r['title'],
                'doc_type': r['doc_type'],
                'source': r['source'],
                'source_page': r.get('source_page', ''),
                'difficulty': r.get('difficulty', ''),
                'knowledge_points': kps,
                'osi_layer': r.get('osi_layer', ''),
                'created_at': str(r['created_at']) if r.get('created_at') else '',
            })

        cursor.close(); conn.close()
        return jsonify({
            'success': True, 'items': documents, 'total': total,
            'page': page, 'page_size': page_size
        })
    except Exception as e:
        return jsonify({'success': False, 'message': '获取文档列表失败', 'error': str(e)}), 500


@app.route('/api/knowledge/documents/<int:doc_id>', methods=['GET'])
def knowledge_document_detail(doc_id):
    """获取文档详情及其分块列表。"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        cursor.execute(
            """SELECT doc_id, title, doc_type, source, source_page, difficulty,
                      knowledge_points, osi_layer, status, created_at, updated_at
               FROM knowledge_documents WHERE doc_id = %s""",
            (doc_id,)
        )
        doc = cursor.fetchone()
        if not doc:
            cursor.close(); conn.close()
            return jsonify({'success': False, 'message': '文档不存在'}), 404

        kps_raw = doc.get('knowledge_points', '')
        kps = json.loads(kps_raw) if kps_raw and isinstance(kps_raw, str) else []
        document = {
            'doc_id': doc['doc_id'], 'title': doc['title'],
            'doc_type': doc['doc_type'], 'source': doc['source'],
            'source_page': doc.get('source_page', ''),
            'difficulty': doc.get('difficulty', ''), 'knowledge_points': kps,
            'osi_layer': doc.get('osi_layer', ''),
            'status': doc.get('status', ''),
            'created_at': str(doc['created_at']) if doc.get('created_at') else '',
            'updated_at': str(doc['updated_at']) if doc.get('updated_at') else '',
        }

        cursor.execute(
            """SELECT chunk_id, chunk_index, token_count, sub_topic_id, created_at
               FROM knowledge_chunks WHERE doc_id = %s ORDER BY chunk_index""",
            (doc_id,)
        )
        chunks = []
        for r in (cursor.fetchall() or []):
            chunks.append({
                'chunk_id': r['chunk_id'], 'chunk_index': r['chunk_index'],
                'token_count': r.get('token_count', 0),
                'sub_topic_id': r.get('sub_topic_id'),
                'created_at': str(r['created_at']) if r.get('created_at') else '',
            })
        document['chunks'] = chunks
        document['chunk_count'] = len(chunks)

        cursor.close(); conn.close()
        return jsonify({'success': True, 'document': document})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取文档详情失败', 'error': str(e)}), 500


@app.route('/api/knowledge/sub-topics', methods=['GET'])
def knowledge_sub_topics():
    """获取子知识点列表。可按 parent_kp 过滤。"""
    try:
        parent_kp = request.args.get('parent_kp', '').strip() or None
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        if parent_kp:
            cursor.execute(
                """SELECT sub_topic_id, sub_topic_name, parent_kp, description, sort_order
                   FROM knowledge_sub_topics WHERE parent_kp = %s ORDER BY sort_order""",
                (parent_kp,)
            )
        else:
            cursor.execute(
                """SELECT sub_topic_id, sub_topic_name, parent_kp, description, sort_order
                   FROM knowledge_sub_topics ORDER BY parent_kp, sort_order"""
            )

        rows = cursor.fetchall() or []
        items = [{
            'sub_topic_id': r['sub_topic_id'],
            'sub_topic_name': r['sub_topic_name'],
            'parent_kp': r['parent_kp'],
            'description': r.get('description', ''),
            'sort_order': r.get('sort_order', 0),
        } for r in rows]

        cursor.close(); conn.close()
        return jsonify({'success': True, 'items': items, 'total': len(items)})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取子知识点失败', 'error': str(e)}), 500


@app.route('/api/knowledge/relations', methods=['GET'])
def knowledge_relations_list():
    """获取知识关系图。可按知识点过滤。"""
    try:
        kp = request.args.get('kp', '').strip() or None
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        if kp:
            cursor.execute(
                """SELECT relation_id, source_kp, target_kp, relation_type, description
                   FROM knowledge_relations
                   WHERE source_kp = %s OR target_kp = %s""",
                (kp, kp)
            )
        else:
            cursor.execute(
                """SELECT relation_id, source_kp, target_kp, relation_type, description
                   FROM knowledge_relations"""
            )

        rows = cursor.fetchall() or []
        items = [{
            'relation_id': r['relation_id'],
            'source_kp': r['source_kp'],
            'target_kp': r['target_kp'],
            'relation_type': r['relation_type'],
            'description': r.get('description', ''),
        } for r in rows]

        cursor.close(); conn.close()
        return jsonify({'success': True, 'items': items, 'total': len(items)})
    except Exception as e:
        return jsonify({'success': False, 'message': '获取知识关系失败', 'error': str(e)}), 500


# 题目管理相关API接口
@app.route('/api/admin/import-problems', methods=['POST'])
def import_problems():
    """
    批量导入题目接口
    接收JSON格式的题目数组，批量插入到数据库
    """
    try:
        data = request.get_json(force=True) or {}
        problems = data.get('problems', [])
        
        if not problems or not isinstance(problems, list):
            return jsonify({'success': False, 'message': '请提供有效的题目数组'}), 400
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for i, problem in enumerate(problems):
            try:
                # 验证必需字段
                required_fields = ['problem_num', 'problem', 'answer', 'difficulty', 'knowledge_point']
                for field in required_fields:
                    if not problem.get(field):
                        errors.append(f'第 {i+1} 道题目缺少字段: {field}')
                        continue
                
                # 检查题目编号是否已存在
                cursor.execute("SELECT problem_id FROM problems WHERE problem_num = %s", (problem['problem_num'],))
                if cursor.fetchone():
                    skipped_count += 1
                    continue
                
                # 插入题目
                insert_sql = """
                    INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    problem['problem_num'],
                    problem['problem'],
                    problem['answer'],
                    problem['difficulty'],
                    problem['knowledge_point']
                ))
                imported_count += 1
                
            except Exception as e:
                errors.append(f'第 {i+1} 道题目导入失败: {str(e)}')
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        result = {
            'success': True,
            'imported_count': imported_count,
            'skipped_count': skipped_count,
            'total_count': len(problems)
        }
        
        if errors:
            result['errors'] = errors
            result['message'] = f'导入完成，成功 {imported_count} 道，跳过 {skipped_count} 道，错误 {len(errors)} 道'
        else:
            result['message'] = f'导入完成，成功 {imported_count} 道，跳过 {skipped_count} 道'
        
        return jsonify(result)
        
    except Exception as e:
        print(f'[server] 批量导入题目异常: {e}')
        return jsonify({'success': False, 'message': f'导入失败: {str(e)}'}), 500

@app.route('/api/admin/problems', methods=['GET'])
def get_admin_problems():
    """
    获取题目列表（管理员用）
    支持分页、搜索、筛选
    """
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        search = request.args.get('search', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        knowledge_point = request.args.get('knowledge_point', '').strip()
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 构建查询条件
        where_conditions = []
        params = []
        
        if search:
            where_conditions.append("(problem LIKE %s OR problem_num LIKE %s OR answer LIKE %s)")
            search_param = f'%{search}%'
            params.extend([search_param, search_param, search_param])
        
        if difficulty:
            where_conditions.append("difficulty = %s")
            params.append(difficulty)
        
        if knowledge_point:
            where_conditions.append("knowledge_point = %s")
            params.append(knowledge_point)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # 获取总数
        count_sql = f"SELECT COUNT(*) as total FROM problems WHERE {where_clause}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()['total']
        total_pages = (total_count + page_size - 1) // page_size
        
        # 获取分页数据
        offset = (page - 1) * page_size
        data_sql = f"""
            SELECT problem_id, problem_num, problem, answer, difficulty, knowledge_point, created_at
            FROM problems 
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(data_sql, params + [page_size, offset])
        problems = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'problems': problems,
            'total_count': total_count,
            'total_pages': total_pages,
            'current_page': page,
            'page_size': page_size
        })
        
    except Exception as e:
        print(f'[server] 获取题目列表异常: {e}')
        return jsonify({'success': False, 'message': f'获取题目列表失败: {str(e)}'}), 500

@app.route('/api/admin/problems/<int:problem_id>', methods=['PUT'])
def update_problem(problem_id):
    """
    更新题目
    """
    try:
        data = request.get_json(force=True) or {}
        
        # 验证必需字段
        required_fields = ['problem_num', 'problem', 'answer', 'difficulty', 'knowledge_point']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'缺少字段: {field}'}), 400
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 检查题目是否存在
        cursor.execute("SELECT problem_id FROM problems WHERE problem_id = %s", (problem_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': '题目不存在'}), 404
        
        # 检查题目编号是否与其他题目冲突
        cursor.execute("SELECT problem_id FROM problems WHERE problem_num = %s AND problem_id != %s", 
                      (data['problem_num'], problem_id))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': '题目编号已存在'}), 400
        
        # 更新题目
        update_sql = """
            UPDATE problems 
            SET problem_num = %s, problem = %s, answer = %s, difficulty = %s, knowledge_point = %s
            WHERE problem_id = %s
        """
        cursor.execute(update_sql, (
            data['problem_num'],
            data['problem'],
            data['answer'],
            data['difficulty'],
            data['knowledge_point'],
            problem_id
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '题目更新成功'})
        
    except Exception as e:
        print(f'[server] 更新题目异常: {e}')
        return jsonify({'success': False, 'message': f'更新题目失败: {str(e)}'}), 500

@app.route('/api/admin/problems/<int:problem_id>', methods=['DELETE'])
def delete_problem(problem_id):
    """
    删除题目
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 检查题目是否存在
        cursor.execute("SELECT problem_id FROM problems WHERE problem_id = %s", (problem_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': '题目不存在'}), 404
        
        # 删除相关的答题记录
        cursor.execute("DELETE FROM user_answers WHERE problem_id = %s", (problem_id,))
        
        # 删除题目
        cursor.execute("DELETE FROM problems WHERE problem_id = %s", (problem_id,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '题目删除成功'})
        
    except Exception as e:
        print(f'[server] 删除题目异常: {e}')
        return jsonify({'success': False, 'message': f'删除题目失败: {str(e)}'}), 500

@app.route('/api/admin/problems', methods=['POST'])
def create_problem():
    """
    创建新题目
    """
    try:
        data = request.get_json(force=True) or {}
        
        # 验证必需字段
        required_fields = ['problem_num', 'problem', 'answer', 'difficulty', 'knowledge_point']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'message': f'缺少字段: {field}'}), 400
        
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 检查题目编号是否已存在
        cursor.execute("SELECT problem_id FROM problems WHERE problem_num = %s", (data['problem_num'],))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': '题目编号已存在'}), 400
        
        # 插入题目
        insert_sql = """
            INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (
            data['problem_num'],
            data['problem'],
            data['answer'],
            data['difficulty'],
            data['knowledge_point']
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': '题目创建成功'})
        
    except Exception as e:
        print(f'[server] 创建题目异常: {e}')
        return jsonify({'success': False, 'message': f'创建题目失败: {str(e)}'}), 500

@app.route('/api/admin/knowledge-points', methods=['GET'])
def get_admin_knowledge_points():
    """
    获取所有知识点列表
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        cursor.execute("SELECT DISTINCT knowledge_point FROM problems ORDER BY knowledge_point")
        knowledge_points = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'knowledge_points': knowledge_points
        })
        
    except Exception as e:
        print(f'[server] 获取知识点列表异常: {e}')
        return jsonify({'success': False, 'message': f'获取知识点列表失败: {str(e)}'}), 500

@app.route('/api/admin/stats', methods=['GET'])
def get_admin_stats():
    """
    获取题目统计信息
    """
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        stats = {}
        
        # 总题目数
        cursor.execute("SELECT COUNT(*) as total FROM problems")
        stats['total_problems'] = cursor.fetchone()['total']
        
        # 难度分布
        cursor.execute("""
            SELECT difficulty, COUNT(*) as count 
            FROM problems 
            GROUP BY difficulty
        """)
        difficulty_stats = {}
        for row in cursor.fetchall():
            difficulty_stats[row['difficulty']] = row['count']
        stats['difficulty_stats'] = difficulty_stats
        
        # 知识点分布（前10个）
        cursor.execute("""
            SELECT knowledge_point, COUNT(*) as count 
            FROM problems 
            GROUP BY knowledge_point 
            ORDER BY count DESC 
            LIMIT 10
        """)
        knowledge_stats = {}
        for row in cursor.fetchall():
            knowledge_stats[row['knowledge_point']] = row['count']
        stats['knowledge_stats'] = knowledge_stats
        
        # 最近添加的题目（前5个）
        cursor.execute("""
            SELECT problem_id, problem_num, problem, created_at
            FROM problems 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        stats['recent_problems'] = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f'[server] 获取统计信息异常: {e}')
        return jsonify({'success': False, 'message': f'获取统计信息失败: {str(e)}'}), 500

if __name__ == '__main__':
    # 开发环境建议开启 debug，但禁用自动重载以避免 Windows 下 watchdog 误触发导致频繁重启
    # 注意：仅保留一个 app.run 调用，防止重复与语法错误
    # threaded=True 必须开启：debug 模式下 Flask 默认单线程，会导致流式请求阻塞其他请求
    app.run(port=3001, debug=True, use_reloader=False, threaded=True)
