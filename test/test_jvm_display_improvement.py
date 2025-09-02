#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试改进后的JVM信息显示功能
"""

import asyncio
import os
from web_optimizer import LargeFileOptimizer

async def test_jvm_info_display():
    """测试不同GC类型的JVM信息显示"""
    print("🧪 测试改进后的JVM信息显示功能")
    print("=" * 60)
    
    # 测试文件列表
    test_files = [
        ("uploads/e58bcf5e692d_gc.log", "G1 GC"),
        ("uploads/a780e4f66cd2_verbosegc.005.log", "IBM J9 VM"),
        ("uploads/74ee0b872c81_j9_test.log", "IBM J9 VM (备选)")
    ]
    
    optimizer = LargeFileOptimizer()
    
    for file_path, gc_type in test_files:
        if not os.path.exists(file_path):
            print(f"⚠️ 跳过不存在的文件: {file_path}")
            continue
        
        print(f"\n🔍 测试 {gc_type} 日志: {os.path.basename(file_path)}")
        print("-" * 50)
        
        try:
            # 处理文件
            result = await optimizer.process_large_gc_log(file_path)
            jvm_info = result.get('jvm_info', {})
            
            print(f"📊 原始JVM信息字段:")
            for key, value in jvm_info.items():
                if value is not None:
                    print(f"  ✅ {key}: {value}")
                else:
                    print(f"  ❌ {key}: None")
            
            # 模拟前端显示逻辑
            print(f"\n🖥️ 前端显示效果预览:")
            display_cards = simulate_frontend_display(jvm_info)
            
            if not display_cards:
                print("  ❌ 无有效信息可显示")
            else:
                for card in display_cards:
                    print(f"  📋 {card['label']}: {card['value']}")
            
            print(f"\n📈 显示信息数量: {len(display_cards)} 个")
            
        except Exception as e:
            print(f"❌ 处理失败: {e}")

def simulate_frontend_display(jvm_info):
    """模拟前端显示逻辑"""
    if not jvm_info:
        return []
    
    # 检测GC类型
    gc_strategy = jvm_info.get('gc_strategy') or ''
    jvm_version = jvm_info.get('jvm_version') or ''
    log_format = jvm_info.get('log_format') or ''
    
    # 判断是否为IBM J9 VM
    is_ibm_j9 = 'IBM J9' in gc_strategy or 'IBM J9' in jvm_version or log_format == 'j9vm'
    # 判断是否为G1 GC
    is_g1gc = 'G1' in gc_strategy or 'Garbage-First' in gc_strategy or log_format == 'g1gc'
    
    def is_valid_value(value):
        return (value is not None and 
                value != 'Unknown' and 
                value != 0 and 
                value != '' and
                not (isinstance(value, float) and value != value))  # NaN check
    
    def format_memory(value):
        if not is_valid_value(value):
            return None
        return f"{value} MB"
    
    def format_cores(value):
        if not is_valid_value(value):
            return None
        return f"{value} 核"
    
    def format_duration(seconds):
        if not is_valid_value(seconds) or seconds <= 0:
            return None
        minutes = seconds / 60
        if minutes > 60:
            hours = minutes / 60
            return f"{hours:.1f} 小时"
        else:
            return f"{minutes:.1f} 分钟"
    
    # 准备要显示的卡片数据
    potential_cards = []
    
    # JVM版本
    version = jvm_info.get('jvm_version')
    if is_valid_value(version):
        potential_cards.append({'label': 'JVM版本', 'value': version})
    
    # GC策略
    if is_valid_value(gc_strategy):
        potential_cards.append({'label': 'GC策略', 'value': gc_strategy})
    
    # CPU核心数
    cpu_cores = jvm_info.get('cpu_cores')
    formatted_cores = format_cores(cpu_cores)
    if formatted_cores:
        potential_cards.append({'label': 'CPU核心数', 'value': formatted_cores})
    
    # 系统内存
    total_memory = jvm_info.get('total_memory_mb')
    formatted_memory = format_memory(total_memory)
    if formatted_memory:
        potential_cards.append({'label': '系统内存', 'value': formatted_memory})
    
    # 最大堆内存
    max_heap = jvm_info.get('maximum_heap_mb')
    formatted_max_heap = format_memory(max_heap)
    if formatted_max_heap:
        potential_cards.append({'label': '最大堆内存', 'value': formatted_max_heap})
    
    # 初始堆内存 - 仅对G1GC显示
    if is_g1gc:
        initial_heap = jvm_info.get('initial_heap_mb')
        formatted_initial_heap = format_memory(initial_heap)
        if formatted_initial_heap:
            potential_cards.append({'label': '初始堆内存', 'value': formatted_initial_heap})
    
    # 运行时长
    runtime_seconds = jvm_info.get('runtime_duration_seconds')
    formatted_duration = format_duration(runtime_seconds)
    if formatted_duration:
        potential_cards.append({'label': '运行时长', 'value': formatted_duration})
    
    # IBM J9特有信息
    if is_ibm_j9:
        gc_threads = jvm_info.get('gc_threads')
        if is_valid_value(gc_threads):
            potential_cards.append({'label': 'GC线程数', 'value': f"{gc_threads} 个"})
    
    # G1GC特有信息
    if is_g1gc:
        parallel_workers = jvm_info.get('parallel_workers')
        if is_valid_value(parallel_workers):
            potential_cards.append({'label': '并行工作线程', 'value': f"{parallel_workers} 个"})
        
        heap_region_size = jvm_info.get('heap_region_size')
        if is_valid_value(heap_region_size):
            potential_cards.append({'label': '堆区域大小', 'value': f"{heap_region_size}M"})
    
    return potential_cards

if __name__ == "__main__":
    asyncio.run(test_jvm_info_display())