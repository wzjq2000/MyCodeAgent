# MyCodeAgent

模仿 Claude Code 架构、用 LangGraph 实现的 Python coding agent(学习项目)。

## 核心映射

| Claude Code (TS) | 本项目 (Python) |
|---|---|
| `src/query.ts` 查询循环(async generator + continue 站点) | LangGraph 图循环: agent ⇄ tools |
| `readFileState` (ToolUseContext) | `FileReadState` — 强制 read-before-write / modified-since-read |
| `FileReadTool` / `FileWriteTool` / `FileEditTool` | `tools/` 下的忠实移植(校验链、错误码、结果消息与 TS 一致,含引号归一化) |
| `mapToolResultToToolResultBlockParam` | 工具直接返回模型可见的字符串结果 |
| 流式 `yield` 事件 → UI | `graph.astream(stream_mode=["messages", "values"])` |
| `CLAUDE.md` 记忆 | `prompts.py` 注入项目 / 用户 CLAUDE.md |

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[anthropic,dev]"
```

`.env` 中设置(参照 `.env.example`):

```
ANTHROPIC_API_KEY=sk-ant-...
AGENT_MODEL=claude-opus-5   # 默认值,可省略
```

运行:

```bash
.venv/bin/my-agent "读一下 src/agent.py,解释它是做什么的"
.venv/bin/my-agent           # 交互模式,exit 退出
.venv/bin/my-agent --max-turns 40 "..."
.venv/bin/my-agent --model claude-opus-5 "..."
```

## Project Structure

```
MyCodeAgent/
├── src/my_code_agent/
│   ├── __main__.py     # CLI (typer + rich 流式输出, 单轮/交互两种模式)
│   ├── agent.py        # LangGraph 图: agent → tools → agent(对应 query.ts 主循环)
│   ├── state.py        # AgentState(图状态) + FileReadState(会话读文件记录)
│   ├── prompts.py      # 系统提示词组装 + CLAUDE.md 注入
│   ├── settings.py     # pydantic-settings 读取 .env
│   └── tools/          # Read / Write / Edit(框架无关移植 + StructuredTool 适配层)
└── tests/              # 工具行为测试 + 图编译冒烟测试
```

## Development

```bash
.venv/bin/python -m pytest
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/
```

## Roadmap

- [x] 最小闭环: Read / Write / Edit + 图循环 + CLI
- [ ] 权限系统(`interrupt()` + 权限规则,加入 Bash 工具)
- [ ] 会话持久化(checkpointer)+ 上下文压缩(autocompact 对应物)
- [ ] 子 Agent / MCP