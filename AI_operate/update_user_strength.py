import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection

def add_user_strength_field():
    """
    为用户表添加实力字段并初始化数据
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'wzyProjectDb' 
            AND TABLE_NAME = 'user' 
            AND COLUMN_NAME = 'user_strength'
        """)
        
        result = cursor.fetchone()
        if result[0] > 0:
            print("user_strength字段已存在，跳过添加步骤")
        else:
            # 添加user_strength字段
            print("正在添加user_strength字段...")
            cursor.execute("""
                ALTER TABLE user 
                ADD COLUMN user_strength FLOAT NOT NULL DEFAULT 0.5 
                COMMENT '用户实力水平(0.0-1.0，0.5为中等)'
            """)
            print("user_strength字段添加成功！")
        
        # 为现有用户设置初始实力值
        print("正在计算并更新用户实力值...")
        cursor.execute("""
            UPDATE user u 
            SET user_strength = (
                SELECT COALESCE(AVG(ap.proficiency_level), 0.5)
                FROM ability_profile ap 
                WHERE ap.user_id = u.user_id
            )
            WHERE u.user_id IN (SELECT DISTINCT user_id FROM ability_profile)
        """)
        
        conn.commit()
        print("用户实力值更新完成！")
        
        # 显示更新结果
        cursor.execute("SELECT user_id, name, user_strength FROM user")
        results = cursor.fetchall()
        
        print("\n更新结果：")
        print("用户ID | 用户名 | 实力值")
        print("-" * 30)
        for row in results:
            user_id, name, strength = row
            strength_level = get_strength_level(strength)
            print(f"{user_id:6} | {name:6} | {strength:.2f} ({strength_level})")
            
    except Exception as e:
        print(f"执行过程中出现错误: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_strength_level(strength):
    """根据实力值返回等级描述"""
    if strength >= 0.8:
        return "高级"
    elif strength >= 0.6:
        return "中级"
    elif strength >= 0.4:
        return "初级"
    else:
        return "入门"

if __name__ == "__main__":
    print("开始更新数据库...")
    add_user_strength_field()
    print("数据库更新完成！")