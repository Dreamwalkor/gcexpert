#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MCP服务器部署验证脚本
用于验证MCP服务器是否可以正常部署和运行
"""

import os
import sys
import asyncio
import subprocess
import tempfile
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def check_dependencies():
    """检查依赖是否已安装"""
    print("🔍 检查依赖包...")
    
    required_packages = [
        'mcp',
        'fastapi', 
        'uvicorn',
        'numpy',
        'pytest'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✅ {package}")
        except ImportError:
            missing_packages.append(package)
            print(f"  ❌ {package} - 未安装")
    
    if missing_packages:
        print(f"\n⚠️ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements_web.txt")
        return False
    
    print("✅ 所有依赖包已安装")
    return True

def check_test_data():
    """检查测试数据是否存在"""
    print("\n🧪 检查测试数据...")
    
    test_files = [
        'test/data/sample_g1.log',
        'test/data/sample_j9.log'
    ]
    
    all_exist = True
    for test_file in test_files:
        file_path = project_root / test_file
        if file_path.exists():
            print(f"  ✅ {test_file}")
        else:
            print(f"  ❌ {test_file} - 不存在")
            all_exist = False
    
    if all_exist:
        print("✅ 所有测试数据文件存在")
    else:
        print("⚠️ 部分测试数据文件缺失")
    
    return all_exist

async def test_mcp_functions():
    """测试MCP核心功能"""
    print("\n🚀 测试MCP核心功能...")
    
    try:
        # 导入MCP模块
        from main import (
            list_tools, 
            analyze_gc_log_tool, 
            get_gc_metrics_tool,
            compare_gc_logs_tool,
            detect_gc_issues_tool,
            generate_gc_report_tool
        )
        
        # 测试工具列表
        tools = await list_tools()
        print(f"  ✅ 工具列表 - 共 {len(tools)} 个工具")
        
        # 测试日志分析（如果有测试数据）
        sample_g1 = project_root / 'test/data/sample_g1.log'
        if sample_g1.exists():
            result = await analyze_gc_log_tool({
                'file_path': str(sample_g1),
                'analysis_type': 'basic'
            })
            
            if result and result.content and len(result.content) > 0:
                print("  ✅ 日志分析功能")
                
                # 测试指标获取
                metrics_result = await get_gc_metrics_tool({
                    'metric_types': ['throughput', 'latency']
                })
                if metrics_result and metrics_result.content:
                    print("  ✅ 指标获取功能")
                
                # 测试报告生成
                report_result = await generate_gc_report_tool({
                    'format_type': 'markdown',
                    'include_alerts': True
                })
                if report_result and report_result.content:
                    print("  ✅ 报告生成功能")
            else:
                print("  ❌ 日志分析功能异常")
                return False
        else:
            print("  ⚠️ 跳过功能测试（缺少测试数据）")
        
        print("✅ MCP功能测试通过")
        return True
        
    except Exception as e:
        print(f"  ❌ MCP功能测试失败: {e}")
        return False

def test_web_integration():
    """测试Web集成"""
    print("\n🌐 测试Web集成...")
    
    try:
        from web_frontend import app
        print("  ✅ Web应用导入成功")
        
        # 检查MCP相关的API端点
        routes = [str(route.path) for route in app.routes]
        mcp_routes = [r for r in routes if 'mcp' in r]
        
        if mcp_routes:
            print(f"  ✅ MCP API端点: {mcp_routes}")
        else:
            print("  ⚠️ 未找到MCP API端点")
        
        print("✅ Web集成检查通过")
        return True
        
    except Exception as e:
        print(f"  ❌ Web集成测试失败: {e}")
        return False

def run_formal_tests():
    """运行正式测试套件"""
    print("\n🧪 运行正式测试套件...")
    
    try:
        # 运行同步测试
        result = subprocess.run(
            [sys.executable, 'test/test_mcp_sync.py'],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print("  ✅ 同步测试套件通过")
            if "🎉 所有MCP服务器测试通过！" in result.stdout:
                print("  ✅ 所有测试用例通过")
            return True
        else:
            print("  ❌ 测试套件失败")
            print(f"  错误输出: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("  ❌ 测试超时")
        return False
    except Exception as e:
        print(f"  ❌ 运行测试失败: {e}")
        return False

def generate_deployment_summary():
    """生成部署摘要"""
    print("\n📋 部署摘要")
    print("="*50)
    
    config_info = {
        "MCP服务器": "main.py",
        "Web服务器": "web_frontend.py", 
        "配置文件": "mcp_config.json",
        "依赖文件": "requirements_web.txt",
        "文档": "MCP_SERVER_GUIDE.md"
    }
    
    for key, value in config_info.items():
        file_path = project_root / value
        status = "✅" if file_path.exists() else "❌"
        print(f"{status} {key}: {value}")
    
    print("\n📦 部署命令:")
    print(f"  MCP服务器: python {project_root}/main.py")
    print(f"  Web服务器: python {project_root}/web_frontend.py")
    
    print("\n🔧 配置说明:")
    print("  1. 将 mcp_config.json 中的路径更新为实际部署路径")
    print("  2. 确保所有依赖包已正确安装")
    print("  3. 测试数据文件已准备就绪")

async def main():
    """主验证流程"""
    print("🚀 MCP服务器部署验证")
    print("="*50)
    
    # 检查列表
    checks = [
        ("依赖检查", check_dependencies),
        ("测试数据检查", check_test_data),
        ("Web集成测试", test_web_integration),
        ("正式测试", run_formal_tests)
    ]
    
    # 异步检查
    async_checks = [
        ("MCP功能测试", test_mcp_functions)
    ]
    
    all_passed = True
    
    # 运行同步检查
    for name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"❌ {name}执行失败: {e}")
            all_passed = False
    
    # 运行异步检查
    for name, check_func in async_checks:
        try:
            if not await check_func():
                all_passed = False
        except Exception as e:
            print(f"❌ {name}执行失败: {e}")
            all_passed = False
    
    # 生成摘要
    generate_deployment_summary()
    
    # 最终结果
    print("\n" + "="*50)
    if all_passed:
        print("🎉 所有验证通过！MCP服务器已准备好部署。")
        print("\n📚 详细使用说明请参考: MCP_SERVER_GUIDE.md")
        return 0
    else:
        print("❌ 验证失败，请检查上述问题后重试。")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)