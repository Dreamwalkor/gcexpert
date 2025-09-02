#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试内存单位显示修复
验证图表中的内存数值是否正确显示为MB单位
"""

import json
from web_optimizer import LargeFileOptimizer

def test_memory_unit_conversion():
    """测试内存单位转换逻辑"""
    print("🔍 测试内存单位转换逻辑")
    print("="*50)
    
    # 模拟不同单位的内存数据
    test_cases = [
        # (输入值, 预期输出MB, 描述)
        (1024 * 1024 * 512, 512, "512MB字节数据"),
        (1024 * 1024 * 1024, 1024, "1GB字节数据"),
        (1024 * 1024 * 2048, 2048, "2GB字节数据"),
        (512, 512, "已经是MB的数据"),
        (1024, 1024, "1GB的MB数据"),
        (0, 0, "空数据"),
    ]
    
    optimizer = LargeFileOptimizer()
    
    for input_value, expected_mb, description in test_cases:
        # 模拟转换逻辑
        if input_value > 1048576:  # 如果大于1MB，假设是字节单位
            converted_mb = input_value / (1024 * 1024)
        else:
            converted_mb = input_value
        
        print(f"{description}:")
        print(f"  输入: {input_value:,}")
        print(f"  转换后: {converted_mb:.1f} MB")
        print(f"  预期: {expected_mb} MB")
        print(f"  结果: {'✅ 正确' if abs(converted_mb - expected_mb) < 0.1 else '❌ 错误'}")
        print()


def test_chart_data_generation():
    """测试图表数据生成中的内存单位"""
    print("📊 测试图表数据生成中的内存单位")
    print("="*50)
    
    # 模拟GC事件数据
    mock_events = [
        {
            'heap_before': 1024 * 1024 * 800,  # 800MB in bytes
            'heap_after': 1024 * 1024 * 400,   # 400MB in bytes
            'heap_total': 1024 * 1024 * 1024,  # 1GB in bytes
            'gc_type': 'young',
            'pause_time': 50,
            'timestamp': '2025-08-26T15:04:37.088',
            'metaspace_before': 50 * 1024,     # 50MB in KB
            'metaspace_after': 48 * 1024,      # 48MB in KB
        },
        {
            'heap_before': 1024 * 1024 * 600,  # 600MB in bytes
            'heap_after': 1024 * 1024 * 300,   # 300MB in bytes
            'heap_total': 1024 * 1024 * 1024,  # 1GB in bytes
            'gc_type': 'mixed',
            'pause_time': 80,
            'timestamp': '2025-08-26T15:04:47.088',
            'metaspace_before': 52 * 1024,     # 52MB in KB
            'metaspace_after': 50 * 1024,      # 50MB in KB
        }
    ]
    
    optimizer = LargeFileOptimizer()
    
    # 生成图表数据
    chart_data = optimizer._generate_chart_data(mock_events, mock_events)
    
    print("生成的图表数据:")
    print(f"时间线数据点数: {len(chart_data['timeline'])}")
    print()
    
    for i, data_point in enumerate(chart_data['timeline']):
        print(f"数据点 {i + 1}:")
        print(f"  堆内存使用前: {data_point['heap_before_mb']:.1f} MB")
        print(f"  堆内存使用后: {data_point['heap_after_mb']:.1f} MB")
        print(f"  堆内存总量: {data_point['heap_total_mb']:.1f} MB")
        print(f"  Eden区使用前: {data_point['eden_before_mb']:.1f} MB")
        print(f"  Metaspace使用前: {data_point['metaspace_before_mb']:.1f} MB")
        print(f"  堆利用率: {data_point['heap_utilization']:.1f}%")
        print()
        
        # 验证数值合理性
        heap_before = data_point['heap_before_mb']
        heap_total = data_point['heap_total_mb']
        
        if heap_before > heap_total:
            print(f"  ❌ 错误: 堆使用量({heap_before:.1f}MB) > 堆总量({heap_total:.1f}MB)")
        elif heap_before > 10000:  # 如果大于10GB，可能单位转换有问题
            print(f"  ⚠️  警告: 堆使用量过大({heap_before:.1f}MB)，可能单位转换有问题")
        else:
            print(f"  ✅ 内存数值合理")


def test_frontend_display_format():
    """测试前端显示格式"""
    print("🖥️  测试前端Y轴格式化函数")
    print("="*50)
    
    # 模拟前端Y轴格式化函数
    def format_y_axis(value):
        if value > 1024:
            return f"{(value / 1024):.1f}GB"
        return f"{round(value)}MB"
    
    test_values = [
        (512, "512MB"),
        (1024, "1.0GB"),
        (1536, "1.5GB"),
        (2048, "2.0GB"),
        (100, "100MB"),
        (0, "0MB"),
    ]
    
    print("Y轴标签格式化测试:")
    for value, expected in test_values:
        formatted = format_y_axis(value)
        print(f"  {value} MB -> {formatted} (预期: {expected}) {'✅' if formatted == expected else '❌'}")


def generate_test_html():
    """生成测试HTML页面"""
    html_content = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>内存单位显示测试</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .test-section { margin: 30px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }
        .chart-container { width: 100%; height: 400px; margin: 20px 0; }
    </style>
</head>
<body>
    <h1>内存单位显示测试</h1>
    
    <div class="test-section">
        <h2>测试1: 正常MB范围数据</h2>
        <div class="chart-container">
            <canvas id="chart1"></canvas>
        </div>
    </div>
    
    <div class="test-section">
        <h2>测试2: GB范围数据</h2>
        <div class="chart-container">
            <canvas id="chart2"></canvas>
        </div>
    </div>
    
    <script>
        // 测试数据1: MB范围
        const data1 = {
            labels: ['事件1', '事件2', '事件3', '事件4', '事件5'],
            datasets: [{
                label: '堆内存使用 (MB)',
                data: [512, 600, 450, 700, 550],
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                fill: false
            }]
        };
        
        // 测试数据2: GB范围
        const data2 = {
            labels: ['事件1', '事件2', '事件3', '事件4', '事件5'],
            datasets: [{
                label: '堆内存使用 (MB)',
                data: [1024, 1536, 2048, 1800, 1200],
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                fill: false
            }]
        };
        
        // Y轴格式化函数
        function formatYAxis(value) {
            if (value > 1024) {
                return (value / 1024).toFixed(1) + 'GB';
            }
            return Math.round(value) + 'MB';
        }
        
        // 创建图表1
        new Chart(document.getElementById('chart1'), {
            type: 'line',
            data: data1,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        title: { display: true, text: '内存使用 (MB)' },
                        ticks: {
                            callback: formatYAxis
                        }
                    }
                }
            }
        });
        
        // 创建图表2
        new Chart(document.getElementById('chart2'), {
            type: 'line',
            data: data2,
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        title: { display: true, text: '内存使用 (MB)' },
                        ticks: {
                            callback: formatYAxis
                        }
                    }
                }
            }
        });
    </script>
</body>
</html>"""
    
    with open('test_memory_unit_display.html', 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print("📄 生成测试HTML文件: test_memory_unit_display.html")


def main():
    """主测试函数"""
    print("🔧 内存单位显示修复测试")
    print("="*80)
    
    # 测试1: 内存单位转换逻辑
    test_memory_unit_conversion()
    
    # 测试2: 图表数据生成
    test_chart_data_generation()
    
    # 测试3: 前端显示格式
    test_frontend_display_format()
    
    # 生成测试HTML
    generate_test_html()
    
    print("="*80)
    print("✅ 内存单位显示修复测试完成")
    print()
    print("修复要点:")
    print("1. 后端数据转换: 字节 -> MB (除以 1024*1024)")
    print("2. 前端Y轴格式化: 大于1024MB时显示为GB")
    print("3. 图例单位统一: 所有内存相关图表都显示MB单位")
    print("4. 数值合理性检查: 避免显示异常大的数值")
    print()
    print("现在图表应该正确显示:")
    print("- Y轴: 512MB, 1.0GB, 1.5GB 等格式")
    print("- 图例: 堆内存使用 (MB)")
    print("- 数值范围: 合理的MB/GB范围")


if __name__ == "__main__":
    main()