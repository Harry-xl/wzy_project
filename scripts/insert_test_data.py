"""
星伴(StarPal) 测试数据导入脚本。
创建测试用户、计算机网络题目、模拟学习记录。

用法:
    python scripts/insert_test_data.py
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection


# ================================================================
# 1. 测试用户
# ================================================================
TEST_USERS = [
    {
        "email": "test@star.com",
        "name": "测试学生",
        "password": "123456",  # 明文，入库时自动哈希
    },
    {
        "email": "demo@star.com",
        "name": "演示用户",
        "password": "demo123",
    },
]

# ================================================================
# 2. 计算机网络题目（20 道，覆盖多个知识点和难度）
# ================================================================
TEST_PROBLEMS = [
    # ---- 网络体系结构 ----
    {
        "problem_num": "NET-00101",
        "problem": "在 OSI 七层模型中，路由器工作在哪一层？\nA. 物理层\nB. 数据链路层\nC. 网络层\nD. 传输层",
        "answer": "C",
        "difficulty": "简单",
        "knowledge_point": "网络体系结构",
    },
    {
        "problem_num": "NET-00102",
        "problem": "TCP/IP 模型中，对应 OSI 数据链路层和物理层的是哪一层？\nA. 应用层\nB. 传输层\nC. 网际层\nD. 网络接口层",
        "answer": "D",
        "difficulty": "简单",
        "knowledge_point": "网络体系结构",
    },
    # ---- IP 地址与子网划分 ----
    {
        "problem_num": "NET-00201",
        "problem": "某公司获得一个 C 类地址 192.168.1.0/24，需要划分为 4 个子网，每个子网至少容纳 50 台主机。可行的子网掩码是？\nA. 255.255.255.192 (/26)\nB. 255.255.255.224 (/27)\nC. 255.255.255.240 (/28)\nD. 255.255.255.128 (/25)",
        "answer": "A",
        "difficulty": "中等",
        "knowledge_point": "IP地址与子网划分",
    },
    {
        "problem_num": "NET-00202",
        "problem": "IP 地址 172.16.100.50/20 所在的网络地址是多少？\nA. 172.16.100.0\nB. 172.16.96.0\nC. 172.16.0.0\nD. 172.16.64.0",
        "answer": "B",
        "difficulty": "困难",
        "knowledge_point": "IP地址与子网划分",
    },
    {
        "problem_num": "NET-00203",
        "problem": "CIDR 地址块 10.0.0.0/10 包含多少个 IP 地址？\nA. 约 200 万\nB. 约 400 万\nC. 约 100 万\nD. 约 1600 万",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "IP地址与子网划分",
    },
    # ---- TCP 连接管理 ----
    {
        "problem_num": "NET-00301",
        "problem": "TCP 三次握手过程中，第二个报文（SYN+ACK）的确认号是多少？\nA. 客户端的初始序列号\nB. 客户端的初始序列号 + 1\nC. 服务器的初始序列号\nD. 服务器的初始序列号 + 1",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "TCP连接管理",
    },
    {
        "problem_num": "NET-00302",
        "problem": "TCP 四次挥手时，主动关闭方在发送最后一个 ACK 后进入什么状态？\nA. CLOSE_WAIT\nB. TIME_WAIT\nC. FIN_WAIT_2\nD. LAST_ACK",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "TCP连接管理",
    },
    {
        "problem_num": "NET-00303",
        "problem": "TIME_WAIT 状态持续 2MSL 的主要原因是？\nA. 确保对方收到最后一个 ACK\nB. 让旧连接的报文从网络中消失\nC. 等待对方重传数据\nD. A 和 B 都正确",
        "answer": "D",
        "difficulty": "简单",
        "knowledge_point": "TCP连接管理",
    },
    # ---- TCP 可靠传输与流量控制 ----
    {
        "problem_num": "NET-00401",
        "problem": "TCP 中，接收方通告的窗口大小 rwnd = 0 时，发送方会做什么？\nA. 立即关闭连接\nB. 持续发送数据直到超时\nC. 启动坚持定时器，定期发送窗口探测报文\nD. 减小拥塞窗口 cwnd",
        "answer": "C",
        "difficulty": "中等",
        "knowledge_point": "TCP可靠传输与流量控制",
    },
    # ---- TCP 拥塞控制 ----
    {
        "problem_num": "NET-00501",
        "problem": "TCP 拥塞控制中，当 cwnd < ssthresh 时，处于什么阶段？\nA. 拥塞避免\nB. 慢启动\nC. 快重传\nD. 快恢复",
        "answer": "B",
        "difficulty": "简单",
        "knowledge_point": "TCP拥塞控制",
    },
    {
        "problem_num": "NET-00502",
        "problem": "TCP Reno 与 Tahoe 相比，最大的改进是什么？\nA. 增加了慢启动\nB. 增加了拥塞避免\nC. 增加了快重传和快恢复\nD. 增加了选择性确认 SACK",
        "answer": "C",
        "difficulty": "中等",
        "knowledge_point": "TCP拥塞控制",
    },
    {
        "problem_num": "NET-00503",
        "problem": "收到 3 个冗余 ACK 后，TCP Reno 将 ssthresh 设为？\nA. cwnd\nB. cwnd / 2\nC. 1 MSS\nD. ssthresh 不变",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "TCP拥塞控制",
    },
    # ---- 路由算法与协议 ----
    {
        "problem_num": "NET-00601",
        "problem": "OSPF 使用什么算法计算最短路径？\nA. Bellman-Ford\nB. Dijkstra SPF\nC. 距离矢量\nD. 路径矢量",
        "answer": "B",
        "difficulty": "简单",
        "knowledge_point": "路由算法与协议",
    },
    {
        "problem_num": "NET-00602",
        "problem": "RIP 协议的最大跳数限制是多少？\nA. 10\nB. 15\nC. 16\nD. 无限制",
        "answer": "B",
        "difficulty": "简单",
        "knowledge_point": "路由算法与协议",
    },
    {
        "problem_num": "NET-00603",
        "problem": "BGP 使用什么传输层协议和端口？\nA. UDP 179\nB. TCP 179\nC. UDP 520\nD. TCP 520",
        "answer": "B",
        "difficulty": "简单",
        "knowledge_point": "路由算法与协议",
    },
    # ---- HTTP 与 HTTPS ----
    {
        "problem_num": "NET-00701",
        "problem": "HTTP 状态码 301 和 302 的区别是什么？\nA. 301 临时重定向，302 永久重定向\nB. 301 永久重定向，302 临时重定向\nC. 两者都是永久重定向\nD. 两者都是临时重定向",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "HTTP与HTTPS",
    },
    {
        "problem_num": "NET-00702",
        "problem": "HTTPS 默认使用哪个端口？\nA. 80\nB. 8080\nC. 443\nD. 8443",
        "answer": "C",
        "difficulty": "简单",
        "knowledge_point": "HTTP与HTTPS",
    },
    # ---- DNS 系统 ----
    {
        "problem_num": "NET-00801",
        "problem": "DNS 解析过程中，本地 DNS 服务器采用什么方式向根域名服务器查询？\nA. 递归查询\nB. 迭代查询\nC. 广播查询\nD. 组播查询",
        "answer": "B",
        "difficulty": "中等",
        "knowledge_point": "DNS系统",
    },
    # ---- ARP 协议 ----
    {
        "problem_num": "NET-00901",
        "problem": "ARP 协议的主要功能是什么？\nA. 将域名解析为 IP 地址\nB. 将 IP 地址解析为 MAC 地址\nC. 将 MAC 地址解析为 IP 地址\nD. 将端口号解析为 IP 地址",
        "answer": "B",
        "difficulty": "简单",
        "knowledge_point": "ARP协议",
    },
    # ---- 网络安全与防火墙 ----
    {
        "problem_num": "NET-01001",
        "problem": "SYN Flood 攻击利用了 TCP 的什么机制？\nA. 四次挥手\nB. 滑动窗口\nC. 三次握手\nD. 拥塞控制",
        "answer": "C",
        "difficulty": "中等",
        "knowledge_point": "网络安全与防火墙",
    },
]

# ================================================================
# 3. 模拟答题记录（测试学生做题 20 次，覆盖 6 个知识点）
# ================================================================
# 格式: (problem_num, user_answer, is_correct)
# 模拟模式：TCP连接管理答得好，TCP拥塞控制掌握一般，IP子网划分较弱
SIMULATED_ANSWERS = [
    # 第1天（6天前）: 5道题
    ("NET-00101", "C", True),   # OSI七层-路由器工作层 — 正确
    ("NET-00102", "C", False),  # TCP/IP vs OSI — 错误（答了C）
    ("NET-00301", "B", True),   # 三次握手ACK号 — 正确
    ("NET-00601", "B", True),   # OSPF算法 — 正确
    ("NET-00702", "C", True),   # HTTPS端口 — 正确
    # 第2天（5天前）: 5道题
    ("NET-00201", "C", False),  # 子网掩码计算 — 错误
    ("NET-00302", "B", True),   # TIME_WAIT状态 — 正确
    ("NET-00501", "A", False),  # 慢启动 vs 拥塞避免 — 错误（答了A）
    ("NET-00602", "B", True),   # RIP最大跳数 — 正确
    ("NET-00901", "B", True),   # ARP功能 — 正确
    # 第3天（4天前）: 5道题
    ("NET-00202", "C", False),  # 子网地址计算 — 错误
    ("NET-00303", "D", True),   # TIME_WAIT原因 — 正确
    ("NET-00502", "B", False),  # Reno vs Tahoe — 错误
    ("NET-00603", "B", True),   # BGP端口 — 正确
    ("NET-00801", "A", False),  # DNS查询方式 — 错误（答了A）
    # 第4天（2天前）: 5道题
    ("NET-00201", "A", True),   # 子网掩码 — 这次正确了
    ("NET-00503", "C", False),  # 3冗余ACK后的ssthresh — 错误
    ("NET-00701", "B", True),   # 301 vs 302 — 正确
    ("NET-01001", "C", True),   # SYN Flood攻击 — 正确
    ("NET-00203", "A", False),  # CIDR地址块计数 — 错误
]


def main():
    conn = get_connection()
    if not conn:
        print("[ERROR] 数据库连接失败")
        return

    cursor = conn.cursor(dictionary=True)

    try:
        # ---- 1. 创建测试用户 ----
        print("[1/3] 创建测试用户...")
        for u in TEST_USERS:
            hashed = generate_password_hash(u["password"], method='pbkdf2:sha256')
            try:
                cursor.execute(
                    """INSERT INTO user (email, name, password) VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE name=VALUES(name), password=VALUES(password)""",
                    (u["email"], u["name"], hashed),
                )
                conn.commit()
                print(f"  {u['email']} (密码: {u['password']}) — 已就绪")
            except Exception as e:
                print(f"  {u['email']} — 失败: {e}")

        # ---- 2. 导入题目 ----
        print("\n[2/3] 导入计算机网络题目...")
        imported = 0
        for p in TEST_PROBLEMS:
            try:
                cursor.execute(
                    """INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point)
                       VALUES (%s, %s, %s, %s, %s)
                       ON DUPLICATE KEY UPDATE
                       problem=VALUES(problem), answer=VALUES(answer),
                       difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point)""",
                    (p["problem_num"], p["problem"], p["answer"],
                     p["difficulty"], p["knowledge_point"]),
                )
                conn.commit()
                imported += 1
            except Exception as e:
                print(f"  {p['problem_num']} 导入失败: {e}")
        print(f"  已导入: {imported} 道题目")

        # ---- 3. 模拟学习记录 ----
        print("\n[3/3] 模拟学习记录...")

        # 获取测试用户的 user_id
        cursor.execute("SELECT user_id FROM user WHERE email = 'test@star.com'")
        user_row = cursor.fetchone()
        if not user_row:
            print("  [ERROR] 测试用户不存在，跳过")
            return
        user_id = user_row["user_id"]

        # 获取已导入题目的 problem_id 映射
        cursor.execute("SELECT problem_id, problem_num FROM problems WHERE problem_num LIKE 'NET-%'")
        pid_map = {r["problem_num"]: r["problem_id"] for r in cursor.fetchall()}

        # 清除该用户旧数据（幂等）
        cursor.execute("DELETE FROM user_answers WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM ability_profile WHERE user_id = %s", (user_id,))
        cursor.execute("DELETE FROM learning_sessions WHERE user_id = %s", (user_id,))
        conn.commit()
        print("  已清除旧的测试数据")

        # 模拟按时间顺序答题（4天，每天5道）
        day_offsets = [6, 5, 4, 2]  # 几天前
        answer_count = 0

        for day_idx, offset in enumerate(day_offsets):
            day_answers = SIMULATED_ANSWERS[day_idx * 5 : (day_idx + 1) * 5]

            for prob_num, user_ans, is_correct in day_answers:
                pid = pid_map.get(prob_num)
                if not pid:
                    continue

                # 答题时间
                answer_time = datetime.now() - timedelta(days=offset, hours=day_idx * 3)

                # 写入 user_answers
                cursor.execute(
                    """INSERT INTO user_answers (user_id, problem_id, user_answer, is_correct, answer_time)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (user_id, pid, user_ans, is_correct, answer_time),
                )
                answer_count += 1

                # 更新 ability_profile
                cursor.execute(
                    "SELECT knowledge_point FROM problems WHERE problem_id = %s", (pid,)
                )
                kp = cursor.fetchone()["knowledge_point"]

                cursor.execute(
                    "SELECT proficiency_level FROM ability_profile WHERE user_id = %s AND knowledge_point = %s",
                    (user_id, kp),
                )
                current = cursor.fetchone()
                current_level = current["proficiency_level"] if current else 0.5

                if is_correct:
                    new_level = min(1.0, current_level + 0.1)
                else:
                    new_level = max(0.0, current_level - 0.05)

                cursor.execute(
                    """INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level)
                       VALUES (%s, %s, %s)
                       ON DUPLICATE KEY UPDATE proficiency_level = %s""",
                    (user_id, kp, new_level, new_level),
                )
                conn.commit()

        # 更新用户整体实力
        cursor.execute(
            "SELECT AVG(proficiency_level) AS avg FROM ability_profile WHERE user_id = %s",
            (user_id,),
        )
        avg = cursor.fetchone()["avg"] or 0.5
        cursor.execute(
            "UPDATE user SET user_strength = %s WHERE user_id = %s",
            (round(avg, 2), user_id),
        )

        # 创建学习会话
        for day_idx, offset in enumerate(day_offsets):
            day_answers = SIMULATED_ANSWERS[day_idx * 5 : (day_idx + 1) * 5]
            total = len(day_answers)
            correct = sum(1 for _, _, is_correct in day_answers if is_correct)
            start_time = datetime.now() - timedelta(days=offset)
            end_time = start_time + timedelta(hours=1)

            cursor.execute(
                """INSERT INTO learning_sessions (user_id, start_time, end_time, total_problems, correct_problems)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, start_time, end_time, total, correct),
            )
        conn.commit()

        print(f"  已生成: {answer_count} 条答题记录")
        print(f"  已生成: 4 个学习会话")

        # ---- 总结 ----
        print("\n" + "=" * 50)
        print("测试数据导入完成！")
        print("=" * 50)

        # 用户
        cursor.execute("SELECT user_id, email, name, user_strength FROM user")
        for u in cursor.fetchall():
            print(f"  用户: {u['email']} (ID={u['user_id']}, 实力={u.get('user_strength', 'N/A')})")

        # 题目
        cursor.execute("SELECT COUNT(*) AS cnt FROM problems")
        print(f"  题库: {cursor.fetchone()['cnt']} 道")

        # 能力画像
        cursor.execute(
            """SELECT knowledge_point, proficiency_level FROM ability_profile
               WHERE user_id = %s ORDER BY proficiency_level ASC""",
            (user_id,),
        )
        print(f"  能力画像 (user_id={user_id}):")
        for r in cursor.fetchall():
            bar = "█" * int(r["proficiency_level"] * 20)
            print(f"    {r['knowledge_point']}: {r['proficiency_level']:.2f} {bar}")

        # 会话
        cursor.execute(
            """SELECT start_time, total_problems, correct_problems,
                      ROUND(correct_problems/total_problems*100, 1) AS rate
               FROM learning_sessions WHERE user_id = %s ORDER BY start_time""",
            (user_id,),
        )
        print(f"  学习会话:")
        for r in cursor.fetchall():
            t = str(r["start_time"])[:16]
            print(f"    {t} | {r['correct_problems']}/{r['total_problems']} ({r['rate']}%)")

        print(f"\n  测试账号登录: test@star.com / 123456")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
