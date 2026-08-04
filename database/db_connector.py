import os
import mysql.connector
from mysql.connector import pooling

# 数据库配置（从环境变量读取，提供合理默认值）
DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'wzyProjectDb'),
    'port': int(os.getenv('MYSQL_PORT', '3306'))
}

# 创建连接池
connection_pool = pooling.MySQLConnectionPool(
    pool_name="wzy_pool",
    pool_size=5,
    **DB_CONFIG
)

def get_connection():
    """
    获取数据库连接
    """
    try:
        return connection_pool.get_connection()
    except mysql.connector.Error as err:
        print(f"数据库连接失败: {err}")
        return None

# 测试连接
if __name__ == "__main__":
    conn = get_connection()
    if conn:
        print("成功连接到数据库！")
        conn.close()