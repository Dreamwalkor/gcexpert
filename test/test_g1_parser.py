#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G1 GC日志解析器测试用例
使用测试驱动开发（TDD）方法验证功能正确性
"""

import os
import sys
import pytest

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from parser.g1_parser import G1LogParser, parse_gc_log
from utils.log_loader import LogLoader, GCLogType


class TestG1LogParser:
    """G1日志解析器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.parser = G1LogParser()
        self.test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.sample_g1_log_path = os.path.join(self.test_data_dir, 'sample_g1.log')
        
        # 加载测试数据
        loader = LogLoader()
        self.log_content, self.log_type = loader.load_log_file(self.sample_g1_log_path)
    
    def test_log_type_detection(self):
        """测试日志类型检测"""
        assert self.log_type == GCLogType.G1, f"期望检测到G1类型，实际得到: {self.log_type}"
    
    def test_parse_gc_young_count(self):
        """测试Young GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有4次Young GC
        assert result['gc_count']['young'] == 4, f"期望Young GC次数为4，实际得到: {result['gc_count']['young']}"
        assert result['gc_count']['young'] >= 1, "Young GC次数应该大于等于1"
    
    def test_parse_gc_mixed_count(self):
        """测试Mixed GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有2次Mixed GC
        assert result['gc_count']['mixed'] == 2, f"期望Mixed GC次数为2，实际得到: {result['gc_count']['mixed']}"
    
    def test_parse_gc_full_count(self):
        """测试Full GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有1次Full GC
        assert result['gc_count']['full'] == 1, f"期望Full GC次数为1，实际得到: {result['gc_count']['full']}"
    
    def test_total_gc_count(self):
        """测试总GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        expected_total = 7  # 4 young + 2 mixed + 1 full
        assert result['gc_count']['total'] == expected_total, f"期望总GC次数为{expected_total}，实际得到: {result['gc_count']['total']}"
    
    def test_total_pause_time(self):
        """测试总暂停时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        assert result['total_pause'] > 0, "总暂停时间应该大于0"
        # 按照测试数据计算期望值: 15.234 + 12.567 + 25.678 + 18.901 + 32.123 + 150.456 + 14.789 = 269.748
        expected_total_pause = 269.748
        assert abs(result['total_pause'] - expected_total_pause) < 0.1, f"期望总暂停时间约为{expected_total_pause}ms，实际得到: {result['total_pause']}ms"
    
    def test_average_pause_time(self):
        """测试平均暂停时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        assert result['avg_pause'] > 0, "平均暂停时间应该大于0"
        expected_avg = result['total_pause'] / result['gc_count']['total']
        assert abs(result['avg_pause'] - expected_avg) < 0.01, f"平均暂停时间计算错误"
    
    def test_max_pause_time(self):
        """测试最大暂停时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，最大暂停时间应该是Full GC的150.456ms
        expected_max = 150.456
        assert abs(result['max_pause'] - expected_max) < 0.01, f"期望最大暂停时间为{expected_max}ms，实际得到: {result['max_pause']}ms"
    
    def test_min_pause_time(self):
        """测试最小暂停时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，最小暂停时间应该是12.567ms
        expected_min = 12.567
        assert abs(result['min_pause'] - expected_min) < 0.01, f"期望最小暂停时间为{expected_min}ms，实际得到: {result['min_pause']}ms"
    
    def test_memory_statistics(self):
        """测试内存统计信息"""
        result = self.parser.parse_gc_log(self.log_content)
        
        memory_stats = result['memory_stats']
        
        # 验证内存统计数据的合理性
        assert memory_stats['avg_heap_before'] > 0, "平均GC前堆大小应该大于0"
        assert memory_stats['avg_heap_after'] > 0, "平均GC后堆大小应该大于0"
        assert memory_stats['avg_heap_before'] > memory_stats['avg_heap_after'], "GC前平均堆大小应该大于GC后"
        assert memory_stats['max_heap_used'] > 0, "最大堆使用量应该大于0"
        assert memory_stats['total_reclaimed'] > 0, "总回收内存应该大于0"
    
    def test_gc_events_extraction(self):
        """测试GC事件提取"""
        result = self.parser.parse_gc_log(self.log_content)
        
        events = result['events']
        assert len(events) == 7, f"期望提取7个GC事件，实际得到: {len(events)}"
        
        # 验证第一个事件的属性
        first_event = events[0]
        assert first_event['gc_type'] == 'young', f"第一个事件应该是young类型，实际得到: {first_event['gc_type']}"
        assert first_event['pause_time'] == 15.234, f"第一个事件暂停时间应该是15.234ms"
        assert first_event['heap_before'] == 512, f"第一个事件GC前堆大小应该是512MB"
        assert first_event['heap_after'] == 256, f"第一个事件GC后堆大小应该是256MB"
    
    def test_convenience_function(self):
        """测试便捷函数接口"""
        result = parse_gc_log(self.log_content)
        
        # 便捷函数应该产生相同的结果
        parser_result = self.parser.parse_gc_log(self.log_content)
        
        assert result['gc_count'] == parser_result['gc_count'], "便捷函数和解析器应该产生相同的GC统计结果"
        assert abs(result['total_pause'] - parser_result['total_pause']) < 0.01, "便捷函数和解析器应该产生相同的暂停时间统计"
    
    def test_empty_log_handling(self):
        """测试空日志处理"""
        result = self.parser.parse_gc_log("")
        
        # 空日志应该返回默认值
        assert result['gc_count']['total'] == 0, "空日志的GC总次数应该为0"
        assert result['total_pause'] == 0.0, "空日志的总暂停时间应该为0"
        assert len(result['events']) == 0, "空日志应该没有事件"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])
