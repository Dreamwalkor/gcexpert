#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
分析上传的GC日志文件
直接执行该脚本分析uploads目录中的日志
"""

import os
import sys
import asyncio

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入所需模块
from utils.log_loader import LogLoader, GCLogType
from parser.g1_parser import parse_gc_log as parse_g1_log
from parser.ibm_parser import parse_gc_log as parse_j9_log
from analyzer.metrics import analyze_gc_metrics
from analyzer.report_generator import generate_gc_report

async def analyze_gc_log(file_path):
    """分析指定的GC日志文件并输出结果"""
    print(f"\n🔍 正在分析日志文件: {file_path}")
    print("=" * 60)
    
    try:
        # 加载日志文件
        loader = LogLoader()
        log_content, log_type = loader.load_log_file(file_path)
        print(f"✅ 日志加载成功")
        print(f"📊 检测到的日志类型: {log_type.value}")
        
        # 获取日志概要
        summary = loader.get_log_summary(log_content, log_type)
        print(f"📏 日志总行数: {summary['total_lines']}")
        print(f"📦 文件大小: {summary['file_size_bytes'] / 1024:.1f} KB")
        print(f"🎯 估计GC事件数: {summary['estimated_gc_events']}")
        
        # 根据日志类型选择解析器
        if log_type == GCLogType.G1:
            print("🔄 使用G1 GC解析器...")
            parse_result = parse_g1_log(log_content)
            parser_type = "G1 GC"
        elif log_type == GCLogType.IBM_J9:
            print("🔄 使用IBM J9VM解析器...")
            parse_result = parse_j9_log(log_content)
            parser_type = "IBM J9VM"
        else:
            print("❌ 不支持的日志格式")
            return False
        
        # 分析性能指标
        events = parse_result.get('events', [])
        if not events:
            print("⚠️ 日志文件中未找到GC事件")
            return False
        
        print(f"📈 解析到 {len(events)} 个GC事件")
        print("🔍 分析性能指标...")
        metrics = analyze_gc_metrics(events)
        
        # 生成报告
        print("📝 生成分析报告...")
        try:
            # 准备分析数据
            analysis_data = {
                'gc_type': parser_type,
                'file_path': file_path,
                'total_events': len(events)
            }
            
            # 转换指标数据
            metrics_data = {
                'throughput': {
                    'app_time_percentage': getattr(metrics, 'throughput_percentage', 0),
                    'gc_time_percentage': getattr(metrics, 'gc_overhead_percentage', 0)
                },
                'latency': {
                    'avg_pause_time': getattr(metrics, 'avg_pause_time', 0),
                    'max_pause_time': getattr(metrics, 'max_pause_time', 0),
                    'p95_pause_time': getattr(metrics, 'p95_pause_time', 0),
                    'p99_pause_time': getattr(metrics, 'p99_pause_time', 0)
                },
                'memory': {
                    'memory_reclaim_efficiency': getattr(metrics, 'memory_reclaim_efficiency', 0)
                }
            }
            
            # 生成Markdown报告
            report = generate_gc_report(
                analysis_data=analysis_data,
                metrics_data=metrics_data,
                format_type="markdown"
            )
            
            # 输出报告预览
            print("\n" + "=" * 60)
            report_lines = report.split('\n')
            for line in report_lines[:20]:
                print(line)
            if len(report_lines) > 20:
                print("... 报告内容过多，完整内容请查看保存的报告文件")
            
            # 保存报告到文件
            report_file = f"{os.path.basename(file_path)}.report.md"
            with open(report_file, "w", encoding="utf-8") as f:
                f.write(report)
            print(f"\n✅ 报告已保存到: {report_file}")
            
        except Exception as e:
            print(f"⚠️ 生成报告时出错: {e}")
            # 输出基本信息
            print(f"\n📊 基本分析结果:")
            print(f"- 日志类型: {parser_type}")
            print(f"- GC事件数: {len(events)}")
            if hasattr(metrics, 'performance_score'):
                print(f"- 性能评分: {metrics.performance_score:.1f}/100")
            if hasattr(metrics, 'avg_pause_time'):
                print(f"- 平均停顿: {metrics.avg_pause_time:.1f}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ 分析过程出错: {e}")
        return False

async def main():
    """主函数"""
    # 获取uploads目录
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    
    # 检查uploads目录是否存在
    if not os.path.exists(uploads_dir):
        print(f"❌ uploads目录不存在: {uploads_dir}")
        return
    
    # 指定要分析的最新上传的日志文件
    selected_file = os.path.join(uploads_dir, "e58bcf5e692d_gc.log")
    
    if not os.path.exists(selected_file):
        # 如果指定的文件不存在，则列出所有.log文件并让用户选择
        log_files = [f for f in os.listdir(uploads_dir) if f.endswith('.log')]
        
        if not log_files:
            print(f"❌ 在 {uploads_dir} 目录中未找到.log文件")
            return
        
        print(f"📂 在uploads目录中找到 {len(log_files)} 个日志文件:")
        for i, file in enumerate(log_files, 1):
            print(f"  {i}. {file}")
        
        # 选择要分析的文件
        while True:
            try:
                choice = input("\n请选择要分析的文件编号 (默认分析第一个): ")
                if not choice:  # 默认选择第一个
                    choice = "1"
                
                index = int(choice) - 1
                if 0 <= index < len(log_files):
                    selected_file = os.path.join(uploads_dir, log_files[index])
                    break
                else:
                    print(f"❌ 无效的选择，请输入1到{len(log_files)}之间的数字")
            except ValueError:
                print("❌ 请输入有效的数字")
    
    print(f"✅ 选择分析文件: {os.path.basename(selected_file)}")
    # 分析选定的文件
    await analyze_gc_log(selected_file)

if __name__ == "__main__":
    asyncio.run(main())