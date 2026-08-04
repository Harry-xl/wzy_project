-- 插入测试用户数据（幂等）
INSERT IGNORE INTO `user` (email, name, password) VALUES
('test1@example.com', '张三', 'password123');

INSERT IGNORE INTO `user` (email, name, password) VALUES
('test2@example.com', '李四', 'password456');

INSERT IGNORE INTO `user` (email, name, password) VALUES
('test3@example.com', '王五', 'password789');

-- 插入C语言题目数据（幂等）
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C001', '以下哪个不是C语言的基本数据类型？\nA. int\nB. float\nC. string\nD. char', 'C', '简单', 'C语言基础')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C002', '在C语言中，以下哪个语句正确声明了一个整型指针？\nA. int p;\nB. int *p;\nC. pointer int p;\nD. int p*;', 'B', '简单', '指针')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C003', '以下C语言代码的输出是什么？\n```c\n#include <stdio.h>\nint main() {\n    int a = 5;\n    printf("%d %d %d", a++, a, ++a);\n    return 0;\n}\n```', '输出结果依赖于编译器实现，因为表达式求值顺序未定义', '中等', '表达式求值')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C004', '在C语言中，以下关于结构体的说法错误的是？\nA. 结构体可以包含不同类型的成员\nB. 结构体可以嵌套定义\nC. 结构体默认情况下是按值传递给函数的\nD. 结构体成员默认是public访问权限', 'D', '中等', '结构体')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C005', '以下C语言代码的输出是什么？\n```c\n#include <stdio.h>\nint main() {\n    int arr[5] = {1, 2, 3, 4, 5};\n    int *ptr = arr + 1;\n    printf("%d, %d", *ptr, *(ptr+2));\n    return 0;\n}\n```', '2, 4', '中等', '指针和数组')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C006', '在C语言中，malloc()和calloc()的主要区别是什么？', 'malloc()分配未初始化的内存，而calloc()分配并初始化为零的内存', '中等', '内存管理')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C007', '以下C语言代码有什么问题？如何修复？\n```c\n#include <stdio.h>\nint main() {\n    char *str = "Hello";\n    str[0] = \'h\';\n    printf("%s\n", str);\n    return 0;\n}\n```', '问题是尝试修改字符串字面量，这是未定义行为。修复方法是使用字符数组：char str[] = "Hello";', '困难', '字符串和内存')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C008', '解释C语言中的volatile关键字的作用及其使用场景。', 'volatile关键字告诉编译器变量可能会被程序外部改变，防止编译器优化。常用于硬件寄存器访问、多线程共享变量、信号处理等场景。', '困难', '关键字')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C009', '编写一个C函数，实现两个单向链表的合并，要求合并后的链表仍然有序。假设原链表都是按升序排列的。', '```c\nstruct Node* mergeLists(struct Node* l1, struct Node* l2) {\n    struct Node dummy;\n    struct Node* tail = &dummy;\n    dummy.next = NULL;\n    \n    while (l1 && l2) {\n        if (l1->val <= l2->val) {\n            tail->next = l1;\n            l1 = l1->next;\n        } else {\n            tail->next = l2;\n            l2 = l2->next;\n        }\n        tail = tail->next;\n    }\n    \n    tail->next = l1 ? l1 : l2;\n    return dummy.next;\n}\n```', '困难', '链表')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point) VALUES
('C010', '解释C语言中的内存泄漏问题，并给出一个可能导致内存泄漏的代码示例及其修复方法。', '内存泄漏是指程序分配的内存在使用完后未被释放，导致该内存无法再被使用。示例：\n```c\nvoid leak_example() {\n    int *p = (int*)malloc(sizeof(int));\n    *p = 10;\n    // 没有调用free(p)就返回了\n}\n```\n修复方法是在使用完内存后调用free(p)释放内存。', '困难', '内存管理')
ON DUPLICATE KEY UPDATE problem=VALUES(problem), answer=VALUES(answer), difficulty=VALUES(difficulty), knowledge_point=VALUES(knowledge_point);

-- 插入用户能力画像数据（幂等，根据唯一键 user_knowledge）
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, 'C语言基础', 0.8)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '指针', 0.6)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '表达式求值', 0.5)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '结构体', 0.7)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '指针和数组', 0.6)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '内存管理', 0.4)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '字符串和内存', 0.5)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '关键字', 0.3)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(1, '链表', 0.2)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);

INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, 'C语言基础', 0.9)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '指针', 0.7)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '表达式求值', 0.6)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '结构体', 0.5)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '指针和数组', 0.4)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '内存管理', 0.3)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '字符串和内存', 0.2)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '关键字', 0.1)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(2, '链表', 0.4)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);

INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, 'C语言基础', 0.5)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '指针', 0.4)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '表达式求值', 0.3)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '结构体', 0.6)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '指针和数组', 0.7)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '内存管理', 0.8)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '字符串和内存', 0.7)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '关键字', 0.6)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level) VALUES
(3, '链表', 0.5)
ON DUPLICATE KEY UPDATE proficiency_level=VALUES(proficiency_level);

-- 插入用户答题记录（幂等：如果同一用户、同题已有记录则忽略）
INSERT IGNORE INTO user_answers (user_id, problem_id, user_answer, is_correct) VALUES
(1, 1, 'C', 1),
(1, 2, 'B', 1),
(1, 3, '输出依赖于编译器', 1),
(1, 4, 'C', 0),
(1, 5, '2, 4', 1),

(2, 1, 'C', 1),
(2, 2, 'B', 1),
(2, 3, '5 6 7', 0),
(2, 6, 'malloc分配内存不初始化，calloc分配并初始化为0', 1),
(2, 7, '字符串字面量不能修改', 1),

(3, 8, 'volatile防止编译器优化', 1),
(3, 9, '略', 0),
(3, 10, '内存泄漏是未释放不再使用的内存', 1),
(3, 1, 'B', 0),
(3, 2, 'B', 1);

-- 插入学习会话记录（允许重复多次导入，这里也用 INSERT IGNORE 简化）
INSERT IGNORE INTO learning_sessions (user_id, start_time, end_time, total_problems, correct_problems) VALUES
(1, '2023-01-01 10:00:00', '2023-01-01 10:30:00', 5, 4),
(1, '2023-01-02 14:00:00', '2023-01-02 14:45:00', 8, 6),
(2, '2023-01-01 09:00:00', '2023-01-01 09:40:00', 6, 5),
(2, '2023-01-03 16:00:00', '2023-01-03 16:50:00', 10, 7),
(3, '2023-01-02 11:00:00', '2023-01-02 11:30:00', 4, 2),
(3, '2023-01-04 15:00:00', '2023-01-04 15:40:00', 7, 4);


USE wzyProjectDb;

-- 1. 删除依赖题目的用户答题记录
TRUNCATE TABLE user_answers;

-- 2. 删除包含旧知识点的用户能力画像
TRUNCATE TABLE ability_profile;

-- 3. 清空旧题目表
SET FOREIGN_KEY_CHECKS = 0; -- 临时关闭外键检查以允许截断
TRUNCATE TABLE problems;
SET FOREIGN_KEY_CHECKS = 1; -- 恢复外键检查

-- 4. 重置所有用户的整体实力为默认值 0.5
UPDATE user SET user_strength = 0.5;
SHOW CREATE TABLE problems;

ALTER TABLE problems
MODIFY COLUMN osi_layer ENUM(
  '应用层',
  '表示层',
  '会话层',
  '传输层',
  '网络层',
  '数据链路层',
  '物理层'
) NULL COMMENT 'OSI层级分类';

ALTER TABLE problems
MODIFY COLUMN osi_layer ENUM(
  '应用层',
  '表示层',
  '会话层',
  '传输层',
  '网络层',
  '数据链路层',
  '物理层'
) NULL COMMENT 'OSI层级分类';

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE user_answers;
TRUNCATE TABLE ability_profile;
TRUNCATE TABLE problems;
SET FOREIGN_KEY_CHECKS = 1;
UPDATE user SET user_strength = 0.5;


