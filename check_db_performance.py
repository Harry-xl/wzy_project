import os
import mysql.connector
import time

# 数据库配置
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'wzyProjectDb')
}

def check_table_structure():
    """检查ability_profile表结构和索引"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        print("=== ability_profile表结构 ===")
        cursor.execute("SHOW CREATE TABLE ability_profile")
        result = cursor.fetchone()
        print(result[1])
        
        print("\n=== ability_profile表索引 ===")
        cursor.execute("SHOW INDEX FROM ability_profile")
        indexes = cursor.fetchall()
        for index in indexes:
            print(f"表: {index[0]}, 索引名: {index[2]}, 列名: {index[4]}, 唯一性: {index[1]}")
        
        print("\n=== user表索引 ===")
        cursor.execute("SHOW INDEX FROM user")
        indexes = cursor.fetchall()
        for index in indexes:
            print(f"表: {index[0]}, 索引名: {index[2]}, 列名: {index[4]}, 唯一性: {index[1]}")
            
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"检查表结构失败: {e}")

def test_query_performance():
    """测试查询性能"""
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)
        
        # 测试用户画像查询性能
        print("\n=== 查询性能测试 ===")
        
        # 获取一个测试用户ID
        cursor.execute("SELECT user_id FROM user LIMIT 1")
        test_user = cursor.fetchone()
        if not test_user:
            print("没有找到测试用户")
            return
            
        user_id = test_user['user_id']
        print(f"测试用户ID: {user_id}")
        
        # 测试能力画像查询
        start_time = time.time()
        cursor.execute("""
            SELECT knowledge_point, proficiency_level 
            FROM ability_profile 
            WHERE user_id = %s
        """, (user_id,))
        results = cursor.fetchall()
        end_time = time.time()
        
        print(f"能力画像查询耗时: {(end_time - start_time) * 1000:.2f}ms")
        print(f"返回记录数: {len(results)}")
        
        # 测试用户基本信息查询
        start_time = time.time()
        cursor.execute("SELECT name, email, user_strength FROM user WHERE user_id=%s", (user_id,))
        user_info = cursor.fetchone()
        end_time = time.time()
        
        print(f"用户信息查询耗时: {(end_time - start_time) * 1000:.2f}ms")
        
        # 检查数据量
        cursor.execute("SELECT COUNT(*) as total FROM ability_profile")
        total_records = cursor.fetchone()['total']
        print(f"ability_profile表总记录数: {total_records}")
        
        cursor.execute("SELECT COUNT(*) as total FROM user")
        total_users = cursor.fetchone()['total']
        print(f"user表总记录数: {total_users}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"性能测试失败: {e}")

if __name__ == "__main__":
    check_table_structure()
    test_query_performance()