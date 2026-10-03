---
title: 医智助手 · Medical Assistant Demo
emoji: 🏥
colorFrom: green
colorTo: blue
sdk: docker
app_port: 8010
pinned: false
license: other
tags:
  - medical
  - rag
  - flask
  - vue
---

# 医智助手 · 在线演示

基于 RAG（检索增强生成）的医疗知识库智能问答系统。本 Space 为**完整可交互演示**：
注册 / 登录 / 智能问答（SSE 流式 + 引用溯源）/ 知识库管理 / 人工复核 HITL / 数据看板，全流程真实可用。

## 演示账号（也可直接注册新账号，新注册默认为患者角色）

| 账号 | 密码 | 角色 |
|---|---|---|
| patientdemo | demo123 | 患者：档案 / 住院 / 预约 / 公开库问答 |
| doctordemo | demo123 | 医生：知识库管理 / 患者管理 / 复核 |
| admindemo | demo123 | 管理员：全系统看板 / 用户管理 / 审计日志 |

## 演示模式说明

- 检索链路完整：BM25 + 向量召回 + **融合精排 v4（强制必经）** + HITL 过滤 + 引用溯源
- 未配置 LLM Key 时走内置离线兜底生成（基于检索片段合成回答）；在 Space
  Settings → Variables 配置 `OPENAI_API_KEY / OPENAI_BASE_URL / OPENAI_CHAT_MODEL`
  可获得真实大模型回答
- 免费层无持久磁盘：Space 重启后数据库重新播种，演示数据回归初始状态
- 闲置后冷启动约 30~60 秒（首次构建播种需数分钟）

源码仓库：https://github.com/SFANBLOG/medical-assistant-master （MulanPSL-2.0）
