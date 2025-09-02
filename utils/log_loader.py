#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志加载工具
提供日志文件加载、预处理和格式检测功能
"""

import os
import re
from typing import Optional, Tuple
from enum import Enum


class GCLogType(Enum):
    """GC日志类型枚举"""
    G1 = "g1"
    IBM_J9 = "ibm_j9"
    UNKNOWN = "unknown"


class LogLoader:
    """GC日志加载器"""
    
    def __init__(self):
        # G1日志特征模式
        self.g1_patterns = [
            re.compile(r'\[GC pause.*\(young\)'),
            re.compile(r'\[GC pause.*\(mixed\)'),
            re.compile(r'G1\s+Evacuation\s+Pause'),
            re.compile(r'\[G1.*\]')
        ]
        
        # IBM J9日志特征模式
        self.j9_patterns = [
            re.compile(r'<gc\s+type="'),
            re.compile(r'<mem-info'),
            re.compile(r'<nursery'),
            re.compile(r'<allocation-request')
        ]
    
    def load_log_file(self, file_path: str) -> Tuple[str, GCLogType]:
        """
        加载GC日志文件
        
        Args:
            file_path: 日志文件路径
            
        Returns:
            元组：(日志内容, 日志类型)
            
        Raises:
            FileNotFoundError: 文件不存在
            IOError: 文件读取错误
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"日志文件不存在: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            raise IOError(f"读取日志文件失败: {e}")
        
        log_type = self.detect_log_type(content)
        processed_content = self.preprocess_log(content, log_type)
        
        return processed_content, log_type
    
    def detect_log_type(self, log_content: str) -> GCLogType:
        """
        检测日志类型
        
        Args:
            log_content: 日志内容
            
        Returns:
            日志类型
        """
        # 检测G1特征
        g1_score = 0
        for pattern in self.g1_patterns:
            if pattern.search(log_content):
                g1_score += 1
        
        # 检测IBM J9特征
        j9_score = 0
        for pattern in self.j9_patterns:
            if pattern.search(log_content):
                j9_score += 1
        
        # 根据识别分数判定类型
        if g1_score > 0 and g1_score >= j9_score:
            return GCLogType.G1
        elif j9_score > 0:
            return GCLogType.IBM_J9
        else:
            return GCLogType.UNKNOWN
    
    def preprocess_log(self, log_content: str, log_type: GCLogType) -> str:
        """
        预处理日志内容
        
        Args:
            log_content: 原始日志内容
            log_type: 日志类型
            
        Returns:
            预处理后的日志内容
        """
        # 移除空行和多余空格
        lines = log_content.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line:  # 跳过空行
                # 统一空格分隔符
                line = re.sub(r'\s+', ' ', line)
                cleaned_lines.append(line)
        
        processed_content = '\n'.join(cleaned_lines)
        
        # 按类型进行特定预处理
        if log_type == GCLogType.G1:
            processed_content = self._preprocess_g1_log(processed_content)
        elif log_type == GCLogType.IBM_J9:
            processed_content = self._preprocess_j9_log(processed_content)
        
        return processed_content
    
    def _preprocess_g1_log(self, content: str) -> str:
        """预处理G1日志"""
        # G1日志特定的预处理逻辑
        # 保持原始的行结构，不进行合并
        return content
    
    def _preprocess_j9_log(self, content: str) -> str:
        """预处理IBM J9日志"""
        # IBM J9日志特定的预处理逻辑
        # 主要是确保XML格式的正确性
        
        # 修复可能的XML格式问题
        content = re.sub(r'<(\w+)([^>]*)(?<!/)>', r'<\1\2>', content)  # 确保标签格式
        
        return content
    
    def get_log_summary(self, log_content: str, log_type: GCLogType) -> dict:
        """
        获取日志概要信息
        
        Args:
            log_content: 日志内容
            log_type: 日志类型
            
        Returns:
            日志概要信息
        """
        lines = log_content.split('\n')
        non_empty_lines = [line for line in lines if line.strip()]
        
        summary = {
            'log_type': log_type.value,
            'total_lines': len(non_empty_lines),
            'file_size_bytes': len(log_content.encode('utf-8')),
            'estimated_gc_events': 0
        }
        
        # 估算GC事件数量
        if log_type == GCLogType.G1:
            summary['estimated_gc_events'] = len([line for line in lines if '[GC pause' in line])
        elif log_type == GCLogType.IBM_J9:
            summary['estimated_gc_events'] = len([line for line in lines if '<gc type=' in line])
        
        return summary


# 便捷函数
def load_gc_log(file_path: str) -> Tuple[str, GCLogType]:
    """加载GC日志文件的便捷函数"""
    loader = LogLoader()
    return loader.load_log_file(file_path)


def detect_log_type(log_content: str) -> GCLogType:
    """检测日志类型的便捷函数"""
    loader = LogLoader()
    return loader.detect_log_type(log_content)


if __name__ == '__main__':
    # 简单的测试代码
    sample_g1_log = """
2024-01-01T10:00:01.123: [GC pause (G1 Evacuation Pause) (young) 15.234 ms] 512M->256M(1024M)
"""
    
    sample_j9_log = """
<gc type="scavenge" id="1" totalTime="5.123" timestamp="2024-01-01T10:00:01.123">
<mem-info before="1048576" after="524288" total="2097152" />
</gc>
"""
    
    print(f"G1日志类型: {detect_log_type(sample_g1_log)}")
    print(f"J9日志类型: {detect_log_type(sample_j9_log)}")