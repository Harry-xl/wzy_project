import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.Ability_Profile import AbilityProfile

def show_all_users_profiles():
    """
    显示所有用户的能力画像概览
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 获取所有用户
        cursor.execute("SELECT user_id, name FROM user")
        users = cursor.fetchall()
        
        print("\n" + "="*60)
        print("           所有用户能力画像概览")
        print("="*60)
        
        for user in users:
            user_id = user['user_id']
            user_name = user['name']
            
            print(f"\n👤 用户: {user_name} (ID: {user_id})")
            print("-" * 40)
            
            # 获取用户能力画像
            profile = AbilityProfile(user_id)
            profile_data = profile._load_profile()
            
            if profile_data:
                # 按熟练度排序
                sorted_profile = sorted(profile_data.items(), key=lambda x: x[1], reverse=True)
                
                for knowledge_point, proficiency in sorted_profile:
                    # 创建进度条
                    bar_length = 20
                    filled_length = int(bar_length * proficiency)
                    bar = '█' * filled_length + '░' * (bar_length - filled_length)
                    
                    level = "🟢优秀" if proficiency >= 0.8 else "🟡良好" if proficiency >= 0.6 else "🟠一般" if proficiency >= 0.4 else "🔴需加强"
                    
                    print(f"  {knowledge_point:<15} [{bar}] {proficiency:.2f} {level}")
            else:
                print("  暂无能力画像数据")
                
    finally:
        if conn:
            conn.close()

def show_user_detail(user_id):
    """
    显示指定用户的详细能力画像
    """
    conn = get_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 获取用户信息
        cursor.execute("SELECT name FROM user WHERE user_id = %s", (user_id,))
        user = cursor.fetchone()
        
        if not user:
            print(f"用户 {user_id} 不存在")
            return
            
        # 获取用户实力
        profile = AbilityProfile(user_id)
        user_strength = profile.get_user_strength()
        
        print(f"\n👤 用户: {user['name']} (ID: {user_id})")
        print(f"💪 用户实力: {user_strength:.2f} ({get_strength_level(user_strength)})")
        print("="*50)
        
        # 获取能力画像
        profile = AbilityProfile(user_id)
        profile_data = profile._load_profile()
        
        if profile_data:
            print("\n📊 知识点熟练度:")
            sorted_profile = sorted(profile_data.items(), key=lambda x: x[1], reverse=True)
            
            for knowledge_point, proficiency in sorted_profile:
                bar_length = 30
                filled_length = int(bar_length * proficiency)
                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                
                level = "优秀" if proficiency >= 0.8 else "良好" if proficiency >= 0.6 else "一般" if proficiency >= 0.4 else "需加强"
                
                print(f"  {knowledge_point:<15} [{bar}] {proficiency:.2f} ({level})")
                
            # 分析强弱项
            strong_points = [k for k, v in profile_data.items() if v >= 0.7]
            weak_points = [k for k, v in profile_data.items() if v < 0.5]
            
            print(f"\n💪 强项知识点: {', '.join(strong_points) if strong_points else '暂无'}")
            print(f"📚 需加强知识点: {', '.join(weak_points) if weak_points else '暂无'}")
            
        else:
            print("暂无能力画像数据")
            
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
    while True:
        print("\n" + "="*50)
        print("         用户能力画像查看系统")
        print("="*50)
        print("1. 查看所有用户能力画像概览")
        print("2. 查看指定用户详细能力画像")
        print("3. 退出")
        
        choice = input("\n请选择操作 (1-3): ")
        
        if choice == '1':
            show_all_users_profiles()
        elif choice == '2':
            try:
                user_id = int(input("请输入用户ID: "))
                show_user_detail(user_id)
            except ValueError:
                print("请输入有效的用户ID")
        elif choice == '3':
            print("再见！")
            break
        else:
            print("无效选择，请重新输入")