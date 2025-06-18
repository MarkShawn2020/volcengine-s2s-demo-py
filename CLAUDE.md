## 开发原则

1. 不要编码，除非得到我许可
2. 编码应尽量简洁、高效，不要写一堆异常捕捉、重试等
3. 编码要始终保持良好的类型定义习惯

## 框架相关

- python
  - 优先使用 poetry
- nodejs
  - 优先使用 pnpm、typescript

## 代码修改记录

- @src/adapters/browser_adapter.py 去除_find_available_port函数，并考虑使用从环境变量读取 websocket_adapter_server_uri 的方式，并默认 ws://localhost:8765，而非拆成host、port
