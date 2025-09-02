#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
G1 GC日志解析器 - 支持JVM统一日志格式
适配现代G1垃圾收集器日志格式 (JDK 9+)
支持Young GC、Mixed GC、Full GC和Concurrent GC的统计分析
特别针对异常GC情况（如连续Full GC、内存泄漏等）提供诊断信息
Author: GC Analysis Team
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class G1GCEvent:
    """G1 GC事件数据结构 - 适用于JVM统一日志格式"""
    timestamp: str  # 时间戳
    gc_id: int      # GC ID
    gc_type: str    # 'young', 'mixed', 'full', 'concurrent_start', 'concurrent_cycle'
    gc_subtype: Optional[str] = None  # 具体类型如 'Normal', 'Concurrent Start', 'G1 Compaction Pause'
    pause_time: float = 0.0  # 暂停时间（毫秒）
    heap_before: int = 0     # GC前堆大小（MB）
    heap_after: int = 0      # GC后堆大小（MB）
    heap_total: int = 0      # 总堆大小（MB）
    trigger_reason: Optional[str] = None  # 触发原因
    
    # G1特有字段
    eden_before: int = 0     # Eden区域数量（GC前）
    eden_after: int = 0      # Eden区域数量（GC后）
    eden_target: int = 0     # Eden区域目标数量
    survivor_before: int = 0 # Survivor区域数量（GC前）
    survivor_after: int = 0  # Survivor区域数量（GC后）
    survivor_target: int = 0 # Survivor区域目标数量
    old_before: int = 0      # Old区域数量（GC前）
    old_after: int = 0       # Old区域数量（GC后）
    humongous_before: int = 0 # Humongous区域数量（GC前）
    humongous_after: int = 0  # Humongous区域数量（GC后）
    archive_regions: int = 0  # Archive区域数量
    
    # Metaspace信息
    metaspace_before: int = 0  # GC前Metaspace使用量（KB）
    metaspace_after: int = 0   # GC后Metaspace使用量（KB）
    metaspace_total: int = 0   # Metaspace总大小（KB）
    metaspace_committed: int = 0  # Metaspace已提交大小（KB）
    
    # 阶段信息
    pre_evacuate_time: float = 0.0      # Pre Evacuate时间
    merge_heap_roots_time: float = 0.0  # Merge Heap Roots时间
    evacuate_collection_set_time: float = 0.0  # Evacuate Collection Set时间
    post_evacuate_time: float = 0.0     # Post Evacuate时间
    other_time: float = 0.0             # Other时间
    
    # Full GC阶段信息（如果是Full GC）
    mark_live_objects_time: float = 0.0    # Phase 1: Mark live objects
    prepare_compaction_time: float = 0.0   # Phase 2: Prepare for compaction  
    adjust_pointers_time: float = 0.0      # Phase 3: Adjust pointers
    compact_heap_time: float = 0.0        # Phase 4: Compact heap
    
    # 线程和CPU信息
    workers_used: int = 0       # 使用的worker线程数
    workers_total: int = 0      # 总worker线程数
    user_time: float = 0.0      # User时间
    sys_time: float = 0.0       # System时间
    real_time: float = 0.0      # Real时间
    
    # 异常情况标识
    is_abnormal: bool = False   # 是否异常
    abnormal_reason: Optional[str] = None  # 异常原因


class G1LogParser:
    """G1 GC日志解析器 - 支持JVM统一日志格式"""
    
    def __init__(self):
        # JVM统一日志格式模式匹配
        # 示例: [2025-08-26T15:03:29.558+0800][3.715s][info][gc,start    ] GC(0) Pause Young (Normal) (G1 Evacuation Pause)
        self.gc_start_pattern = re.compile(
            r'\[(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{4})\]\[([\d.]+)s\]\[info\]\[gc,start\s*\] GC\((\d+)\) Pause (\w+)(?:\s+\(([^)]*)\))?(?:\s+\(([^)]*)\))?'
        )
        
        # GC结束模式 - 包含堆内存信息
        # 示例: [2025-08-26T15:03:29.583+0800][3.740s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 173M->23M(512M) 24.846ms
        self.gc_end_pattern = re.compile(
            r'\[(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{4})\]\[([\d.]+)s\]\[info\]\[gc\s*\] GC\((\d+)\) Pause (\w+)(?:\s+\(([^)]*)\))?(?:\s+\(([^)]*)\))?\s+(\d+)M->(\d+)M\((\d+)M\)\s+([\d.]+)ms'
        )
        
        # Full GC模式
        # 示例: [2025-08-26T15:27:20.684+0800][1434.841s][info][gc             ] GC(5098) Pause Full (G1 Compaction Pause) 510M->510M(512M) 654.933ms
        self.full_gc_pattern = re.compile(
            r'\[(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{4})\]\[([\d.]+)s\]\[info\]\[gc\s*\] GC\((\d+)\) Pause Full\s+\(([^)]*)\)\s+(\d+)M->(\d+)M\((\d+)M\)\s+([\d.]+)ms'
        )
        
        # Concurrent事件模式
        # 示例: [2025-08-26T15:27:21.909+0800][1436.066s][info][gc             ] GC(5097) Concurrent Mark Cycle 2449.142ms
        self.concurrent_pattern = re.compile(
            r'\[(\d{4}-\d{2}-\d{2}T[\d:.]+[+-]\d{4})\]\[([\d.]+)s\]\[info\]\[gc\s*\] GC\((\d+)\) Concurrent ([^\s]+(?:\s+[^\s]+)*)\s+([\d.]+)ms'
        )
        
        # 堆区域信息模式
        # 示例: [2025-08-26T15:03:29.583+0800][3.740s][info][gc,heap     ] GC(0) Eden regions: 170->0(150)
        self.heap_regions_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,heap\s*\] GC\((\d+)\) (\w+) regions: (\d+)->(\d+)(?:\((\d+)\))?'
        )
        
        # GC阶段信息模式
        # 示例: [2025-08-26T15:03:29.583+0800][3.740s][info][gc,phases   ] GC(0)   Pre Evacuate Collection Set: 0.1ms
        self.phases_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,phases\s*\] GC\((\d+)\)\s+([^:]+):\s+([\d.]+)ms'
        )
        
        # Full GC阶段信息模式
        # 示例: [2025-08-26T15:27:20.645+0800][1434.802s][info][gc,phases      ] GC(5098) Phase 4: Compact heap 48.647ms
        self.full_gc_phases_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,phases\s*\] GC\((\d+)\) Phase (\d+): ([^\d]+)\s+([\d.]+)ms'
        )
        
        # Worker线程信息模式
        # 示例: [2025-08-26T15:03:29.561+0800][3.718s][info][gc,task     ] GC(0) Using 4 workers of 4 for evacuation
        self.task_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,task\s*\] GC\((\d+)\) Using (\d+) workers of (\d+) for (.+)'
        )
        
        # CPU信息模式
        # 示例: [2025-08-26T15:03:29.583+0800][3.740s][info][gc,cpu      ] GC(0) User=0.07s Sys=0.00s Real=0.03s
        self.cpu_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,cpu\s*\] GC\((\d+)\) User=([\d.]+)s Sys=([\d.]+)s Real=([\d.]+)s'
        )
        
        # 错误和异常情况模式
        self.ergo_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,ergo\s*\] (.+)'
        )
        
        # Concurrent Mark相关模式
        self.marking_pattern = re.compile(
            r'\[([\d:T.-]+)\]\[([\d.]+)s\]\[info\]\[gc,marking\s*\] GC\((\d+)\) Concurrent ([^\s]+(?:\s+[^\s]+)*)(?:\s+([\d.]+)ms)?'
        )
        
        # Metaspace信息模式
        # 示例: [2025-08-26T15:03:29.583+0800][3.740s][info][gc,metaspace] GC(0) Metaspace: 1234K->1234K(4096K)
        self.metaspace_pattern = re.compile(
            r'\[([\d:T.+-]+)\]\[([\d.]+)s\]\[info\]\[gc,metaspace\s*\] GC\((\d+)\) Metaspace: (\d+)K->(\d+)K\((\d+)K\)'
        )
    
    def parse_gc_log(self, log_content: str) -> Dict:
        """
        解析G1 GC日志内容
        
        Args:
            log_content: GC日志文件内容
            
        Returns:
            解析结果字典，包含GC统计信息
        """
        events = self._extract_gc_events(log_content)
        return self._analyze_events(events)
    
    def _extract_gc_events(self, log_content: str) -> List[G1GCEvent]:
        """提取G1 GC事件 - 支持JVM统一日志格式"""
        events = []
        lines = log_content.split('\n')
        
        # 临时存储正在构建的事件
        current_events = {}  # gc_id -> G1GCEvent
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 尝试匹配GC开始事件
            start_match = self.gc_start_pattern.search(line)
            if start_match:
                timestamp, runtime, gc_id, gc_type, subtype1, subtype2 = start_match.groups()
                gc_id = int(gc_id)
                
                event = G1GCEvent(
                    timestamp=timestamp,
                    gc_id=gc_id,
                    gc_type=gc_type.lower(),
                    gc_subtype=subtype1 or subtype2
                )
                
                current_events[gc_id] = event
                continue
                
            # 尝试匹配GC结束事件（普通的Young/Mixed GC）
            end_match = self.gc_end_pattern.search(line)
            if end_match:
                timestamp, runtime, gc_id, gc_type, subtype1, subtype2, heap_before, heap_after, heap_total, pause_time = end_match.groups()
                gc_id = int(gc_id)
                
                if gc_id in current_events:
                    event = current_events[gc_id]
                    event.pause_time = float(pause_time)
                    event.heap_before = int(heap_before)
                    event.heap_after = int(heap_after)
                    event.heap_total = int(heap_total)
                    events.append(event)
                    del current_events[gc_id]
                continue
                
            # 尝试匹配Full GC事件
            full_match = self.full_gc_pattern.search(line)
            if full_match:
                timestamp, runtime, gc_id, gc_subtype, heap_before, heap_after, heap_total, pause_time = full_match.groups()
                gc_id = int(gc_id)
                
                event = G1GCEvent(
                    timestamp=timestamp,
                    gc_id=gc_id,
                    gc_type='full',
                    gc_subtype=gc_subtype,
                    pause_time=float(pause_time),
                    heap_before=int(heap_before),
                    heap_after=int(heap_after),
                    heap_total=int(heap_total)
                )
                
                # 检查是否为异常Full GC
                if heap_before == heap_after:
                    event.is_abnormal = True
                    event.abnormal_reason = f'内存无法回收: {heap_before}M->({heap_after}M)'
                    
                events.append(event)
                
                # 如果有对应的开始事件，删除它
                if gc_id in current_events:
                    del current_events[gc_id]
                continue
                
            # 尝试匹配Concurrent事件
            concurrent_match = self.concurrent_pattern.search(line)
            if concurrent_match:
                timestamp, runtime, gc_id, concurrent_type, duration = concurrent_match.groups()
                gc_id = int(gc_id)
                
                event = G1GCEvent(
                    timestamp=timestamp,
                    gc_id=gc_id,
                    gc_type='concurrent',
                    gc_subtype=concurrent_type,
                    pause_time=float(duration) if duration else 0.0
                )
                
                # 检查并发标记是否被中止
                if 'Abort' in concurrent_type:
                    event.is_abnormal = True
                    event.abnormal_reason = f'并发标记被中止: {concurrent_type}'
                    
                events.append(event)
                continue
                
            # 解析堆区域信息
            heap_match = self.heap_regions_pattern.search(line)
            if heap_match:
                timestamp, runtime, gc_id, region_type, before, after, target = heap_match.groups()
                gc_id = int(gc_id)
                
                if gc_id in current_events:
                    event = current_events[gc_id]
                    
                    if region_type.lower() == 'eden':
                        event.eden_before = int(before)
                        event.eden_after = int(after)
                        event.eden_target = int(target) if target else 0
                    elif region_type.lower() == 'survivor':
                        event.survivor_before = int(before)
                        event.survivor_after = int(after)
                        event.survivor_target = int(target) if target else 0
                    elif region_type.lower() == 'old':
                        event.old_before = int(before)
                        event.old_after = int(after)
                    elif region_type.lower() == 'humongous':
                        event.humongous_before = int(before)
                        event.humongous_after = int(after)
                    elif region_type.lower() == 'archive':
                        event.archive_regions = int(after)
                continue
                
            # 解析GC阶段信息
            phases_match = self.phases_pattern.search(line)
            if phases_match:
                timestamp, runtime, gc_id, phase_name, phase_time = phases_match.groups()
                gc_id = int(gc_id)
                
                if gc_id in current_events:
                    event = current_events[gc_id]
                    phase_time = float(phase_time)
                    
                    phase_name = phase_name.strip()
                    if 'Pre Evacuate' in phase_name:
                        event.pre_evacuate_time = phase_time
                    elif 'Merge Heap Roots' in phase_name:
                        event.merge_heap_roots_time = phase_time
                    elif 'Evacuate Collection Set' in phase_name:
                        event.evacuate_collection_set_time = phase_time
                    elif 'Post Evacuate' in phase_name:
                        event.post_evacuate_time = phase_time
                    elif 'Other' in phase_name:
                        event.other_time = phase_time
                continue
                
            # 解析Full GC阶段信息
            full_phases_match = self.full_gc_phases_pattern.search(line)
            if full_phases_match:
                timestamp, runtime, gc_id, phase_num, phase_name, phase_time = full_phases_match.groups()
                gc_id = int(gc_id)
                
                # 寻找对应的Full GC事件
                matching_event = None
                for event in reversed(events):
                    if event.gc_id == gc_id and event.gc_type == 'full':
                        matching_event = event
                        break
                        
                if matching_event:
                    phase_time = float(phase_time)
                    phase_name = phase_name.strip()
                    
                    if 'Mark live objects' in phase_name:
                        matching_event.mark_live_objects_time = phase_time
                    elif 'Prepare for compaction' in phase_name:
                        matching_event.prepare_compaction_time = phase_time
                    elif 'Adjust pointers' in phase_name:
                        matching_event.adjust_pointers_time = phase_time
                    elif 'Compact heap' in phase_name:
                        matching_event.compact_heap_time = phase_time
                continue
                
            # 解析Worker线程信息
            task_match = self.task_pattern.search(line)
            if task_match:
                timestamp, runtime, gc_id, workers_used, workers_total, task_type = task_match.groups()
                gc_id = int(gc_id)
                
                if gc_id in current_events:
                    event = current_events[gc_id]
                    event.workers_used = int(workers_used)
                    event.workers_total = int(workers_total)
                continue
                
            # 解析CPU信息
            cpu_match = self.cpu_pattern.search(line)
            if cpu_match:
                timestamp, runtime, gc_id, user_time, sys_time, real_time = cpu_match.groups()
                gc_id = int(gc_id)
                
                # 寻找对应的GC事件
                matching_event = None
                for event in reversed(events):
                    if event.gc_id == gc_id:
                        matching_event = event
                        break
                        
                if matching_event:
                    matching_event.user_time = float(user_time)
                    matching_event.sys_time = float(sys_time)
                    matching_event.real_time = float(real_time)
                continue
                
            # 解析Metaspace信息
            metaspace_match = self.metaspace_pattern.search(line)
            if metaspace_match:
                timestamp, runtime, gc_id, metaspace_before, metaspace_after, metaspace_total = metaspace_match.groups()
                gc_id = int(gc_id)
                
                # 寻找对应的GC事件
                matching_event = None
                for event in reversed(events):
                    if event.gc_id == gc_id:
                        matching_event = event
                        break
                
                # 如果没有找到已完成的事件，检查正在构建的事件
                if not matching_event and gc_id in current_events:
                    matching_event = current_events[gc_id]
                    
                if matching_event:
                    matching_event.metaspace_before = int(metaspace_before)
                    matching_event.metaspace_after = int(metaspace_after)
                    matching_event.metaspace_total = int(metaspace_total)
                continue
                
            # 解析错误和异常情况
            ergo_match = self.ergo_pattern.search(line)
            if ergo_match:
                timestamp, runtime, message = ergo_match.groups()
                
                # 检查是否是异常情况
                if 'Attempting full compaction' in message or 'maximum full compaction' in message:
                    # 查找最近的事件并标记为异常
                    if events:
                        last_event = events[-1]
                        last_event.is_abnormal = True
                        if not last_event.abnormal_reason:
                            last_event.abnormal_reason = message
                continue
        
        # 处理未完成的事件
        for gc_id, event in current_events.items():
            events.append(event)
            
        return events
    
    def _analyze_events(self, events: List[G1GCEvent]) -> Dict:
        """分析G1 GC事件并生成统计信息，包括异常情况诊断"""
        if not events:
            return {
                'gc_count': {'young': 0, 'mixed': 0, 'full': 0, 'concurrent': 0, 'total': 0},
                'total_pause': 0.0,
                'avg_pause': 0.0,
                'max_pause': 0.0,
                'min_pause': 0.0,
                'memory_stats': {
                    'avg_heap_before': 0,
                    'avg_heap_after': 0,
                    'max_heap_used': 0,
                    'total_reclaimed': 0,
                    'avg_reclaim_rate': 0.0
                },
                'region_stats': {
                    'avg_eden_before': 0,
                    'avg_eden_after': 0,
                    'avg_survivor_before': 0,
                    'avg_survivor_after': 0,
                    'avg_old_before': 0,
                    'avg_old_after': 0,
                    'avg_humongous': 0
                },
                'abnormal_analysis': {
                    'has_abnormal_events': False,
                    'abnormal_count': 0,
                    'abnormal_reasons': [],
                    'consecutive_full_gc_count': 0,
                    'memory_leak_suspected': False,
                    'recommendations': []
                },
                'events': []
            }
        
        # 按类型统计GC次数
        gc_count = {'young': 0, 'mixed': 0, 'full': 0, 'concurrent': 0}
        for event in events:
            if event.gc_type in gc_count:
                gc_count[event.gc_type] += 1
            else:
                # 处理未知类型
                if 'other' not in gc_count:
                    gc_count['other'] = 0
                gc_count['other'] += 1
        gc_count['total'] = len(events)
        
        # 暂停时间统计（只计算非并发事件）
        pause_events = [event for event in events if event.gc_type != 'concurrent' and event.pause_time > 0]
        if pause_events:
            pause_times = [event.pause_time for event in pause_events]
            total_pause = sum(pause_times)
            avg_pause = total_pause / len(pause_events)
            max_pause = max(pause_times)
            min_pause = min(pause_times)
        else:
            total_pause = avg_pause = max_pause = min_pause = 0.0
        
        # 内存使用统计（只计算有堆信息的事件）
        heap_events = [event for event in events if event.heap_before > 0 and event.heap_after >= 0]
        if heap_events:
            heap_before_sizes = [event.heap_before for event in heap_events]
            heap_after_sizes = [event.heap_after for event in heap_events]
            reclaimed_amounts = [max(0, event.heap_before - event.heap_after) for event in heap_events]
            
            avg_heap_before = sum(heap_before_sizes) / len(heap_events)
            avg_heap_after = sum(heap_after_sizes) / len(heap_events)
            max_heap_used = max(heap_before_sizes)
            total_reclaimed = sum(reclaimed_amounts)
            avg_reclaim_rate = (total_reclaimed / sum(heap_before_sizes)) * 100 if sum(heap_before_sizes) > 0 else 0.0
        else:
            avg_heap_before = avg_heap_after = max_heap_used = total_reclaimed = avg_reclaim_rate = 0
        
        memory_stats = {
            'avg_heap_before': avg_heap_before,
            'avg_heap_after': avg_heap_after,
            'max_heap_used': max_heap_used,
            'total_reclaimed': total_reclaimed,
            'avg_reclaim_rate': avg_reclaim_rate
        }
        
        # 区域统计（G1特有）
        region_events = [event for event in events if event.eden_before > 0 or event.survivor_before > 0 or event.old_before > 0]
        if region_events:
            eden_before = [event.eden_before for event in region_events if event.eden_before > 0]
            eden_after = [event.eden_after for event in region_events if event.eden_after >= 0]
            survivor_before = [event.survivor_before for event in region_events if event.survivor_before > 0]
            survivor_after = [event.survivor_after for event in region_events if event.survivor_after >= 0]
            old_before = [event.old_before for event in region_events if event.old_before > 0]
            old_after = [event.old_after for event in region_events if event.old_after >= 0]
            humongous = [event.humongous_before for event in region_events if event.humongous_before > 0]
            
            region_stats = {
                'avg_eden_before': sum(eden_before) / len(eden_before) if eden_before else 0,
                'avg_eden_after': sum(eden_after) / len(eden_after) if eden_after else 0,
                'avg_survivor_before': sum(survivor_before) / len(survivor_before) if survivor_before else 0,
                'avg_survivor_after': sum(survivor_after) / len(survivor_after) if survivor_after else 0,
                'avg_old_before': sum(old_before) / len(old_before) if old_before else 0,
                'avg_old_after': sum(old_after) / len(old_after) if old_after else 0,
                'avg_humongous': sum(humongous) / len(humongous) if humongous else 0
            }
        else:
            region_stats = {
                'avg_eden_before': 0, 'avg_eden_after': 0,
                'avg_survivor_before': 0, 'avg_survivor_after': 0,
                'avg_old_before': 0, 'avg_old_after': 0, 'avg_humongous': 0
            }
        
        # 异常情况分析
        abnormal_analysis = self._analyze_abnormal_situations(events)
        
        # 转换events为可序列化格式
        serializable_events = []
        for event in events:
            serializable_events.append({
                'timestamp': event.timestamp,
                'gc_id': event.gc_id,
                'gc_type': event.gc_type,
                'gc_subtype': event.gc_subtype,
                'pause_time': event.pause_time,
                'heap_before': event.heap_before,
                'heap_after': event.heap_after,
                'heap_total': event.heap_total,
                'trigger_reason': event.trigger_reason,
                'eden_before': event.eden_before,
                'eden_after': event.eden_after,
                'eden_target': event.eden_target,
                'survivor_before': event.survivor_before,
                'survivor_after': event.survivor_after,
                'survivor_target': event.survivor_target,
                'old_before': event.old_before,
                'old_after': event.old_after,
                'humongous_before': event.humongous_before,
                'humongous_after': event.humongous_after,
                'archive_regions': event.archive_regions,
                # Metaspace信息
                'metaspace_before': event.metaspace_before,
                'metaspace_after': event.metaspace_after,
                'metaspace_total': event.metaspace_total,
                'metaspace_committed': event.metaspace_committed,
                'pre_evacuate_time': event.pre_evacuate_time,
                'merge_heap_roots_time': event.merge_heap_roots_time,
                'evacuate_collection_set_time': event.evacuate_collection_set_time,
                'post_evacuate_time': event.post_evacuate_time,
                'other_time': event.other_time,
                'mark_live_objects_time': event.mark_live_objects_time,
                'prepare_compaction_time': event.prepare_compaction_time,
                'adjust_pointers_time': event.adjust_pointers_time,
                'compact_heap_time': event.compact_heap_time,
                'workers_used': event.workers_used,
                'workers_total': event.workers_total,
                'user_time': event.user_time,
                'sys_time': event.sys_time,
                'real_time': event.real_time,
                'is_abnormal': event.is_abnormal,
                'abnormal_reason': event.abnormal_reason
            })
        
        return {
            'gc_count': gc_count,
            'total_pause': total_pause,
            'avg_pause': avg_pause,
            'max_pause': max_pause,
            'min_pause': min_pause,
            'memory_stats': memory_stats,
            'region_stats': region_stats,
            'abnormal_analysis': abnormal_analysis,
            'events': serializable_events
        }
    
    def _analyze_abnormal_situations(self, events: List[G1GCEvent]) -> Dict:
        """分析异常GC情况并提供诊断建议"""
        abnormal_events = [event for event in events if event.is_abnormal]
        abnormal_count = len(abnormal_events)
        has_abnormal_events = abnormal_count > 0
        
        abnormal_reasons = []
        if abnormal_events:
            abnormal_reasons = list(set([event.abnormal_reason for event in abnormal_events if event.abnormal_reason]))
        
        # 分析连续Full GC情况
        consecutive_full_gc_count = self._count_consecutive_full_gc(events)
        
        # 分析内存泄漏疑似情况
        memory_leak_suspected = self._detect_memory_leak_patterns(events)
        
        # 生成建议
        recommendations = self._generate_recommendations(events, consecutive_full_gc_count, memory_leak_suspected, abnormal_events)
        
        return {
            'has_abnormal_events': has_abnormal_events,
            'abnormal_count': abnormal_count,
            'abnormal_reasons': abnormal_reasons,
            'consecutive_full_gc_count': consecutive_full_gc_count,
            'memory_leak_suspected': memory_leak_suspected,
            'recommendations': recommendations
        }
    
    def _count_consecutive_full_gc(self, events: List[G1GCEvent]) -> int:
        """计算连续Full GC次数"""
        max_consecutive = 0
        current_consecutive = 0
        
        for event in events:
            if event.gc_type == 'full':
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0
                
        return max_consecutive
    
    def _detect_memory_leak_patterns(self, events: List[G1GCEvent]) -> bool:
        """检测内存泄漏模式"""
        heap_events = [event for event in events if event.heap_before > 0 and event.heap_after > 0]
        if len(heap_events) < 5:
            return False
            
        # 检查是否存在多次Full GC后内存仍然很高的情况
        full_gc_events = [event for event in heap_events if event.gc_type == 'full']
        if len(full_gc_events) >= 3:
            # 检查Full GC后内存使用率
            high_memory_after_full_gc = 0
            for event in full_gc_events:
                if event.heap_total > 0:
                    memory_usage_rate = (event.heap_after / event.heap_total) * 100
                    if memory_usage_rate > 80:  # 超过80%认为异常
                        high_memory_after_full_gc += 1
                        
            if high_memory_after_full_gc >= 2:
                return True
                
        # 检查是否存在内存无法回收的情况
        no_reclaim_count = 0
        for event in heap_events:
            if event.heap_before == event.heap_after and event.heap_before > 0:
                no_reclaim_count += 1
                
        if no_reclaim_count >= 3:
            return True
            
        return False
    
    def _generate_recommendations(self, events: List[G1GCEvent], consecutive_full_gc: int, 
                                memory_leak_suspected: bool, abnormal_events: List[G1GCEvent]) -> List[str]:
        """生成优化建议"""
        recommendations = []
        
        # 基于连续Full GC的建议
        if consecutive_full_gc >= 3:
            recommendations.append(
                f'检测到{consecutive_full_gc}次连续Full GC，建议检查堆内存设置是否过小或存在内存泄漏'
            )
            recommendations.append('建议调整G1HeapRegionSize和增加堆内存大小')
            
        # 基于内存泄漏的建议
        if memory_leak_suspected:
            recommendations.append('怀疑存在内存泄漏，建议使用heap dump工具分析内存使用情况')
            recommendations.append('建议检查应用程序中的大对象和长期引用')
            
        # 基于异常事件的建议
        if abnormal_events:
            concurrent_aborts = [event for event in abnormal_events if 'Abort' in (event.abnormal_reason or '')]
            if concurrent_aborts:
                recommendations.append('检测到并发标记被中止，建议调整G1ConcRefinementThreads参数')
                
        # 基于GC频率的建议
        full_gc_events = [event for event in events if event.gc_type == 'full']
        if len(full_gc_events) > len(events) * 0.1:  # Full GC超过10%
            recommendations.append('Full GC次数过多，建议检查应用程序的对象分配模式')
            
        # 基于暂停时间的建议
        pause_events = [event for event in events if event.pause_time > 0]
        if pause_events:
            long_pause_events = [event for event in pause_events if event.pause_time > 100]  # 超过100ms
            if len(long_pause_events) > len(pause_events) * 0.2:  # 超过20%的事件暂停时间过长
                recommendations.append('检测到较多长暂停事件，建议调整MaxGCPauseMillis参数')
                
        if not recommendations:
            recommendations.append('GC表现正常，暂无优化建议')
            
        return recommendations


# 提供便捷的函数接口
def parse_gc_log(log_content: str) -> Dict:
    """解析G1 GC日志的便捷函数"""
    parser = G1LogParser()
    return parser.parse_gc_log(log_content)


if __name__ == '__main__':
    # 基于现代JVM统一日志格式的测试代码
    sample_log = """
[2025-08-26T15:03:29.558+0800][3.715s][info][gc,start    ] GC(0) Pause Young (Normal) (G1 Evacuation Pause)
[2025-08-26T15:03:29.561+0800][3.718s][info][gc,task     ] GC(0) Using 4 workers of 4 for evacuation
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,phases   ] GC(0)   Pre Evacuate Collection Set: 0.1ms
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,phases   ] GC(0)   Evacuate Collection Set: 20.1ms
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,heap     ] GC(0) Eden regions: 170->0(150)
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,heap     ] GC(0) Survivor regions: 0->20(22)
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,heap     ] GC(0) Old regions: 0->0
[2025-08-26T15:03:29.583+0800][3.740s][info][gc          ] GC(0) Pause Young (Normal) (G1 Evacuation Pause) 173M->23M(512M) 24.846ms
[2025-08-26T15:03:29.583+0800][3.740s][info][gc,cpu      ] GC(0) User=0.07s Sys=0.00s Real=0.03s
[2025-08-26T15:27:20.684+0800][1434.841s][info][gc             ] GC(5098) Pause Full (G1 Compaction Pause) 510M->510M(512M) 654.933ms
[2025-08-26T15:27:20.684+0800][1434.841s][info][gc,cpu         ] GC(5098) User=2.40s Sys=0.00s Real=0.66s
"""
    result = parse_gc_log(sample_log)
    print(f"解析结果: {result}")
    
    # 打印异常分析结果
    if result['abnormal_analysis']['has_abnormal_events']:
        print("\n=== 异常情况检测 ===")
        print(f"异常事件数量: {result['abnormal_analysis']['abnormal_count']}")
        print(f"连续Full GC次数: {result['abnormal_analysis']['consecutive_full_gc_count']}")
        print(f"疑似内存泄漏: {result['abnormal_analysis']['memory_leak_suspected']}")
        print("\n优化建议:")
        for recommendation in result['abnormal_analysis']['recommendations']:
            print(f"- {recommendation}")