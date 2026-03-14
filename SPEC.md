# 背单词系统 - 项目规格说明书

## 1. 项目概述

- **项目名称**: 背单词系统 (WordMaster)
- **项目类型**: C/S架构桌面应用
- **技术栈**:
  - 后端: FastAPI + SQLite (轻量化数据库)
  - 前端: Vue3 + Element Plus
  - 音频: 浏览器Web Speech API (TTS语音合成)
- **核心功能**: 单词听写学习系统，支持新学、复习、记忆曲线算法
- **目标用户**: 英语学习者

## 2. 数据库设计

### 2.1 用户表 (users)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| username | String | 用户名(唯一) |
| password_hash | String | 密码哈希 |
| created_at | DateTime | 创建时间 |

### 2.2 单词库表 (word_banks)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| name | String | 词库名称 |
| user_id | Integer | 所属用户ID |
| word_count | Integer | 单词数量 |
| created_at | DateTime | 创建时间 |

### 2.3 单词表 (words)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| bank_id | Integer | 所属词库ID |
| seq_num | Integer | 单词序号 |
| word | String | 英文单词 |
| phonetic | String | 音标 |
| meaning | String | 中文释义 |

### 2.4 学习组表 (study_groups)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| user_id | Integer | 所属用户ID |
| bank_id | Integer | 所属词库ID |
| name | String | 组名(时间戳命名) |
| start_seq | Integer | 起始单词序号 |
| end_seq | Integer | 结束单词序号 |
| status | String | 状态(new/learning/reviewing/completed) |
| created_at | DateTime | 创建时间 |
| completed_at | DateTime | 完成时间 |

### 2.5 学习记录表 (study_records)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| group_id | Integer | 学习组ID |
| word_id | Integer | 单词ID |
| round | Integer | 轮次 |
| correct | Boolean | 是否正确 |
| studied_at | DateTime | 学习时间 |

### 2.6 复习计划表 (review_plans)
| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer | 主键 |
| group_id | Integer | 学习组ID |
| review_date | Date | 复习日期 |
| review_round | Integer | 复习轮次(艾宾浩斯) |
| status | String | 状态(pending/completed) |

## 3. 功能模块

### 3.1 用户管理
- 注册/登录
- 用户档案独立管理
- JWT认证

### 3.2 单词库维护
- 导入CSV词库 (格式: 序号,单词,音标,释义)
- 删除词库
- 查看词库列表

### 3.3 单词新学
- 设置学习范围(起始-结束序号)
- 学习组时间戳命名 (如: 20240315_143022)
- 听写流程:
  1. 随机打乱单词顺序
  2. 展示中文释义+音标
  3. TTS播放发音
  4. 用户输入拼写
  5. 判断正误
  6. 错误单词进入下一轮
  7. 循环直到全部正确
  8. 强化听写一遍
- 记录每轮学习结果

### 3.4 单词复习
- 艾宾浩斯记忆曲线复习计划
- 复习时间点: 1天后, 3天后, 7天后, 15天后, 30天后
- 显示当日应复习的单词组
- 复习流程与新学相同

### 3.5 存档备份
- 导出学习数据(JSON格式)
- 导入学习数据
- 学习组存档管理

## 4. API设计

### 认证
- POST /api/auth/register
- POST /api/auth/login
- GET /api/auth/me

### 词库
- GET /api/banks - 获取词库列表
- POST /api/banks - 导入词库
- DELETE /api/banks/{id} - 删除词库
- GET /api/banks/{id}/words - 获取词库单词

### 学习组
- GET /api/groups - 获取学习组列表
- POST /api/groups - 创建学习组
- GET /api/groups/{id} - 获取学习组详情

### 学习
- POST /api/study/start - 开始学习
- POST /api/study/check - 检查拼写
- GET /api/study/next - 获取下一个单词

### 复习
- GET /api/review/today - 获取今日复习计划
- POST /api/review/start - 开始复习

### 备份
- POST /api/backup/export - 导出数据
- POST /api/backup/import - 导入数据

## 5. 前端页面

1. 登录/注册页
2. 词库管理页
3. 学习组列表页
4. 单词新学页 (听写界面)
5. 复习列表页
6. 复习页 (听写界面)
7. 数据备份页
