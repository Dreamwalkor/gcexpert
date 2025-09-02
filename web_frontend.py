#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GC日志分析Web前端 - 精简版
支持文件上传、实时分析和图表展示
"""

import os
import sys
import asyncio
import json
import hashlib
from datetime import datetime
from typing import Dict, Any
import tempfile
import logging

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
    from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    print("请安装FastAPI: pip install fastapi uvicorn python-multipart")
    sys.exit(1)

from web_optimizer import LargeFileOptimizer

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建FastAPI应用
app = FastAPI(title="GC日志分析平台", version="1.0.0")

# 挂载静态文件服务器
app.mount("/static", StaticFiles(directory=project_root), name="static")

# 添加CORS支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量
analysis_results = {}
processing_status = {}
optimizer = LargeFileOptimizer()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


@app.post("/api/upload")
async def upload_file(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """上传GC日志文件"""
    try:
        # 生成文件ID
        content = await file.read()
        file_id = hashlib.md5(content + file.filename.encode()).hexdigest()[:12]
        
        # 保存文件
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 初始化状态
        processing_status[file_id] = {"status": "uploaded", "progress": 0}
        
        # 后台处理
        background_tasks.add_task(process_file_background, file_path, file_id)
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "size_mb": len(content) / (1024 * 1024),
            "message": "上传成功，正在处理..."
        }
        
    except Exception as e:
        logger.error(f"上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_file_background(file_path: str, file_id: str):
    """后台处理文件"""
    try:
        # 创建进度回调函数
        def update_progress(stage: str, progress: int, message: str = ""):
            processing_status[file_id] = {
                "status": "processing", 
                "progress": progress,
                "stage": stage,
                "message": message
            }
            logger.info(f"处理进度 [{file_id}]: {stage} - {progress}% - {message}")
        
        # 初始化进度
        update_progress("初始化", 5, "开始处理文件...")
        
        # 使用优化器处理，传入进度回调
        result = await optimizer.process_large_gc_log(file_path, progress_callback=update_progress)
        
        processing_status[file_id] = {"status": "completed", "progress": 100, "message": "处理完成"}
        analysis_results[file_id] = result
        
        logger.info(f"文件处理完成: {file_id}")
        
    except Exception as e:
        logger.error(f"处理文件失败: {e}")
        processing_status[file_id] = {"status": "error", "progress": 0, "error": str(e)}


@app.get("/api/status/{file_id}")
async def get_status(file_id: str):
    """获取处理状态"""
    if file_id not in processing_status:
        raise HTTPException(status_code=404, detail="文件ID不存在")
    return processing_status[file_id]


@app.get("/api/result/{file_id}")
async def get_result(file_id: str):
    """获取分析结果"""
    if file_id not in analysis_results:
        raise HTTPException(status_code=404, detail="结果不存在或处理未完成")
    return analysis_results[file_id]


@app.get("/api/debug/result/{file_id}")
async def get_debug_result(file_id: str):
    """获取调试信息"""
    if file_id not in analysis_results:
        raise HTTPException(status_code=404, detail="结果不存在或处理未完成")
    
    result = analysis_results[file_id]
    
    # 添加调试信息
    jvm_info = result.get('jvm_info', {})
    debug_info = {
        'jvm_info_keys': list(jvm_info.keys()),
        'jvm_info_has_totalMemoryMb': 'totalMemoryMb' in jvm_info,
        'jvm_info_has_maximumHeapMb': 'maximumHeapMb' in jvm_info,
        'jvm_info_has_runtimeDurationSeconds': 'runtimeDurationSeconds' in jvm_info,
        'jvm_info_type': str(type(jvm_info)),
        'result_type': str(type(result))
    }
    
    # 复制主要结果并添加调试信息
    debug_result = {
        'debug_info': debug_info,
        'jvm_info': jvm_info
    }
    
    return debug_result


@app.get("/api/mcp/status")
async def get_mcp_status():
    """获取MCP服务器状态"""
    logger.info("MCP状态API被调用")
    try:
        # 检查MCP模块是否可用
        import main
        logger.info("main模块导入成功")
        
        # 检查MCP服务器是否正常
        tools = await main.list_tools()
        logger.info(f"获取到{len(tools)}个工具")
        
        return {
            "status": "active",
            "tools_count": len(tools),
            "available_tools": [tool.name for tool in tools],
            "message": "MCP服务器运行正常"
        }
    except ImportError as e:
        logger.error(f"MCP模块导入失败: {e}")
        return {
            "status": "unavailable",
            "message": "MCP模块未安装"
        }
    except Exception as e:
        logger.error(f"MCP状态检查失败: {e}")
        return {
            "status": "error",
            "message": f"MCP服务器错误: {str(e)}"
        }


@app.post("/api/mcp/analyze")
async def mcp_analyze_log(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """使用MCP分析GC日志"""
    try:
        # 保存上传文件
        content = await file.read()
        file_id = hashlib.md5(content + file.filename.encode()).hexdigest()[:12]
        
        # 保存文件
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}_{file.filename}")
        with open(file_path, "wb") as f:
            f.write(content)
        
        # 使用MCP分析
        from main import analyze_gc_log_tool, generate_gc_report_tool
        
        # 分析日志
        analysis_result = await analyze_gc_log_tool({
            "file_path": file_path,
            "analysis_type": "detailed"
        })
        
        # 生成报告
        report_result = await generate_gc_report_tool({
            "format_type": "plain",
            "include_alerts": True
        })
        
        return {
            "file_id": file_id,
            "analysis": analysis_result.content[0].text,
            "report": report_result.content[0].text,
            "message": "MCP分析完成"
        }
        
    except Exception as e:
        logger.error(f"MCP分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"MCP分析失败: {str(e)}")


@app.get("/test-mcp")
async def get_test_mcp_page():
    """返回MCP测试页面"""
    return FileResponse("/Users/sxd/mylab/gcmcp/versions/v1_no_database/test_mcp.html")


@app.get("/")
async def get_index():
    """返回主页面"""
    return HTMLResponse(content=get_html_page())


def get_html_page():
    """生成HTML页面"""
    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GC日志分析平台</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom"></script>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .upload-box { 
            border: 2px dashed #ccc; 
            padding: 40px; 
            text-align: center; 
            background: white; 
            border-radius: 10px; 
            margin: 20px 0;
        }
        .upload-box:hover { border-color: #007bff; }
        .progress-bar { 
            width: 100%; 
            height: 25px; 
            background: #e9ecef; 
            border-radius: 12px; 
            margin: 15px 0;
            box-shadow: inset 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
            position: relative;
        }
        .progress-fill { 
            height: 100%; 
            background: linear-gradient(90deg, #007bff, #0056b3); 
            border-radius: 12px; 
            transition: width 0.5s ease-in-out;
            position: relative;
            box-shadow: 0 2px 4px rgba(0,123,255,0.3);
        }
        .progress-fill::after {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
            animation: shimmer 2s infinite;
        }
        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }
        .progress-text {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: bold;
            color: #495057;
            font-size: 0.9em;
            text-shadow: 0 1px 2px rgba(255,255,255,0.8);
        }
        #uploadProgress {
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin: 20px 0;
        }
        #uploadProgress h3 {
            margin-top: 0;
            color: #2c3e50;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        #statusText {
            margin-top: 10px;
            font-size: 0.95em;
            color: #6c757d;
            line-height: 1.4;
        }
        .metrics-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
            gap: 20px; 
        }
        .metric-card { 
            background: white; 
            padding: 20px; 
            border-radius: 10px; 
            text-align: center; 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        .chart-container h4 {
            margin-top: 0;
            margin-bottom: 15px;
            color: #2c3e50;
            border-bottom: 1px solid #eee;
            padding-bottom: 10px;
        }
        .chart-controls {
            margin-bottom: 15px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 5px;
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        .chart-controls label {
            font-weight: bold;
            margin-right: 5px;
        }
        .status-banner { 
            padding: 10px 15px; 
            border-radius: 5px; 
            margin: 10px 0; 
            font-weight: bold;
        }
        .status-active { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status-error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .mcp-section {
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            margin: 20px 0;
        }
        .mcp-tools {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 10px;
        }
        .mcp-tool {
            background: #007bff;
            color: white;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8em;
        }
        .btn-small {
            padding: 5px 10px;
            font-size: 0.9em;
        }
        #customRange {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-left: 10px;
            padding: 5px 10px;
            background: white;
            border-radius: 3px;
            border: 1px solid #ddd;
        }
        #customRange input {
            width: 80px;
        }
        .btn { 
            background: #007bff; 
            color: white; 
            border: none; 
            padding: 10px 20px; 
            border-radius: 5px; 
            cursor: pointer;
        }
        .btn:hover { background: #0056b3; }
        .hidden { display: none; }
        .alert { padding: 10px; margin: 5px 0; border-radius: 5px; }
        .alert-warning { background: #fff3cd; border: 1px solid #ffeaa7; }
        .alert-critical { background: #f8d7da; border: 1px solid #f5c6cb; }
        
        /* 新增：章节布局样式 */
        .section-card {
            background: white;
            margin: 30px 0;
            padding: 25px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            border-left: 4px solid #007bff;
        }
        
        .section-card h3 {
            margin-top: 0;
            margin-bottom: 20px;
            font-size: 1.5em;
            color: #2c3e50;
            border-bottom: 2px solid #ecf0f1;
            padding-bottom: 10px;
        }
        
        .section-card h4 {
            margin-top: 25px;
            margin-bottom: 15px;
            font-size: 1.2em;
            color: #34495e;
        }
        
        /* JVM信息样式 */
        .jvm-info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
        }
        
        .jvm-info-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #e9ecef;
        }
        
        .jvm-info-label {
            font-size: 0.9em;
            color: #6c757d;
            margin-bottom: 5px;
        }
        
        .jvm-info-value {
            font-size: 1.1em;
            font-weight: bold;
            color: #495057;
        }
        
        /* 百分位统计样式 */
        .percentiles-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
            margin-top: 15px;
        }
        
        .percentile-card {
            background: #e8f4fd;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            border: 1px solid #bee5eb;
        }
        
        .percentile-value {
            font-size: 1.3em;
            font-weight: bold;
            color: #0c5460;
            margin-bottom: 5px;
        }
        
        .percentile-label {
            font-size: 0.9em;
            color: #6c757d;
        }
        
        /* 图表布局样式 */
        .chart-container {
            margin-bottom: 30px;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        .chart-container canvas {
            width: 100% !important;
            height: auto !important;
            max-height: 400px;
        }
        
        /* 响应式图表容器 */
        @media (max-width: 768px) {
            .chart-container {
                padding: 15px;
            }
            
            .chart-container canvas {
                max-height: 300px;
            }
        }
        
        @media (max-width: 480px) {
            .chart-container {
                padding: 10px;
            }
            
            .chart-container canvas {
                max-height: 250px;
            }
        }
        
        /* 分析文本样式 */
        .analysis-content {
            display: grid;
            gap: 25px;
        }
        
        .analysis-text {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #28a745;
            font-size: 1.05em;
            line-height: 1.6;
        }
        
        .auto-summary .analysis-text {
            border-left-color: #17a2b8;
        }
        
        .tuning-recommendations .analysis-text {
            border-left-color: #ffc107;
        }
        
        /* 术语说明样式 */
        .terminology-content {
            display: flex;
            flex-direction: column;
            gap: 30px;
        }
        
        .section-toggle {
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            user-select: none;
        }
        
        .toggle-btn {
            background: #007bff;
            color: white;
            border: none;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            cursor: pointer;
            transition: transform 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .toggle-btn.collapsed {
            transform: rotate(-90deg);
        }
        
        .term-category {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            border-left: 4px solid #007bff;
        }
        
        .term-category h4 {
            margin-top: 0;
            margin-bottom: 20px;
            color: #2c3e50;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            gap: 8px;
            cursor: pointer;
            user-select: none;
        }
        
        .term-category h4::before {
            content: "▶";
            transition: transform 0.3s ease;
            margin-right: 8px;
        }
        
        .term-category.expanded h4::before {
            transform: rotate(90deg);
        }
        
        .term-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        
        .term-category.expanded .term-grid {
            max-height: 2000px; /* 足够大的值以容纳内容 */
        }
        
        .term-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            border: 1px solid #e9ecef;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        
        .term-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .term-item strong {
            display: block;
            color: #495057;
            font-size: 1.1em;
            margin-bottom: 8px;
            border-bottom: 1px solid #e9ecef;
            padding-bottom: 5px;
        }
        
        .term-item p {
            margin: 0;
            color: #6c757d;
            line-height: 1.5;
            font-size: 0.95em;
        }

            line-height: 1.5;
            font-size: 0.95em;
        }
        
        /* 不同类别的颜色主题 */
        .term-category:nth-child(1) { border-left-color: #007bff; }
        .term-category:nth-child(2) { border-left-color: #28a745; }
        .term-category:nth-child(3) { border-left-color: #ffc107; }
        .term-category:nth-child(4) { border-left-color: #dc3545; }
        .term-category:nth-child(5) { border-left-color: #6f42c1; }
        .term-category:nth-child(6) { border-left-color: #fd7e14; }
        .term-category:nth-child(7) { border-left-color: #20c997; }
        
        /* 响应式设计 */
        @media (max-width: 768px) {
            .term-grid {
                grid-template-columns: 1fr;
            }
            
            .term-item {
                padding: 12px;
            }
            
            .term-category {
                padding: 15px;
            }
        }
        
        @media (max-width: 480px) {
            .terminology-content {
                gap: 20px;
            }
            
            .term-category h4 {
                font-size: 1.1em;
            }
            
            .term-item strong {
                font-size: 1em;
            }
            
            .term-item p {
                font-size: 0.9em;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 GC日志分析平台</h1>
        
        <!-- MCP状态部分 -->
        <div class="mcp-section">
            <h3>🤖 MCP服务器状态</h3>
            <div id="mcp-status" class="status-banner status-error">检查中...</div>
            <div class="mcp-tools" id="mcp-tools"></div>
            <button class="btn" onclick="checkMCPStatus()" style="margin-top: 10px;">手动检查MCP状态</button>
            <div id="debug-output" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 5px; max-height: 100px; overflow-y: auto;"></div>
        </div>
        <p>支持G1 GC和IBM J9VM格式，优化处理大文件（最大10GB）</p>
        
        <div class="upload-box" id="uploadBox">
            <h3>📁 选择或拖拽GC日志文件</h3>
            <input type="file" id="fileInput" accept=".log,.txt,.xml" style="margin: 10px;">
            <br>
            <button class="btn" onclick="document.getElementById('fileInput').click()">选择文件</button>
        </div>
        
        <div id="uploadProgress" class="hidden">
            <h3>📊 处理进度</h3>
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill"></div>
                <div class="progress-text" id="progressText">0%</div>
            </div>
            <p id="statusText">准备中...</p>
        </div>
        
        <div id="results" class="hidden">
            <h2>📈 GC日志分析报告</h2>
            
            <!-- 第一部分：概览与核心指标 -->
            <section id="dashboard" class="section-card">
                <h3>📊 概览与核心指标</h3>
                
                <!-- JVM环境信息 -->
                <div class="jvm-info-section">
                    <h4>🖥️ JVM环境信息</h4>
                    <div id="jvmDebug" style="margin-bottom: 10px; font-size: 0.8em; color: #6c757d;"></div>
                    <div class="jvm-info-grid" id="jvmInfoGrid"></div>
                </div>
                
                <!-- 核心性能指标 -->
                <div class="kpi-section">
                    <h4>🎯 核心性能指标</h4>
                    <div class="metrics-grid" id="metricsGrid"></div>
                </div>
            </section>
            
            <!-- 第二部分：GC停顿分析 -->
            <section id="pause-analysis" class="section-card">
                <h3>⏱️ GC停顿分析</h3>
                
                <div class="chart-container">
                    <h4>GC停顿时间序列图</h4>
                    <div class="chart-controls">
                        <label for="timeRange">时间范围:</label>
                        <select id="timeRange" onchange="updateTimeRange()">
                            <option value="all">全部时间</option>
                            <option value="recent-100">最近100个事件</option>
                            <option value="recent-500">最近500个事件</option>
                            <option value="recent-1000">最近1000个事件</option>
                            <option value="custom">自定义范围</option>
                        </select>
                        <div id="customRange" class="hidden">
                            <label>开始事件:</label>
                            <input type="number" id="startEvent" min="0" value="0">
                            <label>结束事件:</label>
                            <input type="number" id="endEvent" min="1" value="100">
                            <button class="btn btn-small" onclick="applyCustomRange()">应用</button>
                        </div>
                        <button class="btn btn-small" onclick="resetZoom()">重置缩放</button>
                    </div>
                    <canvas id="pauseChart" width="100%" height="300"></canvas>
                </div>
                
                <div class="chart-container">
                    <h4>GC停顿分布直方图</h4>
                    <canvas id="pauseDistributionChart" width="100%" height="300"></canvas>
                </div>
                
                <div class="percentiles-section">
                    <h4>📈 百分位统计</h4>
                    <div class="percentiles-grid" id="percentilesGrid"></div>
                </div>
            </section>
            
            <!-- 第三部分：堆内存分析 -->
            <section id="heap-analysis" class="section-card">
                <h3>💾 堆内存分析</h3>
                
                <div class="chart-container">
                    <h4>堆内存使用趋势图</h4>
                    <div class="chart-controls">
                        <label>显示内存区域:</label>
                        <label><input type="checkbox" id="showHeap" checked> 堆内存</label>
                        <label><input type="checkbox" id="showEden" checked> Eden区</label>
                        <label><input type="checkbox" id="showSurvivor"> Survivor区</label>
                        <label><input type="checkbox" id="showOld"> 老年代</label>
                        <label><input type="checkbox" id="showMetaspace" checked> Metaspace</label>
                        <button class="btn btn-small" onclick="updateMemoryChart()">更新图表</button>
                    </div>
                    <canvas id="memoryChart" width="100%" height="350"></canvas>
                </div>
                
                <div class="chart-container">
                    <h4>堆利用率趋势</h4>
                    <canvas id="utilizationChart" width="100%" height="300"></canvas>
                </div>
                
                <div class="chart-container">
                    <h4>分代内存变化对比</h4>
                    <canvas id="generationalChart" width="100%" height="300"></canvas>
                </div>
                
                <div class="chart-container">
                    <h4>📊 GC类型分布</h4>
                    <canvas id="typeChart" width="100%" height="300"></canvas>
                </div>
            </section>
            
            <!-- 第四部分：分析与建议 -->
            <section id="analysis-recommendations" class="section-card">
                <h3>💡 分析与建议</h3>
                
                <div class="analysis-content">
                    <div class="auto-summary">
                        <h4>自动摘要</h4>
                        <div id="autoSummaryText" class="analysis-text"></div>
                    </div>
                    
                    <div class="performance-alerts">
                        <h4>⚠️ 性能警报</h4>
                        <div id="alertsList"></div>
                    </div>
                    
                    <div class="tuning-recommendations">
                        <h4>🔧 调优建议</h4>
                        <div id="recommendationsText" class="analysis-text"></div>
                    </div>
                </div>
            </section>
        </div>
        
        <!-- 术语说明部分 -->
        <section id="terminology" class="section-card">
            <h3 class="section-toggle">📚 术语说明 <button class="toggle-btn" id="terminologyToggle">▼</button></h3>
            
            <div class="terminology-content" id="terminologyContent">
                <div class="term-category">
                    <h4>🏗️ JVM内存结构</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>堆内存 (Heap)</strong>
                            <p>JVM中存储对象实例的主要内存区域，是垃圾回收的主要目标。包含新生代和老年代。</p>
                        </div>
                        <div class="term-item">
                            <strong>Eden区</strong>
                            <p>新生代的一部分，新创建的对象首先分配在这里。Eden区满时会触发Minor GC。</p>
                        </div>
                        <div class="term-item">
                            <strong>Survivor区</strong>
                            <p>新生代的一部分，包含S0和S1两个区域，用于存放经过一次GC后仍存活的对象。</p>
                        </div>
                        <div class="term-item">
                            <strong>老年代 (Old Generation)</strong>
                            <p>存放长期存活的对象，当对象在新生代中经历多次GC后会被移到老年代。</p>
                        </div>
                        <div class="term-item">
                            <strong>Metaspace</strong>
                            <p>存储类的元数据信息，如类定义、方法信息等。替代了Java 8之前的永久代。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>🔄 GC类型</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>Minor GC / Young GC</strong>
                            <p>只回收新生代的垃圾回收，频率高但停顿时间短。主要清理Eden区和Survivor区。</p>
                        </div>
                        <div class="term-item">
                            <strong>Major GC / Old GC</strong>
                            <p>主要回收老年代的垃圾回收，停顿时间较长。通常伴随Minor GC一起执行。</p>
                        </div>
                        <div class="term-item">
                            <strong>Full GC</strong>
                            <p>回收整个堆内存和Metaspace的垃圾回收，停顿时间最长，应尽量避免频繁发生。</p>
                        </div>
                        <div class="term-item">
                            <strong>Mixed GC (G1)</strong>
                            <p>G1垃圾回收器特有，同时回收新生代和部分老年代区域的混合回收。</p>
                        </div>
                        <div class="term-item">
                            <strong>Concurrent GC</strong>
                            <p>与应用程序并发执行的垃圾回收，减少停顿时间，如CMS和G1的并发阶段。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>📊 性能指标</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>停顿时间 (Pause Time)</strong>
                            <p>GC执行期间应用程序暂停的时间，通常以毫秒为单位。停顿时间越短，用户体验越好。</p>
                        </div>
                        <div class="term-item">
                            <strong>吞吐量 (Throughput)</strong>
                            <p>应用程序运行时间占总时间的比例。吞吐量 = 应用时间 / (应用时间 + GC时间)。</p>
                        </div>
                        <div class="term-item">
                            <strong>堆利用率</strong>
                            <p>堆内存使用量占堆总容量的百分比。过高可能导致频繁GC，过低则浪费内存。</p>
                        </div>
                        <div class="term-item">
                            <strong>回收效率</strong>
                            <p>单次GC回收的内存量占GC前内存使用量的比例，反映GC的回收效果。</p>
                        </div>
                        <div class="term-item">
                            <strong>分配速率</strong>
                            <p>应用程序每秒分配的内存量，影响GC的触发频率。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>🎯 垃圾回收器</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>G1 GC</strong>
                            <p>低延迟垃圾回收器，适合大堆内存应用。将堆分为多个区域，可预测停顿时间。</p>
                        </div>
                        <div class="term-item">
                            <strong>CMS GC</strong>
                            <p>并发标记清除回收器，主要用于老年代，可与应用程序并发执行。</p>
                        </div>
                        <div class="term-item">
                            <strong>Parallel GC</strong>
                            <p>并行回收器，使用多线程进行垃圾回收，适合吞吐量优先的应用。</p>
                        </div>
                        <div class="term-item">
                            <strong>ZGC / Shenandoah</strong>
                            <p>超低延迟垃圾回收器，停顿时间通常在10ms以下，适合对延迟敏感的应用。</p>
                        </div>
                        <div class="term-item">
                            <strong>IBM J9 GC</strong>
                            <p>IBM JVM的垃圾回收器，包含多种策略如Scavenge、Global GC等。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>📈 统计术语</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>P50 / P90 / P99</strong>
                            <p>百分位数统计。P90表示90%的GC停顿时间都小于等于该值，用于评估性能稳定性。</p>
                        </div>
                        <div class="term-item">
                            <strong>平均值 (Average)</strong>
                            <p>所有GC事件的算术平均值，提供整体性能的基本概览。</p>
                        </div>
                        <div class="term-item">
                            <strong>最大值 (Maximum)</strong>
                            <p>观察期间出现的最长停顿时间，反映最坏情况下的性能表现。</p>
                        </div>
                        <div class="term-item">
                            <strong>标准差</strong>
                            <p>衡量数据分散程度的指标，标准差越小说明性能越稳定。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>⚠️ 性能警报</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>长停顿警报</strong>
                            <p>当GC停顿时间超过设定阈值时触发，通常表示需要调优GC参数。</p>
                        </div>
                        <div class="term-item">
                            <strong>频繁GC警报</strong>
                            <p>当GC频率过高时触发，可能表示堆内存不足或分配速率过快。</p>
                        </div>
                        <div class="term-item">
                            <strong>内存泄漏警报</strong>
                            <p>当堆利用率持续上升且回收效率下降时触发，可能存在内存泄漏。</p>
                        </div>
                        <div class="term-item">
                            <strong>吞吐量下降警报</strong>
                            <p>当GC时间占比过高导致应用吞吐量下降时触发。</p>
                        </div>
                    </div>
                </div>
                
                <div class="term-category">
                    <h4>🔧 调优建议</h4>
                    <div class="term-grid">
                        <div class="term-item">
                            <strong>堆大小调整</strong>
                            <p>根据应用内存需求调整-Xms和-Xmx参数，避免堆过小导致频繁GC。</p>
                        </div>
                        <div class="term-item">
                            <strong>GC策略选择</strong>
                            <p>根据应用特点选择合适的垃圾回收器，如延迟敏感选G1，吞吐量优先选Parallel。</p>
                        </div>
                        <div class="term-item">
                            <strong>新生代比例</strong>
                            <p>调整新生代与老年代的比例，通常新生代占堆的1/3到1/4比较合适。</p>
                        </div>
                        <div class="term-item">
                            <strong>并发线程数</strong>
                            <p>根据CPU核心数调整GC并发线程数，提高GC效率。</p>
                        </div>
                    </div>
                </div>
            </div>
        </section>
    </div>

    <script>
        let currentFileId = null;
        let fullChartData = null;
        let pauseChart = null;
        
        // 文件上传事件
        document.getElementById('fileInput').addEventListener('change', function(e) {
            if (e.target.files.length > 0) {
                uploadFile(e.target.files[0]);
            }
        });
        
        // 拖拽上传
        const uploadBox = document.getElementById('uploadBox');
        uploadBox.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadBox.style.borderColor = '#007bff';
        });
        
        uploadBox.addEventListener('dragleave', (e) => {
            uploadBox.style.borderColor = '#ccc';
        });
        
        uploadBox.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadBox.style.borderColor = '#ccc';
            if (e.dataTransfer.files.length > 0) {
                uploadFile(e.dataTransfer.files[0]);
            }
        });
        
        async function uploadFile(file) {
            const formData = new FormData();
            formData.append('file', file);
            
            // 显示进度条并初始化
            const uploadProgress = document.getElementById('uploadProgress');
            const progressFill = document.getElementById('progressFill');
            const progressText = document.getElementById('progressText');
            const statusText = document.getElementById('statusText');
            
            uploadProgress.classList.remove('hidden');
            progressFill.style.width = '0%';
            progressFill.style.background = 'linear-gradient(90deg, #007bff, #0056b3)'; // 重置颜色
            progressText.textContent = '0%';
            statusText.textContent = '正在上传文件...';
            
            try {
                const response = await fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                });
                
                const result = await response.json();
                currentFileId = result.file_id;
                
                // 上传完成，显示文件信息
                progressFill.style.width = '5%';
                progressText.textContent = '5%';
                statusText.textContent = 
                    `文件上传成功 (${result.size_mb.toFixed(1)}MB)，开始处理...`;
                
                // 开始轮询状态
                pollStatus();
                
            } catch (error) {
                progressFill.style.background = '#dc3545'; // 红色表示错误
                statusText.textContent = '上传失败: ' + error.message;
                console.error('上传失败:', error);
            }
        }
        
        async function pollStatus() {
            try {
                const response = await fetch(`/api/status/${currentFileId}`);
                const status = await response.json();
                
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                const statusText = document.getElementById('statusText');
                
                // 确保进度值在0-100范围内
                const progress = Math.min(100, Math.max(0, status.progress || 0));
                progressFill.style.width = progress + '%';
                progressText.textContent = progress + '%';
                
                if (status.status === 'processing') {
                    // 根据进度阶段调整进度条颜色
                    if (progress < 10) {
                        progressFill.style.background = 'linear-gradient(90deg, #17a2b8, #138496)'; // 蓝色 - 初始化
                    } else if (progress < 70) {
                        progressFill.style.background = 'linear-gradient(90deg, #007bff, #0056b3)'; // 主蓝色 - 解析中
                    } else if (progress < 95) {
                        progressFill.style.background = 'linear-gradient(90deg, #28a745, #1e7e34)'; // 绿色 - 分析中
                    } else {
                        progressFill.style.background = 'linear-gradient(90deg, #ffc107, #e0a800)'; // 黄色 - 即将完成
                    }
                    
                    // 显示详细的进度信息
                    let statusMessage = `正在处理... ${progress}%`;
                    if (status.stage) {
                        statusMessage = `${status.stage} - ${progress}%`;
                    }
                    if (status.message) {
                        statusMessage += ` - ${status.message}`;
                    }
                    statusText.textContent = statusMessage;
                    
                    // 根据进度调整更新频率 - 更精细的控制
                    let updateInterval;
                    if (progress < 10) {
                        updateInterval = 200; // 初始化阶段快速更新
                    } else if (progress < 70) {
                        updateInterval = 400; // 解析阶段中等频率
                    } else if (progress < 95) {
                        updateInterval = 600; // 分析阶段稍慢
                    } else {
                        updateInterval = 300; // 最后阶段快速更新
                    }
                    
                    setTimeout(pollStatus, updateInterval);
                } else if (status.status === 'completed') {
                    progressFill.style.width = '100%';
                    progressFill.style.background = 'linear-gradient(90deg, #28a745, #1e7e34)'; // 绿色表示完成
                    progressText.textContent = '100%';
                    statusText.textContent = '处理完成！正在加载结果...';
                    loadResults();
                } else if (status.status === 'error') {
                    progressFill.style.background = '#dc3545'; // 红色表示错误
                    statusText.textContent = '处理失败: ' + (status.error || '未知错误');
                } else {
                    // 处理未知状态
                    statusText.textContent = `状态: ${status.status} - ${progress}%`;
                    setTimeout(pollStatus, 1000);
                }
                
            } catch (error) {
                console.error('获取状态失败:', error);
                const statusText = document.getElementById('statusText');
                statusText.textContent = '获取状态失败，正在重试...';
                // 减少错误时的更新频率
                setTimeout(pollStatus, 3000);
            }
        }
        
        async function loadResults() {
            try {
                const response = await fetch(`/api/result/${currentFileId}`);
                const result = await response.json();
                
                console.log('API返回的完整结果:', result);
                console.log('API返回的JVM信息:', result.jvm_info);
                
                displayResults(result);
                
                document.getElementById('uploadProgress').classList.add('hidden');
                document.getElementById('results').classList.remove('hidden');
                
            } catch (error) {
                alert('加载结果失败: ' + error.message);
            }
        }
        
        function displayResults(result) {
            console.log('开始显示结果:', result);
            
            // 调试JVM信息
            console.log('JVM信息:', result.jvm_info);
            if (result.jvm_info) {
                console.log('JVM版本:', result.jvm_info.jvm_version);
                console.log('GC策略:', result.jvm_info.gc_strategy);
                console.log('CPU核心数:', result.jvm_info.cpu_cores);
                console.log('系统内存:', result.jvm_info.total_memory_mb);
                console.log('最大堆内存:', result.jvm_info.maximum_heap_mb);
                console.log('运行时长:', result.jvm_info.runtime_duration_seconds);
                
                // 检查兼容字段
                console.log('兼容字段检查:');
                console.log('totalMemoryMb:', result.jvm_info.totalMemoryMb);
                console.log('maximumHeapMb:', result.jvm_info.maximumHeapMb);
                console.log('runtimeDurationSeconds:', result.jvm_info.runtimeDurationSeconds);
            }
            
            try {
                // 显示JVM环境信息
                displayJVMInfo(result.jvm_info);
                
                // 显示指标
                displayMetrics(result.metrics);
                
                // 显示百分位统计
                displayPercentiles(result.metrics);
                
                // 保存完整数据并显示图表
                fullChartData = result.chart_data;
                if (fullChartData) {
                    console.log('图表数据加载成功');
                    displayCharts(fullChartData);
                    // 显示停顿分布图
                    displayPauseDistribution(result.pause_distribution);
                } else {
                    console.error('图表数据为空');
                }
                
                // 显示警报和分析
                displayAlerts(result.alerts);
                displayAnalysis(result);
                
                // 初始化时间范围控件
                initTimeRangeControls();
                
            } catch (error) {
                console.error('显示结果失败:', error);
            }
        }
        
        function initTimeRangeControls() {
            if (fullChartData && fullChartData.timeline) {
                const totalEvents = fullChartData.timeline.length;
                const endEventInput = document.getElementById('endEvent');
                endEventInput.max = totalEvents;
                endEventInput.value = totalEvents;
                
                // 更新选项文本
                const timeRange = document.getElementById('timeRange');
                const options = timeRange.options;
                for (let i = 0; i < options.length; i++) {
                    const option = options[i];
                    if (option.value.startsWith('recent-')) {
                        const count = parseInt(option.value.split('-')[1]);
                        if (count > totalEvents) {
                            option.disabled = true;
                            option.text += ` (超出范围)`;
                        }
                    }
                }
            }
        }
        
        function updateTimeRange() {
            const timeRange = document.getElementById('timeRange').value;
            const customRange = document.getElementById('customRange');
            
            if (timeRange === 'custom') {
                customRange.classList.remove('hidden');
            } else {
                customRange.classList.add('hidden');
                applyTimeRange(timeRange);
            }
        }
        
        function applyCustomRange() {
            const startEvent = parseInt(document.getElementById('startEvent').value);
            const endEvent = parseInt(document.getElementById('endEvent').value);
            
            if (startEvent >= endEvent) {
                alert('开始事件应小于结束事件');
                return;
            }
            
            applyTimeRange('custom', startEvent, endEvent);
        }
        
        function applyTimeRange(range, customStart = null, customEnd = null) {
            if (!fullChartData || !fullChartData.timeline) return;
            
            let filteredData;
            const totalEvents = fullChartData.timeline.length;
            
            switch (range) {
                case 'all':
                    filteredData = fullChartData.timeline;
                    break;
                case 'recent-100':
                    filteredData = fullChartData.timeline.slice(-100);
                    break;
                case 'recent-500':
                    filteredData = fullChartData.timeline.slice(-500);
                    break;
                case 'recent-1000':
                    filteredData = fullChartData.timeline.slice(-1000);
                    break;
                case 'custom':
                    filteredData = fullChartData.timeline.slice(customStart, customEnd);
                    break;
                default:
                    filteredData = fullChartData.timeline;
            }
            
            // 更新所有图表
            updatePauseChart(filteredData);
            updateMemoryChart();
            updateUtilizationChart(filteredData);
            updateGenerationalChart(filteredData);  // 添加分代内存图表更新
        }
        
        function resetZoom() {
            document.getElementById('timeRange').value = 'all';
            document.getElementById('customRange').classList.add('hidden');
            applyTimeRange('all');
        }
        
        function displayMetrics(metrics) {
            const grid = document.getElementById('metricsGrid');
            grid.innerHTML = '';
            
            if (!metrics) return;
            
            const cards = [
                {label: '吞吐量', value: metrics.throughput_percentage?.toFixed(1) + '%'},
                {label: '平均停顿', value: metrics.avg_pause_time?.toFixed(1) + 'ms'},
                {label: '最大停顿', value: metrics.max_pause_time?.toFixed(1) + 'ms'},
                {label: '性能评分', value: metrics.performance_score?.toFixed(0) + '/100'}
            ];
            
            cards.forEach(card => {
                const div = document.createElement('div');
                div.className = 'metric-card';
                div.innerHTML = `
                    <div class="metric-value">${card.value}</div>
                    <div>${card.label}</div>
                `;
                grid.appendChild(div);
            });
        }
        
        function displayCharts(chartData) {
            if (!chartData) {
                console.warn('图表数据为空');
                return;
            }
            
            console.log('加载图表数据:', chartData);
            
            // GC停顿时间趋势
            if (chartData.timeline && chartData.timeline.length > 0) {
                updatePauseChart(chartData.timeline);
                updateMemoryChart();
                updateUtilizationChart(chartData.timeline);
                updateGenerationalChart(chartData.timeline);  // 添加分代内存图表
            } else {
                console.warn('时间轴数据为空');
            }
            
            // GC类型分布
            if (chartData.gc_type_stats && Object.keys(chartData.gc_type_stats).length > 0) {
                try {
                    const ctx2 = document.getElementById('typeChart').getContext('2d');
                    const types = Object.keys(chartData.gc_type_stats);
                    const counts = Object.values(chartData.gc_type_stats);
                    
                    new Chart(ctx2, {
                        type: 'pie',
                        data: {
                            labels: types,
                            datasets: [{
                                data: counts,
                                backgroundColor: ['#007bff', '#28a745', '#ffc107', '#dc3545']
                            }]
                        },
                        options: { 
                            responsive: true,
                            plugins: {
                                legend: { position: 'bottom' },
                                tooltip: {
                                    callbacks: {
                                        label: function(context) {
                                            const label = context.label || '';
                                            const value = context.parsed;
                                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                            const percentage = ((value / total) * 100).toFixed(1);
                                            return `${label}: ${value} (${percentage}%)`;
                                        }
                                    }
                                }
                            }
                        }
                    });
                } catch (error) {
                    console.error('创建类型分布图表失败:', error);
                }
            } else {
                console.warn('GC类型统计数据为空');
            }
        }
        
        function updatePauseChart(timelineData) {
            if (!timelineData || timelineData.length === 0) {
                console.warn('停顿时间图表数据为空');
                return;
            }
            
            console.log('更新停顿时间图表:', timelineData.length, '个数据点');
            
            const ctx1 = document.getElementById('pauseChart');
            if (!ctx1) {
                console.error('找不到pauseChart元素');
                return;
            }
            
            // 销毁旧图表
            if (pauseChart) {
                pauseChart.destroy();
            }
            
            try {
                // 安全获取数据，提供默认值
                const labels = timelineData.map((d, index) => {
                    return d.timestamp || d.formatted_timestamp || `事件 ${index + 1}`;
                });
                
                const pauseTimeData = timelineData.map(d => {
                    const pauseTime = d.pause_time || 0;
                    return typeof pauseTime === 'number' ? pauseTime : 0;
                });
                
                const heapBeforeData = timelineData.map(d => {
                    const heapBefore = d.heap_before_mb || d.heap_before || 0;
                    return typeof heapBefore === 'number' ? heapBefore : 0;
                });
                
                // 创建新图表
                pauseChart = new Chart(ctx1.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'GC停顿时间 (ms)',
                            data: pauseTimeData,
                            borderColor: '#007bff',
                            backgroundColor: 'rgba(0, 123, 255, 0.1)',
                            tension: 0.1,
                            fill: true
                        }, {
                            label: '堆使用前 (MB)',
                            data: heapBeforeData,
                            borderColor: '#ffc107',
                            backgroundColor: 'rgba(255, 193, 7, 0.1)',
                            tension: 0.1,
                            yAxisID: 'y1'
                        }]
                    },
                    options: {
                        responsive: true,
                        interaction: {
                            intersect: false,
                            mode: 'index'
                        },
                        plugins: {
                            legend: {
                                position: 'top'
                            },
                            tooltip: {
                                callbacks: {
                                    afterLabel: function(context) {
                                        const dataIndex = context.dataIndex;
                                        const data = timelineData[dataIndex];
                                        if (!data) return [];
                                        
                                        const result = [];
                                        if (data.gc_type) {
                                            result.push(`GC类型: ${data.gc_type}`);
                                        }
                                        if (data.heap_after_mb !== undefined) {
                                            result.push(`堆使用后: ${(data.heap_after_mb || 0).toFixed(2)}MB`);
                                        }
                                        return result;
                                    }
                                }
                            },
                            zoom: {
                                zoom: {
                                    wheel: {
                                        enabled: true,
                                    },
                                    pinch: {
                                        enabled: true
                                    },
                                    mode: 'x',
                                },
                                pan: {
                                    enabled: true,
                                    mode: 'x',
                                }
                            }
                        },
                        scales: {
                            x: {
                                title: {
                                    display: true,
                                    text: '时间'
                                }
                            },
                            y: {
                                type: 'linear',
                                display: true,
                                position: 'left',
                                title: {
                                    display: true,
                                    text: '停顿时间 (ms)'
                                }
                            },
                            y1: {
                                type: 'linear',
                                display: true,
                                position: 'right',
                                title: {
                                    display: true,
                                    text: '堆使用 (MB)'
                                },
                                grid: {
                                    drawOnChartArea: false,
                                },
                            }
                        }
                    }
                });
                
                console.log('停顿时间图表创建成功');
                
            } catch (error) {
                console.error('创建停顿时间图表失败:', error);
            }
        }
        
        function displayAlerts(alerts) {
            const list = document.getElementById('alertsList');
            list.innerHTML = '';
            
            if (!alerts || alerts.length === 0) {
                list.innerHTML = '<p>✅ 未发现性能问题</p>';
                return;
            }
            
            alerts.forEach(alert => {
                const div = document.createElement('div');
                div.className = 'alert alert-' + (alert.severity === 'CRITICAL' ? 'critical' : 'warning');
                div.innerHTML = `
                    <strong>${alert.severity}:</strong> ${alert.message}
                    <br><small>建议: ${alert.recommendation}</small>
                `;
                list.appendChild(div);
            });
        }
        
        // 新增：显示JVM环境信息 - 根据GC类型显示不同信息
        function displayJVMInfo(jvmInfo) {
            const grid = document.getElementById('jvmInfoGrid');
            const debugDiv = document.getElementById('jvmDebug');
            grid.innerHTML = '';
            
            // 清空调试信息（生产环境不显示）
            if (debugDiv) {
                debugDiv.innerHTML = '';
            }
            
            console.log('传入的JVM信息:', jvmInfo);
            
            if (!jvmInfo) {
                console.error('jvmInfo为空');
                return;
            }
            
            // 添加详细的调试信息到控制台
            console.log('JVM信息详细字段:');
            for (let key in jvmInfo) {
                console.log(`  ${key}: ${jvmInfo[key]} (类型: ${typeof jvmInfo[key]})`);
            }
            
            // 检测GC类型
            const gcStrategy = jvmInfo.gc_strategy || jvmInfo.gcStrategy || '';
            const jvmVersion = jvmInfo.jvm_version || jvmInfo.jvmVersion || '';
            const logFormat = jvmInfo.log_format || '';
            
            console.log('检测到的GC信息:', { gcStrategy, jvmVersion, logFormat });
            
            // 判断是否为IBM J9 VM
            const isIBMJ9 = gcStrategy.includes('IBM J9') || jvmVersion.includes('IBM J9') || logFormat === 'j9vm';
            // 判断是否为G1 GC
            const isG1GC = gcStrategy.includes('G1') || gcStrategy.includes('Garbage-First') || logFormat === 'g1gc';
            
            console.log('GC类型判断:', { isIBMJ9, isG1GC });
            
            // 定义字段验证函数
            function isValidValue(value) {
                return value !== undefined && 
                       value !== null && 
                       value !== 'Unknown' && 
                       value !== 0 && 
                       value !== '' &&
                       !(typeof value === 'number' && isNaN(value));
            }
            
            function formatMemory(value) {
                if (!isValidValue(value)) return null;
                return `${value} MB`;
            }
            
            function formatCores(value) {
                if (!isValidValue(value)) return null;
                return `${value} 核`;
            }
            
            function formatDuration(seconds) {
                if (!isValidValue(seconds) || seconds <= 0) return null;
                const minutes = seconds / 60;
                if (minutes > 60) {
                    const hours = minutes / 60;
                    return `${hours.toFixed(1)} 小时`;
                } else {
                    return `${minutes.toFixed(1)} 分钟`;
                }
            }
            
            // 准备要显示的卡片数据
            const potentialCards = [];
            
            // JVM版本 - 总是尝试显示
            const version = jvmInfo.jvm_version || jvmInfo.jvmVersion;
            if (isValidValue(version)) {
                potentialCards.push({label: 'JVM版本', value: version});
            }
            
            // GC策略 - 总是尝试显示
            if (isValidValue(gcStrategy)) {
                potentialCards.push({label: 'GC策略', value: gcStrategy});
            }
            
            // CPU核心数
            const cpuCores = jvmInfo.cpu_cores || jvmInfo.cpuCores;
            const formattedCores = formatCores(cpuCores);
            if (formattedCores) {
                potentialCards.push({label: 'CPU核心数', value: formattedCores});
            }
            
            // 系统内存
            const totalMemory = jvmInfo.total_memory_mb || jvmInfo.totalMemoryMb;
            const formattedMemory = formatMemory(totalMemory);
            if (formattedMemory) {
                potentialCards.push({label: '系统内存', value: formattedMemory});
            }
            
            // 最大堆内存
            const maxHeap = jvmInfo.maximum_heap_mb || jvmInfo.maximumHeapMb;
            const formattedMaxHeap = formatMemory(maxHeap);
            if (formattedMaxHeap) {
                potentialCards.push({label: '最大堆内存', value: formattedMaxHeap});
            }
            
            // 初始堆内存 - 仅对G1GC显示
            if (isG1GC) {
                const initialHeap = jvmInfo.initial_heap_mb || jvmInfo.initialHeapMb;
                const formattedInitialHeap = formatMemory(initialHeap);
                if (formattedInitialHeap) {
                    potentialCards.push({label: '初始堆内存', value: formattedInitialHeap});
                }
            }
            
            // 运行时长
            const runtimeSeconds = jvmInfo.runtime_duration_seconds || jvmInfo.runtimeDurationSeconds;
            const formattedDuration = formatDuration(runtimeSeconds);
            if (formattedDuration) {
                potentialCards.push({label: '运行时长', value: formattedDuration});
            }
            
            // IBM J9特有信息
            if (isIBMJ9) {
                // GC线程数
                const gcThreads = jvmInfo.gc_threads;
                if (isValidValue(gcThreads)) {
                    potentialCards.push({label: 'GC线程数', value: `${gcThreads} 个`});
                }
            }
            
            // G1GC特有信息
            if (isG1GC) {
                // 并行工作线程数
                const parallelWorkers = jvmInfo.parallel_workers;
                if (isValidValue(parallelWorkers)) {
                    potentialCards.push({label: '并行工作线程', value: `${parallelWorkers} 个`});
                }
                
                // 堆区域大小
                const heapRegionSize = jvmInfo.heap_region_size;
                if (isValidValue(heapRegionSize)) {
                    potentialCards.push({label: '堆区域大小', value: `${heapRegionSize}M`});
                }
            }
            
            console.log('要显示的卡片:', potentialCards);
            
            // 如果没有任何有效信息，显示提示
            if (potentialCards.length === 0) {
                const div = document.createElement('div');
                div.className = 'jvm-info-card';
                div.innerHTML = `
                    <div class="jvm-info-label">JVM信息</div>
                    <div class="jvm-info-value">无法获取</div>
                `;
                grid.appendChild(div);
                return;
            }
            
            // 显示有效的JVM信息卡片
            potentialCards.forEach(card => {
                const div = document.createElement('div');
                div.className = 'jvm-info-card';
                div.innerHTML = `
                    <div class="jvm-info-label">${card.label}</div>
                    <div class="jvm-info-value">${card.value}</div>
                `;
                console.log('添加卡片:', card);
                grid.appendChild(div);
            });
        }
        
        // 新增：显示百分位统计
        function displayPercentiles(metrics) {
            const grid = document.getElementById('percentilesGrid');
            grid.innerHTML = '';
            
            if (!metrics) {
                console.error('没有metrics数据');
                return;
            }
            
            console.log('百分位数据:', metrics);
            console.log('P50:', metrics.p50_pause_time);
            console.log('P90:', metrics.p90_pause_time);
            console.log('P95:', metrics.p95_pause_time);
            console.log('P99:', metrics.p99_pause_time);
            console.log('insufficient_data:', metrics.insufficient_data);
            
            // 检查是否存在有效的百分位数据
            const hasValidData = ((metrics.p50_pause_time > 0 || 
                               metrics.p90_pause_time > 0 || 
                               metrics.p95_pause_time > 0 || 
                               metrics.p99_pause_time > 0) &&
                               metrics.insufficient_data !== true) && 
                               metrics.abnormal_distribution !== true; // 异常分布也不显示卡片
            
            console.log('百分位数据有效性:', hasValidData);
            console.log('是否异常分布:', metrics.abnormal_distribution);
            
            // 如果没有有效数据，显示提示信息
            if (!hasValidData) {
                // 先检查是否有任何GC事件
                let infoMsg = '';
                if (metrics.abnormal_distribution === true) {
                    infoMsg = `检测到异常分布: 只有1%的GC事件有长停顿，需要考虑P99值${metrics.p99_pause_time.toFixed(1)}ms。`;
                } else if (metrics.insufficient_data === true) {
                    if (metrics.max_pause_time > 0) {
                        infoMsg = `数据点不足，无法准确计算百分位值。共检测到${Math.round(metrics.max_pause_time)}ms停顿时间。`;
                    } else {
                        infoMsg = '未检测到足够的GC停顿事件来计算百分位值';
                    }
                } else if (metrics.avg_pause_time === 0) {
                    infoMsg = '未检测到有效的GC停顿事件';
                } else if (metrics.max_pause_time > 0) {
                    infoMsg = `数据不足，无法计算百分位值。总计${metrics.max_pause_time.toFixed(1)}ms停顿时间。`;
                } else {
                    infoMsg = '数据不足，无法计算百分位值';
                }
                
                const infoDiv = document.createElement('div');
                infoDiv.className = 'info-message';
                infoDiv.style.padding = '15px';
                infoDiv.style.color = '#6c757d';
                infoDiv.style.fontStyle = 'italic';
                infoDiv.style.textAlign = 'center';
                infoDiv.style.width = '100%';
                infoDiv.innerHTML = infoMsg;
                grid.appendChild(infoDiv);
                return;
            }
            
            // 确保所有字段都有默认值
            const safeMetrics = {
                p50_pause_time: metrics.p50_pause_time || metrics.p50PauseTime || 0,
                p90_pause_time: metrics.p90_pause_time || metrics.p90PauseTime || 0,
                p95_pause_time: metrics.p95_pause_time || metrics.p95PauseTime || 0,
                p99_pause_time: metrics.p99_pause_time || metrics.p99PauseTime || 0
            };
            
            const percentiles = [
                {label: 'P50', value: safeMetrics.p50_pause_time.toFixed(1) + 'ms'},
                {label: 'P90', value: safeMetrics.p90_pause_time.toFixed(1) + 'ms'},
                {label: 'P95', value: safeMetrics.p95_pause_time.toFixed(1) + 'ms'},
                {label: 'P99', value: safeMetrics.p99_pause_time.toFixed(1) + 'ms'}
            ];
            
            percentiles.forEach(perc => {
                const div = document.createElement('div');
                div.className = 'percentile-card';
                div.innerHTML = `
                    <div class="percentile-value">${perc.value}</div>
                    <div class="percentile-label">${perc.label}</div>
                `;
                grid.appendChild(div);
            });
        }
        
        // 新增：显示停顿分布图表
        function displayPauseDistribution(distributionData) {
            if (!distributionData || !distributionData.distribution) {
                console.warn('停顿分布数据为空');
                return;
            }
            
            try {
                const ctx = document.getElementById('pauseDistributionChart');
                if (!ctx) {
                    console.error('找不到pauseDistributionChart元素');
                    return;
                }
                
                const distribution = distributionData.distribution;
                const labels = distribution.map(item => item.label);
                const counts = distribution.map(item => item.count);
                
                new Chart(ctx.getContext('2d'), {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'GC次数',
                            data: counts,
                            backgroundColor: '#007bff',
                            borderColor: '#0056b3',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            tooltip: {
                                callbacks: {
                                    afterLabel: function(context) {
                                        const index = context.dataIndex;
                                        const item = distribution[index];
                                        return `占比: ${item.percentage}%`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: { title: { display: true, text: '停顿时间区间' } },
                            y: { title: { display: true, text: 'GC次数' } }
                        }
                    }
                });
                
                console.log('停顿分布图表创建成功');
                
            } catch (error) {
                console.error('创建停顿分布图表失败:', error);
            }
        }
        
        // 内存趋势图表
        let memoryChart = null;
        function updateMemoryChart() {
            if (!fullChartData || !fullChartData.timeline || fullChartData.timeline.length === 0) {
                console.warn('内存图表数据为空');
                return;
            }
            
            const ctx = document.getElementById('memoryChart');
            if (!ctx) {
                console.error('找不到memoryChart元素');
                return;
            }
            
            const timelineData = getCurrentTimelineData();
            if (!timelineData || timelineData.length === 0) {
                console.warn('当前时间线数据为空');
                return;
            }
            
            if (memoryChart) memoryChart.destroy();
            
            try {
                const datasets = [];
                
                // 安全获取数据，提供默认值
                const safeMapData = (data, field) => {
                    return data.map(d => {
                        const value = d[field];
                        return typeof value === 'number' ? value : 0;
                    });
                };
                
                const labels = timelineData.map((d, index) => {
                    return d.timestamp || d.formatted_timestamp || `事件 ${index + 1}`;
                });
                
                if (document.getElementById('showHeap') && document.getElementById('showHeap').checked) {
                    datasets.push({
                        label: '堆内存使用前 (MB)',
                        data: safeMapData(timelineData, 'heap_before_mb'),
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        fill: false
                    });
                    datasets.push({
                        label: '堆内存使用后 (MB)',
                        data: safeMapData(timelineData, 'heap_after_mb'),
                        borderColor: '#0056b3',
                        backgroundColor: 'rgba(0, 86, 179, 0.1)',
                        fill: false
                    });
                }
                
                if (document.getElementById('showEden') && document.getElementById('showEden').checked) {
                    datasets.push({
                        label: 'Eden区使用前 (MB)',
                        data: safeMapData(timelineData, 'eden_before_mb'),
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        fill: false
                    });
                }
                
                if (document.getElementById('showSurvivor') && document.getElementById('showSurvivor').checked) {
                    datasets.push({
                        label: 'Survivor区 (MB)',
                        data: safeMapData(timelineData, 'survivor_before_mb'),
                        borderColor: '#ffc107',
                        backgroundColor: 'rgba(255, 193, 7, 0.1)',
                        fill: false
                    });
                }
                
                if (document.getElementById('showOld') && document.getElementById('showOld').checked) {
                    datasets.push({
                        label: '老年代使用前 (MB)',
                        data: safeMapData(timelineData, 'old_before_mb'),
                        borderColor: '#dc3545',
                        backgroundColor: 'rgba(220, 53, 69, 0.1)',
                        fill: false
                    });
                }
                
                if (document.getElementById('showMetaspace') && document.getElementById('showMetaspace').checked) {
                    datasets.push({
                        label: 'Metaspace使用前 (MB)',
                        data: safeMapData(timelineData, 'metaspace_before_mb'),
                        borderColor: '#ff6600',  // 橙色，表示使用前
                        backgroundColor: 'rgba(255, 102, 0, 0.1)',
                        fill: false,
                        borderWidth: 2,
                        pointStyle: 'circle'
                    });
                    datasets.push({
                        label: 'Metaspace使用后 (MB)',
                        data: safeMapData(timelineData, 'metaspace_after_mb'),
                        borderColor: '#009900',  // 绿色，表示使用后
                        backgroundColor: 'rgba(0, 153, 0, 0.1)',
                        fill: false,
                        borderWidth: 2,
                        borderDash: [5, 5],  // 虚线样式，更容易区分
                        pointStyle: 'triangle'
                    });
                }
                
                memoryChart = new Chart(ctx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            zoom: {
                                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                                pan: { enabled: true, mode: 'x' }
                            }
                        },
                        scales: {
                            x: { title: { display: true, text: '时间' } },
                            y: { 
                                title: { display: true, text: '内存使用 (MB)' },
                                ticks: {
                                    callback: function(value, index, values) {
                                        // 确保Y轴显示为MB单位，如果值太大则转换
                                        if (value > 1024) {
                                            return (value / 1024).toFixed(1) + 'GB';
                                        }
                                        return Math.round(value) + 'MB';
                                    }
                                }
                            }
                        }
                    }
                });
                
                console.log('内存图表创建成功');
                
            } catch (error) {
                console.error('创建内存图表失败:', error);
            }
        }
        
        // 堆利用率图表
        let utilizationChart = null;
        function updateUtilizationChart(timelineData) {
            if (!timelineData || timelineData.length === 0) {
                console.warn('利用率图表数据为空');
                return;
            }
            
            const ctx = document.getElementById('utilizationChart');
            if (!ctx) {
                console.error('找不到utilizationChart元素');
                return;
            }
            
            if (utilizationChart) utilizationChart.destroy();
            
            try {
                // 安全获取数据
                const labels = timelineData.map((d, index) => {
                    return d.timestamp || d.formatted_timestamp || `事件 ${index + 1}`;
                });
                
                const heapUtilizationData = timelineData.map(d => {
                    const utilization = d.heap_utilization;
                    return typeof utilization === 'number' ? utilization : 0;
                });
                
                const reclaimEfficiencyData = timelineData.map(d => {
                    const efficiency = d.reclaim_efficiency;
                    return typeof efficiency === 'number' ? efficiency : 0;
                });
                
                utilizationChart = new Chart(ctx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: '堆利用率 (%)',
                            data: heapUtilizationData,
                            borderColor: '#ff6b6b',
                            backgroundColor: 'rgba(255, 107, 107, 0.1)',
                            fill: true
                        }, {
                            label: '回收效率 (%)',
                            data: reclaimEfficiencyData,
                            borderColor: '#4ecdc4',
                            backgroundColor: 'rgba(78, 205, 196, 0.1)',
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            zoom: {
                                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                                pan: { enabled: true, mode: 'x' }
                            }
                        },
                        scales: {
                            x: { title: { display: true, text: '时间' } },
                            y: { title: { display: true, text: '百分比 (%)' }, min: 0, max: 100 }
                        }
                    }
                });
                
                console.log('利用率图表创建成功');
                
            } catch (error) {
                console.error('创建利用率图表失败:', error);
            }
        }
        
        // 分代内存变化对比图表
        let generationalChart = null;
        function updateGenerationalChart(timelineData) {
            if (!timelineData || timelineData.length === 0) {
                console.warn('分代内存图表数据为空');
                return;
            }
            
            const ctx = document.getElementById('generationalChart');
            if (!ctx) {
                console.error('找不到generationalChart元素');
                return;
            }
            
            if (generationalChart) generationalChart.destroy();
            
            try {
                // 安全获取数据
                const labels = timelineData.map((d, index) => {
                    return d.timestamp || d.formatted_timestamp || `事件 ${index + 1}`;
                });
                
                const edenData = timelineData.map(d => {
                    const eden = d.eden_before_mb;
                    return typeof eden === 'number' ? eden : 0;
                });
                
                const survivorData = timelineData.map(d => {
                    const survivor = d.survivor_before_mb;
                    return typeof survivor === 'number' ? survivor : 0;
                });
                
                const oldData = timelineData.map(d => {
                    const old = d.old_before_mb;
                    return typeof old === 'number' ? old : 0;
                });
                
                const metaspaceData = timelineData.map(d => {
                    const metaspace = d.metaspace_before_mb;
                    return typeof metaspace === 'number' ? metaspace : 0;
                });
                
                generationalChart = new Chart(ctx.getContext('2d'), {
                    type: 'line',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Eden区 (MB)',
                            data: edenData,
                            borderColor: '#28a745',
                            backgroundColor: 'rgba(40, 167, 69, 0.1)',
                            fill: false
                        }, {
                            label: 'Survivor区 (MB)',
                            data: survivorData,
                            borderColor: '#ffc107',
                            backgroundColor: 'rgba(255, 193, 7, 0.1)',
                            fill: false
                        }, {
                            label: '老年代 (MB)',
                            data: oldData,
                            borderColor: '#dc3545',
                            backgroundColor: 'rgba(220, 53, 69, 0.1)',
                            fill: false
                        }, {
                            label: 'Metaspace (MB)',
                            data: metaspaceData,
                            borderColor: '#6f42c1',
                            backgroundColor: 'rgba(111, 66, 193, 0.1)',
                            fill: false
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: {
                            legend: { position: 'top' },
                            zoom: {
                                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                                pan: { enabled: true, mode: 'x' }
                            }
                        },
                        scales: {
                            x: { title: { display: true, text: '时间' } },
                            y: { 
                                title: { display: true, text: '内存使用 (MB)' },
                                ticks: {
                                    callback: function(value, index, values) {
                                        // 确保Y轴显示为MB单位，如果值太大则转换
                                        if (value > 1024) {
                                            return (value / 1024).toFixed(1) + 'GB';
                                        }
                                        return Math.round(value) + 'MB';
                                    }
                                }
                            }
                        }
                    }
                });
                
                console.log('分代内存图表创建成功');
                
            } catch (error) {
                console.error('创建分代内存图表失败:', error);
            }
        }
        
        function getCurrentTimelineData() {
            const timeRange = document.getElementById('timeRange').value;
            if (!fullChartData || !fullChartData.timeline) return [];
            
            let filteredData = fullChartData.timeline;
            const totalEvents = filteredData.length;
            
            switch (timeRange) {
                case 'recent-100': return filteredData.slice(-100);
                case 'recent-500': return filteredData.slice(-500);
                case 'recent-1000': return filteredData.slice(-1000);
                case 'custom':
                    const start = parseInt(document.getElementById('startEvent').value) || 0;
                    const end = parseInt(document.getElementById('endEvent').value) || totalEvents;
                    return filteredData.slice(start, end);
                default: return filteredData;
            }
        }
        
        // 新增： 显示分析摘要
        function displayAnalysis(result) {
            const summaryElement = document.getElementById('autoSummaryText');
            const recommendationsElement = document.getElementById('recommendationsText');
            
            if (!result.metrics) {
                summaryElement.innerHTML = '分析数据不足，无法生成摘要。';
                recommendationsElement.innerHTML = '请确保日志文件包含有效的GC数据。';
                return;
            }
            
            const metrics = result.metrics;
            const jvmInfo = result.jvm_info || {};
            
            // 生成自动摘要
            let summary = `系统运行了 ${formatDuration(jvmInfo.runtime_duration_seconds)}，`;
            summary += `共发生 ${result.total_events} 次GC事件。`;
            summary += `<br><br>吞吐量为 ${metrics.throughput_percentage?.toFixed(2)}%，`;
            
            if (metrics.throughput_percentage >= 98) {
                summary += '处于优秀水平。';
            } else if (metrics.throughput_percentage >= 95) {
                summary += '处于良好水平。';
            } else {
                summary += '需要关注。';
            }
            
            summary += `<br><br>平均停顿时间为 ${metrics.avg_pause_time?.toFixed(1)}ms，`;
            summary += `最大停顿时间为 ${metrics.max_pause_time?.toFixed(1)}ms。`;
            
            if (metrics.max_pause_time <= 100) {
                summary += '停顿时间表现优秀。';
            } else if (metrics.max_pause_time <= 200) {
                summary += '停顿时间表现良好。';
            } else {
                summary += '存在较长停顿，建议优化。';
            }
            
            summaryElement.innerHTML = summary;
            
            // 生成调优建议
            let recommendations = '基于当前分析结果的建议：<br><br>';
            
            if (metrics.throughput_percentage < 95) {
                recommendations += '• 吞吐量偏低，考虑调整堆大小或优化GC参数<br>';
            }
            
            if (metrics.max_pause_time > 200) {
                recommendations += '• 最大停顿时间较长，建议设置 -XX:MaxGCPauseMillis=100<br>';
            }
            
            if (metrics.gc_frequency > 5) {
                recommendations += '• GC频率较高，考虑增加堆内存大小<br>';
            }
            
            if (jvmInfo.gc_strategy === 'G1 (Garbage-First)') {
                recommendations += '• 当前使用G1收集器，可以通过以下参数进行调优：<br>';
                recommendations += '  - 调整 -XX:G1NewSizePercent 控制年轻代大小<br>';
                recommendations += '  - 设置 -XX:InitiatingHeapOccupancyPercent 控制Mixed GC触发时机<br>';
            } else if (jvmInfo.gc_strategy && jvmInfo.gc_strategy.includes('IBM J9')) {
                recommendations += '• 当前使用IBM J9 GC，可以通过以下参数进行调优：<br>';
                if (jvmInfo.gc_strategy.includes('gencon')) {
                    recommendations += '  - 调整 -Xmn 控制Nursery区大小<br>';
                    recommendations += '  - 设置 -Xgcpolicy:gencon 优化代际GC性能<br>';
                } else if (jvmInfo.gc_strategy.includes('balanced')) {
                    recommendations += '  - 考虑调整 -Xgc:targetPausetime 控制停顿目标<br>';
                    recommendations += '  - 优化 -Xgc:maxTenuringThreshold 设置<br>';
                } else if (jvmInfo.gc_strategy.includes('optthruput')) {
                    recommendations += '  - 考虑增加堆大小以提高吞吐量<br>';
                    recommendations += '  - 调整 -Xgcthreads 优化并行GC性能<br>';
                }
                recommendations += '  - 使用 -Xgcpolicy 切换不同GC策略<br>';
            }
            
            recommendations += '<br>建议在业务高峰期持续监控GC性能。';
            
            recommendationsElement.innerHTML = recommendations;
        }
        
        // 工具函数：格式化时长
        function formatDuration(seconds) {
            if (!seconds || seconds <= 0) return '未知';
            
            if (seconds < 60) {
                return `${seconds.toFixed(1)} 秒`;
            } else if (seconds < 3600) {
                return `${(seconds / 60).toFixed(1)} 分钟`;
            } else {
                return `${(seconds / 3600).toFixed(1)} 小时`;
            }
        }
        
        // 检查MCP服务器状态
        async function checkMCPStatus() {
            console.log("[开始检查MCP状态]");
            
            try {
                console.log("[发送API请求]");
                const response = await fetch('/api/mcp/status');
                console.log(`[收到响应] 状态码: ${response.status}`);
                
                const status = await response.json();
                console.log(`[解析JSON] status: ${status.status}, tools: ${status.tools_count}`);
                
                const statusElement = document.getElementById('mcp-status');
                const toolsElement = document.getElementById('mcp-tools');
                
                if (status.status === 'active') {
                    console.log("[MCP状态为active]");
                    statusElement.className = 'status-banner status-active';
                    statusElement.textContent = `✅ MCP服务器正常运行 - 共${status.tools_count}个工具可用`;
                    
                    // 显示可用工具
                    toolsElement.innerHTML = status.available_tools
                        .map(tool => `<span class="mcp-tool">${tool}</span>`)
                        .join('');
                } else {
                    console.log(`[MCP状态非active] ${status.status}`);
                    statusElement.className = 'status-banner status-error';
                    statusElement.textContent = `❌ ${status.message}`;
                    toolsElement.innerHTML = '';
                }
            } catch (error) {
                console.error(`[MCP状态检查错误] ${error.message}`);
                const statusElement = document.getElementById('mcp-status');
                statusElement.className = 'status-banner status-error';
                statusElement.textContent = `❌ 无法连接MCP服务器: ${error.message}`;
            }
        }
        
        // 页面加载时检查MCP状态
        window.addEventListener('DOMContentLoaded', function() {
            console.log('[DOMContentLoaded事件触发] 自动检查MCP状态');
            setTimeout(checkMCPStatus, 100); // 稍微延迟一下，确保页面完全加载
            
            // 初始化术语部分折叠功能
            initTerminologyCollapse();
            // 初始化整个术语部分的折叠功能
            initSectionToggle();
        });
        
        // 初始化整个术语部分的折叠功能
        function initSectionToggle() {
            const toggleBtn = document.getElementById('terminologyToggle');
            const content = document.getElementById('terminologyContent');
            const header = toggleBtn.closest('h3');
            
            // 默认展开状态
            let isExpanded = true;
            
            // 添加点击事件监听器到按钮和标题
            toggleBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                toggleSection();
            });
            
            header.addEventListener('click', function() {
                toggleSection();
            });
            
            function toggleSection() {
                isExpanded = !isExpanded;
                if (isExpanded) {
                    content.style.display = 'flex';
                    toggleBtn.textContent = '▼';
                    toggleBtn.classList.remove('collapsed');
                } else {
                    content.style.display = 'none';
                    toggleBtn.textContent = '►';
                    toggleBtn.classList.add('collapsed');
                }
            }
        }
        
        // 初始化术语部分折叠功能
        function initTerminologyCollapse() {
            const termCategories = document.querySelectorAll('.term-category');
            termCategories.forEach(category => {
                const header = category.querySelector('h4');
                const grid = category.querySelector('.term-grid');
                
                // 默认折叠所有术语部分
                category.classList.remove('expanded');
                grid.style.maxHeight = '0px';
                
                // 添加点击事件监听器
                header.addEventListener('click', function() {
                    category.classList.toggle('expanded');
                    if (category.classList.contains('expanded')) {
                        grid.style.maxHeight = grid.scrollHeight + 'px';
                    } else {
                        grid.style.maxHeight = '0px';
                    }
                });
            });
        }
    </script>
</body>
</html>"""


if __name__ == "__main__":
    print("🚀 启动GC日志分析Web服务...")
    print("📱 访问地址: http://localhost:8000")
    print("💡 使用Ctrl+C停止服务")
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")