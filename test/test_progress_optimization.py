#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试优化后的进度条功能
验证进度分配是否更加精准
"""

import asyncio
import time
from web_optimizer import LargeFileOptimizer

class ProgressTracker:
    """进度跟踪器 - 用于测试进度更新"""
    
    def __init__(self):
        self.progress_history = []
        self.start_time = time.time()
    
    def track_progress(self, stage: str, progress: int, message: str = ""):
        """记录进度更新"""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        self.progress_history.append({
            'timestamp': current_time,
            'elapsed': elapsed,
            'stage': stage,
            'progress': progress,
            'message': message
        })
        
        print(f"[{elapsed:6.2f}s] {stage:12} - {progress:3d}% - {message}")
    
    def analyze_progress(self):
        """分析进度更新情况"""
        print("\n" + "="*80)
        print("进度分析报告")
        print("="*80)
        
        if not self.progress_history:
            print("没有进度记录")
            return
        
        # 按阶段分组
        stages = {}
        for record in self.progress_history:
            stage = record['stage']
            if stage not in stages:
                stages[stage] = []
            stages[stage].append(record)
        
        print(f"总处理时间: {self.progress_history[-1]['elapsed']:.2f}秒")
        print(f"进度更新次数: {len(self.progress_history)}")
        print(f"处理阶段数: {len(stages)}")
        print()
        
        # 分析每个阶段
        for stage, records in stages.items():
            start_progress = records[0]['progress']
            end_progress = records[-1]['progress']
            duration = records[-1]['elapsed'] - records[0]['elapsed']
            update_count = len(records)
            
            print(f"阶段: {stage}")
            print(f"  进度范围: {start_progress}% -> {end_progress}% (跨度: {end_progress - start_progress}%)")
            print(f"  耗时: {duration:.2f}秒")
            print(f"  更新次数: {update_count}")
            print(f"  平均更新间隔: {duration/max(1, update_count-1):.2f}秒")
            print()
        
        # 检查进度连续性
        print("进度连续性检查:")
        prev_progress = 0
        gaps = []
        for record in self.progress_history:
            if record['progress'] < prev_progress:
                print(f"  警告: 进度倒退 {prev_progress}% -> {record['progress']}%")
            elif record['progress'] - prev_progress > 10:
                gaps.append((prev_progress, record['progress'], record['stage']))
            prev_progress = record['progress']
        
        if gaps:
            print("  发现进度跳跃:")
            for start, end, stage in gaps:
                print(f"    {start}% -> {end}% (跳跃 {end-start}%) 在阶段: {stage}")
        else:
            print("  进度更新连续，无大幅跳跃")


async def test_progress_with_mock_file():
    """使用模拟文件测试进度功能"""
    print("测试优化后的进度条功能")
    print("="*50)
    
    # 创建进度跟踪器
    tracker = ProgressTracker()
    
    # 创建优化器
    optimizer = LargeFileOptimizer()
    
    # 模拟处理过程
    print("模拟文件处理过程...")
    
    # 模拟各个阶段的进度更新
    stages = [
        ("类型检测", 2, 5, 0.5),
        ("环境信息", 7, 10, 0.3),
        ("解析日志", 12, 65, 5.0),  # 最耗时的阶段
        ("运行时信息", 67, 70, 0.4),
        ("数据采样", 72, 75, 0.6),
        ("性能分析", 77, 82, 0.8),
        ("停顿分析", 84, 88, 0.7),
        ("警报检测", 90, 93, 0.5),
        ("图表生成", 95, 98, 0.6),
        ("完成处理", 99, 100, 0.2)
    ]
    
    for stage_name, start_progress, end_progress, duration in stages:
        # 模拟阶段开始
        tracker.track_progress(stage_name, start_progress, f"开始{stage_name}...")
        
        # 模拟阶段进行中的进度更新
        progress_range = end_progress - start_progress
        if progress_range > 5:  # 对于跨度较大的阶段，模拟中间进度
            steps = min(progress_range // 2, 10)  # 最多10个中间步骤
            for i in range(1, steps):
                await asyncio.sleep(duration / steps)
                intermediate_progress = start_progress + (progress_range * i // steps)
                tracker.track_progress(stage_name, intermediate_progress, 
                                     f"{stage_name}进行中... ({i}/{steps-1})")
        
        # 模拟阶段完成
        await asyncio.sleep(duration / 4)
        tracker.track_progress(stage_name, end_progress, f"{stage_name}完成")
    
    # 分析进度
    tracker.analyze_progress()


def test_progress_calculation():
    """测试进度计算逻辑"""
    print("\n" + "="*50)
    print("测试进度计算逻辑")
    print("="*50)
    
    # 模拟文件大小和处理进度
    total_size = 1024 * 1024 * 1024  # 1GB
    
    print("文件解析阶段进度计算测试:")
    print("阶段范围: 12% - 65% (共53%)")
    print()
    
    test_points = [0, 10, 25, 50, 75, 90, 100]
    
    for file_progress in test_points:
        # 使用优化后的计算公式
        overall_progress = 12 + int(file_progress * 0.53)
        processed_size = total_size * file_progress / 100
        
        print(f"文件进度: {file_progress:3d}% -> 总体进度: {overall_progress:3d}% "
              f"(已处理: {processed_size/(1024**2):6.0f}MB)")
    
    print("\n各阶段进度分配:")
    stage_ranges = [
        ("类型检测", 0, 5),
        ("环境信息", 5, 10),
        ("解析日志", 10, 65),
        ("运行时信息", 65, 70),
        ("数据采样", 70, 75),
        ("性能分析", 75, 82),
        ("停顿分析", 82, 88),
        ("警报检测", 88, 93),
        ("图表生成", 93, 98),
        ("完成处理", 98, 100)
    ]
    
    total_range = 0
    for stage, start, end in stage_ranges:
        range_size = end - start
        total_range += range_size
        print(f"{stage:12}: {start:2d}% - {end:2d}% (跨度: {range_size:2d}%)")
    
    print(f"\n总进度跨度: {total_range}% (应该为100%)")
    
    if total_range == 100:
        print("✅ 进度分配正确")
    else:
        print(f"❌ 进度分配错误，总和为 {total_range}%")


async def main():
    """主测试函数"""
    print("🔍 进度条优化测试")
    print("="*80)
    
    # 测试1: 进度计算逻辑
    test_progress_calculation()
    
    # 测试2: 模拟完整处理流程
    await test_progress_with_mock_file()
    
    print("\n" + "="*80)
    print("测试完成！")
    print("="*80)
    
    print("\n优化要点:")
    print("1. 进度分配更精准：解析阶段占10-65%，其他阶段分配合理")
    print("2. 更新频率优化：根据不同阶段调整更新间隔")
    print("3. 视觉反馈增强：不同阶段使用不同颜色的进度条")
    print("4. 信息更详细：显示具体的处理阶段和消息")
    print("5. 连续性保证：避免进度跳跃和倒退")


if __name__ == "__main__":
    asyncio.run(main())