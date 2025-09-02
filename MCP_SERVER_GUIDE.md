# GC日志分析MCP服务器使用指南

## 📖 概述

GC日志分析MCP（Model Context Protocol）服务器是一个专业的GC性能分析工具，支持G1 GC和IBM J9VM日志格式。通过标准化的MCP接口，可以与支持MCP协议的AI助手（如Claude Desktop）无缝集成。

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements_web.txt
```

### 2. 运行MCP服务器

```bash
python main.py
```

### 3. 配置AI助手

将以下配置添加到您的AI助手配置文件中：

```json
{
  "mcpServers": {
    "gc-log-analyzer": {
      "command": "python",
      "args": ["/Users/sxd/mylab/gcmcp/versions/v1_no_database/main.py"],
      "env": {}
    }
  }
}
```

## 🛠️ 可用工具

### 1. analyze_gc_log - 分析GC日志

**功能**: 分析GC日志文件，支持G1和IBM J9VM格式

**参数**:
- `file_path` (必需): GC日志文件路径
- `analysis_type` (可选): 分析类型，"basic" 或 "detailed"，默认 "basic"

**示例**:
```
请分析这个GC日志文件：/path/to/gc.log，需要详细分析
```

### 2. get_gc_metrics - 获取GC指标

**功能**: 获取当前分析的详细性能指标

**参数**:
- `metric_types` (可选): 指标类型列表，支持 "throughput", "latency", "frequency", "memory", "trends", "health" 或 "all"

**示例**:
```
获取吞吐量和延迟指标
```

### 3. compare_gc_logs - 比较GC日志

**功能**: 对比分析两个GC日志文件的性能差异

**参数**:
- `file_path_1` (必需): 第一个日志文件路径
- `file_path_2` (必需): 第二个日志文件路径

**示例**:
```
比较这两个日志文件的性能：/path/to/before.log 和 /path/to/after.log
```

### 4. detect_gc_issues - 检测GC问题

**功能**: 基于阈值检测GC性能问题并提供优化建议

**参数**:
- `threshold_config` (可选): 自定义阈值配置
  - `max_pause_time`: 最大停顿时间阈值（毫秒），默认100
  - `min_throughput`: 最小吞吐量阈值（百分比），默认95

**示例**:
```
检测当前日志的性能问题，最大停顿时间阈值设置为50ms
```

### 5. generate_gc_report - 生成分析报告

**功能**: 生成专业的GC性能分析报告

**参数**:
- `format_type` (可选): 报告格式，"markdown" 或 "html"，默认 "markdown"
- `output_file` (可选): 输出文件路径
- `include_alerts` (可选): 是否包含性能警报，默认 true

**示例**:
```
生成HTML格式的分析报告，保存到 /tmp/gc_report.html
```

## 📊 支持的GC日志格式

### G1 GC日志格式
```
2023-10-01T10:00:00.123+0800: [GC pause (G1 Humongous Allocation) (young), 0.0234567 secs]
[Parallel Time: 18.5 ms, GC Workers: 8]
[GC Worker Start (ms): Min: 2841.0, Avg: 2841.2, Max: 2841.4, Diff: 0.4]
[Eden: 1024.0M(1024.0M)->0.0B(1536.0M) Survivors: 128.0M->192.0M Heap: 2048.0M(4096.0M)->1280.0M(4096.0M)]
[Times: user=0.12 sys=0.01, real=0.02 secs]
```

### IBM J9VM日志格式
```
<gc type="nursery" id="1" totalMemory="1073741824" freeMemory="715636736">
  <allocation bytes="358105088" />
  <time totalms="15.625" />
</gc>
```

## 🎯 使用场景

### 1. 日常性能监控
- 上传生产环境GC日志
- 获取关键性能指标
- 检测潜在性能问题

### 2. 性能调优
- 比较调优前后的GC日志
- 分析参数调整效果
- 验证优化成果

### 3. 问题排查
- 检测GC性能瓶颈
- 识别内存泄漏迹象
- 获取优化建议

### 4. 报告生成
- 生成专业的分析报告
- 支持Markdown和HTML格式
- 包含图表和警报信息

## 📈 性能指标说明

### 吞吐量指标
- **应用程序时间比例**: 应用运行时间占总时间的百分比
- **GC时间比例**: GC停顿时间占总时间的百分比

### 延迟指标
- **平均GC暂停时间**: 所有GC事件的平均停顿时间
- **最大GC暂停时间**: 单次GC的最长停顿时间
- **P99延迟**: 99%的GC停顿时间都小于此值

### 频率指标
- **GC频率**: 平均每秒发生的GC次数
- **Young GC频率**: 年轻代GC频率
- **Full GC频率**: 完整GC频率

### 内存指标
- **平均堆利用率**: 平均堆内存使用率
- **最大堆利用率**: 峰值堆内存使用率
- **内存回收效率**: GC回收内存的效率

## ⚠️ 性能警报系统

系统会自动检测以下性能问题并生成警报：

### 严重警报 (Critical)
- GC停顿时间超过100ms
- 吞吐量低于95%
- Full GC频率过高

### 警告 (Warning)
- P99延迟较高
- GC频率异常
- 内存使用趋势异常

### 信息 (Info)
- 一般性能建议
- 趋势分析结果

## 🔧 高级配置

### 自定义阈值
```python
# 在detect_gc_issues中使用自定义阈值
threshold_config = {
    "max_pause_time": 50,      # 最大停顿时间50ms
    "min_throughput": 98       # 最小吞吐量98%
}
```

### 批量处理
```bash
# 使用脚本批量处理多个日志文件
for log_file in *.log; do
    python -c "
import asyncio
from main import analyze_gc_log_tool
asyncio.run(analyze_gc_log_tool({'file_path': '$log_file', 'analysis_type': 'detailed'}))
"
done
```

## 🧪 测试验证

运行完整测试套件：
```bash
python test/test_mcp_sync.py
```

运行特定测试：
```bash
python -m pytest test/test_mcp_server.py -v
```

## 📁 项目结构

```
gcmcp/
├── main.py                 # MCP服务器主程序
├── mcp_config.json         # MCP配置文件
├── requirements_web.txt    # 依赖包列表
├── analyzer/               # 分析器模块
│   ├── metrics.py          # 性能指标计算
│   └── report_generator.py # 报告生成器
├── parser/                 # 日志解析器
│   ├── g1_parser.py        # G1 GC解析器
│   └── ibm_parser.py       # IBM J9VM解析器
├── rules/                  # 规则引擎
│   └── alert_engine.py     # 警报引擎
└── test/                   # 测试用例
    ├── test_mcp_server.py  # MCP服务器测试
    └── data/               # 测试数据
```

## 🚨 故障排除

### 常见问题

1. **导入错误**
   ```
   ModuleNotFoundError: No module named 'mcp'
   ```
   解决方案：`pip install mcp>=1.0.0`

2. **文件不存在错误**
   ```
   FileNotFoundError: 文件不存在: /path/to/file.log
   ```
   解决方案：检查文件路径是否正确，使用绝对路径

3. **不支持的日志格式**
   ```
   ValueError: 不支持的日志格式
   ```
   解决方案：确保日志文件是G1 GC或IBM J9VM格式

### 调试模式

启用详细日志输出：
```bash
export PYTHONPATH=.
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import main
"
```

## 📞 支持与反馈

如果遇到问题或有建议，请：
1. 检查本文档的故障排除部分
2. 运行测试验证环境配置
3. 查看日志输出获取详细错误信息

## 🔄 版本信息

当前版本：v1.0.0
- 支持G1 GC和IBM J9VM日志格式
- 提供5个核心MCP工具
- 包含完整的性能警报系统
- 支持HTML和Markdown报告生成

---

## 📚 相关文档

- [README.md](README.md) - 项目总体介绍
- [VERSION_INFO.md](VERSION_INFO.md) - 版本更新历史
- [quick_start.sh](quick_start.sh) - 快速启动脚本