#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试进度条功能
"""

import asyncio
import time
from web_optimizer import LargeFileOptimizer

async def test_progress_callback():
    """测试进度回调功能"""
    print("🧪 测试进度回调功能")
    
    # 模拟进度回调
    def progress_callback(stage: str, progress: int, message: str = ""):
        print(f"[{progress:3d}%] {stage}: {message}")
        time.sleep(0.1)  # 模拟处理时间
    
    # 模拟各个处理阶段
    stages = [
        ("初始化", 5, "开始处理文件..."),
        ("类型检测", 10, "检测日志格式..."),
        ("环境信息", 15, "提取JVM环境信息..."),
        ("解析日志", 20, "开始解析GC事件..."),
        ("解析日志", 30, "已处理 100MB / 500MB，解析到 1000 个事件"),
        ("解析日志", 45, "已处理 250MB / 500MB，解析到 2500 个事件"),
        ("解析日志", 60, "已处理 400MB / 500MB，解析到 4000 个事件"),
        ("解析日志", 70, "已处理 500MB / 500MB，解析到 5000 个事件"),
        ("运行时信息", 75, "更新运行时信息..."),
        ("数据采样", 80, "智能采样分析..."),
        ("性能分析", 85, "计算性能指标..."),
        ("停顿分析", 90, "分析停顿分布..."),
        ("警报检测", 95, "检测性能问题..."),
        ("图表生成", 98, "生成图表数据..."),
        ("完成", 100, "处理完成！")
    ]
    
    print("\n📊 模拟进度更新:")
    for stage, progress, message in stages:
        progress_callback(stage, progress, message)
    
    print("\n✅ 进度回调测试完成")

async def test_with_real_file():
    """使用真实文件测试进度功能"""
    import os
    
    # 查找测试文件
    test_files = [
        "uploads/e58bcf5e692d_gc.log",
        "test/data/sample_g1.log",
        "uploads/22b702a941a7_test_g1.log"
    ]
    
    test_file = None
    for file_path in test_files:
        if os.path.exists(file_path):
            test_file = file_path
            break
    
    if not test_file:
        print("⚠️ 未找到测试文件，跳过真实文件测试")
        return
    
    print(f"\n🧪 使用真实文件测试: {test_file}")
    file_size_mb = os.path.getsize(test_file) / (1024 * 1024)
    print(f"📁 文件大小: {file_size_mb:.1f} MB")
    
    # 创建进度回调
    def progress_callback(stage: str, progress: int, message: str = ""):
        print(f"[{progress:3d}%] {stage}: {message}")
    
    # 使用优化器处理
    optimizer = LargeFileOptimizer()
    start_time = time.time()
    
    try:
        result = await optimizer.process_large_gc_log(test_file, progress_callback)
        end_time = time.time()
        
        print(f"\n✅ 处理完成 (耗时: {end_time - start_time:.2f}秒)")
        print(f"   总事件数: {result['total_events']:,}")
        print(f"   分析事件数: {result['analyzed_events']:,}")
        
        if result['metrics']:
            metrics = result['metrics']
            print(f"   性能评分: {metrics.get('performance_score', 0):.1f}/100")
            print(f"   平均停顿: {metrics.get('avg_pause_time', 0):.1f}ms")
    
    except Exception as e:
        print(f"❌ 处理失败: {e}")

if __name__ == "__main__":
    print("🔍 GC日志分析进度条测试")
    print("=" * 50)
    
    # 运行测试
    asyncio.run(test_progress_callback())
    asyncio.run(test_with_real_file())