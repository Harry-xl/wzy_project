# 创建一个测试脚本
import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from AI_operate.exam import get_user_progress
from AI_operate.Ability_Profile import AbilityProfile

def view_user_profile(user_id):
    """
    查看指定用户的能力画像
    """
    print(f"\n=== 用户 {user_id} 的能力画像 ===")
    
    # 方法1：使用 get_user_progress 获取完整报告
    report = get_user_progress(user_id)
    
    print("\n📊 能力画像：")
    if report['profile']:
        for knowledge_point, proficiency in report['profile'].items():
            level = "优秀" if proficiency >= 0.8 else "良好" if proficiency >= 0.6 else "一般" if proficiency >= 0.4 else "需加强"
            print(f"  {knowledge_point}: {proficiency:.2f} ({level})")
    else:
        print("  暂无能力画像数据")
    
    print("\n📈 答题统计：")
    stats = report['stats']
    if stats['total_answers'] > 0:
        accuracy = (stats['correct_answers'] / stats['total_answers']) * 100
        print(f"  总答题数: {stats['total_answers']}")
        print(f"  正确答题数: {stats['correct_answers']}")
        print(f"  正确率: {accuracy:.1f}%")
        print(f"  涉及题目数: {stats['unique_problems']}")
    else:
        print("  暂无答题记录")
    
    print("\n🎯 学习会话：")
    sessions = report['sessions']
    if sessions['total_sessions'] > 0:
        session_accuracy = (sessions['correct_problems'] / sessions['total_problems']) * 100 if sessions['total_problems'] > 0 else 0
        print(f"  学习会话数: {sessions['total_sessions']}")
        print(f"  总题目数: {sessions['total_problems']}")
        print(f"  正确题目数: {sessions['correct_problems']}")
        print(f"  会话正确率: {session_accuracy:.1f}%")
        print(f"  最后学习时间: {sessions['last_session']}")
    else:
        print("  暂无学习会话记录")
    '''
    # 方法2：获取AI分析
    print("\n🤖 AI分析：")
    profile = AbilityProfile(user_id)
    analysis = profile.get_ai_analysis()
    print(analysis)
    '''

if __name__ == "__main__":
    # 查看用户1的能力画像
    view_user_profile(1)
    
    # 查看用户2的能力画像
    view_user_profile(2)