#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IBM J9VM GC日志解析器
支持解析IBM J9 JVM生成的GC日志 (适用于真实生产环境格式)
提供GC事件、内存使用统计信息
Author: GC Analysis Team
"""

import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class J9GCEvent:
    """IBM J9 GC事件数据结构 - 适应真实生产环境格式"""
    timestamp: str
    gc_type: str  # 'scavenge', 'global', 'concurrent'
    duration: float  # GC持续时间（毫秒）
    heap_before: int  # GC前堆大小（字节）
    heap_after: int   # GC后堆大小（字节）
    heap_total: int   # 总堆大小（字节）
    
    # 扩展字段以适应真实日志格式
    context_id: Optional[str] = None
    trigger_reason: Optional[str] = None
    nursery_before: Optional[int] = None  # Nursery区域GC前大小
    nursery_after: Optional[int] = None   # Nursery区域GC后大小
    nursery_total: Optional[int] = None   # Nursery区域总大小
    tenure_before: Optional[int] = None   # Tenure区域GC前大小
    tenure_after: Optional[int] = None    # Tenure区域GC后大小
    tenure_total: Optional[int] = None    # Tenure区域总大小
    allocate_before: Optional[int] = None  # Allocate区域GC前大小
    allocate_after: Optional[int] = None   # Allocate区域GC后大小
    survivor_before: Optional[int] = None  # Survivor区域GC前大小
    survivor_after: Optional[int] = None   # Survivor区域GC后大小
    gc_id: Optional[str] = None
    interval_ms: Optional[float] = None
    
    # Metaspace信息
    metaspace_before: Optional[int] = None  # GC前Metaspace使用量（KB）
    metaspace_after: Optional[int] = None   # GC后Metaspace使用量（KB）
    metaspace_total: Optional[int] = None   # Metaspace总大小（KB）
    metaspace_committed: Optional[int] = None  # Metaspace已提交大小（KB）


class J9LogParser:
    """IBM J9 GC日志解析器 - 适用于真实生产环境格式"""
    
    def __init__(self):
        # 基于真实生产环境日志格式的模式匹配
        # 示例: <gc-start id="5" type="scavenge" contextid="4" timestamp="2025-08-12T10:30:41.848">
        self.gc_start_pattern = re.compile(
            r'<gc-start\s+id="([^"]+)"\s+type="([^"]+)"\s+contextid="([^"]+)"\s+timestamp="([^"]+)"[^>]*>'
        )
        
        # GC结束模式匹配
        # 示例: <gc-end id="8" type="scavenge" contextid="4" durationms="4.063" ... timestamp="2025-08-12T10:30:41.852" activeThreads="16">
        self.gc_end_pattern = re.compile(
            r'<gc-end\s+id="([^"]+)"\s+type="([^"]+)"\s+contextid="([^"]+)"\s+durationms="([^"]+)"[^>]*timestamp="([^"]+)"[^>]*>'
        )
        
        # 内存信息模式匹配（用于gc-start和gc-end）
        # 示例: <mem-info id="6" free="38984672" total="52428800" percent="74">
        self.mem_info_pattern = re.compile(
            r'<mem-info\s+id="([^"]+)"\s+free="([^"]+)"\s+total="([^"]+)"\s+percent="([^"]+)"[^>]*>'
        )
        
        # 各内存区域模式匹配
        # 示例: <mem type="nursery" free="0" total="13107200" percent="0">
        self.mem_type_pattern = re.compile(
            r'<mem\s+type="([^"]+)"\s+free="([^"]+)"\s+total="([^"]+)"\s+percent="([^"]+)"[^>]*/?>' 
        )
        
        # 分配统计模式匹配
        self.allocation_stats_pattern = re.compile(
            r'<allocation-stats\s+totalBytes="([^"]+)"[^>]*>'
        )
        
        # 堆扩展模式匹配
        self.heap_resize_pattern = re.compile(
            r'<heap-resize\s+id="([^"]+)"\s+type="([^"]+)"\s+space="([^"]+)"\s+amount="([^"]+)"[^>]*>'
        )
    
    def parse_gc_log(self, log_content: str) -> Dict:
        """
        解析IBM J9 GC日志内容
        
        Args:
            log_content: GC日志文件内容
            
        Returns:
            解析结果字典，包含GC统计信息
        """
        events = self._extract_gc_events(log_content)
        return self._analyze_events(events)
    
    def _extract_gc_events(self, log_content: str) -> List[J9GCEvent]:
        """提取IBM J9 GC事件 - 基于真实生产环境格式"""
        events = []
        lines = log_content.split('\n')
        
        current_event = None
        in_gc_start_block = False
        in_gc_end_block = False
        current_mem_context = None  # 追踪当前内存上下文
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # 尝试匹配GC开始事件
            gc_start_match = self.gc_start_pattern.search(line)
            if gc_start_match:
                gc_id, gc_type, context_id, timestamp = gc_start_match.groups()
                current_event = J9GCEvent(
                    timestamp=timestamp,
                    gc_type=gc_type,
                    duration=0.0,  # 将在gc-end时更新
                    heap_before=0,
                    heap_after=0,
                    heap_total=0,
                    gc_id=gc_id,
                    context_id=context_id
                )
                in_gc_start_block = True
                in_gc_end_block = False  # 确保状态清晰
                continue
                
            # 尝试匹配GC结束事件
            gc_end_match = self.gc_end_pattern.search(line)
            if gc_end_match and current_event:
                gc_id, gc_type, context_id, duration_ms, timestamp = gc_end_match.groups()
                current_event.duration = float(duration_ms)
                in_gc_start_block = False  # 结束gc-start阶段
                in_gc_end_block = True     # 开始gc-end阶段
                continue
                
            # 如果遇到gc-end结束标签，完成当前事件
            if '</gc-end>' in line and current_event:
                events.append(current_event)
                current_event = None
                in_gc_start_block = False
                in_gc_end_block = False
                current_mem_context = None
                continue
                
            # 在GC事件块内解析内存信息
            if current_event and (in_gc_start_block or in_gc_end_block):
                # 匹配主要内存信息
                mem_info_match = self.mem_info_pattern.search(line)
                if mem_info_match:
                    mem_id, free, total, percent = mem_info_match.groups()
                    used = int(total) - int(free)
                    
                    if in_gc_start_block:
                        current_event.heap_before = used
                        current_event.heap_total = int(total)
                    elif in_gc_end_block:
                        current_event.heap_after = used
                        current_event.heap_total = int(total)
                    continue
                    
                # 匹配具体内存区域信息
                mem_type_match = self.mem_type_pattern.search(line)
                if mem_type_match:
                    mem_type, free, total, percent = mem_type_match.groups()
                    used = int(total) - int(free)
                    
                    # 根据内存类型和GC阶段更新相应字段
                    if mem_type == "nursery":
                        current_event.nursery_total = int(total)
                        if in_gc_start_block:
                            current_event.nursery_before = used
                        elif in_gc_end_block:
                            current_event.nursery_after = used
                    elif mem_type == "tenure":
                        current_event.tenure_total = int(total)
                        if in_gc_start_block:
                            current_event.tenure_before = used
                        elif in_gc_end_block:
                            current_event.tenure_after = used
                    elif mem_type == "allocate":
                        if in_gc_start_block:
                            current_event.allocate_before = used
                        elif in_gc_end_block:
                            current_event.allocate_after = used
                    elif mem_type == "survivor":
                        if in_gc_start_block:
                            current_event.survivor_before = used
                        elif in_gc_end_block:
                            current_event.survivor_after = used
                    continue
                    
                # 匹配分配统计信息
                alloc_stats_match = self.allocation_stats_pattern.search(line)
                if alloc_stats_match:
                    total_bytes = alloc_stats_match.group(1)
                    # 可以用于触发原因分析
                    if not current_event.trigger_reason:
                        current_event.trigger_reason = f"allocation request: {total_bytes} bytes"
                    continue
                    
        # 处理未闭合的事件
        if current_event:
            events.append(current_event)
        
        return events
    
    def _analyze_events(self, events: List[J9GCEvent]) -> Dict:
        """分析IBM J9 GC事件并生成统计信息"""
        if not events:
            return {
                'gc_count': {'scavenge': 0, 'global': 0, 'concurrent': 0, 'total': 0},
                'total_time': 0.0,
                'avg_time': 0.0,
                'max_time': 0.0,
                'min_time': 0.0,
                'memory_stats': {
                    'avg_heap_before': 0,
                    'avg_heap_after': 0,
                    'max_heap_used': 0,
                    'total_reclaimed': 0,
                    'avg_nursery_before': 0,
                    'avg_nursery_after': 0
                },
                'events': []
            }
        
        # 按类型统计GC次数
        gc_count = {'scavenge': 0, 'global': 0, 'concurrent': 0}
        for event in events:
            if event.gc_type in gc_count:
                gc_count[event.gc_type] += 1
            else:
                # 处理未知类型
                if 'other' not in gc_count:
                    gc_count['other'] = 0
                gc_count['other'] += 1
        gc_count['total'] = len(events)
        
        # GC时间统计
        durations = [event.duration for event in events]
        total_time = sum(durations)
        avg_time = total_time / len(events)
        max_time = max(durations)
        min_time = min(durations)
        
        # 内存使用统计
        heap_before_sizes = [event.heap_before for event in events if event.heap_before > 0]
        heap_after_sizes = [event.heap_after for event in events if event.heap_after > 0]
        reclaimed_amounts = [
            event.heap_before - event.heap_after 
            for event in events 
            if event.heap_before > 0 and event.heap_after > 0
        ]
        
        # Nursery统计
        nursery_events = [event for event in events if event.nursery_before is not None]
        nursery_before_sizes = [event.nursery_before for event in nursery_events if event.nursery_before is not None]
        nursery_after_sizes = [event.nursery_after for event in nursery_events if event.nursery_after is not None]
        
        memory_stats = {
            'avg_heap_before': sum(heap_before_sizes) / len(heap_before_sizes) if heap_before_sizes else 0,
            'avg_heap_after': sum(heap_after_sizes) / len(heap_after_sizes) if heap_after_sizes else 0,
            'max_heap_used': max(heap_before_sizes) if heap_before_sizes else 0,
            'total_reclaimed': sum(reclaimed_amounts) if reclaimed_amounts else 0,
            'avg_nursery_before': sum(nursery_before_sizes) / len(nursery_before_sizes) if nursery_before_sizes else 0,
            'avg_nursery_after': sum(nursery_after_sizes) / len(nursery_after_sizes) if nursery_after_sizes else 0
        }
        
        # 转换events为可序列化格式
        serializable_events = []
        for event in events:
            serializable_events.append({
                'timestamp': event.timestamp,
                'gc_type': event.gc_type,
                'duration': event.duration,
                'heap_before': event.heap_before,
                'heap_after': event.heap_after,
                'heap_total': event.heap_total,
                'gc_id': event.gc_id,
                'context_id': event.context_id,
                'trigger_reason': event.trigger_reason,
                'nursery_before': event.nursery_before,
                'nursery_after': event.nursery_after,
                'nursery_total': event.nursery_total,
                'tenure_before': event.tenure_before,
                'tenure_after': event.tenure_after,
                'tenure_total': event.tenure_total,
                'allocate_before': event.allocate_before,
                'allocate_after': event.allocate_after,
                'survivor_before': event.survivor_before,
                'survivor_after': event.survivor_after,
                'interval_ms': event.interval_ms,
                # Metaspace信息
                'metaspace_before': event.metaspace_before,
                'metaspace_after': event.metaspace_after,
                'metaspace_total': event.metaspace_total,
                'metaspace_committed': event.metaspace_committed
            })
        
        return {
            'gc_count': gc_count,
            'total_time': total_time,
            'avg_time': avg_time,
            'max_time': max_time,
            'min_time': min_time,
            'memory_stats': memory_stats,
            'events': serializable_events
        }


# 提供便捷的函数接口
def parse_gc_log(log_content: str) -> Dict:
    """解析IBM J9 GC日志的便捷函数"""
    parser = J9LogParser()
    return parser.parse_gc_log(log_content)


if __name__ == '__main__':
    # 基于真实生产环境格式的测试代码
    sample_log = """
<?xml version="1.0" ?>
<verbosegc xmlns="http://www.ibm.com/j9/verbosegc" version="fa000e8_CMPRSS">
<gc-start id="5" type="scavenge" contextid="4" timestamp="2025-08-12T10:30:41.848">
  <mem-info id="6" free="38984672" total="52428800" percent="74">
    <mem type="nursery" free="0" total="13107200" percent="0">
      <mem type="allocate" free="0" total="6553600" percent="0" />
      <mem type="survivor" free="0" total="6553600" percent="0" />
    </mem>
    <mem type="tenure" free="38984672" total="39321600" percent="99">
      <mem type="soa" free="37018592" total="37355520" percent="99" />
      <mem type="loa" free="1966080" total="1966080" percent="100" />
    </mem>
  </mem-info>
</gc-start>
<allocation-stats totalBytes="6886848" >
  <allocated-bytes non-tlh="984560" tlh="5902288" />
</allocation-stats>
<gc-end id="8" type="scavenge" contextid="4" durationms="4.063" usertimems="11.075" systemtimems="5.067" stalltimems="31.653" timestamp="2025-08-12T10:30:41.852" activeThreads="16">
  <mem-info id="9" free="43341360" total="52428800" percent="82">
    <mem type="nursery" free="4356688" total="13107200" percent="33">
      <mem type="allocate" free="4356688" total="6553600" percent="66" />
      <mem type="survivor" free="0" total="6553600" percent="0" />
    </mem>
  </mem-info>
</gc-end>
</verbosegc>
"""
    result = parse_gc_log(sample_log)
    print(f"解析结果: {result}")