#!/bin/bash

# 定义服务名称和日志目录
algorithm_cmd="python3 main.py"
backend_cmd="python3 backend_server.py"
frontend_cmd="streamlit run web.py"
log_dir="log"

# 前台模式停止服务函数
stop_console_services() {
    echo ""
    echo "Stopping services in console mode..."
    if [ -n "$algorithm_pid" ] && kill -0 $algorithm_pid 2>/dev/null; then
        kill $algorithm_pid
        echo "Algorithm service stopped (PID: $algorithm_pid)"
    fi
    if [ -n "$backend_pid" ] && kill -0 $backend_pid 2>/dev/null; then
        kill $backend_pid
        echo "Backend service stopped (PID: $backend_pid)"
    fi
    if [ -n "$frontend_pid" ] && kill -0 $frontend_pid 2>/dev/null; then
        kill $frontend_pid
        echo "Frontend service stopped (PID: $frontend_pid)"
    fi
    echo "All services stopped!"
    exit 0
}

# 停止服务函数
stop_services() {
    echo "Stopping all services..."
    
    # 停止算法服务 - check if already defined (console mode) or need to find process
    if [ -n "$algorithm_pid" ] && kill -0 $algorithm_pid 2>/dev/null; then
        kill $algorithm_pid
        echo "Algorithm service stopped (PID: $algorithm_pid)"
    else
        # 查找并停止算法服务
        algorithm_pid=$(pgrep -f "$algorithm_cmd" | head -1)
        if [ -n "$algorithm_pid" ]; then
            kill $algorithm_pid
            echo "Algorithm service stopped (PID: $algorithm_pid)"
        else
            echo "Algorithm service not running"
        fi
    fi
    
    # 停止后端服务 - check if already defined (console mode) or need to find process
    if [ -n "$backend_pid" ] && kill -0 $backend_pid 2>/dev/null; then
        kill $backend_pid
        echo "Backend service stopped (PID: $backend_pid)"
    else
        # 查找并停止后端服务
        backend_pid=$(pgrep -f "$backend_cmd" | head -1)
        if [ -n "$backend_pid" ]; then
            kill $backend_pid
            echo "Backend service stopped (PID: $backend_pid)"
        else
            echo "Backend service not running"
        fi
    fi
    
    # 停止前端服务 - check if already defined (console mode) or need to find process
    if [ -n "$frontend_pid" ] && kill -0 $frontend_pid 2>/dev/null; then
        kill $frontend_pid
        echo "Frontend service stopped (PID: $frontend_pid)"
    else
        # 查找并停止前端服务
        frontend_pid=$(pgrep -f "$frontend_cmd" | head -1)
        if [ -n "$frontend_pid" ]; then
            kill $frontend_pid
            echo "Frontend service stopped (PID: $frontend_pid)"
        else
            echo "Frontend service not running"
        fi
    fi
    
    echo "All services stopped!"
    # 移除exit 0，让restart命令可以继续执行
}

# 显示帮助信息
show_help() {
    echo "Usage: $0 [start|stop|restart]"
    echo ""
    echo "Commands:"
    echo "  start           Start all services in console mode (foreground with logs)"
    echo "  stop            Stop all services"
    echo "  restart         Restart all services in console mode (foreground with logs)"
    echo "  help            Show this help message"
    echo ""
    echo "If no command is specified, 'start' is assumed."
    exit 0
}

# 处理命令行参数
case "$1" in
    stop)
        stop_services
        exit 0
        ;;
    restart)
        stop_services
        echo ""
        echo "Restarting services in 2 seconds..."
        sleep 2
        ;;
    help|-h|--help)
        show_help
        ;;
    start|"")
        # 继续启动服务
        ;;
    *)
        echo "Error: Unknown command '$1'"
        show_help
        ;;
esac

# 创建日志目录
mkdir -p $log_dir

# 清空旧日志
> $log_dir/ecs

# 停止之前可能运行的服务（如果不是restart命令）
if [ "$1" != "restart" ]; then
    echo "Stopping any existing services..."
    pkill -f "$algorithm_cmd" || true
    pkill -f "$backend_cmd" || true
    pkill -f "$frontend_cmd" || true
    sleep 1
fi

echo "Starting all services..."
echo "Running in console mode (foreground)..."

# 设置信号处理，捕获 Ctrl+C
trap stop_console_services INT TERM

echo "Algorithm service output:"
echo "----------------------------"
# 启动算法服务并同时输出到控制台和日志文件
$algorithm_cmd 2>&1 | tee -a $log_dir/ecs &
algorithm_pid=$!

# 等待1秒
sleep 1

echo ""
echo "Backend service output:"
echo "----------------------------"
# 启动后端服务并同时输出到控制台和日志文件
$backend_cmd 2>&1 | tee -a $log_dir/ecs &
backend_pid=$!

# 等待1秒
sleep 1

echo ""
echo "Frontend service output:"
echo "----------------------------"
# 启动前端服务并同时输出到控制台和日志文件
$frontend_cmd 2>&1 | tee -a $log_dir/ecs &
frontend_pid=$!

# 等待用户中断 (Ctrl+C)
echo ""
echo "All services are running in console mode. Press Ctrl+C to stop."
wait $algorithm_pid $backend_pid $frontend_pid