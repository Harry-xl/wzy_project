import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.append(str(BASE_DIR))

from AI_operate.Ability_Profile import AbilityProfile

def check_user_strength(user_id):
    profile = AbilityProfile(user_id)
    strength = profile.get_user_strength()
    profile_data = profile._load_profile()
    
    print(f"用户 {user_id} 的实力水平: {strength:.2f}")
    print("知识点熟练度:")
    for kp, level in sorted(profile_data.items(), key=lambda x: x[1], reverse=True):
        print(f"  {kp}: {level:.2f}")

if __name__ == "__main__":
    user_id = input("请输入用户ID: ")
    check_user_strength(int(user_id))