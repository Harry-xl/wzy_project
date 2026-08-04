# db.py
import pymysql
from config import DB_CONFIG

def get_connection():
    return pymysql.connect(
        host=DB_CONFIG["host"],
        user=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        database=DB_CONFIG["database"],
        charset=DB_CONFIG["charset"],
        autocommit=False
    )

def insert_problems_batch(rows: list):
    if not rows:
        return 0

    sql = """
    INSERT INTO problems
    (problem_num, problem, answer, difficulty, knowledge_point, osi_layer)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      problem = VALUES(problem),
      answer = VALUES(answer),
      difficulty = VALUES(difficulty),
      knowledge_point = VALUES(knowledge_point),
      osi_layer = VALUES(osi_layer)
    """

    conn = get_connection()
    inserted = 0
    try:
        with conn.cursor() as cursor:
            for row in rows:
                try:
                    cursor.execute(sql, row)
                    inserted += 1
                except Exception as e:
                    print(f"[DB] 写库失败，跳过：{row[0]} | 错误：{e}")
        conn.commit()
        return inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
