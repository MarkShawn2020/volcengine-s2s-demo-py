# WebSocket分数同步功能

## 功能概述

游戏启动时会自动开启一个WebSocket服务器（localhost:6666），实时同步游戏分数和状态给连接的客户端。

## 同步时机

WebSocket服务器会在以下时刻同步分数：

1. **游戏开始** - 发送游戏开始事件
2. **用户输入姓名** - 更新玩家信息
3. **每个问题完成** - 更新累计分数
4. **游戏结束** - 发送最终分数
5. **按0重启游戏** - 发送重启事件

## 消息格式

### 初始状态消息
```json
{
  "type": "initial_state",
  "score": 0.0,
  "status": "waiting"
}
```

### 分数更新消息
```json
{
  "type": "score_update",
  "score": 85.5,
  "status": "question_1_completed",
  "user_name": "张三",
  "timestamp": 1640995200.123
}
```

### 状态类型
- `waiting` - 等待开始
- `started` - 游戏开始
- `name_received` - 已获取姓名
- `question_1_completed` - 第1题完成
- `question_2_completed` - 第2题完成
- `question_3_completed` - 第3题完成
- `finished` - 游戏结束
- `restarted` - 游戏重启

## 使用方法

### 1. 启动游戏
```bash
poetry run python main_flower_game.py
```

游戏启动后，WebSocket服务器会自动在 `ws://localhost:6666` 启动。

### 2. 测试连接

#### 方法1：使用HTML测试页面
在浏览器中打开 `test_websocket.html`，可以看到实时的分数监控界面。

#### 方法2：使用Python测试客户端
```bash
poetry run python test_websocket_client.py
```

#### 方法3：使用其他WebSocket客户端
连接到 `ws://localhost:6666` 即可接收实时分数更新。

## 技术实现

### 架构设计
- `GameScoreWebSocketServer` - 独立的WebSocket服务器模块
- `FlowerGameApp` - 集成WebSocket服务器启动和停止
- `FlowerGameAdapter` - 在关键时刻调用分数同步

### 职责分离
- `FlowerGameApp`：负责应用生命周期管理，包括WebSocket服务器的启动和停止
- `FlowerGameAdapter`：负责游戏逻辑，在适当时机通知WebSocket服务器
- `GameScoreWebSocketServer`：专门负责WebSocket通信和客户端管理

## 注意事项

1. 确保端口6666未被占用
2. 如果需要修改端口，可以在`FlowerGameApp`的`__init__`方法中修改`GameScoreWebSocketServer`的初始化参数
3. WebSocket服务器支持多客户端同时连接
4. 客户端断开连接不会影响游戏运行

## 扩展功能

可以基于此WebSocket接口开发：
- 实时分数排行榜
- 游戏数据统计面板
- 移动端监控应用
- 第三方集成接口