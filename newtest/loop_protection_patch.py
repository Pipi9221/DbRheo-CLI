"""无限循环保护补丁 - 优先级1改进措施"""

# 这个文件展示了需要添加到client.py的关键保护代码

# ============= 1. 在DatabaseClient.__init__中添加 =============
def __init__(self, config: DatabaseConfig):
    # ... 现有代码 ...
    self._consecutive_continues = 0  # 连续"Please continue"计数
    self._absolute_turn_limit = 50   # 绝对轮次上限

# ============= 2. 在send_message_stream开始处添加 =============
async def send_message_stream(self, request, signal, prompt_id, turns=100, original_model=None):
    # 现有代码: self._process_completed_tools()
    # 现有代码: self.session_turn_count += 1
    
    # 【新增】绝对轮次上限检查
    if self.session_turn_count > self._absolute_turn_limit:
        log_info("Client", f"⚠️ 达到绝对轮次上限 {self._absolute_turn_limit}")
        yield {"type": "AbsoluteTurnLimitReached", "value": f"已达到绝对轮次上限({self._absolute_turn_limit})"}
        return
    
    # 【新增】turns参数检查（更严格）
    bounded_turns = min(turns, 100)
    if bounded_turns <= 0:
        log_info("Client", "⚠️ turns参数已耗尽，停止递归")
        yield {"type": "TurnLimitReached", "value": "已达到最大轮次限制"}
        return
    
    # 【新增】连续"Please continue"检测
    if isinstance(request, list) and len(request) == 1:
        if isinstance(request[0], dict) and request[0].get('text') == 'Please continue.':
            self._consecutive_continues += 1
            if self._consecutive_continues > 5:
                log_info("Client", f"⚠️ 检测到连续{self._consecutive_continues}次'Please continue'")
                yield {"type": "ContinueLoopDetected", "value": "检测到可能的循环，已自动停止"}
                self._consecutive_continues = 0  # 重置
                return
        else:
            self._consecutive_continues = 0  # 非continue消息，重置计数
    
    # ... 继续现有代码 ...

# ============= 3. 工具执行超时改进（在scheduler中） =============
# 在DatabaseToolScheduler.schedule中添加超时处理
async def schedule(self, tool_calls, signal):
    for tool_call in tool_calls:
        try:
            # 【新增】添加超时保护
            result = await asyncio.wait_for(
                self._execute_tool(tool_call),
                timeout=30  # 30秒超时
            )
        except asyncio.TimeoutError:
            log_info("Scheduler", f"⚠️ 工具 {tool_call.request.name} 执行超时(30s)")
            tool_call.status = 'error'
            tool_call.response = ToolResponse(
                error="工具执行超时(30秒)",
                summary="执行超时，请检查查询是否过于复杂"
            )

# ============= 使用说明 =============
"""
将以上代码片段添加到对应文件中：

1. client.py - DatabaseClient类
   - __init__: 添加计数器初始化
   - send_message_stream: 添加三个检查点

2. scheduler.py - DatabaseToolScheduler类
   - schedule: 添加超时处理

这些改进可以有效防止：
- 无限递归（绝对上限50轮）
- 循环调用（连续5次"Please continue"）
- 工具卡死（30秒超时）
"""
