#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志导入指南和工具
提供详细的日志导入说明和验证功能
"""

import os
import sys

# 添加项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.log_loader import LogLoader, GCLogType
from main import analyze_gc_log_tool
import asyncio


def print_import_guide():
    """打印GC日志导入指南"""
    print("""
🔍 GC日志导入完整指南

1. 📁 支持的日志格式
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   🔸 G1 GC日志 (OpenJDK/Oracle JDK)
   格式特征：
   - 包含 [GC pause] 关键字
   - 有 (young)、(mixed) 标识
   - 包含 G1 Evacuation Pause 信息
   
   示例：
   2024-01-01T10:00:01.123: [GC pause (G1 Evacuation Pause) (young) 15.234 ms] 512M->256M(1024M)

   🔸 IBM J9VM日志 (XML格式)
   格式特征：
   - XML结构 <gc type="...">
   - 包含 <mem-info> 内存信息
   - 包含 <nursery> 新生代信息
   
   示例：
   <gc type="scavenge" id="1" totalTime="5.123" timestamp="2024-01-01T10:00:01.123">
     <mem-info before="1048576" after="524288" total="2097152" />
   </gc>

2. 🚀 生成GC日志的JVM参数
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   🔸 G1 GC (JDK 11+)
   -XX:+UseG1GC
   -Xloggc:gc.log
   -XX:+PrintGC
   -XX:+PrintGCDetails
   -XX:+PrintGCTimeStamps
   -XX:+PrintGCDateStamps

   🔸 G1 GC (JDK 9+) 统一日志
   -XX:+UseG1GC
   -Xlog:gc*:gc.log:time,tags

   🔸 IBM J9VM
   -Xverbosegc
   -Xverbosegc:gc.xml

3. 📂 导入方法
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   方法1: 编程接口导入
   ```python
   from utils.log_loader import load_gc_log
   
   # 加载日志文件
   content, log_type = load_gc_log("/path/to/gc.log")
   print(f"日志类型: {log_type.value}")
   ```

   方法2: MCP工具接口导入
   ```python
   await analyze_gc_log_tool({
       "file_path": "/path/to/gc.log",
       "analysis_type": "detailed"
   })
   ```

   方法3: 命令行导入验证
   ```bash
   python gc_log_import_guide.py verify /path/to/gc.log
   ```

4. 📋 文件要求
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ✅ 文件编码: UTF-8 (推荐)
   ✅ 文件大小: 无限制 (系统自动处理)
   ✅ 文件扩展名: .log, .txt, .xml 或任意
   ✅ 内容格式: 文本或XML格式

5. 🔧 常见问题处理
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   ❓ 文件编码问题
   解决：系统自动处理，使用 errors='ignore' 模式

   ❓ 日志格式不识别
   解决：检查日志是否包含GC信息，参考上述格式特征

   ❓ 文件过大
   解决：系统支持大文件，自动进行内存优化处理

   ❓ 混合格式日志
   解决：提取纯GC部分，或分别处理不同格式

6. 🧪 验证导入
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   使用以下命令验证日志是否可以正确导入：
   
   python gc_log_import_guide.py verify /path/to/your/gc.log

   或者使用测试示例：
   
   python gc_log_import_guide.py demo

7. 📊 导入后的操作
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

   导入成功后，您可以：
   ✅ 查看详细性能指标
   ✅ 生成专业分析报告
   ✅ 检测性能问题
   ✅ 与其他日志对比
   ✅ 设置性能警报
""")


async def verify_log_file(file_path: str):
    """验证日志文件是否可以正确导入和分析"""
    print(f"\n🔍 验证日志文件: {file_path}")
    print("=" * 60)
    
    try:
        # 检查文件存在
        if not os.path.exists(file_path):
            print("❌ 文件不存在")
            return False
        
        print("✅ 文件存在")
        
        # 加载并检测日志类型
        loader = LogLoader()
        print("📂 正在加载日志文件...")
        
        try:
            content, log_type = loader.load_log_file(file_path)
            print(f"✅ 日志加载成功")
            print(f"📊 检测到的日志类型: {log_type.value}")
            
            # 获取日志概要
            summary = loader.get_log_summary(content, log_type)
            print(f"📏 日志总行数: {summary['total_lines']}")
            print(f"📦 文件大小: {summary['file_size_bytes']} 字节")
            print(f"🎯 估计GC事件数: {summary['estimated_gc_events']}")
            
            if log_type == GCLogType.UNKNOWN:
                print("⚠️ 无法识别日志格式，可能不是标准的GC日志")
                print("💡 请检查日志是否包含GC相关信息")
                return False
                
        except Exception as e:
            print(f"❌ 日志加载失败: {e}")
            return False
        
        # 尝试分析日志
        print("🔄 正在尝试分析日志...")
        try:
            result = await analyze_gc_log_tool({
                "file_path": file_path,
                "analysis_type": "basic"
            })
            
            if result.content:
                print("✅ 日志分析成功")
                content_text = result.content[0].text
                lines = content_text.split('\n')[:5]  # 显示前5行
                print("📋 分析结果预览:")
                for line in lines:
                    if line.strip():
                        print(f"   {line}")
                
                print("\n🎉 日志文件验证完成！可以正常使用。")
                return True
            else:
                print("❌ 分析结果为空")
                return False
                
        except Exception as e:
            print(f"❌ 日志分析失败: {e}")
            return False
            
    except Exception as e:
        print(f"❌ 验证过程出错: {e}")
        return False


async def demo_import():
    """演示如何导入示例日志"""
    print("\n🎭 日志导入演示")
    print("=" * 40)
    
    # 示例文件路径
    sample_files = [
        "test/data/sample_g1.log",
        "test/data/sample_j9.log"
    ]
    
    for sample_file in sample_files:
        if os.path.exists(sample_file):
            print(f"\n📁 演示文件: {sample_file}")
            success = await verify_log_file(sample_file)
            if success:
                print("✨ 演示成功")
            else:
                print("⚠️ 演示遇到问题")
        else:
            print(f"⚠️ 示例文件不存在: {sample_file}")


def create_sample_logs():
    """创建示例日志文件供用户参考"""
    print("\n📝 创建示例日志文件")
    print("=" * 30)
    
    # G1 GC示例
    g1_sample = """2024-01-01T10:00:01.123: [GC pause (G1 Evacuation Pause) (young) 15.234 ms] 512M->256M(1024M)
2024-01-01T10:00:05.456: [GC pause (G1 Evacuation Pause) (young) 12.567 ms] 600M->300M(1024M)
2024-01-01T10:00:10.789: [GC pause (G1 Evacuation Pause) (mixed) 25.678 ms] 800M->400M(1024M)
2024-01-01T10:00:15.012: [GC pause (G1 Evacuation Pause) (young) 18.901 ms] 700M->350M(1024M)
2024-01-01T10:00:20.345: [Full GC (System.gc()) 150.456 ms] 900M->200M(1024M)"""
    
    # IBM J9VM示例
    j9_sample = """<?xml version="1.0" ?>
<verbosegc xmlns="http://www.ibm.com/j9/verbosegc" version="1.0">
<gc type="scavenge" id="1" totalTime="5.123" timestamp="2024-01-01T10:00:01.123">
<mem-info before="1048576" after="524288" total="2097152" />
<nursery before="262144" after="131072" />
</gc>
<gc type="global" id="2" totalTime="15.456" timestamp="2024-01-01T10:00:10.789">
<mem-info before="1572864" after="786432" total="2097152" />
</gc>
</verbosegc>"""
    
    # 创建示例文件
    try:
        with open("example_g1.log", "w", encoding="utf-8") as f:
            f.write(g1_sample)
        print("✅ 创建了 example_g1.log")
        
        with open("example_j9.log", "w", encoding="utf-8") as f:
            f.write(j9_sample)
        print("✅ 创建了 example_j9.log")
        
        print("\n💡 您可以使用这些示例文件进行测试:")
        print("   python gc_log_import_guide.py verify example_g1.log")
        print("   python gc_log_import_guide.py verify example_j9.log")
        
    except Exception as e:
        print(f"❌ 创建示例文件失败: {e}")


async def main():
    """主函数"""
    if len(sys.argv) < 2:
        print_import_guide()
        return
    
    command = sys.argv[1].lower()
    
    if command == "verify" and len(sys.argv) > 2:
        file_path = sys.argv[2]
        await verify_log_file(file_path)
    elif command == "demo":
        await demo_import()
    elif command == "create-samples":
        create_sample_logs()
    elif command == "help":
        print_import_guide()
    else:
        print("🔧 用法:")
        print("  python gc_log_import_guide.py help              # 显示完整指南")
        print("  python gc_log_import_guide.py verify <file>     # 验证日志文件")
        print("  python gc_log_import_guide.py demo              # 运行演示")
        print("  python gc_log_import_guide.py create-samples    # 创建示例文件")


if __name__ == "__main__":
    asyncio.run(main())