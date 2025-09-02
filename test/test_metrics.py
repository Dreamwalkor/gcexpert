#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC性能指标分析器测试用例
使用测试驱动开发（TDD）方法验证功能正确性
"""

import os
import sys
import pytest

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from analyzer.metrics import GCMetricsAnalyzer, GCMetrics, analyze_gc_metrics
from parser.g1_parser import parse_gc_log as parse_g1_log
from parser.ibm_parser import parse_gc_log as parse_j9_log
from utils.log_loader import LogLoader


class TestGCMetricsAnalyzer:
    """GC性能指标分析器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.analyzer = GCMetricsAnalyzer()
        
        # 准备测试数据
        self.sample_events = [
            {
                'gc_type': 'young', 'pause_time': 15.5, 'timestamp': 1.0,
                'heap_before': 512, 'heap_after': 256, 'heap_total': 1024
            },
            {
                'gc_type': 'young', 'pause_time': 12.3, 'timestamp': 3.0,
                'heap_before': 600, 'heap_after': 300, 'heap_total': 1024
            },
            {
                'gc_type': 'mixed', 'pause_time': 25.8, 'timestamp': 6.0,
                'heap_before': 800, 'heap_after': 400, 'heap_total': 1024
            },
            {
                'gc_type': 'full', 'pause_time': 150.0, 'timestamp': 10.0,
                'heap_before': 900, 'heap_after': 200, 'heap_total': 1024
            }
        ]
        
        # 高性能事件（优秀案例）
        self.excellent_events = [
            {
                'gc_type': 'young', 'pause_time': 5.0, 'timestamp': 1.0,
                'heap_before': 300, 'heap_after': 100, 'heap_total': 1024
            },
            {
                'gc_type': 'young', 'pause_time': 7.0, 'timestamp': 10.0,
                'heap_before': 400, 'heap_after': 150, 'heap_total': 1024
            }
        ]
        
        # 低性能事件（严重案例）
        self.critical_events = [
            {
                'gc_type': 'full', 'pause_time': 800.0, 'timestamp': 1.0,
                'heap_before': 1000, 'heap_after': 500, 'heap_total': 1024
            },
            {
                'gc_type': 'full', 'pause_time': 900.0, 'timestamp': 2.0,
                'heap_before': 1000, 'heap_after': 600, 'heap_total': 1024
            },
            {
                'gc_type': 'full', 'pause_time': 1000.0, 'timestamp': 3.0,
                'heap_before': 1000, 'heap_after': 700, 'heap_total': 1024
            }
        ]
    
    def test_empty_events_handling(self):
        """测试空事件列表的处理"""
        metrics = self.analyzer.analyze([])
        
        assert metrics.throughput_percentage == 0.0, "空事件的吞吐量应该为0"
        assert metrics.performance_score == 0.0, "空事件的性能评分应该为0"
        assert metrics.health_status == 'unknown', "空事件的健康状态应该为unknown"
        assert metrics.gc_frequency == 0.0, "空事件的GC频率应该为0"
    
    def test_throughput_calculation(self):
        """测试吞吐量计算"""
        # 使用固定时间窗口进行测试
        time_window = 10.0  # 10秒
        metrics = self.analyzer.analyze(self.sample_events, time_window)
        
        # 验证吞吐量计算
        assert metrics.throughput_percentage > 0, "吞吐量应该大于0"
        assert metrics.throughput_percentage <= 100, "吞吐量不应该超过100%"
        assert metrics.gc_overhead_percentage >= 0, "GC开销应该非负"
        assert metrics.gc_overhead_percentage <= 100, "GC开销不应该超过100%"
        
        # 验证吞吐量和开销的关系
        total_percentage = metrics.throughput_percentage + metrics.gc_overhead_percentage
        assert abs(total_percentage - 100.0) < 0.1, f"吞吐量和开销之和应该约等于100%，实际为{total_percentage}"
    
    def test_latency_metrics_calculation(self):
        """测试延迟指标计算"""
        metrics = self.analyzer.analyze(self.sample_events)
        
        # 验证基本延迟统计
        assert metrics.avg_pause_time > 0, "平均停顿时间应该大于0"
        assert metrics.max_pause_time >= metrics.avg_pause_time, "最大停顿时间应该不小于平均停顿时间"
        assert metrics.min_pause_time <= metrics.avg_pause_time, "最小停顿时间应该不大于平均停顿时间"
        
        # 验证百分位数的顺序关系
        assert metrics.p50_pause_time <= metrics.p95_pause_time, "P50应该不大于P95"
        assert metrics.p95_pause_time <= metrics.p99_pause_time, "P95应该不大于P99"
        assert metrics.p99_pause_time <= metrics.max_pause_time, "P99应该不大于最大值"
        
        # 根据测试数据验证具体值
        expected_max = 150.0  # 测试数据中的最大停顿时间
        assert abs(metrics.max_pause_time - expected_max) < 0.1, f"最大停顿时间应该为{expected_max}ms"
        
        expected_min = 12.3  # 测试数据中的最小停顿时间
        assert abs(metrics.min_pause_time - expected_min) < 0.1, f"最小停顿时间应该为{expected_min}ms"
    
    def test_frequency_metrics_calculation(self):
        """测试频率指标计算"""
        time_window = 10.0  # 10秒时间窗口
        metrics = self.analyzer.analyze(self.sample_events, time_window)
        
        # 验证总体频率
        expected_total_freq = len(self.sample_events) / time_window
        assert abs(metrics.gc_frequency - expected_total_freq) < 0.01, f"总GC频率应该为{expected_total_freq}"
        
        # 验证Young GC频率
        young_count = len([e for e in self.sample_events if e['gc_type'] == 'young'])
        expected_young_freq = young_count / time_window
        assert abs(metrics.young_gc_frequency - expected_young_freq) < 0.01, f"Young GC频率应该为{expected_young_freq}"
        
        # 验证Full GC频率
        full_count = len([e for e in self.sample_events if e['gc_type'] == 'full'])
        expected_full_freq = full_count / time_window
        assert abs(metrics.full_gc_frequency - expected_full_freq) < 0.01, f"Full GC频率应该为{expected_full_freq}"
    
    def test_memory_metrics_calculation(self):
        """测试内存指标计算"""
        metrics = self.analyzer.analyze(self.sample_events)
        
        # 验证内存利用率
        assert 0 <= metrics.avg_heap_utilization <= 100, "平均堆利用率应该在0-100%之间"
        assert 0 <= metrics.max_heap_utilization <= 100, "最大堆利用率应该在0-100%之间"
        assert metrics.max_heap_utilization >= metrics.avg_heap_utilization, "最大利用率应该不小于平均利用率"
        
        # 验证内存分配和回收指标
        assert metrics.memory_allocation_rate >= 0, "内存分配率应该非负"
        assert 0 <= metrics.memory_reclaim_efficiency <= 100, "内存回收效率应该在0-100%之间"
    
    def test_trend_analysis(self):
        """测试趋势分析"""
        # 测试递增趋势
        increasing_events = [
            {'gc_type': 'young', 'pause_time': 10.0, 'timestamp': 1.0, 'heap_before': 100, 'heap_after': 50, 'heap_total': 1024},
            {'gc_type': 'young', 'pause_time': 20.0, 'timestamp': 2.0, 'heap_before': 200, 'heap_after': 100, 'heap_total': 1024},
            {'gc_type': 'young', 'pause_time': 30.0, 'timestamp': 3.0, 'heap_before': 300, 'heap_after': 150, 'heap_total': 1024},
            {'gc_type': 'young', 'pause_time': 40.0, 'timestamp': 4.0, 'heap_before': 400, 'heap_after': 200, 'heap_total': 1024}
        ]
        
        metrics = self.analyzer.analyze(increasing_events)
        assert metrics.pause_time_trend == 'increasing', f"停顿时间趋势应该为increasing，实际为{metrics.pause_time_trend}"
        assert metrics.memory_usage_trend == 'increasing', f"内存使用趋势应该为increasing，实际为{metrics.memory_usage_trend}"
        
        # 测试稳定趋势
        stable_events = [
            {'gc_type': 'young', 'pause_time': 15.0, 'timestamp': i, 'heap_before': 500, 'heap_after': 250, 'heap_total': 1024}
            for i in range(1, 6)
        ]
        
        metrics = self.analyzer.analyze(stable_events)
        assert metrics.pause_time_trend == 'stable', f"停顿时间趋势应该为stable，实际为{metrics.pause_time_trend}"
    
    def test_performance_score_calculation(self):
        """测试性能评分计算"""
        # 测试优秀性能
        excellent_metrics = self.analyzer.analyze(self.excellent_events)
        assert excellent_metrics.performance_score >= 90, f"优秀性能的评分应该>=90，实际为{excellent_metrics.performance_score}"
        assert excellent_metrics.health_status == 'excellent', f"健康状态应该为excellent"
        
        # 测试严重性能问题
        critical_metrics = self.analyzer.analyze(self.critical_events)
        assert critical_metrics.performance_score <= 50, f"严重性能问题的评分应该<=50，实际为{critical_metrics.performance_score}"
        assert critical_metrics.health_status == 'critical', f"健康状态应该为critical"
    
    def test_health_status_determination(self):
        """测试健康状态判定"""
        # 测试各种健康状态
        test_cases = [
            (self.excellent_events, 'excellent'),
            (self.sample_events, ['good', 'warning']),  # 可能是good或warning
            (self.critical_events, 'critical')
        ]
        
        for events, expected_status in test_cases:
            metrics = self.analyzer.analyze(events)
            if isinstance(expected_status, list):
                assert metrics.health_status in expected_status, f"健康状态应该在{expected_status}中，实际为{metrics.health_status}"
            else:
                assert metrics.health_status == expected_status, f"健康状态应该为{expected_status}，实际为{metrics.health_status}"
    
    def test_convenience_function(self):
        """测试便捷函数"""
        # 测试便捷函数是否与分析器产生相同结果
        analyzer_result = self.analyzer.analyze(self.sample_events)
        function_result = analyze_gc_metrics(self.sample_events)
        
        assert analyzer_result.throughput_percentage == function_result.throughput_percentage, "便捷函数应该产生相同的吞吐量结果"
        assert analyzer_result.performance_score == function_result.performance_score, "便捷函数应该产生相同的性能评分"
        assert analyzer_result.health_status == function_result.health_status, "便捷函数应该产生相同的健康状态"
    
    def test_integration_with_g1_parser(self):
        """测试与G1解析器的集成"""
        # 加载G1测试数据
        test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        sample_g1_log_path = os.path.join(test_data_dir, 'sample_g1.log')
        
        loader = LogLoader()
        log_content, _ = loader.load_log_file(sample_g1_log_path)
        
        # 解析G1日志
        g1_result = parse_g1_log(log_content)
        g1_events = g1_result['events']
        
        # 分析性能指标
        metrics = self.analyzer.analyze(g1_events)
        
        # 验证结果合理性
        assert metrics.throughput_percentage > 0, "G1日志的吞吐量应该大于0"
        assert metrics.performance_score > 0, "G1日志的性能评分应该大于0"
        assert metrics.health_status in ['excellent', 'good', 'warning', 'critical'], "健康状态应该是有效值"
        
        # 验证GC类型统计
        assert metrics.young_gc_frequency >= 0, "Young GC频率应该非负"
        assert metrics.full_gc_frequency >= 0, "Full GC频率应该非负"
    
    def test_integration_with_j9_parser(self):
        """测试与J9解析器的集成"""
        # 加载J9测试数据
        test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        sample_j9_log_path = os.path.join(test_data_dir, 'sample_j9.log')
        
        loader = LogLoader()
        log_content, _ = loader.load_log_file(sample_j9_log_path)
        
        # 解析J9日志
        j9_result = parse_j9_log(log_content)
        j9_events = j9_result['events']
        
        # 分析性能指标
        metrics = self.analyzer.analyze(j9_events)
        
        # 验证结果合理性
        assert metrics.throughput_percentage > 0, "J9日志的吞吐量应该大于0"
        assert metrics.performance_score > 0, "J9日志的性能评分应该大于0"
        assert metrics.health_status in ['excellent', 'good', 'warning', 'critical'], "健康状态应该是有效值"
    
    def test_custom_time_window(self):
        """测试自定义时间窗口"""
        # 测试不同的时间窗口设置
        time_windows = [5.0, 10.0, 30.0]
        
        for time_window in time_windows:
            metrics = self.analyzer.analyze(self.sample_events, time_window)
            
            # 验证频率计算随时间窗口变化
            expected_freq = len(self.sample_events) / time_window
            assert abs(metrics.gc_frequency - expected_freq) < 0.01, f"时间窗口{time_window}s的频率计算错误"
    
    def test_percentile_calculation(self):
        """测试百分位数计算"""
        # 使用已知数据测试百分位数计算
        test_data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
        
        p50 = self.analyzer._percentile(test_data, 50)
        assert abs(p50 - 5.5) < 0.1, f"P50应该约为5.5，实际为{p50}"
        
        p95 = self.analyzer._percentile(test_data, 95)
        assert abs(p95 - 9.55) < 0.1, f"P95应该约为9.55，实际为{p95}"
        
        p99 = self.analyzer._percentile(test_data, 99)
        assert abs(p99 - 9.91) < 0.1, f"P99应该约为9.91，实际为{p99}"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])