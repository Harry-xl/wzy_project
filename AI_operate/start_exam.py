import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent  # 需要回到上一级目录（项目根目录）
sys.path.append(str(BASE_DIR))

# 直接导入同目录下的模块
from exam import get_personalized_problems, get_random_problems
from Ability_Profile import AbilityProfile

def start_exam(user_id=None, num_problems=5):
    """
    开始做题
    """
    print("=== 开始做题 ===")
    
    # 获取题目
    if user_id:
        print(f"为用户 {user_id} 获取个性化题目...")
        problems = get_personalized_problems(user_id, num_problems)
    else:
        print("获取随机题目...")
        problems = get_random_problems(num_problems)
    
    if not problems:
        print("没有找到题目，请检查数据库连接。")
        return
    
    correct_count = 0
    
    for i, problem in enumerate(problems, 1):
        print(f"\n第 {i} 题 ({problem['difficulty']}) - {problem['knowledge_point']}")
        print(f"题目编号：{problem['problem_num']}")
        print(f"题目：{problem['problem']}")
        
        user_answer = input("请输入您的答案：").strip()
        
        is_correct = user_answer == problem['answer'].strip()
        
        if is_correct:
            print("✓ 回答正确！")
            correct_count += 1
        else:
            print(f"✗ 回答错误。正确答案是：{problem['answer']}")
        
        # 如果有用户ID，更新能力画像
        if user_id:
            profile = AbilityProfile(user_id)
            profile.analyze_answer(problem['problem_id'], user_answer, is_correct)
    
    print(f"\n=== 做题结束 ===")
    print(f"总题数：{len(problems)}")
    print(f"正确数：{correct_count}")
    print(f"正确率：{correct_count/len(problems)*100:.1f}%")
    
    # 如果有用户ID，显示能力画像
    if user_id:
        print("\n=== 您的能力画像 ===")
        profile = AbilityProfile(user_id)
        profile_data = profile._load_profile()
        user_strength = profile.get_user_strength()
        
        print(f"整体实力：{user_strength:.2f}")
        print("知识点熟练度：")
        for knowledge_point, proficiency in sorted(profile_data.items(), key=lambda x: x[1], reverse=True):
            print(f"  {knowledge_point}: {proficiency:.2f}")

if __name__ == "__main__":
    print("欢迎使用做题系统！")
    
    # 选择模式
    mode = input("请选择模式：\n1. 游客模式（随机题目）\n2. 用户模式（个性化推荐）\n请输入选择（1或2）：")
    
    if mode == "2":
        user_id = input("请输入用户ID：")
        try:
            user_id = int(user_id)
            start_exam(user_id)
        except ValueError:
            print("用户ID必须是数字")
    else:
        start_exam()