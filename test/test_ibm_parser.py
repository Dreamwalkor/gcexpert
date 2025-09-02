#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IBM J9VM GC日志解析器测试用例
使用测试驱动开发（TDD）方法验证功能正确性
"""

import os
import sys
import pytest

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from parser.ibm_parser import J9LogParser, parse_gc_log
from utils.log_loader import LogLoader, GCLogType


class TestJ9LogParser:
    """IBM J9日志解析器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.parser = J9LogParser()
        self.test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.sample_j9_log_path = os.path.join(self.test_data_dir, 'sample_j9.log')
        
        # 加载测试数据
        loader = LogLoader()
        self.log_content, self.log_type = loader.load_log_file(self.sample_j9_log_path)
    
    def test_log_type_detection(self):
        """测试日志类型检测"""
        assert self.log_type == GCLogType.IBM_J9, f"期望检测到IBM J9类型，实际得到: {self.log_type}"
    
    def test_parse_gc_scavenge_count(self):
        """测试Scavenge GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有3次Scavenge GC
        assert result['gc_count']['scavenge'] == 3, f"期望Scavenge GC次数为3，实际得到: {result['gc_count']['scavenge']}"
    
    def test_parse_gc_global_count(self):
        """测试Global GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有1次Global GC
        assert result['gc_count']['global'] == 1, f"期望Global GC次数为1，实际得到: {result['gc_count']['global']}"
    
    def test_parse_gc_concurrent_count(self):
        """测试Concurrent GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，应该有1次Concurrent GC
        assert result['gc_count']['concurrent'] == 1, f"期望Concurrent GC次数为1，实际得到: {result['gc_count']['concurrent']}"
    
    def test_total_gc_count(self):
        """测试总GC次数统计"""
        result = self.parser.parse_gc_log(self.log_content)
        
        expected_total = 5  # 3 scavenge + 1 global + 1 concurrent
        assert result['gc_count']['total'] == expected_total, f"期望总GC次数为{expected_total}，实际得到: {result['gc_count']['total']}"
    
    def test_total_gc_time(self):
        """测试总GC时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        assert result['total_time'] > 0, "总GC时间应该大于0"
        # 按照测试数据计算期望值: 5.123 + 6.789 + 15.456 + 7.234 + 2.567 = 37.169
        expected_total_time = 37.169
        assert abs(result['total_time'] - expected_total_time) < 0.1, f"期望总GC时间约为{expected_total_time}ms，实际得到: {result['total_time']}ms"
    
    def test_average_gc_time(self):
        """测试平均GC时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        assert result['avg_time'] > 0, "平均GC时间应该大于0"
        expected_avg = result['total_time'] / result['gc_count']['total']
        assert abs(result['avg_time'] - expected_avg) < 0.01, f"平均GC时间计算错误"
    
    def test_max_gc_time(self):
        """测试最大GC时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，最大GC时间应该是Global GC的15.456ms
        expected_max = 15.456
        assert abs(result['max_time'] - expected_max) < 0.01, f"期望最大GC时间为{expected_max}ms，实际得到: {result['max_time']}ms"
    
    def test_min_gc_time(self):
        """测试最小GC时间"""
        result = self.parser.parse_gc_log(self.log_content)
        
        # 根据测试数据，最小GC时间应该是Concurrent GC的2.567ms
        expected_min = 2.567
        assert abs(result['min_time'] - expected_min) < 0.01, f"期望最小GC时间为{expected_min}ms，实际得到: {result['min_time']}ms"
    
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
    
    def test_nursery_statistics(self):
        """测试Nursery区域统计信息"""
        result = self.parser.parse_gc_log(self.log_content)
        
        memory_stats = result['memory_stats']
        
        # Nursery统计信息应该存在（只有Scavenge GC才有Nursery信息）
        assert memory_stats['avg_nursery_before'] > 0, "平均Nursery GC前大小应该大于0"
        assert memory_stats['avg_nursery_after'] > 0, "平均Nursery GC后大小应该大于0"
        assert memory_stats['avg_nursery_before'] > memory_stats['avg_nursery_after'], "Nursery GC前平均大小应该大于GC后"
    
    def test_gc_events_extraction(self):
        """测试GC事件提取"""
        result = self.parser.parse_gc_log(self.log_content)
        
        events = result['events']
        assert len(events) == 5, f"期望提取5个GC事件，实际得到: {len(events)}"
        
        # 验证第一个事件的属性
        first_event = events[0]
        assert first_event['gc_type'] == 'scavenge', f"第一个事件应该是scavenge类型，实际得到: {first_event['gc_type']}"
        assert first_event['duration'] == 5.123, f"第一个事件持续时间应该是5.123ms"
        assert first_event['heap_before'] == 1048576, f"第一个事件GC前堆大小应该是1048576字节"
        assert first_event['heap_after'] == 524288, f"第一个事件GC后堆大小应该是524288字节"
        
        # 验证Nursery信息
        assert first_event['nursery_before'] == 262144, f"第一个事件Nursery GC前大小应该是262144字节"
        assert first_event['nursery_after'] == 131072, f"第一个事件Nursery GC后大小应该是131072字节"
    
    def test_trigger_reason_extraction(self):
        """测试GC触发原因提取"""
        result = self.parser.parse_gc_log(self.log_content)
        
        events = result['events']
        
        # 验证触发原因
        scavenge_events = [e for e in events if e['gc_type'] == 'scavenge']
        for event in scavenge_events:
            assert event['trigger_reason'] == 'allocation failure', f"Scavenge GC的触发原因应该是'allocation failure'，实际得到: {event['trigger_reason']}"
        
        global_events = [e for e in events if e['gc_type'] == 'global']
        for event in global_events:
            assert event['trigger_reason'] == 'heap full', f"Global GC的触发原因应该是'heap full'，实际得到: {event['trigger_reason']}"
    
    def test_convenience_function(self):
        """测试便捷函数接口"""
        result = parse_gc_log(self.log_content)
        
        # 便捷函数应该产生相同的结果
        parser_result = self.parser.parse_gc_log(self.log_content)
        
        assert result['gc_count'] == parser_result['gc_count'], "便捷函数和解析器应该产生相同的GC统计结果"
        assert abs(result['total_time'] - parser_result['total_time']) < 0.01, "便捷函数和解析器应该产生相同的GC时间统计"
    
    def test_empty_log_handling(self):
        """测试空日志处理"""
        result = self.parser.parse_gc_log("")
        
        # 空日志应该返回默认值
        assert result['gc_count']['total'] == 0, "空日志的GC总次数应该为0"
        assert result['total_time'] == 0.0, "空日志的总GC时间应该为0"
        assert len(result['events']) == 0, "空日志应该没有事件"
    
    def test_malformed_xml_handling(self):
        """测试格式错误的XML处理"""
        # 这个测试目的是验证空内容或格式错误时的鲁棒性
        malformed_log = """
        <!-- 只有注释，没有有效的GC数据 -->
        """
        
        # 对于无效数据，应该返回空结果而不是报错
        result = self.parser.parse_gc_log(malformed_log)
        
        # 应该返回空结果
        assert result['gc_count']['total'] == 0, "对于无效数据，应该返回空结果"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])