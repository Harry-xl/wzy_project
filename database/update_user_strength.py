import os
import mysql.connector

# MySQL配置
db_config = {
    'host': os.getenv('MYSQL_HOST', 'localhost'),
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', ''),
    'database': os.getenv('MYSQL_DATABASE', 'wzyProjectDb')
}

def update_database():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 添加user_strength字段
        print("添加user_strength字段...")
        cursor.execute("""
            ALTER TABLE user ADD COLUMN user_strength FLOAT NOT NULL DEFAULT 0.5 
            COMMENT 'User strength level (0.0-1.0, 0.5 is medium)'
        """)
        
        # 为现有用户计算并设置初始实力值
        print("为现有用户设置初始实力值...")
        cursor.execute("""
            UPDATE user 
            SET user_strength = (
                SELECT COALESCE(AVG(proficiency_level), 0.5) 
                FROM ability_profile 
                WHERE ability_profile.user_id = user.user_id
            )
        """)
        
        conn.commit()
        print("数据库更新成功！")
        
        # 验证更新结果
        cursor.execute("SELECT user_id, name, user_strength FROM user")
        results = cursor.fetchall()
        print("\n用户实力数据：")
        for row in results:
            print(f"用户ID: {row[0]}, 姓名: {row[1]}, 实力: {row[2]:.2f}")
            
    except mysql.connector.Error as e:
        if e.errno == 1060:  # 字段已存在
            print("user_strength字段已存在，跳过添加步骤")
            # 仍然更新实力值
            cursor.execute("""
                UPDATE user 
                SET user_strength = (
                    SELECT COALESCE(AVG(proficiency_level), 0.5) 
                    FROM ability_profile 
                    WHERE ability_profile.user_id = user.user_id
                )
            """)
            conn.commit()
            print("用户实力值更新完成！")
        else:
            print(f"数据库错误: {e}")
    except Exception as e:
        print(f"执行失败: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    update_database()