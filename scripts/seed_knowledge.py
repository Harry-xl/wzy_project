"""
星伴(StarPal) 知识库种子数据导入脚本。

将《计算机网络》(谢希仁 第8版) 核心内容、RFC 标准摘要、知识点体系
导入知识库系统，包括子知识点、知识关系、知识文档和知识块。

用法:
    python scripts/seed_knowledge.py              # 完整导入（含嵌入生成）
    python scripts/seed_knowledge.py --dry-run    # 仅打印，不写入

注意: 嵌入生成需要 DeepSeek API Key 配置正确。
      如无 API Key，数据仅写入 MySQL，ChromaDB 索引将为空。
"""

import argparse
import json
import sys
from pathlib import Path

# 添加项目根目录到系统路径
BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.embedding_service import EmbeddingService
from AI_operate.rag_service import RAGService


# ================================================================
# 种子数据定义
# ================================================================

# ---- 子知识点（~85 个，按粗粒度知识点分组）----
SUB_TOPICS = [
    # 计算机网络概述
    ("计算机网络定义与分类", "计算机网络概述", "计算机网络的定义、分类（LAN/WAN/MAN）及典型特征", 1),
    ("网络拓扑结构", "计算机网络概述", "星型、总线型、环型、网状、树型拓扑的特点与对比", 2),
    ("电路交换与分组交换", "计算机网络概述", "电路交换、报文交换、分组交换的原理与时延分析", 3),
    ("网络性能指标", "计算机网络概述", "带宽、吞吐量、时延（发送/传播/处理/排队）、时延带宽积、RTT", 4),

    # 网络体系结构
    ("OSI七层模型", "网络体系结构", "物理层、数据链路层、网络层、传输层、会话层、表示层、应用层的功能", 1),
    ("TCP/IP四层模型", "网络体系结构", "网络接口层、网际层、传输层、应用层与OSI的对应关系", 2),
    ("五层协议体系结构", "网络体系结构", "综合OSI和TCP/IP的五层模型，每层的典型协议与数据单元(PDU)", 3),

    # 物理层基础
    ("物理层基本概念", "物理层基础", "物理层接口特性：机械/电气/功能/规程特性", 1),
    ("信道复用技术", "物理层基础", "FDM频分复用、TDM时分复用、STDM统计时分复用、WDM波分复用、CDM码分复用", 2),
    ("数字传输系统", "物理层基础", "PCM脉冲编码调制、采样定理(Nyquist)、量化与编码", 3),

    # 数据链路层基础
    ("数据链路层功能", "数据链路层基础", "帧定界、透明传输、差错检测(CRC)、流量控制的基本概念", 1),
    ("PPP协议", "数据链路层基础", "PPP帧格式、LCP链路控制协议、NCP网络控制协议、PPP工作状态", 2),
    ("CSMA/CD协议", "数据链路层基础", "载波监听多点接入/碰撞检测：争用期、最短帧长、截断二进制指数退避算法", 3),

    # 滑动窗口与可靠传输
    ("停止-等待协议", "滑动窗口与可靠传输", "停等协议原理、信道利用率计算、ACK超时重传机制", 1),
    ("后退N帧(GBN)", "滑动窗口与可靠传输", "GBN发送窗口、累积确认、超时重传全部未确认帧", 2),
    ("选择重传(SR)", "滑动窗口与可靠传输", "SR发送/接收窗口、逐帧确认、仅重传出错帧", 3),

    # MAC子层与以太网
    ("以太网帧格式", "MAC子层与以太网", "DIX V2与IEEE 802.3帧格式、MAC地址格式、类型/长度字段", 1),
    ("交换机与MAC表", "MAC子层与以太网", "交换机自学习算法、MAC地址表构建、广播风暴与STP概述", 2),
    ("VLAN虚拟局域网", "MAC子层与以太网", "VLAN概念、802.1Q帧格式、Trunk端口、VLAN间路由", 3),

    # ARP协议
    ("ARP工作原理", "ARP协议", "ARP请求/响应流程、ARP缓存表、ARP欺骗与防护", 1),
    ("ARP报文格式", "ARP协议", "ARP报文各字段：硬件类型、协议类型、操作码(1请求/2响应)", 2),
    ("Gratuitous ARP", "ARP协议", "免费ARP的作用：IP冲突检测、更新ARP缓存", 3),

    # IPv4与IPv6
    ("IPv4报文格式", "IPv4与IPv6", "版本、首部长度、总长度、标识、标志、片偏移、TTL、协议、首部校验和", 1),
    ("IP分片与重组", "IPv4与IPv6", "MTU、DF/MF标志位、片偏移计算、分片重组机制", 2),
    ("IPv6地址与报文", "IPv4与IPv6", "IPv6地址格式(128位)、报文首部简化、扩展首部、IPv4→IPv6过渡技术", 3),

    # IP地址与子网划分
    ("分类编址(A/B/C类)", "IP地址与子网划分", "A类(0.)、B类(10.)、C类(110.)地址范围与默认掩码", 1),
    ("子网掩码计算", "IP地址与子网划分", "子网掩码、网络地址、广播地址、可用IP范围的计算方法", 2),
    ("CIDR无类编址", "IP地址与子网划分", "CIDR斜线记法、地址块聚合(超网)、最长前缀匹配", 3),
    ("VLSM可变长子网", "IP地址与子网划分", "VLSM概念、子网划分步骤、地址利用率优化", 4),

    # 路由算法与协议
    ("距离矢量算法", "路由算法与协议", "Bellman-Ford算法、路由环路问题(无穷计数)、水平分割与毒性反转", 1),
    ("RIP协议详解", "路由算法与协议", "RIPv1/v2区别、跳数限制(15)、更新定时器、UDP 520端口", 2),
    ("链路状态算法与OSPF", "路由算法与协议", "Dijkstra SPF算法、LSA泛洪、DR/BDR选举、OSPF区域划分", 3),
    ("BGP协议详解", "路由算法与协议", "BGP路径矢量、AS自治系统、eBGP/iBGP、路由属性(Local_Pref/AS_Path/MED)", 4),

    # ICMP协议
    ("ICMP报文类型", "ICMP协议", "差错报告(3终点不可达/11超时/5重定向)与查询报文(8回显请求/0回显应答)", 1),
    ("Ping与Traceroute", "ICMP协议", "Ping(ICMP Echo)与Traceroute(TTL递增+ICMP超时)的实现原理", 2),

    # NAT与DHCP
    ("NAT地址转换", "NAT与DHCP", "静态NAT/动态NAT/NAPT(PAT)、NAT穿越问题、内网穿透方案", 1),
    ("DHCP动态配置", "NAT与DHCP", "DHCP Discover/Offer/Request/ACK四次交互、租约续期、DHCP中继", 2),

    # 多播与移动IP
    ("IGMP与多播路由", "多播与移动IP", "IGMP协议版本、多播地址(224.0.0.0/4)、多播转发树", 1),
    ("移动IP", "多播与移动IP", "归属代理(HA)、外地代理(FA)、转交地址(CoA)、三角路由问题", 2),

    # UDP协议
    ("UDP报文格式", "UDP协议", "UDP首部(源端口/目的端口/长度/校验和)、伪首部校验和计算", 1),
    ("UDP特点与应用", "UDP协议", "无连接/不可靠/无拥塞控制、适用场景(DNS/SNMP/音视频流)", 2),

    # TCP连接管理
    ("三次握手机制", "TCP连接管理", "SYN(seq=x)→SYN+ACK(seq=y,ack=x+1)→ACK(seq=x+1,ack=y+1)完整流程", 1),
    ("四次挥手机制", "TCP连接管理", "FIN→ACK→FIN→ACK，TIME_WAIT状态(2MSL)的原因与意义", 2),
    ("TCP状态转换", "TCP连接管理", "CLOSED/LISTEN/SYN-SENT/SYN-RCVD/ESTABLISHED/FIN-WAIT/CLOSE-WAIT/TIME-WAIT", 3),

    # TCP可靠传输与流量控制
    ("序列号与确认号", "TCP可靠传输与流量控制", "字节编号(ISN)、累积确认、捎带确认(Piggybacking)", 1),
    ("滑动窗口协议", "TCP可靠传输与流量控制", "发送窗口(swnd)=min(cwnd,rwnd)、窗口滑动与可用窗口计算", 2),
    ("零窗口探测", "TCP可靠传输与流量控制", "接收方窗口为零时发送方的坚持定时器(Persist Timer)探测", 3),

    # TCP拥塞控制
    ("慢启动", "TCP拥塞控制", "cwnd从1MSS指数增长至ssthresh的过程", 1),
    ("拥塞避免", "TCP拥塞控制", "cwnd超过ssthresh后线性增长(每个RTT+1MSS)", 2),
    ("快重传与快恢复", "TCP拥塞控制", "收到3个冗余ACK→立即重传→ssthresh=cwnd/2→cwnd=ssthresh进入拥塞避免", 3),
    ("Tahoe/Reno/CUBIC对比", "TCP拥塞控制", "三种拥塞控制算法的演进：Tahoe(慢启动+拥塞避免)、Reno(增加快重传快恢复)、CUBIC(高BDP优化)", 4),

    # DNS系统
    ("DNS解析流程", "DNS系统", "递归查询与迭代查询、本地DNS→根DNS→顶级DNS→权威DNS的层次解析", 1),
    ("DNS记录类型", "DNS系统", "A/AAAA/CNAME/MX/NS/PTR/SOA/TXT记录的作用与格式", 2),
    ("DNS缓存与安全", "DNS系统", "TTL缓存策略、DNS污染与劫持、DNSSEC数字签名验证", 3),

    # HTTP与HTTPS
    ("HTTP请求与响应", "HTTP与HTTPS", "请求方法(GET/POST/PUT/DELETE/HEAD)、状态码(1xx/2xx/3xx/4xx/5xx)、常用头部字段", 1),
    ("HTTP持久连接", "HTTP与HTTPS", "HTTP/1.0非持久vs HTTP/1.1持久连接(Keep-Alive)、流水线(Pipelining)", 2),
    ("HTTPS与TLS握手", "HTTP与HTTPS", "TLS 1.3握手流程、证书链验证、前向安全性(ECDHE)", 3),
    ("HTTP缓存策略", "HTTP与HTTPS", "强缓存(Cache-Control/Expires)与协商缓存(ETag/Last-Modified)", 4),

    # 高级Web协议
    ("HTTP/2与HTTP/3", "高级Web协议", "HTTP/2多路复用/头部压缩(HPACK)/服务器推送、HTTP/3 QUIC协议/UDP改进", 1),
    ("WebSocket", "高级Web协议", "WebSocket握手(Upgrade)、全双工通信帧格式、与HTTP长轮询的对比", 2),

    # FTP与电子邮件
    ("FTP协议", "FTP与电子邮件", "控制连接(21)与数据连接(20)、主动/被动模式(PASV)、TFTP简单文件传输", 1),
    ("SMTP与POP3/IMAP", "FTP与电子邮件", "SMTP邮件发送(25)、POP3(110)/IMAP(143)邮件接收、MIME多用途邮件扩展", 2),

    # CDN与负载均衡
    ("CDN内容分发", "CDN与负载均衡", "CDN工作原理、DNS重定向、边缘节点缓存、命中率优化", 1),
    ("负载均衡策略", "CDN与负载均衡", "L4(LVS/NAT/DR)与L7(Nginx反向代理)负载均衡、一致性哈希算法", 2),

    # 零拷贝与传输优化
    ("零拷贝技术", "零拷贝与传输优化", "mmap+write、sendfile、SG-DMA三种零拷贝方案的系统调用对比", 1),
    ("TCP优化参数", "零拷贝与传输优化", "Nagle算法、延迟ACK、TCP_NODELAY、窗口缩放(Window Scale)、时间戳选项", 2),

    # QoS与流量管理
    ("QoS服务质量", "QoS与流量管理", "IntServ(RSVP资源预留)与DiffServ(DSCP差分服务)两种QoS模型", 1),
    ("流量整形与调度", "QoS与流量管理", "漏桶(Leaky Bucket)与令牌桶(Token Bucket)算法、WFQ加权公平队列", 2),

    # 网络安全与防火墙
    ("对称加密与公钥加密", "网络安全与防火墙", "AES/DES对称加密、RSA/ECC公钥加密、数字签名与哈希函数(SHA-256)", 1),
    ("防火墙与ACL", "网络安全与防火墙", "包过滤防火墙、状态检测防火墙、应用层网关(ALG)、ACL规则设计", 2),
    ("网络攻击与防御", "网络安全与防火墙", "DDoS(SYN Flood/UDP Flood/DNS放大)、ARP欺骗、中间人攻击与防御措施", 3),
]

# ---- 知识关系（~55 条）----
KNOWLEDGE_RELATIONS = [
    # 前置关系(prerequisite)
    ("计算机网络概述", "网络体系结构", "prerequisite", "理解网络分类后学习体系结构"),
    ("网络体系结构", "物理层基础", "prerequisite", "理解OSI/TCP-IP分层后深入学习物理层"),
    ("物理层基础", "数据链路层基础", "prerequisite", ""),
    ("数据链路层基础", "滑动窗口与可靠传输", "prerequisite", "链路层基础→可靠传输机制"),
    ("数据链路层基础", "MAC子层与以太网", "prerequisite", ""),
    ("滑动窗口与可靠传输", "TCP可靠传输与流量控制", "prerequisite", "停等→GBN→SR为TCP流量控制基础"),
    ("MAC子层与以太网", "ARP协议", "prerequisite", "以太网帧格式→ARP地址解析"),
    ("网络体系结构", "IPv4与IPv6", "prerequisite", ""),
    ("IPv4与IPv6", "IP地址与子网划分", "prerequisite", "IP报文→IP地址划分"),
    ("IP地址与子网划分", "路由算法与协议", "prerequisite", "理解IP编址后学习路由"),
    ("路由算法与协议", "ICMP协议", "prerequisite", ""),
    ("IP地址与子网划分", "NAT与DHCP", "prerequisite", ""),
    ("网络体系结构", "UDP协议", "prerequisite", ""),
    ("UDP协议", "TCP连接管理", "prerequisite", "UDP简单传输→TCP可靠连接"),
    ("TCP连接管理", "TCP可靠传输与流量控制", "prerequisite", "连接建立→可靠传输"),
    ("TCP可靠传输与流量控制", "TCP拥塞控制", "prerequisite", "滑动窗口→拥塞窗口"),
    ("网络体系结构", "DNS系统", "prerequisite", ""),
    ("DNS系统", "HTTP与HTTPS", "prerequisite", "DNS域名解析→HTTP访问"),
    ("HTTP与HTTPS", "高级Web协议", "prerequisite", "HTTP/1.1→HTTP/2 →HTTP/3"),
    ("HTTP与HTTPS", "CDN与负载均衡", "prerequisite", ""),
    ("TCP拥塞控制", "QoS与流量管理", "prerequisite", ""),
    ("网络体系结构", "网络安全与防火墙", "prerequisite", ""),

    # 扩展关系(extension)
    ("TCP连接管理", "FTP与电子邮件", "extension", "TCP连接应用到应用层协议"),
    ("IP地址与子网划分", "多播与移动IP", "extension", "单播→多播/移动IP"),
    ("TCP拥塞控制", "零拷贝与传输优化", "extension", "拥塞控制→传输效率优化"),
    ("滑动窗口与可靠传输", "TCP可靠传输与流量控制", "extension", "通用可靠传输→TCP具体实现"),

    # 相关关系(related)
    ("IPv4与IPv6", "NAT与DHCP", "related", "IP编址与地址分配"),
    ("ARP协议", "ICMP协议", "related", "网络层辅助协议"),
    ("DNS系统", "CDN与负载均衡", "related", "DNS重定向→CDN调度"),
    ("HTTP与HTTPS", "网络安全与防火墙", "related", "HTTPS依赖TLS安全基础"),
    ("TCP拥塞控制", "QoS与流量管理", "related", "拥塞管理与服务质量"),
    ("UDP协议", "DNS系统", "related", "DNS主要使用UDP传输"),
    ("TCP连接管理", "网络安全与防火墙", "related", "SYN Flood攻击与防火墙防御"),

    # 组成关系(part_of)
    ("物理层基础", "网络体系结构", "part_of", "OSI第1层"),
    ("数据链路层基础", "网络体系结构", "part_of", "OSI第2层"),
    ("IPv4与IPv6", "网络体系结构", "part_of", "OSI第3层-网络层核心"),
    ("TCP连接管理", "网络体系结构", "part_of", "OSI第4层-传输层核心"),
    ("DNS系统", "网络体系结构", "part_of", "OSI第7层-应用层"),
    ("HTTP与HTTPS", "网络体系结构", "part_of", "OSI第7层-应用层"),
    ("CSMA/CD协议", "MAC子层与以太网", "part_of", "以太网介质访问控制"),
    ("三次握手机制", "TCP连接管理", "part_of", ""),
    ("四次挥手机制", "TCP连接管理", "part_of", ""),
    ("慢启动", "TCP拥塞控制", "part_of", ""),
    ("拥塞避免", "TCP拥塞控制", "part_of", ""),
    ("快重传与快恢复", "TCP拥塞控制", "part_of", ""),
    ("距离矢量算法", "路由算法与协议", "part_of", "RIP基于距离矢量"),
    ("链路状态算法与OSPF", "路由算法与协议", "part_of", "OSPF基于链路状态"),
]

# ---- 知识文档 —— 教材章节摘要 ----
TEXTBOOK_CHAPTERS = [
    {
        "title": "第1章 计算机网络概述",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第1章",
        "doc_type": "textbook",
        "knowledge_points": ["计算机网络概述", "网络体系结构"],
        "difficulty": "基础",
        "content": """
计算机网络是计算机技术与通信技术相结合的产物。计算机网络的定义：将分布在不同地理位置的、具有独立功能的计算机系统，通过通信设备和线路连接起来，在网络操作系统和网络协议的管理下，实现资源共享和信息传递的系统。

计算机网络的分类：
1. 按覆盖范围：局域网（LAN, Local Area Network）、城域网（MAN）、广域网（WAN）
2. 按拓扑结构：星型拓扑、总线型拓扑、环型拓扑、网状拓扑、树型拓扑
3. 按交换方式：电路交换、报文交换、分组交换

电路交换（Circuit Switching）：在通信之前建立一条专用的物理通路，通信期间独占该通路。优点是传输时延小，缺点是信道利用率低。典型应用是传统电话网络。

报文交换（Message Switching）：以报文为单位，采用存储-转发方式。无需预先建立连接，但时延较大。

分组交换（Packet Switching）：将报文分割为小的分组（Packet），每个分组独立路由。优点是信道利用率高、灵活，缺点是可能产生分组丢失和乱序。

网络性能指标：
- 带宽（Bandwidth）：网络通信线路所能传输数据的能力，单位bps
- 吞吐量（Throughput）：单位时间内通过某个网络的实际数据量
- 时延（Delay）：发送时延 + 传播时延 + 处理时延 + 排队时延
- 时延带宽积：传播时延 × 带宽，衡量管道中可容纳的比特数
- 往返时间RTT（Round-Trip Time）：从发送端发送数据开始到收到接收端确认的时延

计算机网络的体系结构是分层设计的。最著名的是OSI七层模型和TCP/IP四层模型。分层的优点：各层独立、灵活性好、结构可分割、易于实现和维护、促进标准化。

OSI七层模型（自下而上）：物理层 → 数据链路层 → 网络层 → 传输层 → 会话层 → 表示层 → 应用层

TCP/IP四层模型：网络接口层 → 网际层（IP层）→ 传输层 → 应用层

实际教学中常采用五层协议体系结构：物理层 → 数据链路层 → 网络层 → 传输层 → 应用层
""",
    },
    {
        "title": "第2章 物理层",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第2章",
        "doc_type": "textbook",
        "knowledge_points": ["物理层基础"],
        "difficulty": "基础",
        "content": """
物理层是OSI模型的最底层，负责在物理传输介质上透明地传输比特流。

物理层的主要任务：
1. 定义接口的机械特性（连接器形状、引脚数等）
2. 电气特性（电压范围、传输速率等）
3. 功能特性（每个引脚的功能定义）
4. 规程特性（事件发生的顺序）

信道复用技术是物理层的重要概念：

频分复用（FDM, Frequency Division Multiplexing）：将信道总带宽划分为多个子频带，每个用户占用一个子频带。各用户同时传输，但使用不同的频率。典型应用：广播电视、ADSL。

时分复用（TDM, Time Division Multiplexing）：将时间划分为固定长度的帧，每帧再划分为固定数量的时隙。每个用户占用一个时隙。缺点是即使用户无数据传输，时隙也空闲浪费。

统计时分复用（STDM, Statistical TDM）：按需分配时隙，只有有数据要发送的用户才占用时隙，提高了信道利用率。

波分复用（WDM, Wavelength Division Multiplexing）：光的频分复用，将不同波长的光信号合并传输。DWDM（密集波分复用）可实现上百个波长的复用。

码分复用（CDM, Code Division Multiplexing）：每个用户使用不同的正交码片序列，共享同一频率和时间。CDMA技术广泛应用于3G移动通信。

数字传输系统方面，PCM（脉冲编码调制）是模拟信号数字化的基本方法，包含三个步骤：
1. 采样（Sampling）：奈奎斯特采样定理 — 采样频率 ≥ 2倍信号最高频率
2. 量化（Quantization）：将采样值取整到最近的离散值，产生量化误差
3. 编码（Encoding）：将量化值用二进制表示

奈奎斯特准则：在无噪声信道中，最大数据传输速率 = 2W log2(V) bps，其中W为带宽，V为信号离散等级数。

香农定理：在有噪声信道中，最大数据传输速率 = W log2(1+S/N) bps，其中S/N为信噪比。
""",
    },
    {
        "title": "第3章 数据链路层",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第3章",
        "doc_type": "textbook",
        "knowledge_points": ["数据链路层基础", "滑动窗口与可靠传输", "MAC子层与以太网"],
        "difficulty": "基础",
        "content": """
数据链路层在物理层之上，负责在两个相邻节点之间的链路上无差错地传输帧（Frame）。

数据链路层的三个基本问题：
1. 封装成帧（Framing）：将网络层交下来的IP数据报添加首部和尾部，构成帧。帧定界方法有字节计数法、字符填充法、比特填充法（HDLC的01111110标志字段）。
2. 透明传输（Transparent Transmission）：数据部分可以包含任何比特组合，不干扰帧定界。解决方案：字节填充（转义字符ESC）或比特填充（连续5个1后插入0）。
3. 差错检测（Error Detection）：CRC循环冗余检验。发送方将数据除以生成多项式得到余数（FCS帧检验序列），接收方用同样的多项式除，余数为0则无差错。

PPP协议（Point-to-Point Protocol）：广泛用于拨号上网和广域网链路。特点：简单、支持多种网络层协议、支持身份认证（PAP/CHAP）。PPP帧格式包含标志字段(7E)、地址字段(FF)、控制字段(03)、协议字段、信息字段和FCS字段。

CSMA/CD协议（Carrier Sense Multiple Access with Collision Detection）：以太网使用的介质访问控制协议。
- 先听后发（Carrier Sense）：发送前检测信道是否空闲
- 边发边听（Collision Detection）：发送过程中持续检测是否发生碰撞
- 碰撞停止：检测到碰撞立即停止发送
- 随机重发：使用截断二进制指数退避算法确定重传时间

争用期（Contention Slot）：以太网端到端往返时间2τ，即512比特时间。最短帧长64字节就是为了保证在发送完之前能检测到碰撞。

MAC地址（物理地址）：48位（6字节）全球唯一标识符。前24位为OUI（组织唯一标识符），后24位由厂商分配。

交换机通过自学习算法构建MAC地址表：收到帧时记录源MAC地址和端口的映射。对于未知目的MAC，采用泛洪（Flooding）。交换机隔离碰撞域但不隔离广播域。

VLAN（Virtual LAN）：将一个物理局域网划分成多个逻辑上独立的广播域。IEEE 802.1Q帧格式在源MAC后插入4字节标签（TPID+优先级+CFI+VID）。Trunk端口传输多个VLAN的帧。
""",
    },
    {
        "title": "第4章 网络层（IP协议与路由）",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第4章",
        "doc_type": "textbook",
        "knowledge_points": ["IPv4与IPv6", "IP地址与子网划分", "ARP协议", "ICMP协议", "路由算法与协议", "NAT与DHCP", "多播与移动IP"],
        "difficulty": "进阶",
        "content": """
网络层是OSI模型中最关键的一层，负责将分组从源主机传送到目的主机。核心功能包括路由选择、分组转发和拥塞控制。

IP协议（Internet Protocol）是网络层的核心协议。IPv4报文首部包含：版本(4)、首部长度、区分服务、总长度、标识、标志(DF/MF)、片偏移、TTL生存时间、协议(6=TCP,17=UDP,1=ICMP)、首部校验和、源IP地址、目的IP地址。

IP分片与重组：当IP数据报长度超过链路MTU时，需要进行分片。DF标志(Don't Fragment)=1时不允许分片，MF标志(More Fragments)=1表示还有后续分片。片偏移以8字节为单位。分片在目的主机进行重组。

IPv4地址为32位，分为A、B、C、D、E类：
- A类：0.0.0.0 ~ 127.255.255.255，默认掩码255.0.0.0（/8）
- B类：128.0.0.0 ~ 191.255.255.255，默认掩码255.255.0.0（/16）
- C类：192.0.0.0 ~ 223.255.255.255，默认掩码255.255.255.0（/24）
- D类：224.0.0.0 ~ 239.255.255.255（多播地址）
- E类：240.0.0.0 ~ 255.255.255.255（保留）

子网划分：借用主机位作为子网位。子网掩码中1对应网络位和子网位，0对应主机位。子网数=2^n（n为子网位数），每个子网可用IP数=2^m-2（m为主机位数，减去网络地址和广播地址）。

CIDR（无类域间路由）：使用斜线记法，如192.168.1.0/24。支持路由聚合（超网），通过最长前缀匹配进行路由查找，有效缓解路由表膨胀问题。

VLSM（可变长子网掩码）：允许使用不同长度的子网掩码，进一步提高IP地址利用率。

ARP（地址解析协议）：将IP地址解析为MAC地址。ARP请求是广播帧，ARP响应是单播帧。主机维护ARP缓存表（动态条目有超时机制）。

ICMP（互联网控制报文协议）：用于报告网络层差错和查询。Ping使用ICMP Echo Request/Reply，Traceroute利用TTL递增和ICMP Time Exceeded。

路由协议分为内部网关协议（IGP）和外部网关协议（EGP）：
- RIP：基于距离向量算法，跳数作为度量（最大15跳），使用UDP 520端口
- OSPF：基于链路状态算法，使用Dijkstra SPF计算最短路径，支持区域划分，收敛速度快
- BGP：路径向量协议，AS间路由，基于策略而非最短路径，使用TCP 179端口

NAT（网络地址转换）：将私有IP转换为公网IP。私有地址范围：10.0.0.0/8、172.16.0.0/12、192.168.0.0/16。NAPT（PAT）使用传输层端口号区分内网主机。

DHCP（动态主机配置协议）：自动分配IP地址。四种报文：Discover(客户端广播)→Offer(服务器单播)→Request(客户端广播)→ACK(服务器确认)。租约到期前需要续期。
""",
    },
    {
        "title": "第5章 传输层（TCP与UDP）",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第5章",
        "doc_type": "textbook",
        "knowledge_points": ["UDP协议", "TCP连接管理", "TCP可靠传输与流量控制", "TCP拥塞控制"],
        "difficulty": "进阶",
        "content": """
传输层为应用进程之间提供端到端的逻辑通信。两个主要协议：UDP（用户数据报协议）和TCP（传输控制协议）。

UDP是无连接的，提供尽最大努力交付，没有拥塞控制，首部仅8字节（源端口、目的端口、长度、校验和）。UDP校验和的计算覆盖伪首部（源IP、目的IP、协议号、UDP长度）+UDP首部+数据。UDP适用于DNS（53端口）、SNMP、音视频实时传输等对实时性要求高但容忍少量丢包的场景。

TCP是面向连接的，提供可靠的、全双工的字节流传输服务。

TCP连接管理——三次握手（Three-Way Handshake）：
1. 客户端发送SYN=1, seq=x（进入SYN-SENT状态）
2. 服务器回复SYN=1, ACK=1, seq=y, ack=x+1（进入SYN-RCVD状态）
3. 客户端回复ACK=1, seq=x+1, ack=y+1（双方进入ESTABLISHED状态）

四次挥手（Four-Way Handshake）：
1. 主动关闭方发送FIN=1, seq=u
2. 被动关闭方回复ACK=1, ack=u+1（半关闭状态）
3. 被动关闭方发送FIN=1, seq=v
4. 主动关闭方回复ACK=1, ack=v+1，进入TIME-WAIT（等待2MSL）

TIME-WAIT状态持续2MSL（Maximum Segment Lifetime，约2分钟），原因：
- 确保最后一个ACK能到达（如丢失，对方重传FIN）
- 让旧连接的所有报文从网络中消失

TCP可靠传输机制：
- 序列号：每个字节编号，ISN（初始序列号）随机生成
- 累积确认：ACK号表示期望收到的下一个字节
- 超时重传：RTO（超时重传时间）通过RTT的加权平均动态计算（Jacobson算法）
- 快速重传：收到3个冗余ACK后立即重传

TCP流量控制——滑动窗口：
- 接收窗口(rwnd)：接收方在ACK中通告的可用缓冲区大小
- 发送窗口(swnd)=min(cwnd, rwnd)
- 零窗口时，发送方启动坚持定时器(Persist Timer)发送窗口探测报文

TCP拥塞控制——四种核心算法：

1. 慢启动（Slow Start）：cwnd初始为1 MSS，每收到一个ACK，cwnd+1（指数增长：1→2→4→8...）。超过ssthresh后进入拥塞避免。

2. 拥塞避免（Congestion Avoidance）：每经过一个RTT，cwnd+1（线性增长）。检测到超时后，ssthresh=cwnd/2，cwnd=1，重新慢启动。

3. 快重传（Fast Retransmit）：收到3个冗余ACK（共4个相同ACK）后，不等超时立即重传丢失的报文段。

4. 快恢复（Fast Recovery）：快重传后，ssthresh=cwnd/2，cwnd=ssthresh，直接进入拥塞避免（而非慢启动）。

TCP拥塞控制算法演进：
- Tahoe：慢启动+拥塞避免+快重传（超时→慢启动）
- Reno：Tahoe+快恢复（快重传后→快恢复而非慢启动）
- CUBIC：面向高BDP网络，使用三次函数而非线性增长
""",
    },
    {
        "title": "第6章 应用层",
        "source": "《计算机网络》(谢希仁 第8版)",
        "source_page": "第6章",
        "doc_type": "textbook",
        "knowledge_points": ["DNS系统", "HTTP与HTTPS", "高级Web协议", "FTP与电子邮件"],
        "difficulty": "进阶",
        "content": """
应用层是网络体系结构的最高层，为应用程序提供网络服务接口。

DNS（域名系统）：将域名解析为IP地址的分层命名系统。
DNS域名空间是树形结构，从根开始。顶级域名分为：国家顶级域名(cn/uk/jp)、通用顶级域名(com/org/net/edu)。

域名解析过程：
1. 查询本地DNS缓存 → 查询hosts文件
2. 向本地DNS服务器发起递归查询
3. 本地DNS服务器进行迭代查询：根DNS → 顶级DNS → 权威DNS
4. 返回解析结果并缓存（根据TTL）

DNS记录类型：
- A记录：域名→IPv4地址
- AAAA记录：域名→IPv6地址
- CNAME记录：别名→规范名
- MX记录：邮件交换服务器
- NS记录：域名服务器
- PTR记录：IP→域名（反向解析）
- SOA记录：起始授权记录
- TXT记录：文本信息（如SPF/ DKIM验证）

DNS通常使用UDP 53端口（查询响应可在一个UDP报文中完成），区域传送使用TCP 53端口。

HTTP（超文本传输协议）是无状态的请求-响应协议。

HTTP请求方法：GET（获取）、POST（提交数据）、PUT（更新）、DELETE（删除）、HEAD（仅获取头部）、OPTIONS（查询支持的方法）

HTTP状态码：
- 1xx：信息性状态码（100 Continue）
- 2xx：成功（200 OK, 201 Created, 204 No Content）
- 3xx：重定向（301永久, 302临时, 304 Not Modified）
- 4xx：客户端错误（400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found）
- 5xx：服务器错误（500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable）

HTTP/1.0默认非持久连接（每个请求/响应对新建一个TCP连接）。HTTP/1.1引入持久连接（Connection: Keep-Alive），可在同一连接上发送多个请求。管道化（Pipelining）允许不等待响应连续发送请求。

HTTP缓存策略：
- 强缓存：Cache-Control: max-age=3600 或 Expires
- 协商缓存：ETag（实体标签）和 If-None-Match，Last-Modified 和 If-Modified-Since

HTTPS（HTTP over TLS）：在HTTP和TCP之间增加TLS/SSL层。端口443。
TLS 1.3握手过程（1-RTT）：
1. ClientHello（支持的密码套件、密钥共享）
2. ServerHello（选定密码套件、密钥共享、证书、Finished）
3. Client Finished，开始传输加密数据

HTTPS提供：机密性（对称加密）、完整性（MAC）、身份认证（数字证书）、前向安全性（ECDHE密钥交换）。

HTTP/2的主要改进：二进制分帧、多路复用（同一连接上并发的请求/响应）、头部压缩（HPACK字典）、服务器推送（Server Push）。

HTTP/3使用QUIC协议（基于UDP），解决了TCP队头阻塞问题，实现0-RTT连接建立。

电子邮件系统的三个主要协议：
- SMTP（25端口）：邮件发送（客户端→服务器、服务器→服务器）
- POP3（110端口）：邮件接收，将邮件下载到本地
- IMAP（143端口）：邮件接收，在服务器上管理邮件
""",
    },
]

# ---- 知识文档 —— RFC 标准摘要 ----
RFC_DOCUMENTS = [
    {
        "title": "RFC 793 — TCP 协议规范",
        "source": "RFC 793 (STD 7)",
        "source_page": "Transmission Control Protocol",
        "doc_type": "rfc",
        "knowledge_points": ["TCP连接管理", "TCP可靠传输与流量控制"],
        "difficulty": "进阶",
        "content": """
RFC 793 定义了传输控制协议（TCP），发布日期1981年9月。

TCP被设计用于在分组交换网络中的主机间提供可靠的、端到端的字节流传输服务。它运行在IP之上（协议号6）。

TCP的核心功能包括：
1. 基本数据传输：将字节流分割为段（Segment），每个段有序列号用于排序和去重
2. 可靠性：通过序列号、确认号、校验和、超时重传和重复检测机制确保数据无差错、不丢失、不重复、按序到达
3. 流量控制：接收方通过窗口字段通告可用缓冲区大小，发送方据此控制发送速率
4. 多路复用：通过端口号区分同一主机上的多个应用进程（16位，0-65535）
5. 连接管理：使用三次握手建立连接，四次挥手关闭连接

TCP段首部格式（最小20字节）：源端口、目的端口、序列号、确认号、数据偏移、保留位、控制标志（URG/ACK/PSH/RST/SYN/FIN）、窗口大小、校验和、紧急指针、选项（MSS、窗口缩放、时间戳等）。

连接建立的三次握手中，双方交换初始序列号（ISN），ISN应当是随时间变化的随机值以防止旧连接的报文干扰新连接。

TCP使用累积确认机制：ACK号N表示已收到序列号N-1之前的所有字节。为提高效率，可以使用捎带确认（Piggybacking），将ACK与反向数据一起发送。

重传超时（RTO）的计算基于RTT的测量。RFC 793建议使用平滑后的RTT（SRTT）加上方差来计算RTO，后续在RFC 6298中改进为Jacobson/Karels算法。
""",
    },
    {
        "title": "RFC 791 — IPv4 协议规范",
        "source": "RFC 791 (STD 5)",
        "source_page": "Internet Protocol",
        "doc_type": "rfc",
        "knowledge_points": ["IPv4与IPv6", "IP地址与子网划分"],
        "difficulty": "进阶",
        "content": """
RFC 791 定义了互联网协议版本4（IPv4），发布日期1981年9月。

IP协议提供尽最大努力（best-effort）的无连接数据报传输服务。它不保证可靠交付、不保证顺序、不保证不重复。

IPv4首部格式（最小20字节）：
- 版本(4位)=4
- 首部长度(4位)：以4字节为单位，最小5(20字节)
- 服务类型(8位)：后来重新定义为DSCP+ECN
- 总长度(16位)：首部+数据的字节数，最大65535字节
- 标识(16位)：用于分片重组的分组标识
- 标志(3位)：第1位保留=0，第2位DF(Don't Fragment)，第3位MF(More Fragments)
- 片偏移(13位)：以8字节为单位，指示本分片在原数据报中的位置
- TTL(8位)：每经过一个路由器减1，为0时丢弃
- 协议(8位)：上层协议标识(1=ICMP, 6=TCP, 17=UDP)
- 首部校验和(16位)：仅校验首部，每跳重新计算(TTL变化)
- 源IP地址(32位)
- 目的IP地址(32位)
- 可选字段(0-40字节)：用于测试、安全、路由等

IP分片：如果数据报大小超过出接口MTU，路由器将其分片。DF=1时路由器不下发分片，返回ICMP Destination Unreachable(Fragmentation Needed)。分片在最终目的地重组，使用标识符、标志和片偏移。

IPv4地址分为5类。A类(0.)：网络号8位，主机号24位。B类(10.)：网络号16位，主机号16位。C类(110.)：网络号24位，主机号8位。D类(1110.)：多播地址。E类(1111.)：保留。
""",
    },
    {
        "title": "RFC 2616 — HTTP/1.1 协议规范",
        "source": "RFC 2616 (已由RFC 7230系列更新)",
        "source_page": "Hypertext Transfer Protocol",
        "doc_type": "rfc",
        "knowledge_points": ["HTTP与HTTPS"],
        "difficulty": "基础",
        "content": """
RFC 2616 定义了超文本传输协议HTTP/1.1。HTTP是应用层协议，用于分布式、协作式的超媒体信息系统。

HTTP/1.1相对于HTTP/1.0的关键改进：
1. 持久连接（Persistent Connection）：默认保持TCP连接不关闭，可在同一连接上发送多个请求/响应对（Connection: Keep-Alive）
2. 管道化（Pipelining）：客户端可不等待前一个响应就发送后续请求（实践中较少使用）
3. 分块传输编码（Chunked Transfer Encoding）：动态内容可分块发送，无需预先确定Content-Length
4. 内容协商（Content Negotiation）：Server-Driven、Agent-Driven、Transparent
5. 缓存控制增强：引入Cache-Control头部，替代Expires的局限性
6. Host头部：必须包含，使虚拟主机成为可能
7. 范围请求（Range Request）：支持断点续传

HTTP请求格式：
GET /path HTTP/1.1
Host: example.com
Accept: text/html
...（空行结束头部）

HTTP响应格式：
HTTP/1.1 200 OK
Content-Type: text/html
Content-Length: 1234
...（空行）+ 实体内容

HTTP是无状态协议，Cookie机制通过Set-Cookie和Cookie头部实现状态管理。

HTTPS通过将HTTP置于TLS/SSL之上实现安全通信。TLS提供：
- 机密性：协商对称密钥加密
- 完整性：使用HMAC确保数据未被篡改
- 身份认证：数字证书验证服务器身份（可选客户端认证）
""",
    },
    {
        "title": "RFC 2328 — OSPF 版本2",
        "source": "RFC 2328 (STD 54)",
        "source_page": "OSPF Version 2",
        "doc_type": "rfc",
        "knowledge_points": ["路由算法与协议"],
        "difficulty": "进阶",
        "content": """
RFC 2328 定义了开放最短路径优先（OSPF）路由协议的版本2，用于IPv4自治系统内部路由。

OSPF是一种基于链路状态算法的IGP。每台路由器构建完整的网络拓扑图（链路状态数据库LSDB），独立运行Dijkstra SPF算法计算到达每个网络的最短路径。

OSPF的关键设计：
1. 分层路由：将AS划分为区域（Area），骨干区域为Area 0，所有非骨干区域必须连接到骨干区域
2. LSA（链路状态通告）：路由器通过LSA泛洪通告链路状态，所有OSPF路由器维护完全相同的LSDB
3. DR/BDR：在广播多路访问网络上选举指定路由器（DR）和备份指定路由器（BDR），减少邻接关系数量
4. 度量值：基于带宽（参考带宽/接口带宽），累积计算路径开销

OSPF报文类型：
- Hello：发现和维护邻居关系（广播网络每10秒，NBMA每30秒）
- DBD（数据库描述）：交换LSA摘要
- LSR（链路状态请求）：请求特定LSA的完整数据
- LSU（链路状态更新）：发送完整的LSA数据
- LSAck：确认LSU

OSPF状态机（邻居关系建立过程）：Down → Init → 2-Way → ExStart → Exchange → Loading → Full

OSPF的优势：快速收敛（链路变化后秒级更新）、无路由环路（全拓扑视图）、支持VLSM/CIDR、等价多路径负载均衡(ECMP)、认证支持（明文和MD5）。

OSPF使用IP协议号89，多播地址224.0.0.5(AllSPFRouters)和224.0.0.6(AllDRouters)。
""",
    },
    {
        "title": "RFC 4271 — BGP-4 协议规范",
        "source": "RFC 4271",
        "source_page": "Border Gateway Protocol 4",
        "doc_type": "rfc",
        "knowledge_points": ["路由算法与协议"],
        "difficulty": "高级",
        "content": """
RFC 4271 定义了边界网关协议版本4（BGP-4），是互联网自治系统（AS）间使用的路由协议。

BGP是一种路径向量协议，与IGP不同，BGP不基于最短路径做路由决策，而是基于路由策略。每个BGP路由器维护一个RIB（路由信息库），包含从各邻居收到的路由及其AS路径属性。

BGP的关键概念：
1. AS（自治系统）：由同一机构管理、共享统一路由策略的网络集合。AS号：16位(1-64511为公有，64512-65535为私有)或32位
2. eBGP：不同AS之间的BGP会话（通常直连，TTL=1）
3. iBGP：同一AS内BGP路由器之间的会话（全互联或使用路由反射器/联盟）
4. NLRI（网络层可达性信息）：BGP通告的前缀和路径属性

BGP路由属性：
- AS_Path：经过的AS号序列，用于防止环路（收到包含自身AS号的路由丢弃）
- Next_Hop：到达该前缀的下一跳IP
- Local_Preference：本地优先级（值越大越优先），AS内传播
- MED（Multi-Exit Discriminator）：多出口区分，值越小越优先，AS间传播
- Origin：路由起源（IGP < EGP < Incomplete）
- Community：路由标记，用于灵活策略控制

BGP选路顺序（部分）：
1. 最高Local_Preference
2. 最短AS_Path
3. 最低Origin类型
4. 最低MED
5. eBGP优先于iBGP
6. 最低IGP度量到Next_Hop
7. 最低Router ID

BGP使用TCP 179端口。Keepalive消息每60秒发送一次，Hold Timer默认180秒（3倍Keepalive时间）。
""",
    },
]

# ---- 25 个标准知识点详细解释（作为 knowledge_entry 类型文档）----
KNOWLEDGE_ENTRIES = [
    {
        "title": "OSI七层模型与TCP/IP模型的对比",
        "source": "星伴知识库",
        "doc_type": "knowledge_entry",
        "knowledge_points": ["网络体系结构"],
        "difficulty": "基础",
        "content": """
OSI七层模型是国际标准化组织（ISO）提出的网络体系结构标准。它将网络通信分为7个层次，每层都有自己的功能和协议：

1. 物理层（Physical Layer）：在物理介质上传输原始比特流。定义接口的机械/电气/功能/规程特性。典型设备：集线器（Hub）、中继器。

2. 数据链路层（Data Link Layer）：在相邻节点间无差错传输帧。功能：成帧、差错检测（CRC）、流量控制。典型设备：交换机（Switch）、网桥。协议：PPP、HDLC、以太网。

3. 网络层（Network Layer）：端到端的寻址和路由选择。功能：逻辑寻址（IP地址）、路由选择、分组转发。典型设备：路由器（Router）、三层交换机。协议：IP、ICMP、ARP、OSPF、BGP。

4. 传输层（Transport Layer）：端到端的可靠传输。功能：分段与重组、端口寻址、可靠性保障、流量控制、拥塞控制。协议：TCP、UDP。

5. 会话层（Session Layer）：建立、管理和终止会话连接。功能：会话同步、检查点、令牌管理。

6. 表示层（Presentation Layer）：数据格式转换。功能：加密/解密、压缩/解压缩、编码转换（如ASCII→EBCDIC）。协议：TLS/SSL（部分功能）。

7. 应用层（Application Layer）：为应用程序提供网络服务接口。协议：HTTP、FTP、SMTP、DNS、SNMP。

TCP/IP模型是实际互联网使用的协议栈，分为4层：
- 网络接口层：对应OSI物理层+数据链路层
- 网际层（IP层）：对应OSI网络层
- 传输层：对应OSI传输层
- 应用层：对应OSI会话层+表示层+应用层

实际教学中的五层模型：物理层→数据链路层→网络层→传输层→应用层，去掉了OSI中实现较少的会话层和表示层。

每层的数据单元（PDU）：
- 物理层：比特（Bit）
- 数据链路层：帧（Frame）
- 网络层：分组/数据报（Packet/Datagram）
- 传输层：段（Segment, TCP）或数据报（Datagram, UDP）
- 应用层：消息（Message）
""",
    },
]


# ================================================================
# 导入逻辑
# ================================================================

def seed_sub_topics(conn, dry_run: bool = False) -> int:
    """导入子知识点。"""
    cursor = conn.cursor()
    count = 0
    for name, parent, desc, order in SUB_TOPICS:
        try:
            if dry_run:
                print(f"  [DRY-RUN] sub_topic: {name} → {parent} (order={order})")
                count += 1
            else:
                cursor.execute(
                    """INSERT IGNORE INTO knowledge_sub_topics
                       (sub_topic_name, parent_kp, description, sort_order)
                       VALUES (%s, %s, %s, %s)""",
                    (name, parent, desc, order),
                )
                if cursor.rowcount > 0:
                    count += 1
        except Exception as e:
            print(f"  [WARN] 子知识点插入失败: {name} — {e}")
    conn.commit()
    cursor.close()
    return count


def seed_relations(conn, dry_run: bool = False) -> int:
    """导入知识关系。"""
    cursor = conn.cursor()
    count = 0
    for source, target, rel_type, desc in KNOWLEDGE_RELATIONS:
        try:
            if dry_run:
                count += 1
            else:
                cursor.execute(
                    """INSERT IGNORE INTO knowledge_relations
                       (source_kp, target_kp, relation_type, description)
                       VALUES (%s, %s, %s, %s)""",
                    (source, target, rel_type, desc),
                )
                if cursor.rowcount > 0:
                    count += 1
        except Exception as e:
            print(f"  [WARN] 关系插入失败: {source}→{target} — {e}")
    conn.commit()
    cursor.close()
    return count


def seed_document(conn, doc: dict, dry_run: bool = False) -> int:
    """导入单个文档（幂等：如已存在则返回现有 doc_id）。"""
    cursor = conn.cursor()
    kps_json = json.dumps(doc.get("knowledge_points", []), ensure_ascii=False)

    if dry_run:
        print(f"  [DRY-RUN] doc: {doc['title']}")
        cursor.close()
        return -1

    # 幂等检查：文档是否已存在
    cursor.execute(
        "SELECT doc_id FROM knowledge_documents WHERE title = %s",
        (doc["title"],)
    )
    existing = cursor.fetchone()
    if existing:
        cursor.close()
        return existing[0]

    cursor.execute(
        """INSERT INTO knowledge_documents
           (title, doc_type, knowledge_points, difficulty, source, source_page, status)
           VALUES (%s, %s, %s, %s, %s, %s, 'published')""",
        (
            doc["title"],
            doc.get("doc_type", "textbook"),
            kps_json,
            doc.get("difficulty", "基础"),
            doc.get("source", ""),
            doc.get("source_page", ""),
        ),
    )
    conn.commit()
    doc_id = cursor.lastrowid
    cursor.close()
    return doc_id


def seed_chunks_for_document(
    conn, doc_id: int, doc: dict, rag_service, dry_run: bool = False
) -> int:
    """为文档分块、生成嵌入、索引到 ChromaDB 和 MySQL。（幂等：已有块的文档跳过）"""
    content = doc.get("content", "")
    if not content.strip():
        return 0

    # 幂等检查：已有块的文档跳过
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM knowledge_chunks WHERE doc_id = %s", (doc_id,)
    )
    existing_count = cursor.fetchone()[0]
    cursor.close()
    if existing_count > 0:
        print(f"  (跳过，已有 {existing_count} 个块)")
        return 0

    # 分块
    raw_chunks = EmbeddingService.chunk_document(content)

    if dry_run:
        print(f"  [DRY-RUN] 文档分块: {len(raw_chunks)} 块")
        return len(raw_chunks)

    # 准备块数据
    chunks_data = []
    for i, chunk_text in enumerate(raw_chunks):
        chunks_data.append({
            "chunk_index": i,
            "content": chunk_text,
        })

    # 索引到 ChromaDB + MySQL
    indexed = rag_service.index_chunks(doc_id, chunks_data)
    return indexed


def main():
    parser = argparse.ArgumentParser(description="星伴知识库种子数据导入")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印预览，不实际写入",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="跳过嵌入生成（仅在 MySQL 中写入文本）",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("星伴(StarPal) 知识库种子数据导入")
    print("=" * 60)

    if args.dry_run:
        print("\n>>> DRY-RUN 模式：仅预览，不写入数据 <<<\n")

    # 连接数据库
    conn = get_connection()
    if not conn:
        print("[ERROR] 数据库连接失败")
        sys.exit(1)

    try:
        # ---- 1. 导入子知识点 ----
        print("\n[1/5] 导入子知识点...")
        st_count = seed_sub_topics(conn, args.dry_run)
        print(f"  已处理: {st_count} 个子知识点")

        # ---- 2. 导入知识关系 ----
        print("\n[2/5] 导入知识关系...")
        rel_count = seed_relations(conn, args.dry_run)
        print(f"  已处理: {rel_count} 条关系")

        # ---- 3. 导入教材章节 ----
        print("\n[3/5] 导入教材章节...")
        tb_count = 0
        for doc in TEXTBOOK_CHAPTERS:
            doc_id = seed_document(conn, doc, args.dry_run)
            if doc_id > 0:
                tb_count += 1
        print(f"  已处理: {tb_count} 个教材章节文档")

        # ---- 4. 导入 RFC 文档 ----
        print("\n[4/5] 导入 RFC 标准文档...")
        rfc_count = 0
        for doc in RFC_DOCUMENTS:
            doc_id = seed_document(conn, doc, args.dry_run)
            if doc_id > 0:
                rfc_count += 1
        print(f"  已处理: {rfc_count} 个 RFC 文档")

        # ---- 5. 导入知识点条目 ----
        for doc in KNOWLEDGE_ENTRIES:
            seed_document(conn, doc, args.dry_run)

        # ---- 6. 为所有文档生成嵌入并索引 ----
        if not args.dry_run and not args.skip_embeddings:
            print("\n[5/5] 生成嵌入向量并索引到 ChromaDB...")
            rag = RAGService()

            all_docs = TEXTBOOK_CHAPTERS + RFC_DOCUMENTS + KNOWLEDGE_ENTRIES
            total_chunks = 0

            cursor = conn.cursor(dictionary=True)
            for doc in all_docs:
                cursor.execute(
                    "SELECT doc_id FROM knowledge_documents WHERE title = %s",
                    (doc["title"],),
                )
                row = cursor.fetchone()
                if not row:
                    continue

                doc_id = row["doc_id"]
                chunks_count = seed_chunks_for_document(
                    conn, doc_id, doc, rag, args.dry_run
                )
                total_chunks += chunks_count
                if chunks_count > 0:
                    print(f"  {doc['title'][:40]}... -> {chunks_count} 块已索引")

            cursor.close()
            print(f"\n  总计索引: {total_chunks} 个知识块")
            print(f"  ChromaDB 集合大小: {rag._collection.count()}")
        elif args.skip_embeddings:
            print("\n[5/5] 跳过嵌入生成（--skip-embeddings）")
        else:
            print("\n[5/5] DRY-RUN: 跳过嵌入生成")

    finally:
        conn.close()

    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY-RUN 完成（无数据写入）")
    else:
        print("知识库种子数据导入完成！")
        print(f"  - 子知识点: {len(SUB_TOPICS)} 条")
        print(f"  - 知识关系: {len(KNOWLEDGE_RELATIONS)} 条")
        print(f"  - 教材章节: {len(TEXTBOOK_CHAPTERS)} 篇")
        print(f"  - RFC 文档: {len(RFC_DOCUMENTS)} 篇")
    print("=" * 60)


if __name__ == "__main__":
    main()
