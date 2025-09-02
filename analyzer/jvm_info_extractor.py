#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JVM环境信息提取器
从GC日志中提取JVM版本、GC策略、内存配置等环境信息
"""

import re
from typing import Dict, Optional, List
from datetime import datetime


class JVMInfoExtractor:
    """JVM环境信息提取器"""
    
    def __init__(self):
        # 各种日志格式的正则表达式
        self.patterns = {
            # G1GC 日志模式 - 更新以匹配实际日志格式
            'g1_jvm_version': r'\[info\]\[gc,init\].*Version: (\d+\.\d+\.\d+\+\d+)',
            'g1_gc_strategy': r'\[info\]\[gc\].*Using (\w+)',
            'g1_cpu_info': r'\[info\]\[gc,init\].*CPUs: (\d+) total',
            'g1_memory_info': r'\[info\]\[gc,init\].*Memory: (\d+)M',
            'g1_heap_initial': r'\[info\]\[gc,init\].*Heap Initial Capacity: (\d+)M',
            'g1_heap_max': r'\[info\]\[gc,init\].*Heap Max Capacity: (\d+)M',
            'g1_heap_min': r'\[info\]\[gc,init\].*Heap Min Capacity: (\d+)M',
            'g1_parallel_workers': r'\[info\]\[gc,init\].*Parallel Workers: (\d+)',
            
            # IBM J9 日志模式 - 增强版
            'j9_jvm_version': r'IBM J9 VM version ([^"\s]+)',
            'j9_jvm_build': r'JRE (\d+\.\d+\.\d+) IBM J9 ([^\s]+)',
            'j9_gc_strategy': r'GC mode class sharing is (\w+)',
            'j9_gc_policy': r'<attribute name="gcPolicy" value="([^"]+)"/>',
            'j9_heap_info': r'-Xms(\d+[mMgG]?).*-Xmx(\d+[mMgG]?)',
            'j9_max_heap_size': r'<attribute name="maxHeapSize" value="(\d+)"/>',
            'j9_initial_heap_size': r'<attribute name="initialHeapSize" value="(\d+)"/>',
            'j9_cpu_count': r'<attribute name="physicalMemory" value="(\d+)"/>',
            'j9_physical_memory': r'<attribute name="physicalMemory" value="(\d+)"/>',
            'j9_processor_info': r'<attribute name="numberOfCPUs" value="(\d+)"/>',
            'j9_gc_threads': r'<attribute name="gcthreads" value="(\d+)"/>',
            
            # 通用时间戳模式
            'timestamp_g1': r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\+\d{4}\]',
            'timestamp_j9': r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)',
            'timestamp_relative': r'\[(\d+\.\d+)s\]'
        }
    
    def extract_jvm_info(self, log_content: str, events: Optional[List[Dict]] = None) -> Dict:
        """
        从日志内容中提取JVM环境信息
        
        Args:
            log_content: GC日志内容
            events: 解析后的GC事件列表（可选，用于计算运行时长）
            
        Returns:
            JVM环境信息字典
        """
        jvm_info = {
            'jvm_version': None,
            'gc_strategy': None,
            'cpu_cores': None,
            'total_memory_mb': None,
            'initial_heap_mb': None,
            'maximum_heap_mb': None,
            'runtime_duration_seconds': None,
            'log_format': 'unknown',
            'gc_log_start_time': None,
            'gc_log_end_time': None,
            'total_gc_events': 0,
            # G1GC特有字段
            'parallel_workers': None,
            'heap_region_size': None,
            'heap_min_capacity_mb': None,
            # IBM J9特有字段
            'gc_threads': None,
            'gc_policy': None
        }
        
        # 检测日志格式
        log_format = self._detect_log_format(log_content)
        jvm_info['log_format'] = log_format
        
        # 提取JVM版本信息
        self._extract_version_info(log_content, jvm_info, log_format)
        
        # 提取GC策略信息
        self._extract_gc_strategy(log_content, jvm_info, log_format)
        
        # 提取硬件和内存信息
        self._extract_hardware_info(log_content, jvm_info, log_format)
        
        # 计算运行时长
        if events:
            self._calculate_runtime_from_events(events, jvm_info)
        else:
            self._calculate_runtime_from_log(log_content, jvm_info)
        
        # 统计GC事件数量
        if events:
            jvm_info['total_gc_events'] = len(events)
        else:
            jvm_info['total_gc_events'] = self._count_gc_events(log_content)
        
        return jvm_info
    
    def _detect_log_format(self, log_content: str) -> str:
        """检测日志格式"""
        if '[info][gc,init]' in log_content or '[gc,init]' in log_content:
            return 'g1gc'
        elif 'IBM J9 VM' in log_content or 'J9VM' in log_content or '<verbosegc' in log_content:
            return 'j9vm'
        elif 'OpenJDK' in log_content or 'HotSpot' in log_content:
            return 'hotspot'
        else:
            return 'unknown'
    
    def _extract_version_info(self, log_content: str, jvm_info: Dict, log_format: str):
        """提取JVM版本信息"""
        if log_format == 'g1gc':
            # G1GC日志中查找版本信息
            version_match = re.search(self.patterns['g1_jvm_version'], log_content)
            if version_match:
                jvm_info['jvm_version'] = version_match.group(1)
            else:
                # 尝试其他版本模式
                alt_patterns = [
                    r'Java HotSpot.*VM (\d+\.\d+\.\d+)',
                    r'OpenJDK.*VM (\d+\.\d+\.\d+)',
                    r'version (\d+\.\d+\.\d+[^,\s]*)'
                ]
                for pattern in alt_patterns:
                    match = re.search(pattern, log_content, re.IGNORECASE)
                    if match:
                        jvm_info['jvm_version'] = match.group(1)
                        break
        
        elif log_format == 'j9vm':
            # IBM J9 日志中查找版本信息
            version_match = re.search(self.patterns['j9_jvm_version'], log_content)
            if version_match:
                jvm_info['jvm_version'] = f"IBM J9 {version_match.group(1)}"
            else:
                # 尝试查找JRE版本信息
                build_match = re.search(self.patterns['j9_jvm_build'], log_content)
                if build_match:
                    jre_version, j9_build = build_match.groups()
                    jvm_info['jvm_version'] = f"IBM J9 {j9_build} (JRE {jre_version})"
                else:
                    # 如果找不到具体版本，设置为默认值
                    jvm_info['jvm_version'] = 'IBM J9 VM'
    
    def _extract_gc_strategy(self, log_content: str, jvm_info: Dict, log_format: str):
        """提取GC策略信息"""
        if log_format == 'g1gc':
            # 检查是否使用G1
            if 'Using G1' in log_content:
                jvm_info['gc_strategy'] = 'G1 (Garbage-First)'
            else:
                # 尝试匹配GC策略模式
                match = re.search(self.patterns['g1_gc_strategy'], log_content)
                if match:
                    jvm_info['gc_strategy'] = match.group(1)
                else:
                    # 根据日志内容推断GC策略
                    if 'G1' in log_content or 'Garbage-First' in log_content:
                        jvm_info['gc_strategy'] = 'G1 (Garbage-First)'
                    elif 'Parallel' in log_content:
                        jvm_info['gc_strategy'] = 'Parallel GC'
                    elif 'CMS' in log_content:
                        jvm_info['gc_strategy'] = 'CMS (Concurrent Mark Sweep)'
                    elif 'Serial' in log_content:
                        jvm_info['gc_strategy'] = 'Serial GC'
        
        elif log_format == 'j9vm':
            # IBM J9 GC策略通常在策略相关的日志中
            # 查找具体的GC策略配置
            policy_match = re.search(self.patterns['j9_gc_policy'], log_content, re.DOTALL)
            if policy_match:
                policy = policy_match.group(1)
                if 'gencon' in policy.lower():
                    jvm_info['gc_strategy'] = 'IBM J9 Generational Concurrent (gencon)'
                elif 'balanced' in policy.lower():
                    jvm_info['gc_strategy'] = 'IBM J9 Balanced'
                elif 'optthruput' in policy.lower():
                    jvm_info['gc_strategy'] = 'IBM J9 Throughput (optthruput)'
                elif 'optavgpause' in policy.lower():
                    jvm_info['gc_strategy'] = 'IBM J9 Average Pause (optavgpause)'
                else:
                    jvm_info['gc_strategy'] = f'IBM J9 {policy}'
            elif 'gencon' in log_content.lower():
                jvm_info['gc_strategy'] = 'IBM J9 Generational Concurrent'
            elif 'balanced' in log_content.lower():
                jvm_info['gc_strategy'] = 'IBM J9 Balanced'
            elif 'optthruput' in log_content.lower():
                jvm_info['gc_strategy'] = 'IBM J9 Throughput'
            else:
                jvm_info['gc_strategy'] = 'IBM J9 Default'
    
    def _extract_hardware_info(self, log_content: str, jvm_info: Dict, log_format: str):
        """提取硬件和内存信息"""
        if log_format == 'g1gc':
            # CPU信息
            cpu_match = re.search(self.patterns['g1_cpu_info'], log_content)
            if cpu_match:
                jvm_info['cpu_cores'] = int(cpu_match.group(1))
            
            # 内存信息
            memory_match = re.search(self.patterns['g1_memory_info'], log_content)
            if memory_match:
                jvm_info['total_memory_mb'] = int(memory_match.group(1))
            
            # 堆大小信息 - 更新字段名
            heap_initial_match = re.search(self.patterns['g1_heap_initial'], log_content)
            if heap_initial_match:
                jvm_info['initial_heap_mb'] = int(heap_initial_match.group(1))
            
            heap_max_match = re.search(self.patterns['g1_heap_max'], log_content)
            if heap_max_match:
                jvm_info['maximum_heap_mb'] = int(heap_max_match.group(1))
            
            heap_min_match = re.search(self.patterns['g1_heap_min'], log_content)
            if heap_min_match:
                jvm_info['heap_min_capacity_mb'] = int(heap_min_match.group(1))
            
            # 并行工作线程数
            workers_match = re.search(self.patterns['g1_parallel_workers'], log_content)
            if workers_match:
                jvm_info['parallel_workers'] = int(workers_match.group(1))
            
            # 堆区域大小
            region_size_pattern = r'\[info\]\[gc,init\].*Heap Region Size: (\d+)M'
            region_match = re.search(region_size_pattern, log_content)
            if region_match:
                jvm_info['heap_region_size'] = int(region_match.group(1))
        
        elif log_format == 'j9vm':
            # IBM J9的内存参数通常在启动参数中
            heap_match = re.search(self.patterns['j9_heap_info'], log_content)
            if heap_match:
                initial_heap = self._parse_memory_size(heap_match.group(1))
                max_heap = self._parse_memory_size(heap_match.group(2))
                jvm_info['initial_heap_mb'] = initial_heap
                jvm_info['maximum_heap_mb'] = max_heap
            
            # 查找XML格式的堆配置信息（优先级更高）
            max_heap_match = re.search(self.patterns['j9_max_heap_size'], log_content)
            if max_heap_match:
                heap_bytes = int(max_heap_match.group(1))
                jvm_info['maximum_heap_mb'] = heap_bytes // (1024 * 1024)
            
            initial_heap_match = re.search(self.patterns['j9_initial_heap_size'], log_content)
            if initial_heap_match:
                heap_bytes = int(initial_heap_match.group(1))
                jvm_info['initial_heap_mb'] = heap_bytes // (1024 * 1024)
            
            # 查找系统信息
            processor_match = re.search(self.patterns['j9_processor_info'], log_content)
            if processor_match:
                jvm_info['cpu_cores'] = int(processor_match.group(1))
            
            physical_memory_match = re.search(self.patterns['j9_physical_memory'], log_content)
            if physical_memory_match:
                memory_bytes = int(physical_memory_match.group(1))
                jvm_info['total_memory_mb'] = memory_bytes // (1024 * 1024)
            
            # 查找GC线程数
            gc_threads_match = re.search(self.patterns['j9_gc_threads'], log_content)
            if gc_threads_match:
                jvm_info['gc_threads'] = int(gc_threads_match.group(1))
    
    def _parse_memory_size(self, size_str: str) -> int:
        """解析内存大小字符串（如512m, 4g）为MB"""
        size_str = size_str.lower().strip()
        if size_str.endswith('g'):
            return int(float(size_str[:-1]) * 1024)
        elif size_str.endswith('m'):
            return int(float(size_str[:-1]))
        elif size_str.endswith('k'):
            return int(float(size_str[:-1]) / 1024)
        else:
            # 假设是字节，转换为MB
            return int(float(size_str) / (1024 * 1024))
    
    def _calculate_runtime_from_events(self, events: List[Dict], jvm_info: Dict):
        """从事件列表计算运行时长"""
        if not events or len(events) < 2:
            return
        
        try:
            # 获取第一个和最后一个事件的时间戳
            first_event = events[0]
            last_event = events[-1]
            
            start_time = self._extract_timestamp(first_event)
            end_time = self._extract_timestamp(last_event)
            
            if start_time is not None and end_time is not None:
                runtime_seconds = end_time - start_time
                jvm_info['runtime_duration_seconds'] = max(runtime_seconds, 0)
                jvm_info['gc_log_start_time'] = start_time
                jvm_info['gc_log_end_time'] = end_time
        
        except Exception as e:
            print(f"计算运行时长失败: {e}")
    
    def _extract_timestamp(self, event: Dict) -> Optional[float]:
        """从事件中提取时间戳"""
        timestamp = event.get('timestamp')
        if timestamp is None:
            return None
        
        # 处理不同的时间戳格式
        if isinstance(timestamp, (int, float)):
            return float(timestamp)
        
        if isinstance(timestamp, str):
            # 尝试解析相对时间戳（如 "123.456s"）
            if timestamp.endswith('s'):
                try:
                    return float(timestamp[:-1])
                except ValueError:
                    pass
            
            # 尝试解析ISO时间戳
            try:
                if 'T' in timestamp:
                    # 处理ISO格式时间戳，去掉时区信息
                    if '+' in timestamp:
                        timestamp = timestamp.split('+')[0]
                    elif timestamp.count('-') > 2:  # 处理负时区
                        last_dash = timestamp.rfind('-')
                        if last_dash > 10:  # 确保不是日期部分的-
                            timestamp = timestamp[:last_dash]
                    
                    dt = datetime.fromisoformat(timestamp)
                    return dt.timestamp()
            except ValueError:
                pass
        
        return None
    
    def _calculate_runtime_from_log(self, log_content: str, jvm_info: Dict):
        """从日志内容计算运行时长"""
        relative_timestamps = []
        
        # 优先使用相对时间戳（如[123.456s]）来计算运行时长
        relative_pattern = r'\[(\d+\.\d+)s\]'
        matches = re.findall(relative_pattern, log_content)
        
        for match in matches:
            try:
                relative_timestamps.append(float(match))
            except ValueError:
                continue
        
        if len(relative_timestamps) >= 2:
            runtime_seconds = max(relative_timestamps) - min(relative_timestamps)
            jvm_info['runtime_duration_seconds'] = runtime_seconds
            jvm_info['gc_log_start_time'] = min(relative_timestamps)
            jvm_info['gc_log_end_time'] = max(relative_timestamps)
        else:
            # 如果没有相对时间戳，尝试使用ISO时间戳
            iso_timestamps = []
            iso_pattern = r'\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)'
            iso_matches = re.findall(iso_pattern, log_content)
            
            for match in iso_matches:
                try:
                    dt = datetime.fromisoformat(match)
                    iso_timestamps.append(dt.timestamp())
                except ValueError:
                    continue
            
            if len(iso_timestamps) >= 2:
                runtime_seconds = max(iso_timestamps) - min(iso_timestamps)
                jvm_info['runtime_duration_seconds'] = runtime_seconds
                jvm_info['gc_log_start_time'] = min(iso_timestamps)
                jvm_info['gc_log_end_time'] = max(iso_timestamps)
    
    def _count_gc_events(self, log_content: str) -> int:
        """统计GC事件数量"""
        # 简单的GC事件计数
        gc_patterns = [
            r'\[gc\s*\]',
            r'\[gc,start\]',
            r'GC\(\d+\)',
            r'<gc type='
        ]
        
        total_count = 0
        for pattern in gc_patterns:
            matches = re.findall(pattern, log_content, re.IGNORECASE)
            total_count += len(matches)
        
        return total_count
    
    def format_jvm_info_summary(self, jvm_info: Dict) -> str:
        """格式化JVM信息摘要"""
        summary_lines = []
        
        summary_lines.append(f"🖥️  JVM版本: {jvm_info['jvm_version']}")
        summary_lines.append(f"🗑️  GC策略: {jvm_info['gc_strategy']}")
        
        if jvm_info['cpu_cores'] > 0:
            summary_lines.append(f"⚙️  CPU核心: {jvm_info['cpu_cores']} 核")
        
        if jvm_info['total_memory_mb'] > 0:
            summary_lines.append(f"💾 系统内存: {jvm_info['total_memory_mb']} MB")
        
        if jvm_info['maximum_heap_mb'] > 0:
            summary_lines.append(f"📊 最大堆内存: {jvm_info['maximum_heap_mb']} MB")
        
        if jvm_info['runtime_duration_seconds'] > 0:
            runtime_minutes = jvm_info['runtime_duration_seconds'] / 60
            if runtime_minutes > 60:
                runtime_hours = runtime_minutes / 60
                summary_lines.append(f"⏱️  运行时长: {runtime_hours:.1f} 小时")
            else:
                summary_lines.append(f"⏱️  运行时长: {runtime_minutes:.1f} 分钟")
        
        if jvm_info['total_gc_events'] > 0:
            summary_lines.append(f"🔄 GC事件数: {jvm_info['total_gc_events']} 次")
        
        # IBM J9特有信息
        if jvm_info.get('gc_threads'):
            summary_lines.append(f"🧵 GC线程数: {jvm_info['gc_threads']} 个")
        
        return "\n".join(summary_lines)


# 示例使用
if __name__ == "__main__":
    # 测试用例
    sample_g1_log = """
    [ [2024-01-01T10:00:01.123+0800][info][gc,init] Version 17.0.12+7
    [2024-01-01T10:00:01.124+0800][info][gc,init] CPUs: 4
    [2024-01-01T10:00:01.125+0800][info][gc,init] Memory: 14989M
    [2024-01-01T10:00:01.126+0800][info][gc,init] Using G1
    [2024-01-01T10:00:01.127+0800][info][gc,init] Initial heap size: 256M
    [2024-01-01T10:00:01.128+0800][info][gc,init] Maximum heap size: 4096M
    """
    
    extractor = JVMInfoExtractor()
    jvm_info = extractor.extract_jvm_info(sample_g1_log)
    
    print("JVM环境信息:")
    print(extractor.format_jvm_info_summary(jvm_info))
    print("\n详细信息:")
    for key, value in jvm_info.items():
        print(f"  {key}: {value}")