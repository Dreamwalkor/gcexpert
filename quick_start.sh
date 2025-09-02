#!/bin/bash
# 🚀 GC日志分析平台 - 无数据库版本快速启动脚本

echo "🔍 GC日志分析平台 - 无数据库版本"
echo "=================================="

# 检查当前目录
CURRENT_DIR=$(pwd)
EXPECTED_DIR="/Users/sxd/mylab/gcmcp/versions/v1_no_database"

if [ "$CURRENT_DIR" != "$EXPECTED_DIR" ]; then
    echo "📁 正在切换到无数据库版本目录..."
    cd "$EXPECTED_DIR"
fi

echo "📍 当前目录: $(pwd)"

# 检查Python环境
echo "🐍 检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3未安装，请先安装Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "✅ Python版本: $PYTHON_VERSION"

# 检查依赖包
echo "📦 检查依赖包..."
if [ -f "requirements_web.txt" ]; then
    pip install -r requirements_web.txt -q
    echo "✅ 依赖包安装完成"
else
    echo "⚠️ 未找到requirements_web.txt，跳过依赖安装"
fi

# 验证核心模块
echo "🔧 验证核心模块..."
python3 -c "
try:
    import web_frontend, web_optimizer, main
    print('✅ 核心模块验证通过')
except ImportError as e:
    print(f'❌ 模块导入失败: {e}')
    exit(1)
"

if [ $? -ne 0 ]; then
    echo "❌ 模块验证失败，请检查环境配置"
    exit 1
fi

# 检查示例数据
echo "📊 检查测试数据..."
if [ -d "test/data" ]; then
    echo "✅ 测试数据目录存在"
else
    echo "⚠️ 测试数据目录不存在，某些测试可能无法运行"
fi

echo ""
echo "🎉 无数据库版本准备就绪！"
echo ""
echo "🚀 启动选项:"
echo "1. 启动Web服务: python3 start_enhanced_web.py"
echo "2. 运行测试: python3 -m pytest test/ -v"
echo "3. 命令行分析: python3 main.py --help"
echo ""
echo "🌐 Web界面地址: http://localhost:8000"
echo "📋 功能特性:"
echo "   - 拖拽上传GC日志文件"
echo "   - 实时处理进度显示"
echo "   - 交互式图表分析"
echo "   - 内存趋势图和缩放功能"
echo "   - 支持G1 GC和IBM J9VM格式"
echo ""
echo "⚡ 性能优化:"
echo "   - 最大文件大小: 10GB"
echo "   - 内存限制: 2GB"
echo "   - 分块处理: 64MB"
echo "   - 智能采样: 5万数据点"
echo ""

# 询问是否立即启动
read -p "🤔 是否立即启动Web服务? (y/N): " -r
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 正在启动Web服务..."
    echo "📡 服务地址: http://localhost:8000"
    echo "💡 按 Ctrl+C 停止服务"
    echo ""
    python3 start_enhanced_web.py
else
    echo "💡 提示: 稍后可以运行 'python3 start_enhanced_web.py' 启动服务"
fi