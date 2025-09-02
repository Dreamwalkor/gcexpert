#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP服务器测试用例
使用测试驱动开发（TDD）方法验证MCP功能正确性
"""

import os
import sys
import pytest
import asyncio
import tempfile

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from main import (
    analyze_gc_log_tool,
    get_gc_metrics_tool,
    compare_gc_logs_tool,
    detect_gc_issues_tool,
    list_tools,
    app
)
from mcp.types import Tool, CallToolResult


class TestMCPServer:
    """MCP服务器测试类"""
    
    def setup_method(self):
        """测试前的设置"""
        self.test_data_dir = os.path.join(project_root, 'test', 'data')
        self.sample_g1_log = os.path.join(self.test_data_dir, 'sample_g1.log')
        self.sample_j9_log = os.path.join(self.test_data_dir, 'sample_j9.log')
    
    @pytest.mark.asyncio
    async def test_list_tools(self):
        """测试工具列表功能"""
        tools = await list_tools()
        
        # 验证工具数量和名称
        assert len(tools) == 5, f"期望5个工具，实际得到{len(tools)}个"
        
        tool_names = [tool.name for tool in tools]
        expected_tools = [
            "analyze_gc_log",
            "get_gc_metrics", 
            "compare_gc_logs",
            "detect_gc_issues",
            "generate_gc_report"  # 新增的工具
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"缺少工具: {expected_tool}"
        
        # 验证工具结构
        for tool in tools:
            assert isinstance(tool, Tool), "工具应该是Tool类型"
            assert hasattr(tool, 'name'), "工具应该有name属性"
            assert hasattr(tool, 'description'), "工具应该有description属性"
            assert hasattr(tool, 'inputSchema'), "工具应该有inputSchema属性"
            
            # 验证输入模式结构
            schema = tool.inputSchema
            assert isinstance(schema, dict), "inputSchema应该是字典"
            assert 'type' in schema, "inputSchema应该有type字段"
            assert schema['type'] == 'object', "inputSchema type应该是object"
    
    @pytest.mark.asyncio
    async def test_analyze_gc_log_tool_g1(self):
        """测试G1日志分析工具"""
        if not os.path.exists(self.sample_g1_log):
            pytest.skip("G1测试数据文件不存在")
        
        # 测试基础分析
        result = await analyze_gc_log_tool({
            "file_path": self.sample_g1_log,
            "analysis_type": "basic"
        })
        
        # 验证结果结构
        assert isinstance(result, CallToolResult), "结果应该是CallToolResult类型"
        assert result.content, "结果应该有内容"
        assert len(result.content) > 0, "结果内容不应该为空"
        
        content_text = result.content[0].text
        assert "GC日志基础分析报告" in content_text, "应该包含报告标题"
        assert "G1 GC" in content_text, "应该识别为G1 GC"
        assert "总GC次数" in content_text, "应该包含GC次数统计"
        
        # 测试详细分析
        result = await analyze_gc_log_tool({
            "file_path": self.sample_g1_log,
            "analysis_type": "detailed"
        })
        
        content_text = result.content[0].text
        assert "详细性能指标" in content_text, "详细分析应该包含性能指标"
        assert "吞吐量指标" in content_text, "应该包含吞吐量指标"
        assert "延迟指标" in content_text, "应该包含延迟指标"
    
    @pytest.mark.asyncio
    async def test_analyze_gc_log_tool_j9(self):
        """测试J9日志分析工具"""
        if not os.path.exists(self.sample_j9_log):
            pytest.skip("J9测试数据文件不存在")
        
        result = await analyze_gc_log_tool({
            "file_path": self.sample_j9_log,
            "analysis_type": "detailed"
        })
        
        # 验证结果
        assert isinstance(result, CallToolResult), "结果应该是CallToolResult类型"
        content_text = result.content[0].text
        assert "IBM J9VM" in content_text, "应该识别为IBM J9VM"
        assert "GC日志" in content_text, "应该包含GC日志标识"
    
    @pytest.mark.asyncio
    async def test_analyze_gc_log_tool_errors(self):
        """测试分析工具的错误处理"""
        # 测试文件不存在的情况
        result = await analyze_gc_log_tool({
            "file_path": "/nonexistent/path/test.log",
            "analysis_type": "basic"
        })
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
        
        # 测试缺少参数的情况
        result = await analyze_gc_log_tool({})
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
    
    @pytest.mark.asyncio
    async def test_get_gc_metrics_tool(self):
        """测试获取GC指标工具"""
        # 先分析一个日志文件
        if os.path.exists(self.sample_g1_log):
            await analyze_gc_log_tool({
                "file_path": self.sample_g1_log,
                "analysis_type": "detailed"
            })
        else:
            pytest.skip("需要先有分析数据")
        
        # 测试获取所有指标
        result = await get_gc_metrics_tool({
            "metric_types": ["all"]
        })
        
        content_text = result.content[0].text
        assert "GC性能指标详情" in content_text, "应该包含指标详情标题"
        assert "吞吐量指标" in content_text, "应该包含吞吐量指标"
        assert "延迟指标" in content_text, "应该包含延迟指标"
        
        # 测试获取特定指标
        result = await get_gc_metrics_tool({
            "metric_types": ["throughput", "latency"]
        })
        
        content_text = result.content[0].text
        assert "吞吐量指标" in content_text, "应该包含吞吐量指标"
        assert "延迟指标" in content_text, "应该包含延迟指标"
    
    @pytest.mark.asyncio
    async def test_get_gc_metrics_tool_no_data(self):
        """测试在没有分析数据时获取指标"""
        # 清空全局状态
        import main
        main.current_analysis_result = None
        
        result = await get_gc_metrics_tool({})
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
    
    @pytest.mark.asyncio
    async def test_compare_gc_logs_tool(self):
        """测试日志比较工具"""
        if not os.path.exists(self.sample_g1_log) or not os.path.exists(self.sample_j9_log):
            pytest.skip("需要两个测试数据文件")
        
        result = await compare_gc_logs_tool({
            "file_path_1": self.sample_g1_log,
            "file_path_2": self.sample_j9_log
        })
        
        content_text = result.content[0].text
        assert "GC日志对比分析" in content_text, "应该包含对比分析标题"
        assert "关键指标对比" in content_text, "应该包含指标对比"
        assert "分析结论" in content_text, "应该包含分析结论"
        
        # 验证表格格式
        assert "| 指标 |" in content_text, "应该包含对比表格"
    
    @pytest.mark.asyncio
    async def test_compare_gc_logs_tool_errors(self):
        """测试日志比较工具的错误处理"""
        # 测试文件不存在
        result = await compare_gc_logs_tool({
            "file_path_1": "/nonexistent/file1.log",
            "file_path_2": "/nonexistent/file2.log"
        })
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
        
        # 测试缺少参数
        result = await compare_gc_logs_tool({
            "file_path_1": self.sample_g1_log
        })
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
    
    @pytest.mark.asyncio
    async def test_detect_gc_issues_tool(self):
        """测试GC问题检测工具"""
        # 先分析一个日志文件
        if os.path.exists(self.sample_g1_log):
            await analyze_gc_log_tool({
                "file_path": self.sample_g1_log,
                "analysis_type": "detailed"
            })
        else:
            pytest.skip("需要先有分析数据")
        
        # 测试默认阈值
        result = await detect_gc_issues_tool({})
        
        content_text = result.content[0].text
        assert "GC性能问题检测报告" in content_text, "应该包含问题检测报告标题"
        assert "当前状态" in content_text, "应该包含当前状态"
        assert "健康状态" in content_text, "应该包含健康状态"
        
        # 测试自定义阈值
        result = await detect_gc_issues_tool({
            "threshold_config": {
                "max_pause_time": 50,
                "min_throughput": 98
            }
        })
        
        content_text = result.content[0].text
        assert "问题检测报告" in content_text, "应该包含问题检测报告"
    
    @pytest.mark.asyncio
    async def test_detect_gc_issues_tool_no_data(self):
        """测试在没有分析数据时检测问题"""
        # 清空全局状态
        import main
        main.current_analysis_result = None
        
        result = await detect_gc_issues_tool({})
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
    
    def test_tool_input_schemas(self):
        """测试工具输入模式的有效性"""
        # 这是一个同步测试，验证工具定义的正确性
        tools_data = [
            {
                "name": "analyze_gc_log",
                "required_fields": ["file_path"],
                "optional_fields": ["analysis_type"]
            },
            {
                "name": "get_gc_metrics", 
                "required_fields": [],
                "optional_fields": ["metric_types"]
            },
            {
                "name": "compare_gc_logs",
                "required_fields": ["file_path_1", "file_path_2"],
                "optional_fields": []
            },
            {
                "name": "detect_gc_issues",
                "required_fields": [],
                "optional_fields": ["threshold_config"]
            }
        ]
        
        # 运行异步函数获取工具列表
        async def get_tools():
            return await list_tools()
        
        tools = asyncio.run(get_tools())
        
        for expected_tool in tools_data:
            # 找到对应的工具
            actual_tool = None
            for tool in tools:
                if tool.name == expected_tool["name"]:
                    actual_tool = tool
                    break
            
            assert actual_tool is not None, f"找不到工具: {expected_tool['name']}"
            
            # 验证输入模式
            schema = actual_tool.inputSchema
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            
            # 验证必需字段
            for field in expected_tool["required_fields"]:
                assert field in required, f"工具{expected_tool['name']}缺少必需字段: {field}"
                assert field in properties, f"工具{expected_tool['name']}的properties中缺少字段: {field}"
            
            # 验证可选字段存在于properties中
            for field in expected_tool["optional_fields"]:
                assert field in properties, f"工具{expected_tool['name']}的properties中缺少可选字段: {field}"
    
    @pytest.mark.asyncio
    async def test_tool_call_with_valid_arguments(self):
        """测试使用有效参数调用工具"""
        from main import call_tool
        
        if not os.path.exists(self.sample_g1_log):
            pytest.skip("需要测试数据文件")
        
        # 测试analyze_gc_log工具
        result = await call_tool("analyze_gc_log", {
            "file_path": self.sample_g1_log,
            "analysis_type": "basic"
        })
        
        assert isinstance(result, CallToolResult), "应该返回CallToolResult"
        assert result.content, "结果应该有内容"
        
        content_text = result.content[0].text
        assert "错误" not in content_text, "成功调用不应该包含错误信息"
    
    @pytest.mark.asyncio 
    async def test_tool_call_with_invalid_tool_name(self):
        """测试使用无效工具名称调用"""
        from main import call_tool
        
        result = await call_tool("nonexistent_tool", {})
        
        content_text = result.content[0].text
        assert "错误" in content_text, "应该返回错误信息"
        assert "未知工具" in content_text, "应该指出工具未知"
    
    def test_mcp_server_instance(self):
        """测试MCP服务器实例"""
        # 验证服务器实例存在且配置正确
        assert app is not None, "MCP服务器实例应该存在"
        assert hasattr(app, 'name'), "服务器应该有名称"
        assert app.name == "gc-log-analyzer", "服务器名称应该正确"


if __name__ == '__main__':
    # 运行测试
    pytest.main([__file__, '-v'])