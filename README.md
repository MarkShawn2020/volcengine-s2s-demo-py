# RealtimeDialog

实时语音对话程序，支持语音输入和语音输出。

## 使用说明

此demo使用python3.7环境进行开发调试，其他python版本可能会有兼容性问题，需要自己尝试解决。

1. 配置API密钥
   - 设置环境变量：
     ```bash
     export VOLC_APP_ID="火山控制台上端到端大模型对应的App ID"
     export VOLC_ACCESS_KEY="火山控制台上端到端大模型对应的Access Key"
     export VOLC_APP_KEY="火山控制台上端到端大模型对应的App Key"
     ```
   - 或者创建 `.env` 文件（参考 `.env.example`）

2. 安装依赖
   ```bash
   pip install -r requirements.txt