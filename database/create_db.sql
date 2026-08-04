-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS wzyProjectDb;
USE wzyProjectDb;

-- 用户表
CREATE TABLE IF NOT EXISTS `user` (
    user_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    email VARCHAR(100) UNIQUE NOT NULL COMMENT '用户邮箱',
    name VARCHAR(50) NOT NULL COMMENT '用户姓名',
    password VARCHAR(255) NOT NULL COMMENT '用户密码（哈希）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) COMMENT='用户信息表';

-- 题目表
CREATE TABLE IF NOT EXISTS problems (
    problem_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '题目ID',
    problem_num VARCHAR(20) UNIQUE COMMENT '题目编号',
    problem TEXT NOT NULL COMMENT '题目内容',
    answer TEXT NOT NULL COMMENT '题目答案',
    difficulty ENUM('简单', '中等', '困难') NOT NULL COMMENT '难度等级',
    knowledge_point VARCHAR(100) NOT NULL COMMENT '知识点',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) COMMENT='题目信息表';

-- 用户能力画像表
CREATE TABLE IF NOT EXISTS ability_profile (
    profile_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '画像ID',
    user_id INT NOT NULL COMMENT '用户ID',
    knowledge_point VARCHAR(100) NOT NULL COMMENT '知识点',
    proficiency_level FLOAT NOT NULL DEFAULT 0.0 COMMENT '熟练度', -- 0.0-1.0表示熟练度
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    UNIQUE KEY user_knowledge (user_id, knowledge_point)
) COMMENT='用户能力画像表';

-- 用户答题记录表
CREATE TABLE IF NOT EXISTS user_answers (
    answer_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '答题记录ID',
    user_id INT NOT NULL COMMENT '用户ID',
    problem_id INT NOT NULL COMMENT '题目ID',
    user_answer TEXT NOT NULL COMMENT '用户答案',
    is_correct BOOLEAN NOT NULL COMMENT '是否正确',
    answer_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '答题时间',
    FOREIGN KEY (user_id) REFERENCES `user`(user_id),
    FOREIGN KEY (problem_id) REFERENCES problems(problem_id)
) COMMENT='用户答题记录表';

-- 用户学习会话表
CREATE TABLE IF NOT EXISTS learning_sessions (
    session_id INT AUTO_INCREMENT PRIMARY KEY COMMENT '会话ID',
    user_id INT NOT NULL COMMENT '用户ID',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '开始时间',
    end_time TIMESTAMP NULL COMMENT '结束时间',
    total_problems INT DEFAULT 0 COMMENT '总题目数',
    correct_problems INT DEFAULT 0 COMMENT '正确题目数',
    FOREIGN KEY (user_id) REFERENCES `user`(user_id)
) COMMENT='用户学习会话表';



