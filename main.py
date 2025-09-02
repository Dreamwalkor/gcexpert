#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志分析MCP服务器
提供标准化的MCP接口用于GC日志分析功能
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# 导入MCP库
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    TextContent,
    Tool,
    EmbeddedResource,
)

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入我们的GC分析模块
from parser.g1_parser import parse_gc_log as parse_g1_log
from parser.ibm_parser import parse_gc_log as parse_j9_log
from utils.log_loader import LogLoader, GCLogType
from analyzer.metrics import analyze_gc_metrics, GCMetricsAnalyzer
from analyzer.report_generator import generate_gc_report
from rules.alert_engine import GCAlertEngine

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建MCP服务器实例
app = Server("gc-log-analyzer")

# 全局状态
current_analysis_result = None
metrics_analyzer = GCMetricsAnalyzer()
alert_engine = GCAlertEngine()


@app.list_tools()
async def list_tools() -> List[Tool]:
    """
    返回可用的工具列表
    """
    return [
        Tool(
            name="analyze_gc_log",
            description="分析GC日志文件，支持G1和IBM J9VM格式",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "GC日志文件的路径"
                    },
                    "analysis_type": {
                        "type": "string",
                        "enum": ["basic", "detailed"],
                        "description": "分析类型：basic(基础统计) 或 detailed(详细指标)",
                        "default": "detailed"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_gc_metrics",
            description="获取上次分析的详细性能指标",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "throughput", "latency", "frequency", 
                                "memory", "trends", "health", "all"
                            ]
                        },
                        "description": "要获取的指标类型",
                        "default": ["all"]
                    }
                }
            }
        ),
        Tool(
            name="compare_gc_logs",
            description="比较两个GC日志文件的性能差异",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path_1": {
                        "type": "string",
                        "description": "第一个GC日志文件路径"
                    },
                    "file_path_2": {
                        "type": "string",
                        "description": "第二个GC日志文件路径"
                    }
                },
                "required": ["file_path_1", "file_path_2"]
            }
        ),
        Tool(
            name="detect_gc_issues",
            description="检测GC性能问题和给出优化建议",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold_config": {
                        "type": "object",
                        "description": "自定义阈值配置（可选）",
                        "properties": {
                            "max_pause_time": {"type": "number", "default": 100},
                            "min_throughput": {"type": "number", "default": 95}
                        }
                    }
                }
            }
        ),
        Tool(
            name="generate_gc_report",
            description="生成专业的GC性能分析报告（HTML或Markdown格式）",
            inputSchema={
                "type": "object",
                "properties": {
                    "format_type": {
                        "type": "string",
                        "enum": ["markdown", "html"],
                        "description": "报告格式：markdown 或 html",
                        "default": "markdown"
                    },
                    "output_file": {
                        "type": "string",
                        "description": "输出文件路径（可选）"
                    },
                    "include_alerts": {
                        "type": "boolean",
                        "description": "是否包含性能警报信息",
                        "default": "true"
                    }
                }
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """
    处理工具调用请求
    """
    try:
        if name == "analyze_gc_log":
            return await analyze_gc_log_tool(arguments)
        elif name == "get_gc_metrics":
            return await get_gc_metrics_tool(arguments)
        elif name == "compare_gc_logs":
            return await compare_gc_logs_tool(arguments)
        elif name == "detect_gc_issues":
            return await detect_gc_issues_tool(arguments)
        elif name == "generate_gc_report":
            return await generate_gc_report_tool(arguments)
        else:
            raise ValueError(f"未知工具: {name}")
    
    except Exception as e:
        logger.error(f"工具调用错误 {name}: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 错误: {str(e)}"
                )
            ]
        )


async def analyze_gc_log_tool(arguments: Dict[str, Any]) -> CallToolResult:
    """
    分析GC日志文件工具
    """
    global current_analysis_result
    
    try:
        # 参数验证
        file_path = arguments.get("file_path")
        analysis_type = arguments.get("analysis_type", "detailed")
        
        if not file_path:
            raise ValueError("缺少必需参数 file_path")
        
        if not isinstance(file_path, str):
            raise ValueError(f"file_path 必须是字符串，当前类型: {type(file_path).__name__}")
        
        if analysis_type not in ["basic", "detailed"]:
            raise ValueError(f"analysis_type 必须是 'basic' 或 'detailed'，当前值: {analysis_type}")
        
        # 文件存在性检查
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 文件可读性检查
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"文件不可读: {file_path}")
        
        # 文件大小检查（限制为100MB）
        file_size = os.path.getsize(file_path)
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            raise ValueError(f"文件过大: {file_size / (1024*1024):.1f}MB，最大支持: {max_size / (1024*1024):.1f}MB")
        
        # 加载日志文件
        try:
            loader = LogLoader()
            log_content, log_type = loader.load_log_file(file_path)
        except Exception as e:
            raise ValueError(f"日志文件加载失败: {str(e)}")
        
        # 根据日志类型选择解析器
        try:
            if log_type == GCLogType.G1:
                parse_result = parse_g1_log(log_content)
                parser_type = "G1 GC"
            elif log_type == GCLogType.IBM_J9:
                parse_result = parse_j9_log(log_content)
                parser_type = "IBM J9VM"
            else:
                raise ValueError(f"不支持的日志格式: {log_type}")
        except Exception as e:
            raise ValueError(f"日志解析失败: {str(e)}")
        
        # 验证解析结果
        if not parse_result or not isinstance(parse_result, dict):
            raise ValueError("日志解析结果无效")
        
        # 分析性能指标
        events = parse_result.get('events', [])
        if not events:
            logger.warning(f"日志文件中未找到GC事件: {file_path}")
            metrics = None
        else:
            try:
                metrics = analyze_gc_metrics(events)
            except Exception as e:
                logger.error(f"指标分析失败: {e}")
                metrics = None
        
        # 保存分析结果到全局状态
        current_analysis_result = {
            'file_path': file_path,
            'log_type': log_type.value,
            'parser_type': parser_type,
            'parse_result': parse_result,
            'metrics': metrics,
            'events_count': len(events)
        }
        
        # 生成分析报告
        try:
            if analysis_type == "basic":
                report = generate_basic_report(parse_result, metrics, parser_type)
            else:
                report = generate_detailed_report(parse_result, metrics, parser_type)
        except Exception as e:
            raise ValueError(f"报告生成失败: {str(e)}")
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text", 
                    text=report
                )
            ]
        )
        
    except Exception as e:
        logger.error(f"analyze_gc_log_tool 执行失败: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 分析失败: {str(e)}"
                )
            ]
        )


async def get_gc_metrics_tool(arguments: Dict[str, Any]) -> CallToolResult:
    """
    获取GC指标工具
    """
    global current_analysis_result
    
    try:
        # 检查是否有分析结果
        if not current_analysis_result:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 请先使用 analyze_gc_log 工具分析一个日志文件"
                    )
                ]
            )
        
        # 参数验证
        metric_types = arguments.get("metric_types", ["all"])
        if not isinstance(metric_types, list):
            metric_types = [metric_types] if isinstance(metric_types, str) else ["all"]
        
        # 验证指标类型
        valid_types = ["all", "throughput", "latency", "frequency", "memory", "trends", "health"]
        invalid_types = [t for t in metric_types if t not in valid_types]
        if invalid_types:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 无效的指标类型: {invalid_types}\n支持的类型: {valid_types}"
                    )
                ]
            )
        
        # 获取指标数据
        metrics = current_analysis_result.get('metrics')
        if not metrics:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 没有可用的指标数据，请检查日志文件是否包含GC事件"
                    )
                ]
            )
        
        # 生成指标报告
        try:
            report = generate_metrics_report(metrics, metric_types)
        except Exception as e:
            logger.error(f"指标报告生成失败: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 指标报告生成失败: {str(e)}"
                    )
                ]
            )
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=report
                )
            ]
        )
        
    except Exception as e:
        logger.error(f"get_gc_metrics_tool 执行失败: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 获取指标失败: {str(e)}"
                )
            ]
        )


async def compare_gc_logs_tool(arguments: Dict[str, Any]) -> CallToolResult:
    """
    比较GC日志工具
    """
    try:
        # 参数验证
        file_path_1 = arguments.get("file_path_1")
        file_path_2 = arguments.get("file_path_2")
        
        if not file_path_1 or not file_path_2:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 缺少必需参数: file_path_1 和 file_path_2"
                    )
                ]
            )
        
        if not isinstance(file_path_1, str) or not isinstance(file_path_2, str):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 文件路径必须是字符串"
                    )
                ]
            )
        
        if file_path_1 == file_path_2:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 不能比较相同的文件"
                    )
                ]
            )
        
        # 分析两个文件
        results = []
        for i, file_path in enumerate([file_path_1, file_path_2], 1):
            try:
                # 文件检查
                if not os.path.exists(file_path):
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=f"❌ 文件{i}不存在: {file_path}"
                            )
                        ]
                    )
                
                if not os.access(file_path, os.R_OK):
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=f"❌ 文件{i}不可读: {file_path}"
                            )
                        ]
                    )
                
                # 加载和解析文件
                loader = LogLoader()
                log_content, log_type = loader.load_log_file(file_path)
                
                if log_type == GCLogType.G1:
                    parse_result = parse_g1_log(log_content)
                elif log_type == GCLogType.IBM_J9:
                    parse_result = parse_j9_log(log_content)
                else:
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=f"❌ 文件{i}不支持的日志格式: {log_type}"
                            )
                        ]
                    )
                
                events = parse_result.get('events', [])
                if not events:
                    logger.warning(f"文件{i}中未找到GC事件: {file_path}")
                    metrics = None
                else:
                    metrics = analyze_gc_metrics(events)
                
                results.append({
                    'file_path': file_path,
                    'log_type': log_type.value,
                    'metrics': metrics,
                    'events_count': len(events)
                })
                
            except Exception as e:
                logger.error(f"处理文件{i}失败: {e}")
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"❌ 处理文件{i}失败: {str(e)}"
                        )
                    ]
                )
        
        # 检查是否有有效的指标数据
        if not results[0]['metrics'] or not results[1]['metrics']:
            missing_files = []
            if not results[0]['metrics']:
                missing_files.append("文件1")
            if not results[1]['metrics']:
                missing_files.append("文件2")
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ {', '.join(missing_files)}缺少有效的GC数据，无法进行比较"
                    )
                ]
            )
        
        # 生成比较报告
        try:
            report = generate_comparison_report(results[0], results[1])
        except Exception as e:
            logger.error(f"比较报告生成失败: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 比较报告生成失败: {str(e)}"
                    )
                ]
            )
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=report
                )
            ]
        )
        
    except Exception as e:
        logger.error(f"compare_gc_logs_tool 执行失败: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 比较失败: {str(e)}"
                )
            ]
        )


async def detect_gc_issues_tool(arguments: Dict[str, Any]) -> CallToolResult:
    """
    检测GC问题工具
    """
    global current_analysis_result
    
    try:
        # 检查是否有分析结果
        if not current_analysis_result:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 请先使用 analyze_gc_log 工具分析一个日志文件"
                    )
                ]
            )
        
        # 参数验证
        threshold_config = arguments.get("threshold_config", {})
        if not isinstance(threshold_config, dict):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ threshold_config 必须是字典类型"
                    )
                ]
            )
        
        # 验证阈值参数
        if "max_pause_time" in threshold_config:
            max_pause_time = threshold_config["max_pause_time"]
            if not isinstance(max_pause_time, (int, float)) or max_pause_time <= 0:
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="❌ max_pause_time 必须是正数"
                        )
                    ]
                )
        
        if "min_throughput" in threshold_config:
            min_throughput = threshold_config["min_throughput"]
            if not isinstance(min_throughput, (int, float)) or not (0 <= min_throughput <= 100):
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text="❌ min_throughput 必须是 0-100 之间的数值"
                        )
                    ]
                )
        
        # 获取指标数据
        metrics = current_analysis_result.get('metrics')
        if not metrics:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 没有可用的指标数据，请检查日志文件是否包含GC事件"
                    )
                ]
            )
        
        # 生成问题检测报告
        try:
            report = generate_issues_report(metrics, threshold_config)
        except Exception as e:
            logger.error(f"问题检测报告生成失败: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 问题检测失败: {str(e)}"
                    )
                ]
            )
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=report
                )
            ]
        )
        
    except Exception as e:
        logger.error(f"detect_gc_issues_tool 执行失败: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 检测失败: {str(e)}"
                )
            ]
        )


async def generate_gc_report_tool(arguments: Dict[str, Any]) -> CallToolResult:
    """
    生成GC分析报告工具
    """
    global current_analysis_result, alert_engine
    
    try:
        # 检查是否有分析结果
        if not current_analysis_result:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 请先使用 analyze_gc_log 工具分析一个日志文件"
                    )
                ]
            )
        
        # 参数验证
        format_type = arguments.get("format_type", "markdown")
        output_file = arguments.get("output_file")
        include_alerts = arguments.get("include_alerts", True)
        
        if format_type not in ["markdown", "html"]:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ format_type 必须是 'markdown' 或 'html'"
                    )
                ]
            )
        
        if output_file and not isinstance(output_file, str):
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ output_file 必须是字符串类型"
                    )
                ]
            )
        
        if not isinstance(include_alerts, bool):
            include_alerts = bool(include_alerts)
        
        # 棄取数据
        metrics = current_analysis_result.get('metrics')
        parse_result = current_analysis_result.get('parse_result', {})
        
        if not metrics:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="❌ 没有可用的指标数据，请检查日志文件是否包含GC事件"
                    )
                ]
            )
        
        # 准备分析数据
        analysis_data = {
            'gc_type': current_analysis_result.get('parser_type', 'Unknown'),
            'file_path': current_analysis_result.get('file_path', 'Unknown'),
            'total_events': current_analysis_result.get('events_count', 0)
        }
        
        # 转换指标数据为字典格式
        try:
            metrics_data = {
                'throughput': {
                    'app_time_percentage': metrics.throughput_percentage,
                    'gc_time_percentage': metrics.gc_overhead_percentage
                },
                'latency': {
                    'avg_pause_time': metrics.avg_pause_time,
                    'max_pause_time': metrics.max_pause_time,
                    'p50_pause_time': metrics.p50_pause_time,
                    'p95_pause_time': metrics.p95_pause_time,
                    'p99_pause_time': metrics.p99_pause_time,
                    'min_pause_time': metrics.min_pause_time
                },
                'frequency': {
                    'gc_frequency': metrics.gc_frequency,
                    'young_gc_frequency': metrics.young_gc_frequency,
                    'full_gc_frequency': metrics.full_gc_frequency
                },
                'memory': {
                    'avg_heap_utilization': metrics.avg_heap_utilization,
                    'max_heap_utilization': metrics.max_heap_utilization,
                    'memory_allocation_rate': metrics.memory_allocation_rate,
                    'memory_reclaim_efficiency': metrics.memory_reclaim_efficiency
                }
            }
        except AttributeError as e:
            logger.error(f"指标数据转换失败: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 指标数据格式错误: {str(e)}"
                    )
                ]
            )
        
        # 生成警报（如果需要）
        alerts_data = None
        if include_alerts:
            try:
                # 使用警报引擎分析指标
                if metrics:
                    alerts = alert_engine.evaluate_metrics(metrics)
                    alerts_data = [{
                        'severity': alert.severity.value,
                        'category': alert.category.value,
                        'message': alert.message,
                        'details': alert.recommendation,
                        'threshold': alert.threshold
                    } for alert in alerts]
            except Exception as e:
                logger.warning(f"警报生成失败，将跳过: {e}")
                alerts_data = None
        
        # 检查输出文件目录是否可写
        if output_file:
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except OSError as e:
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=f"❌ 无法创建输出目录: {str(e)}"
                            )
                        ]
                    )
            
            if output_dir and not os.access(output_dir, os.W_OK):
                return CallToolResult(
                    content=[
                        TextContent(
                            type="text",
                            text=f"❌ 输出目录不可写: {output_dir}"
                        )
                    ]
                )
        
        # 生成报告
        try:
            report_content = generate_gc_report(
                analysis_data=analysis_data,
                metrics_data=metrics_data,
                alerts_data=alerts_data,
                format_type=format_type,
                output_file=output_file
            )
            
            result_text = f"✅ {format_type.upper()}格式的GC分析报告已生成\n\n"
            
            if output_file:
                result_text += f"📁 报告已保存到: {output_file}\n\n"
            
            # 如果是Markdown格式，直接显示内容
            if format_type.lower() == "markdown":
                # 限制显示长度以避免输出过长
                max_display_length = 3000
                if len(report_content) > max_display_length:
                    result_text += f"📋 报告内容预览（前{max_display_length}个字符）:\n\n" + report_content[:max_display_length] + "\n\n...内容过长，已截断"
                else:
                    result_text += "📋 报告内容:\n\n" + report_content
            else:
                result_text += "🌐 HTML报告已生成，请查看输出文件"
            
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=result_text
                    )
                ]
            )
            
        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"❌ 生成报告失败: {str(e)}"
                    )
                ]
            )
            
    except Exception as e:
        logger.error(f"generate_gc_report_tool 执行失败: {e}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"❌ 报告生成失败: {str(e)}"
                )
            ]
        )


def generate_basic_report(parse_result: Dict, metrics: Any, parser_type: str) -> str:
    """生成基础分析报告"""
    gc_count = parse_result.get('gc_count', {})
    
    report = f"""
## 📊 GC日志基础分析报告

### 日志信息
- **解析器类型**: {parser_type}
- **总GC次数**: {gc_count.get('total', 0)}

### GC统计
"""
    
    for gc_type, count in gc_count.items():
        if gc_type != 'total' and count > 0:
            report += f"- **{gc_type.title()} GC**: {count}次\n"
    
    if metrics:
        report += f"""
### 关键指标
- **性能评分**: {metrics.performance_score:.1f}/100
- **健康状态**: {metrics.health_status}
- **吞吐量**: {metrics.throughput_percentage:.1f}%
- **平均停顿**: {metrics.avg_pause_time:.1f}ms
- **最大停顿**: {metrics.max_pause_time:.1f}ms
"""
    
    return report.strip()


def generate_detailed_report(parse_result: Dict, metrics: Any, parser_type: str) -> str:
    """生成详细分析报告"""
    basic_report = generate_basic_report(parse_result, metrics, parser_type)
    
    if not metrics:
        return basic_report
    
    detailed_section = f"""

### 📈 详细性能指标

#### 吞吐量指标
- **应用吞吐量**: {metrics.throughput_percentage:.2f}%
- **GC开销**: {metrics.gc_overhead_percentage:.2f}%

#### 延迟指标
- **平均停顿**: {metrics.avg_pause_time:.1f}ms
- **P50停顿**: {metrics.p50_pause_time:.1f}ms
- **P95停顿**: {metrics.p95_pause_time:.1f}ms
- **P99停顿**: {metrics.p99_pause_time:.1f}ms
- **最大停顿**: {metrics.max_pause_time:.1f}ms
- **最小停顿**: {metrics.min_pause_time:.1f}ms

#### 频率指标
- **总GC频率**: {metrics.gc_frequency:.2f} 次/秒
- **Young GC频率**: {metrics.young_gc_frequency:.2f} 次/秒
- **Full GC频率**: {metrics.full_gc_frequency:.2f} 次/秒

#### 内存指标
- **平均堆利用率**: {metrics.avg_heap_utilization:.1f}%
- **最大堆利用率**: {metrics.max_heap_utilization:.1f}%
- **内存分配率**: {metrics.memory_allocation_rate:.1f}MB/事件
- **内存回收效率**: {metrics.memory_reclaim_efficiency:.1f}%

#### 趋势分析
- **停顿时间趋势**: {metrics.pause_time_trend}
- **内存使用趋势**: {metrics.memory_usage_trend}

### 🎯 性能评估
- **综合评分**: {metrics.performance_score:.1f}/100
- **健康状态**: {metrics.health_status}
"""
    
    return basic_report + detailed_section


def generate_metrics_report(metrics: Any, metric_types: List[str]) -> str:
    """生成指标报告"""
    report = "## 📊 GC性能指标详情\n\n"
    
    if "all" in metric_types or "throughput" in metric_types:
        report += f"""### 🚀 吞吐量指标
- 应用吞吐量: {metrics.throughput_percentage:.2f}%
- GC开销: {metrics.gc_overhead_percentage:.2f}%

"""
    
    if "all" in metric_types or "latency" in metric_types:
        report += f"""### ⏱️ 延迟指标
- 平均停顿: {metrics.avg_pause_time:.1f}ms
- P50停顿: {metrics.p50_pause_time:.1f}ms
- P95停顿: {metrics.p95_pause_time:.1f}ms
- P99停顿: {metrics.p99_pause_time:.1f}ms
- 最大停顿: {metrics.max_pause_time:.1f}ms

"""
    
    if "all" in metric_types or "frequency" in metric_types:
        report += f"""### 📊 频率指标
- 总GC频率: {metrics.gc_frequency:.2f} 次/秒
- Young GC频率: {metrics.young_gc_frequency:.2f} 次/秒
- Full GC频率: {metrics.full_gc_frequency:.2f} 次/秒

"""
    
    if "all" in metric_types or "memory" in metric_types:
        report += f"""### 💾 内存指标
- 平均堆利用率: {metrics.avg_heap_utilization:.1f}%
- 最大堆利用率: {metrics.max_heap_utilization:.1f}%
- 内存回收效率: {metrics.memory_reclaim_efficiency:.1f}%

"""
    
    if "all" in metric_types or "trends" in metric_types:
        report += f"""### 📈 趋势分析
- 停顿时间趋势: {metrics.pause_time_trend}
- 内存使用趋势: {metrics.memory_usage_trend}

"""
    
    if "all" in metric_types or "health" in metric_types:
        report += f"""### 🎯 健康评估
- 性能评分: {metrics.performance_score:.1f}/100
- 健康状态: {metrics.health_status}
"""
    
    return report.strip()


def generate_comparison_report(result1: Dict, result2: Dict) -> str:
    """生成比较报告"""
    metrics1 = result1.get('metrics')
    metrics2 = result2.get('metrics')
    
    if not metrics1 or not metrics2:
        return "❌ 无法比较：缺少性能指标数据"
    
    # 计算差异
    throughput_diff = metrics2.throughput_percentage - metrics1.throughput_percentage
    latency_diff = metrics2.avg_pause_time - metrics1.avg_pause_time
    score_diff = metrics2.performance_score - metrics1.performance_score
    
    report = f"""## 📊 GC日志对比分析

### 文件信息
- **文件1**: {result1['file_path']} ({result1['log_type']})
- **文件2**: {result2['file_path']} ({result2['log_type']})

### 关键指标对比

| 指标 | 文件1 | 文件2 | 差异 |
|------|-------|-------|------|
| 性能评分 | {metrics1.performance_score:.1f} | {metrics2.performance_score:.1f} | {score_diff:+.1f} |
| 吞吐量 | {metrics1.throughput_percentage:.1f}% | {metrics2.throughput_percentage:.1f}% | {throughput_diff:+.1f}% |
| 平均停顿 | {metrics1.avg_pause_time:.1f}ms | {metrics2.avg_pause_time:.1f}ms | {latency_diff:+.1f}ms |
| P95停顿 | {metrics1.p95_pause_time:.1f}ms | {metrics2.p95_pause_time:.1f}ms | {metrics2.p95_pause_time - metrics1.p95_pause_time:+.1f}ms |
| GC频率 | {metrics1.gc_frequency:.2f}/s | {metrics2.gc_frequency:.2f}/s | {metrics2.gc_frequency - metrics1.gc_frequency:+.2f}/s |

### 📈 分析结论
"""
    
    if score_diff > 5:
        report += "✅ 文件2的性能明显优于文件1\n"
    elif score_diff < -5:
        report += "❌ 文件2的性能明显劣于文件1\n"
    else:
        report += "➖ 两个文件的性能差异不大\n"
    
    if throughput_diff > 1:
        report += f"📈 文件2的吞吐量提升了{throughput_diff:.1f}%\n"
    elif throughput_diff < -1:
        report += f"📉 文件2的吞吐量下降了{abs(throughput_diff):.1f}%\n"
    
    if latency_diff < -10:
        report += f"⚡ 文件2的停顿时间减少了{abs(latency_diff):.1f}ms\n"
    elif latency_diff > 10:
        report += f"🐌 文件2的停顿时间增加了{latency_diff:.1f}ms\n"
    
    return report


def generate_issues_report(metrics: Any, threshold_config: Dict) -> str:
    """生成问题检测报告"""
    max_pause_time = threshold_config.get("max_pause_time", 100)
    min_throughput = threshold_config.get("min_throughput", 95)
    
    issues = []
    recommendations = []
    
    # 检测停顿时间问题
    if metrics.max_pause_time > max_pause_time:
        issues.append(f"⚠️ 最大停顿时间过长: {metrics.max_pause_time:.1f}ms (阈值: {max_pause_time}ms)")
        recommendations.append("考虑调整GC参数减少停顿时间")
    
    if metrics.p99_pause_time > max_pause_time * 0.8:
        issues.append(f"⚠️ P99停顿时间较高: {metrics.p99_pause_time:.1f}ms")
        recommendations.append("检查是否有内存分配峰值")
    
    # 检测吞吐量问题
    if metrics.throughput_percentage < min_throughput:
        issues.append(f"⚠️ 吞吐量过低: {metrics.throughput_percentage:.1f}% (阈值: {min_throughput}%)")
        recommendations.append("考虑优化GC策略以提高吞吐量")
    
    # 检测GC频率问题
    if metrics.gc_frequency > 10:
        issues.append(f"⚠️ GC频率过高: {metrics.gc_frequency:.1f} 次/秒")
        recommendations.append("检查是否存在内存泄漏或分配过于频繁")
    
    if metrics.full_gc_frequency > 0.1:
        issues.append(f"⚠️ Full GC频率较高: {metrics.full_gc_frequency:.2f} 次/秒")
        recommendations.append("Full GC频繁可能表示堆大小不足或存在内存泄漏")
    
    # 检测趋势问题
    if metrics.pause_time_trend == "increasing":
        issues.append("📈 停顿时间呈上升趋势")
        recommendations.append("监控内存使用情况，可能需要调整堆大小")
    
    if metrics.memory_usage_trend == "increasing":
        issues.append("📈 内存使用呈上升趋势")
        recommendations.append("检查是否存在内存泄漏")
    
    # 生成报告
    report = f"""## 🔍 GC性能问题检测报告

### 当前状态
- **健康状态**: {metrics.health_status}
- **性能评分**: {metrics.performance_score:.1f}/100

"""
    
    if issues:
        report += "### ⚠️ 发现的问题\n"
        for issue in issues:
            report += f"- {issue}\n"
        report += "\n"
    else:
        report += "### ✅ 未发现明显性能问题\n\n"
    
    if recommendations:
        report += "### 💡 优化建议\n"
        for rec in recommendations:
            report += f"- {rec}\n"
        report += "\n"
    
    # 添加详细指标
    report += f"""### 📊 详细指标
- **吞吐量**: {metrics.throughput_percentage:.1f}%
- **平均停顿**: {metrics.avg_pause_time:.1f}ms
- **P99停顿**: {metrics.p99_pause_time:.1f}ms
- **GC频率**: {metrics.gc_frequency:.2f} 次/秒
- **内存回收效率**: {metrics.memory_reclaim_efficiency:.1f}%
"""
    
    return report


async def main():
    """
    MCP服务器主函数
    """
    logger.info("🚀 启动GC日志分析MCP服务器...")
    
    # 使用stdio传输运行服务器
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())