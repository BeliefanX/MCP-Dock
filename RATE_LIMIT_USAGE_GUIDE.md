# MCP-Dock 速率限制管理使用指南

## 概述

本指南介绍如何使用 MCP-Dock 新增的速率限制管理和监控功能。

## 配置管理

### 配置文件位置
```
mcp_dock/config/rate_limit.config.json
```

### 配置参数说明
```json
{
  "max_sessions_per_client": 10,        // 每个客户端IP的最大会话数
  "max_sessions_per_proxy": 50,         // 每个代理的最大会话数
  "session_creation_window": 60,        // 速率限制时间窗口（秒）
  "burst_allowance": 3,                 // 突发连接允许数量
  "adaptive_scaling": true,             // 启用自适应缩放
  "warning_threshold": 0.8              // 警告阈值（0.0-1.0）
}
```

### 动态配置更新

#### 通过API更新配置
```bash
# 更新客户端会话限制
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/config" \
  -H "Content-Type: application/json" \
  -d '{"max_sessions_per_client": 15}'

# 更新多个参数
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/config" \
  -H "Content-Type: application/json" \
  -d '{
    "max_sessions_per_client": 15,
    "max_sessions_per_proxy": 60,
    "adaptive_scaling": false
  }'
```

#### 重载配置文件
```bash
# 从文件重载配置
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/reload"
```

## 监控和诊断

### 实时状态监控

#### 获取速率限制状态
```bash
curl "http://localhost:8000/api/proxy/debug/rate-limit/status"
```

响应示例：
```json
{
  "timestamp": 1749208035.602,
  "rate_limits": {
    "max_sessions_per_client": 10,
    "max_sessions_per_proxy": 50,
    "session_creation_window": 60,
    "adaptive_scaling": true
  },
  "current_usage": {
    "total_sessions": 25,
    "max_client_sessions": 3,
    "max_proxy_sessions": 15,
    "client_utilization_percent": 30.0,
    "proxy_utilization_percent": 30.0
  },
  "violations": {
    "total_1h": 5,
    "last_5min": 2,
    "clients_with_violations": 2
  },
  "health_status": "healthy"
}
```

### 会话健康监控

#### 获取会话统计
```bash
curl "http://localhost:8000/api/proxy/debug/sessions"
```

#### 获取会话健康摘要
```bash
curl "http://localhost:8000/api/proxy/debug/sessions/health"
```

响应示例：
```json
{
  "total_sessions": 25,
  "healthy_sessions": 20,
  "warning_sessions": 3,
  "critical_sessions": 2,
  "recommendations": [
    "Consider reducing session timeout for better resource utilization"
  ],
  "status_breakdown": {
    "healthy": 20,
    "warning_inactive": 3,
    "critical_uninitialized": 2
  }
}
```

### 违规分析

#### 获取违规统计
```bash
curl "http://localhost:8000/api/proxy/debug/rate-limit/violations"
```

响应示例：
```json
{
  "total_violations_1h": 12,
  "violations_by_type": {
    "client_limit": 8,
    "proxy_limit": 4
  },
  "violations_by_severity": {
    "low": 5,
    "medium": 4,
    "high": 2,
    "critical": 1
  },
  "top_violating_clients": [
    ["192.168.1.100", 5],
    ["192.168.1.101", 3]
  ],
  "violation_trends": {
    "last_5min": 2,
    "last_15min": 5,
    "last_30min": 8,
    "last_1h": 12
  },
  "recommendations": [
    "Client 192.168.1.100 has 5 violations - consider investigation"
  ]
}
```

## 维护操作

### 会话清理

#### 手动触发会话清理
```bash
# 使用默认超时（300秒）
curl -X POST "http://localhost:8000/api/proxy/debug/sessions/cleanup"

# 使用自定义超时
curl -X POST "http://localhost:8000/api/proxy/debug/sessions/cleanup?timeout=180"

# 强制清理（使用较短超时）
curl -X POST "http://localhost:8000/api/proxy/debug/sessions/cleanup?timeout=60&force=true"
```

### 历史清理

#### 清理速率限制历史
```bash
# 清理所有客户端的速率限制历史
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/clear"

# 清理特定客户端的历史
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/clear?client_host=192.168.1.100"
```

#### 清理违规历史
```bash
# 清理所有违规历史
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/violations/clear"

# 清理特定客户端的违规历史
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/violations/clear?client_host=192.168.1.100"
```

## 监控仪表板集成

### 关键指标

#### 系统健康指标
- `health_status`: 系统整体健康状态
- `client_utilization_percent`: 客户端利用率
- `proxy_utilization_percent`: 代理利用率

#### 性能指标
- `total_sessions`: 当前总会话数
- `violations.last_5min`: 最近5分钟违规数
- `cache_stats.cache_size`: 缓存大小

#### 告警阈值建议
- **警告**: 利用率 > 70%, 违规数 > 5/5分钟
- **严重**: 利用率 > 90%, 违规数 > 10/5分钟

### 监控脚本示例

#### Bash监控脚本
```bash
#!/bin/bash
# monitor_rate_limits.sh

API_BASE="http://localhost:8000/api/proxy/debug"

echo "=== MCP-Dock 速率限制监控 ==="
echo "时间: $(date)"
echo

# 获取状态
STATUS=$(curl -s "$API_BASE/rate-limit/status")
HEALTH=$(echo "$STATUS" | jq -r '.health_status')
CLIENT_UTIL=$(echo "$STATUS" | jq -r '.current_usage.client_utilization_percent')
PROXY_UTIL=$(echo "$STATUS" | jq -r '.current_usage.proxy_utilization_percent')

echo "健康状态: $HEALTH"
echo "客户端利用率: $CLIENT_UTIL%"
echo "代理利用率: $PROXY_UTIL%"

# 检查违规
VIOLATIONS=$(curl -s "$API_BASE/rate-limit/violations")
RECENT_VIOLATIONS=$(echo "$VIOLATIONS" | jq -r '.violation_trends.last_5min')

echo "最近5分钟违规: $RECENT_VIOLATIONS"

# 告警检查
if [ "$HEALTH" = "critical" ] || [ $(echo "$CLIENT_UTIL > 90" | bc) -eq 1 ]; then
    echo "⚠️ 告警: 系统状态严重或利用率过高"
fi
```

## 故障排除

### 常见问题

#### 1. 速率限制过于严格
**症状**: 大量 `Rate limit exceeded` 错误
**解决方案**: 
```bash
# 增加客户端会话限制
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/config" \
  -d '{"max_sessions_per_client": 20}'
```

#### 2. 会话积累过多
**症状**: 内存使用增长，会话数量持续增加
**解决方案**:
```bash
# 手动清理会话
curl -X POST "http://localhost:8000/api/proxy/debug/sessions/cleanup?force=true"

# 调整清理参数
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/config" \
  -d '{"session_timeout": 180}'
```

#### 3. 违规记录过多
**症状**: 违规历史占用内存
**解决方案**:
```bash
# 清理违规历史
curl -X POST "http://localhost:8000/api/proxy/debug/rate-limit/violations/clear"
```

### 日志分析

#### 关键日志模式
```
# 速率限制违规
🚫 RATE LIMIT VIOLATION: client_limit

# 会话清理
🧹 Bulk cleanup completed: X sessions removed

# 配置重载
🔄 Rate limit configuration reloaded successfully
```

#### 日志级别调整
在 `mcp_dock/utils/logging_config.py` 中调整日志级别：
```python
# 减少日志噪音
logging.getLogger("mcp_dock.core.sse_session_manager").setLevel(logging.WARNING)

# 增加调试信息
logging.getLogger("mcp_dock.core.sse_session_manager").setLevel(logging.DEBUG)
```

## 最佳实践

### 生产环境配置建议
```json
{
  "max_sessions_per_client": 15,
  "max_sessions_per_proxy": 100,
  "session_creation_window": 60,
  "burst_allowance": 5,
  "adaptive_scaling": true,
  "warning_threshold": 0.75
}
```

### 监控频率建议
- **实时监控**: 每30秒检查状态
- **违规分析**: 每5分钟检查违规趋势
- **会话清理**: 每小时检查会话健康
- **配置备份**: 每天备份配置文件

### 性能优化建议
1. **合理设置缓存TTL**: 默认5秒适合大多数场景
2. **定期清理历史**: 避免内存泄漏
3. **监控系统资源**: 关注CPU和内存使用
4. **调整日志级别**: 生产环境使用WARNING级别

通过以上配置和监控，您可以有效管理 MCP-Dock 的速率限制系统，确保系统稳定运行并及时发现和解决问题。
