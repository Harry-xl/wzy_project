-- ============================================================
-- 迁移: 004_unify_knowledge_points
-- 描述: 统一题库与知识库知识点体系
--       1. problems 新增 sub_topic_id 可选FK
--       2. ability_profile 新增 parent_kp_ref 字段
--       3. 替换 C 语言测试题为计算机网络题
--       4. 插入配套 ability_profile 种子数据
-- 日期: 2026-08-07
-- 回滚:
--   ALTER TABLE problems DROP COLUMN sub_topic_id;
--   ALTER TABLE ability_profile DROP COLUMN parent_kp_ref;
--   重新执行原始 insert_test_data.sql 恢复 C 语言数据
-- ============================================================
USE wzyProjectDb;

-- -----------------------------------------------------------
-- 1. problems 表新增子知识点 FK
-- -----------------------------------------------------------
SET @col_st_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'problems'
      AND COLUMN_NAME = 'sub_topic_id'
);
SET @sql_st := IF(@col_st_exists = 0,
    'ALTER TABLE `problems` '
    'ADD COLUMN `sub_topic_id` INT DEFAULT NULL COMMENT ''关联的子知识点ID（可选精确映射）'' AFTER `knowledge_point`, '
    'ADD INDEX `idx_problems_sub_topic` (`sub_topic_id`)',
    'SET @noop := 1'
);
PREPARE stmt_st FROM @sql_st;
EXECUTE stmt_st;
DEALLOCATE PREPARE stmt_st;

-- 添加 FK（仅当列是本次新建时）
SET @fk_st_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'problems'
      AND COLUMN_NAME = 'sub_topic_id'
      AND REFERENCED_TABLE_NAME IS NOT NULL
);
SET @sql_fk_st := IF(@fk_st_exists = 0,
    'ALTER TABLE `problems` '
    'ADD CONSTRAINT `fk_problems_sub_topic` FOREIGN KEY (`sub_topic_id`) '
    'REFERENCES `knowledge_sub_topics`(`sub_topic_id`) ON DELETE SET NULL',
    'SET @noop := 1'
);
PREPARE stmt_fk_st FROM @sql_fk_st;
EXECUTE stmt_fk_st;
DEALLOCATE PREPARE stmt_fk_st;

-- -----------------------------------------------------------
-- 2. ability_profile 新增标准知识点名称引用
-- -----------------------------------------------------------
SET @col_pr_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'ability_profile'
      AND COLUMN_NAME = 'parent_kp_ref'
);
SET @sql_pr := IF(@col_pr_exists = 0,
    'ALTER TABLE `ability_profile` '
    'ADD COLUMN `parent_kp_ref` VARCHAR(200) DEFAULT NULL COMMENT ''标准知识点名称（与knowledge_sub_topics.parent_kp对齐）'' AFTER `knowledge_point`, '
    'ADD INDEX `idx_ap_parent_kp` (`parent_kp_ref`)',
    'SET @noop := 1'
);
PREPARE stmt_pr FROM @sql_pr;
EXECUTE stmt_pr;
DEALLOCATE PREPARE stmt_pr;

-- -----------------------------------------------------------
-- 3. 清空旧 C 语言测试数据（尊重外键顺序）
-- -----------------------------------------------------------
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE user_answers;
TRUNCATE TABLE learning_sessions;
TRUNCATE TABLE ability_profile;
TRUNCATE TABLE problems;
SET FOREIGN_KEY_CHECKS = 1;
UPDATE `user` SET user_strength = 0.5;

-- -----------------------------------------------------------
-- 4. 插入计算机网络测试题（覆盖主要知识点）
--    knowledge_point 使用 knowledge_sub_topics.parent_kp 的有效值
-- -----------------------------------------------------------

-- === 计算机网络概述 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET001', '以下哪项不是计算机网络的常见拓扑结构？\nA. 星型拓扑\nB. 总线型拓扑\nC. 环型拓扑\nD. 栈型拓扑', 'D', '简单', '计算机网络概述',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '网络拓扑结构' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET002', '关于电路交换与分组交换，以下说法正确的是？\nA. 电路交换的信道利用率高于分组交换\nB. 分组交换不需要存储转发\nC. 电路交换在通信前需要建立专用物理通路\nD. 分组交换的时延比电路交换更确定', 'C', '中等', '计算机网络概述',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '电路交换与分组交换' LIMIT 1));

-- === 网络体系结构 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET003', 'OSI七层模型从下到上依次是？\nA. 物理层→数据链路层→网络层→传输层→会话层→表示层→应用层\nB. 物理层→网络层→数据链路层→传输层→会话层→表示层→应用层\nC. 应用层→表示层→会话层→传输层→网络层→数据链路层→物理层\nD. 物理层→数据链路层→传输层→网络层→会话层→表示层→应用层', 'A', '简单', '网络体系结构',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'OSI七层模型' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET004', 'TCP/IP模型中，网际层（IP层）对应OSI模型的哪一层？\nA. 数据链路层\nB. 网络层\nC. 传输层\nD. 会话层', 'B', '简单', '网络体系结构',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'TCP/IP四层模型' LIMIT 1));

-- === 物理层基础 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET005', '以下哪种复用技术使用不同的波长来共享光纤？\nA. FDM（频分复用）\nB. TDM（时分复用）\nC. WDM（波分复用）\nD. CDM（码分复用）', 'C', '中等', '物理层基础',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '信道复用技术' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET006', '根据奈奎斯特采样定理，要无失真地恢复一个最高频率为4kHz的信号，采样频率至少应为？\nA. 2kHz\nB. 4kHz\nC. 8kHz\nD. 16kHz', 'C', '中等', '物理层基础',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '数字传输系统' LIMIT 1));

-- === 数据链路层基础 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET007', '以太网中CSMA/CD协议在检测到碰撞后，采用的退避算法是？\nA. 固定时间退避\nB. 二进制指数退避\nC. 线性退避\nD. 随机固定窗口退避', 'B', '中等', '数据链路层基础',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'CSMA/CD协议' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET008', 'CRC（循环冗余检验）的主要作用是？\nA. 纠正传输中的比特错误\nB. 检测传输中是否出现比特差错\nC. 保证数据按序到达\nD. 进行流量控制', 'B', '简单', '数据链路层基础',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '数据链路层功能' LIMIT 1));

-- === 滑动窗口与可靠传输 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET009', '在选择重传（SR）协议中，接收方收到乱序但窗口内的帧时会？\nA. 丢弃该帧\nB. 缓存该帧并发送确认\nC. 发送NAK\nD. 关闭连接', 'B', '中等', '滑动窗口与可靠传输',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '选择重传(SR)' LIMIT 1));

-- === IPv4与IPv6 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET010', 'IPv4报文首部中，TTL字段的作用是？\nA. 标识上层协议类型\nB. 防止数据报在网络中无限循环\nC. 标识数据报的优先级\nD. 计算首部校验和', 'B', '简单', 'IPv4与IPv6',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'IPv4报文格式' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET011', 'IPv4地址中，B类地址的默认子网掩码是？\nA. 255.0.0.0\nB. 255.255.0.0\nC. 255.255.255.0\nD. 255.255.255.255', 'B', '简单', 'IPv4与IPv6',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'IPv4报文格式' LIMIT 1));

-- === IP地址与子网划分 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET012', '某网络地址为192.168.1.0/27，该子网中可用主机IP数量为？\nA. 30\nB. 32\nC. 14\nD. 62', 'A', '中等', 'IP地址与子网划分',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '子网掩码计算' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET013', 'CIDR（无类域间路由）使用以下哪种方式进行路由查找？\nA. 精确匹配\nB. 最长前缀匹配\nC. 最短路径优先\nD. 轮询', 'B', '中等', 'IP地址与子网划分',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'CIDR无类编址' LIMIT 1));

-- === 路由算法与协议 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET014', 'OSPF协议基于以下哪种算法计算最短路径？\nA. Bellman-Ford算法\nB. Dijkstra SPF算法\nC. 距离向量算法\nD. Prim算法', 'B', '中等', '路由算法与协议',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '链路状态算法与OSPF' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET015', 'RIP协议的最大跳数限制是？\nA. 10跳\nB. 15跳\nC. 20跳\nD. 30跳', 'B', '简单', '路由算法与协议',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'RIP协议详解' LIMIT 1));

-- === ICMP协议 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET016', 'Ping命令使用ICMP的哪种报文类型？\nA. 终点不可达报文\nB. 回显请求与回显应答\nC. 超时报文\nD. 重定向报文', 'B', '简单', 'ICMP协议',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'Ping与Traceroute' LIMIT 1));

-- === ARP协议 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET017', 'ARP协议的主要功能是？\nA. 将域名解析为IP地址\nB. 将IP地址解析为MAC地址\nC. 将端口号映射到应用程序\nD. 检测IP地址冲突', 'B', '简单', 'ARP协议',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'ARP工作原理' LIMIT 1));

-- === NAT与DHCP ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET018', 'DHCP客户端获取IP地址时，正确的四步交互顺序是？\nA. Discover→Request→Offer→ACK\nB. Discover→Offer→Request→ACK\nC. Request→Discover→Offer→ACK\nD. Offer→Discover→Request→ACK', 'B', '中等', 'NAT与DHCP',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'DHCP动态配置' LIMIT 1));

-- === UDP协议 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET019', '关于UDP协议，以下说法错误的是？\nA. UDP提供无连接的数据传输\nB. UDP不保证可靠交付\nC. UDP具有拥塞控制机制\nD. UDP首部比TCP首部小', 'C', '中等', 'UDP协议',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'UDP特点与应用' LIMIT 1));

-- === TCP连接管理 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET020', 'TCP三次握手中，第三次握手报文段的SYN标志位为？\nA. 1\nB. 0\nC. 取决于具体实现\nD. 可以是1或0', 'B', '中等', 'TCP连接管理',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '三次握手机制' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET021', 'TCP四次挥手中，主动关闭方在发送最后一个ACK后进入什么状态？\nA. CLOSED\nB. FIN-WAIT-2\nC. TIME-WAIT\nD. CLOSE-WAIT', 'C', '中等', 'TCP连接管理',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '四次挥手机制' LIMIT 1));

-- === TCP拥塞控制 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET022', 'TCP慢启动阶段，拥塞窗口（cwnd）的增长方式是？\nA. 线性增长\nB. 指数增长\nC. 保持不变\nD. 递减', 'B', '中等', 'TCP拥塞控制',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '慢启动' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET023', 'TCP快重传机制在收到几个冗余ACK后触发？\nA. 1个\nB. 2个\nC. 3个\nD. 4个', 'C', '中等', 'TCP拥塞控制',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '快重传与快恢复' LIMIT 1));

-- === DNS系统 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET024', '以下哪种DNS记录类型用于将域名映射到IPv4地址？\nA. CNAME\nB. MX\nC. NS\nD. A', 'D', '简单', 'DNS系统',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'DNS记录类型' LIMIT 1));

-- === HTTP与HTTPS ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET025', 'HTTP状态码中，301代表什么含义？\nA. 请求成功\nB. 永久重定向\nC. 临时重定向\nD. 未找到', 'B', '简单', 'HTTP与HTTPS',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'HTTP请求与响应' LIMIT 1));

INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET026', 'HTTPS使用以下哪个端口？\nA. 80\nB. 8080\nC. 443\nD. 8443', 'C', '简单', 'HTTP与HTTPS',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = 'HTTPS与TLS握手' LIMIT 1));

-- === TCP可靠传输与流量控制 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET027', 'TCP流量控制中，接收方通过什么字段通告可用缓冲区大小？\nA. 序列号字段\nB. 确认号字段\nC. 窗口大小字段\nD. 校验和字段', 'C', '中等', 'TCP可靠传输与流量控制',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '滑动窗口协议' LIMIT 1));

-- === 网络安全与防火墙 ===
INSERT INTO problems (problem_num, problem, answer, difficulty, knowledge_point, sub_topic_id) VALUES
('NET028', 'SYN Flood攻击利用了TCP协议的哪个特性？\nA. 四次挥手\nB. 三次握手\nC. 滑动窗口\nD. 拥塞控制', 'B', '中等', '网络安全与防火墙',
 (SELECT sub_topic_id FROM knowledge_sub_topics WHERE sub_topic_name = '网络攻击与防御' LIMIT 1));

-- -----------------------------------------------------------
-- 5. 插入能力画像种子数据（测试用户 + 网络知识点）
--    knowledge_point 对齐到 parent_kp
-- -----------------------------------------------------------
INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level, parent_kp_ref) VALUES
(1, '计算机网络概述', 0.75, '计算机网络概述'),
(1, '网络体系结构', 0.60, '网络体系结构'),
(1, '物理层基础', 0.45, '物理层基础'),
(1, '数据链路层基础', 0.55, '数据链路层基础'),
(1, 'IPv4与IPv6', 0.70, 'IPv4与IPv6'),
(1, 'TCP连接管理', 0.50, 'TCP连接管理'),
(1, 'TCP拥塞控制', 0.35, 'TCP拥塞控制'),
(1, 'DNS系统', 0.80, 'DNS系统'),
(1, 'HTTP与HTTPS', 0.65, 'HTTP与HTTPS'),
(1, '网络安全与防火墙', 0.30, '网络安全与防火墙');

INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level, parent_kp_ref) VALUES
(2, '计算机网络概述', 0.85, '计算机网络概述'),
(2, '网络体系结构', 0.70, '网络体系结构'),
(2, '路由算法与协议', 0.40, '路由算法与协议'),
(2, 'IP地址与子网划分', 0.55, 'IP地址与子网划分'),
(2, 'TCP连接管理', 0.65, 'TCP连接管理'),
(2, 'UDP协议', 0.75, 'UDP协议'),
(2, 'ARP协议', 0.60, 'ARP协议'),
(2, 'ICMP协议', 0.50, 'ICMP协议');

INSERT INTO ability_profile (user_id, knowledge_point, proficiency_level, parent_kp_ref) VALUES
(3, '物理层基础', 0.70, '物理层基础'),
(3, '数据链路层基础', 0.65, '数据链路层基础'),
(3, '滑动窗口与可靠传输', 0.45, '滑动窗口与可靠传输'),
(3, 'TCP可靠传输与流量控制', 0.40, 'TCP可靠传输与流量控制'),
(3, 'TCP拥塞控制', 0.55, 'TCP拥塞控制'),
(3, 'DNS系统', 0.60, 'DNS系统'),
(3, 'HTTP与HTTPS', 0.50, 'HTTP与HTTPS'),
(3, 'NAT与DHCP', 0.35, 'NAT与DHCP');