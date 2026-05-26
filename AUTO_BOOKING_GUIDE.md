# ICBC 自动预约功能使用指南

## 新功能概述

该脚本现在支持自动预约ICBC路考时间！当找到合适的预约时间时，程序会：
1. 自动提交预约请求
2. 自动读取Gmail中的验证码
3. 完成预约确认
4. 预约成功后自动退出程序

## 配置步骤

### 1. 设置Gmail应用密码
⚠️ **重要**：必须使用 Gmail 应用密码，不是普通登录密码！

**1.1 开启两步验证**（已开过的跳到 1.2）
- 打开 <https://myaccount.google.com/signinoptions/two-step-verification> → 点「开始使用」→ 绑定手机号 → 完成。

**1.2 生成应用密码**
1. 打开 <https://myaccount.google.com/apppasswords>（如果提示找不到页面，说明 1.1 没开）
2. 在「应用名称」框里随便填，比如 `ICBC`，点「创建」
3. 复制弹出的 16 位密码（如 `abcd efgh ijkl mnop`），**只显示一次**，立刻保存到记事本

> 💡 16 位密码带不带空格都能用。

### 2. 修改配置文件

`config.yml` 已在 `.gitignore` 中，仓库里只有模板 `config.example.yml`。首次使用时先复制一份：

```bash
cp config.example.yml config.yml
```

然后编辑 `config.yml`：

```yaml
# 启用Gmail
gmail:
  enable: true
  email: "your-email@gmail.com"
  password: "your-16-char-app-password"

# 启用自动预约
autoBooking:
  enable: true
  timeSelectionStrategy: "earliest"  # 选择最早的合适时间
  exitAfterSuccess: true  # 预约成功后退出
```

### 3. 运行程序

```bash
python road.py config.yml
```

## 功能特性

### ✅ 已实现的功能

- **自动预约**: 找到合适时间后自动预约
- **Gmail验证码读取**: 自动从Gmail读取ICBC验证码
- **预约冲突检测**: 检查是否已有预约，避免重复
- **智能重试**: 预约失败时自动重试
- **状态持久化**: 记录预约状态，重启后仍然有效
- **时间窗口控制**: 只在指定时间段内尝试预约
- **备用通知**: 自动预约失败时发送通知提醒手动操作

### 🔧 配置选项说明

- `timeSelectionStrategy`: 
  - `"earliest"`: 选择最早的合适时间
  - `"best_time_slot"`: 选择最佳时间段（当前与earliest相同）

- `maxRetryAttempts`: 预约失败时重试次数（默认3次）
- `retryIntervalSeconds`: 重试间隔（默认30秒）
- `verificationCodeTimeoutMinutes`: 等待验证码邮件的超时时间（默认10分钟）
- `bookingTimeWindow`: 只在此时间窗口内尝试预约（默认8:00-22:00）

## 使用场景

### 场景1: 完全自动预约
```yaml
gmail:
  enable: true
autoBooking:
  enable: true
  exitAfterSuccess: true
```
程序会持续监控，找到合适时间后自动预约，成功后退出。

### 场景2: 仅通知模式（原有功能）
```yaml
gmail:
  enable: false
autoBooking:
  enable: false
```
程序只发送通知，不进行自动预约。

### 场景3: 测试模式
```yaml
autoBooking:
  enable: true
  exitAfterSuccess: false
```
进行自动预约但不退出程序，便于测试和调试。

## 安全提醒

1. **使用Gmail应用密码**: 不要使用普通Gmail密码
2. **保护配置文件**: `config.yml` 包含驾照号、关键字、Gmail 应用密码，已被 `.gitignore` 排除，切勿手动加入 git 或上传到任何公开位置
3. **监控日志**: 定期检查 `log_icbc_roadtest_checker.log`
4. **备用方案**: 设置通知确保自动预约失败时能及时知道

## 故障排除

### 常见问题

**Q: Gmail连接失败**
A: 检查是否使用了应用密码，不是普通密码

**Q: 收不到验证码**
A: 检查Gmail垃圾邮件文件夹，或增加验证码超时时间

**Q: 预约一直失败**
A: 检查ICBC网站是否正常，或检查账户信息是否正确

**Q: 程序不退出**
A: 检查`exitAfterSuccess`是否设置为true

### 日志查看
```bash
tail -f log_icbc_roadtest_checker.log
```

## 注意事项

- 程序会创建 `booking_status.json` 文件记录预约状态
- 预约成功后，重新运行程序会自动跳过（除非删除状态文件）
- 建议在网络稳定的环境下运行
- ICBC服务器可能有访问频率限制，请合理设置检查间隔

## 支持与反馈

如遇到问题，请检查日志文件并根据错误信息进行排查。