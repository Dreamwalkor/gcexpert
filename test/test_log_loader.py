#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志加载器测试用例
使用测试驱动开发（TDD）方法验证功能正确性
"""

import os
import sys
import pytest

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from utils.log_loader import LogLoader, GCLogType, load_gc_log, detect_log_type


class TestLogLoader:
    """日志加载器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.loader = LogLoader()
        self.test_data_dir = os.path.join(os.path.dirname(__file__), 'data')
        self.sample_g1_log_path = os.path.join(self.test_data_dir, 'sample_g1.log')
        self.sample_j9_log_path = os.path.join(self.test_data_dir, 'sample_j9.log')
    
    def test_g1_log_type_detection(self):
        """测试G1日志类型检测"""
        content, log_type = self.loader.load_log_file(self.sample_g1_log_path)
        
        assert log_type == GCLogType.G1, f"期望检测到G1类型，实际得到: {log_type}"
    
    def test_j9_log_type_detection(self):
        """测试J9日志类型检测"""
        content, log_type = self.loader.load_log_file(self.sample_j9_log_path)
        
        assert log_type == GCLogType.IBM_J9, f"期望检测到IBM J9类型，实际得到: {log_type}"
    
    def test_load_g1_log_file(self):
        """测试加载G1日志文件"""
        content, log_type = self.loader.load_log_file(self.sample_g1_log_path)
        
        assert len(content) > 0, "日志内容不应该为空"
        assert log_type == GCLogType.G1, "应该检测到G1日志类型"
        assert "[GC pause" in content, "应该包含G1 GC特征字符串"
    
    def test_load_j9_log_file(self):
        """测试加载J9日志文件"""
        content, log_type = self.loader.load_log_file(self.sample_j9_log_path)
        
        assert len(content) > 0, "日志内容不应该为空"
        assert log_type == GCLogType.IBM_J9, "应该检测到IBM J9日志类型"
        assert '<gc type=' in content, "应该包含J9 GC特征字符串"
    
    def test_file_not_found_error(self):
        """测试文件不存在错误处理"""
        non_existent_file = "/path/that/does/not/exist.log"
        
        with pytest.raises(FileNotFoundError):
            self.loader.load_log_file(non_existent_file)
    
    def test_detect_g1_log_type(self):
        """测试G1日志类型检测"""
        g1_content = """
        2024-01-01T10:00:01.123: [GC pause (G1 Evacuation Pause) (young) 15.234 ms]
        """
        log_type = self.loader.detect_log_type(g1_content)
        
        assert log_type == GCLogType.G1, f"期望检测到G1类型，实际得到: {log_type}"
    
    def test_detect_j9_log_type(self):
        """测试J9日志类型检测"""
        j9_content = """
        <gc type="scavenge" id="1" totalTime="5.123">
        <mem-info before="1000" after="500" total="2000" />
        </gc>
        """
        log_type = self.loader.detect_log_type(j9_content)
        
        assert log_type == GCLogType.IBM_J9, f"期望检测到IBM J9类型，实际得到: {log_type}"
    
    def test_detect_unknown_log_type(self):
        """测试未知日志类型检测"""
        unknown_content = """
        This is not a GC log at all.
        Just some random text.
        """
        log_type = self.loader.detect_log_type(unknown_content)
        
        assert log_type == GCLogType.UNKNOWN, f"期望检测到UNKNOWN类型，实际得到: {log_type}"
    
    def test_preprocess_g1_log(self):
        """测试G1日志预处理"""
        raw_content = """
        
        2024-01-01T10:00:01.123: [GC pause (G1 Evacuation Pause) (young)  15.234 ms]   512M->256M(1024M)
        
        2024-01-01T10:00:05.456: [GC pause (G1 Evacuation Pause) (young)  12.567 ms]   600M->300M(1024M)
        
        """
        
        processed = self.loader.preprocess_log(raw_content, GCLogType.G1)
        lines = processed.split('\n')
        
        # 应该移除空行和多余空格
        assert all(line.strip() for line in lines), "不应该有空行"
        assert "  " not in processed, "不应该有多余的空格"
    
    def test_preprocess_j9_log(self):
        """测试J9日志预处理"""
        raw_content = """
        
        <gc type="scavenge" id="1" totalTime="5.123">
        <mem-info before="1000" after="500" total="2000" />
        </gc>
        
        """
        
        processed = self.loader.preprocess_log(raw_content, GCLogType.IBM_J9)
        lines = [line for line in processed.split('\n') if line.strip()]
        
        # 应该移除空行
        assert len(lines) > 0, "应该有处理后的内容"
        assert all(line.strip() for line in processed.split('\n') if line), "不应该有空行"
    
    def test_get_log_summary_g1(self):
        """测试G1日志概要信息"""
        content, _ = self.loader.load_log_file(self.sample_g1_log_path)
        summary = self.loader.get_log_summary(content, GCLogType.G1)
        
        assert summary['log_type'] == 'g1', "日志类型应该是g1"
        assert summary['total_lines'] > 0, "总行数应该大于0"
        assert summary['file_size_bytes'] > 0, "文件大小应该大于0"
        assert summary['estimated_gc_events'] > 0, "预估GC事件数应该大于0"
    
    def test_get_log_summary_j9(self):
        """测试J9日志概要信息"""
        content, _ = self.loader.load_log_file(self.sample_j9_log_path)
        summary = self.loader.get_log_summary(content, GCLogType.IBM_J9)
        
        assert summary['log_type'] == 'ibm_j9', "日志类型应该是ibm_j9"
        assert summary['total_lines'] > 0, "总行数应该大于0"
        assert summary['file_size_bytes'] > 0, "文件大小应该大于0"
        assert summary['estimated_gc_events'] > 0, "预估GC事件数应该大于0"
    
    def test_convenience_functions(self):
        """测试便捷函数"""
        # 测试load_gc_log便捷函数
        content, log_type = load_gc_log(self.sample_g1_log_path)
        assert len(content) > 0, "日志内容不应该为空"
        assert log_type == GCLogType.G1, "应该检测到G1日志类型"
        
        # 测试detect_log_type便捷函数
        g1_content = "[GC pause (G1 Evacuation Pause) (young) 15.234 ms]"
        detected_type = detect_log_type(g1_content)
        assert detected_type == GCLogType.G1, "应该检测到G1日志类型"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])