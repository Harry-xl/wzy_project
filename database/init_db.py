import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import mysql.connector

# 自动加载项目根目录下的 .env 文件
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# 与 server/app.py 保持一致
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'wzyProjectDb')
}

BASE_DIR = Path(__file__).resolve().parent.parent
SQL_DIR = BASE_DIR / 'database'

CREATE_SQL = SQL_DIR / 'create_db.sql'
INSERT_SQL = SQL_DIR / 'insert_test_data.sql'
ADD_STRENGTH_SQL = SQL_DIR / 'add_user_strength.sql'


def read_sql(path: Path) -> str:
    """
    读取 SQL 文件内容。
    :param path: SQL 文件路径
    :return: SQL 文本
    """
    with path.open('r', encoding='utf-8') as f:
        return f.read()


def execute_multi_sql(conn, sql_text: str, info: str):
    """
    在同一个连接中按 multi=True 执行多条 SQL 语句，遇到错误仅记录警告，不中断后续初始化。
    :param conn: MySQL 连接
    :param sql_text: SQL 文本，可能包含多条语句
    :param info: 日志提示信息
    """
    print(f'==> 执行 {info} ...')
    try:
        with conn.cursor() as cursor:
            for result in cursor.execute(sql_text, multi=True):
                # 消费所有结果集，防止 "Unread result found" 错误
                if result.with_rows:
                    result.fetchall()
        conn.commit()
        print(f'==> {info} 完成')
    except Exception as e:
        print(f'[WARN] 执行 {info} 出错：{e}')


def ensure_password_length(conn):
    """
    确保 user.password 字段长度足够存储哈希（如 PBKDF2 串通常超过 100 字符）。
    将其迁移为 VARCHAR(255)。重复执行安全。
    """
    try:
        print('==> 校验并迁移 user.password 字段长度为 VARCHAR(255) ...')
        with conn.cursor() as cursor:
            cursor.execute("""
                ALTER TABLE `user` 
                MODIFY `password` VARCHAR(255) NOT NULL COMMENT '用户密码（哈希存储）'
            """)
        conn.commit()
        print('==> user.password 字段长度已确保为 VARCHAR(255)')
    except Exception as e:
        # 如果字段已是足够长度或没有权限，打印警告但不中断
        print(f'[WARN] 迁移 user.password 字段长度时出错：{e}')


def main():
    print('=== 数据库初始化开始 ===')
    # 第一步：连接到 MySQL（不指定数据库），执行 create_db.sql（包含 CREATE DATABASE 与建表）
    try:
        print('连接到 MySQL（不指定数据库）...')
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
    except Exception as e:
        print('[ERROR] 无法连接 MySQL，请检查账号密码与服务是否启动：', e)
        sys.exit(1)

    try:
        create_sql = read_sql(CREATE_SQL)
        execute_multi_sql(conn, create_sql, 'create_db.sql（建库/建表）')
    finally:
        conn.close()

    # 第二步：连接到具体数据库，执行测试数据与用户实力字段初始化、密码字段长度迁移
    try:
        print(f"连接到数据库 {DB_CONFIG['database']} ...")
        conn2 = mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        print(f'[ERROR] 无法连接数据库 {DB_CONFIG["database"]}：', e)
        sys.exit(1)

    try:
        # 导入测试数据
        insert_sql = read_sql(INSERT_SQL)
        execute_multi_sql(conn2, insert_sql, 'insert_test_data.sql（测试数据）')

        # 增加并初始化用户实力字段
        add_strength_sql = read_sql(ADD_STRENGTH_SQL)
        execute_multi_sql(conn2, add_strength_sql, 'add_user_strength.sql（用户实力字段与初始化）')

        # 确保密码字段长度足够存储哈希
        ensure_password_length(conn2)

        # 知识库表与字段迁移
        kb_sql_path = SQL_DIR / 'migrations' / '002_knowledge_base.sql'
        if kb_sql_path.exists():
            kb_sql = read_sql(kb_sql_path)
            execute_multi_sql(conn2, kb_sql, '002_knowledge_base.sql（知识库表与字段）')

        # 个人资料库迁移
        lib_sql_path = SQL_DIR / 'migrations' / '003_library.sql'
        if lib_sql_path.exists():
            lib_sql = read_sql(lib_sql_path)
            execute_multi_sql(conn2, lib_sql, '003_library.sql（资料库表与双轨字段）')

        # 知识点体系统一 + 计算机网络测试数据
        unify_sql_path = SQL_DIR / 'migrations' / '004_unify_knowledge_points.sql'
        if unify_sql_path.exists():
            unify_sql = read_sql(unify_sql_path)
            execute_multi_sql(conn2, unify_sql, '004_unify_knowledge_points.sql（知识点体系统一）')

        # 学习卡片缓存 + 文档可读内容
        cards_sql_path = SQL_DIR / 'migrations' / '005_learning_cards.sql'
        if cards_sql_path.exists():
            cards_sql = read_sql(cards_sql_path)
            execute_multi_sql(conn2, cards_sql, '005_learning_cards.sql（学习卡片与可读内容）')

        print('=== 数据库初始化完成 ===')
    finally:
        conn2.close()


if __name__ == '__main__':
    main()