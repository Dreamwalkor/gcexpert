#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复后的JVM信息提取器
"""

import os
from analyzer.jvm_info_extractor import JVMInfoExtractor

def test_g1_log_extraction():
    """测试G1日志的JVM信息提取"""
    print("🧪 测试G1日志JVM信息提取")
    
    # 测试文件路径
    test_file = "uploads/e58bcf5e692d_gc.log"
    
    if not os.path.exists(test_file):
        print(f"❌ 测试文件不存在: {test_file}")
        return
    
    # 读取日志文件
    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
        log_content = f.read()
    
    print(f"📁 日志文件大小: {len(log_content)} 字符")
    
    # 创建提取器
    extractor = JVMInfoExtractor()
    
    # 提取JVM信息
    jvm_info = extractor.extract_jvm_info(log_content)
    
    print("\n📊 提取的JVM信息:")
    print("=" * 50)
    
    for key, value in jvm_info.items():
        if value != 'Unknown' and value != 0 and value is not None:
            print(f"✅ {key}: {value}")
        else:
            print(f"❌ {key}: {value}")
    
    print("\n📋 格式化摘要:")
    print("=" * 50)
    summary = extractor.format_jvm_info_summary(jvm_info)
    print(summary)
    
    # 检查关键字段是否提取成功
    success_count = 0
    total_fields = 0
    
    key_fields = ['jvm_version', 'gc_strategy', 'cpu_cores', 'total_memory_mb', 'maximum_heap_mb']
    
    for field in key_fields:
        total_fields += 1
        value = jvm_info.get(field)
        if value and value != 'Unknown' and value != 0:
            success_count += 1
            print(f"✅ {field}: 提取成功")
        else:
            print(f"❌ {field}: 提取失败 ({value})")
    
    success_rate = (success_count / total_fields) * 100
    print(f"\n📈 提取成功率: {success_rate:.1f}% ({success_count}/{total_fields})")
    
    return jvm_info

def test_patterns_manually():
    """手动测试正则表达式模式"""
    print("\n🔍 手动测试正则表达式模式")
    
    # 测试样本
    sample_lines = [
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] Version: 17.0.12+7 (release)",
        "[2025-08-26T15:03:25.848+0800][0.005s][info][gc] Using G1",
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] CPUs: 4 total, 4 available",
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] Memory: 14989M",
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] Heap Initial Capacity: 512M",
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] Heap Max Capacity: 512M",
        "[2025-08-26T15:03:25.855+0800][0.012s][info][gc,init] Parallel Workers: 4"
    ]
    
    import re
    
    patterns = {
        'g1_jvm_version': r'\[info\]\[gc,init\].*Version: (\d+\.\d+\.\d+\+\d+)',
        'g1_gc_strategy': r'\[info\]\[gc\].*Using (\w+)',
        'g1_cpu_info': r'\[info\]\[gc,init\].*CPUs: (\d+) total',
        'g1_memory_info': r'\[info\]\[gc,init\].*Memory: (\d+)M',
        'g1_heap_initial': r'\[info\]\[gc,init\].*Heap Initial Capacity: (\d+)M',
        'g1_heap_max': r'\[info\]\[gc,init\].*Heap Max Capacity: (\d+)M',
        'g1_parallel_workers': r'\[info\]\[gc,init\].*Parallel Workers: (\d+)',
    }
    
    for line in sample_lines:
        print(f"\n测试行: {line}")
        for pattern_name, pattern in patterns.items():
            match = re.search(pattern, line)
            if match:
                print(f"  ✅ {pattern_name}: {match.group(1)}")
            else:
                print(f"  ❌ {pattern_name}: 无匹配")

if __name__ == "__main__":
    print("🔧 JVM信息提取器修复测试")
    print("=" * 60)
    
    # 手动测试正则表达式
    test_patterns_manually()
    
    # 测试完整提取
    test_g1_log_extraction()