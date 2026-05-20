# NewAPI 多站点模型价格一键同步工具

这是一个面向 NewAPI 管理员的 Python GUI 工具，用于读取多个 NewAPI 站点的已启用模型价格，查看未配置价格的模型，并将源站的模型价格同步到多个目标站点。

界面由 PySide6 实现，后端通过 NewAPI 管理接口读取和写入系统价格配置。

## 功能特性

- 多站点管理：添加、编辑、测试 NewAPI 站点连接。
- 源站/目标站选择：选择一个源站，勾选一个或多个目标站。
- 模型价格读取：读取当前站点已启用模型及其价格配置。
- 未设置价格筛选：快速查看启用但未配置价格的模型。
- 多计费模式支持：
  - 按量计费：输入、输出、缓存读取、缓存创建价格。
  - 按次收费：每次调用固定价格。
  - 表达式/阶梯收费：支持 NewAPI `tiered_expr` 表达式。
- 同步预览：执行前展示目标站当前价格、同步后价格和变更状态。
- 安全保护：禁止删除站点、模型、模型价格和阶梯配置。
- 本地凭据保存：站点 Token 和密码保存到本机配置文件，Windows 下使用 DPAPI 加密。

## 安全限制

本工具默认禁止一切删除类操作：

- 禁止删除站点配置。
- 禁止删除模型。
- 禁止删除模型价格。
- 禁止把模型价格同步为 `未设置价格`。
- 禁止跨计费模式同步导致旧价格键被删除。
- 禁止清空已有缓存读取价格或缓存创建价格。
- 禁止删除阶梯配置行。

如果同步预览中出现 `已阻止`，表示该操作需要删除旧配置或清空已有价格，工具会跳过该项，不会写入目标站。

说明：由于 NewAPI 的价格配置是多个 option map 共同组成的，跨模式切换通常需要删除旧的 `ModelPrice`、`ModelRatio`、`CompletionRatio`、`billing_setting.billing_expr` 等键。为了避免误删，本工具不会执行这类操作。如确需清理旧配置，请在 NewAPI 管理后台手工确认后处理。

## 计费规则

### 1. 按量计费

GUI 中填写的是实际美元价格，单位为 `$ / 1M tokens`。

字段：

- 输入价格
- 输出价格
- 缓存读取价格
- 缓存创建价格

写入 NewAPI 时会转换为倍率：

```text
ModelRatio = 输入价格 / 2
CompletionRatio = 输出价格 / 输入价格
CacheRatio = 缓存读取价格 / 输入价格
CreateCacheRatio = 缓存创建价格 / 输入价格
```

示例：

```text
输入价格: $0.25 / 1M
输出价格: $2.00 / 1M
缓存读取: $0.025 / 1M
缓存创建: $0.375 / 1M

写入:
ModelRatio = 0.125
CompletionRatio = 8
CacheRatio = 0.1
CreateCacheRatio = 1.5
```

### 2. 按次收费

GUI 中填写每次调用的美元价格。

写入 NewAPI：

```text
ModelPrice = 每次调用价格
```

### 3. 表达式/阶梯收费

表达式模式会写入：

```text
billing_setting.billing_mode[model] = "tiered_expr"
billing_setting.billing_expr[model] = 表达式
```

表达式中的价格系数使用真实 `$ / 1M tokens` 价格，不使用 `ModelRatio = 价格 / 2` 的换算规则。

示例：

```text
tier("base", p * 2.5 + c * 15 + cr * 0.25)
```

## 目录结构

```text
sync_tool/
  main.py                    # GUI 启动入口
  requirements.txt           # Python 依赖
  app/
    api_bridge.py            # GUI 与后端服务的桥接层
    main_window.py           # 主窗口
    models.py                # Site、ModelPricing 数据模型
    core/
      client.py              # NewAPI HTTP 客户端
      pricing.py             # 价格转换与写入合并逻辑
      sync.py                # 同步预览与执行逻辑
      store.py               # 本地站点凭据存储
    widgets/                 # PySide6 界面组件
    styles/dark.qss          # 暗色主题样式
  tests/                     # 单元测试
```

## 环境要求

- Python 3.10 或更高版本
- Windows 推荐
- NewAPI 站点账号需要具备管理权限

依赖：

```text
PySide6>=6.5.0
```

## 安装与运行

进入项目目录：

```powershell
cd "D:\ai\newapi多个站点模型价格一键同步工具\sync_tool"
```

安装依赖：

```powershell
python -m pip install -r requirements.txt
```

启动 GUI：

```powershell
python main.py
```

## 站点认证配置

工具支持两种认证方式。

### Access Token + New-Api-User

推荐使用此方式。

需要填写：

- 站点名称
- NewAPI 地址
- Access Token
- New-Api-User 用户 ID

请求会携带：

```text
Authorization: Bearer <Access Token>
New-Api-User: <用户 ID>
```

注意：NewAPI 的管理接口会校验 `New-Api-User`，只填 Token 不够。

### 用户名 + 密码

需要填写：

- 站点名称
- NewAPI 地址
- 用户名
- 密码

工具会调用 NewAPI 登录接口获取会话。如果账号开启 2FA，请改用 Access Token 方式。

## 使用流程

1. 打开工具。
2. 在左侧添加 NewAPI 站点。
3. 测试站点连接。
4. 选择一个源站。
5. 等待模型价格加载完成。
6. 在中间模型表中勾选需要同步的模型。
7. 如需修改价格，在右侧选择计费模式并填写价格。
8. 勾选一个或多个目标站。
9. 点击一键同步。
10. 在预览窗口确认变更。
11. 执行同步。

## 同步行为

同步执行时会重新读取目标站当前 option maps，然后只合并写入选中模型对应的价格键。

工具不会直接覆盖整个 NewAPI 配置，也不会写入未选中的模型。

可能的预览状态：

- `CREATE`：目标站未配置价格，将新增价格。
- `UPDATE`：目标站已有同模式价格，将更新价格。
- `NO_CHANGE`：目标站价格一致，无需修改。
- `BLOCKED`：该操作需要删除或清空旧配置，已阻止。

## 本地数据存储

站点配置默认保存在：

```text
%APPDATA%\NewApiPriceSync\sites.json
```

Windows 下 Token 和密码使用 DPAPI 加密，仅当前 Windows 用户可解密。

## 测试

进入 `sync_tool` 目录后执行：

```powershell
python -B -m unittest discover -s tests -v
```

当前测试覆盖：

- NewAPI 价格倍率换算。
- 按次、按量、表达式写入规则。
- 删除保护。
- 同步预览和同步执行。
- 本地凭据存储。
- Access Token 请求头。

## 打包为 Windows exe

可以使用 PyInstaller 打包：

```powershell
python -m pip install pyinstaller
pyinstaller --noconfirm --windowed --name NewApiPriceSync main.py
```

如果需要同时带上样式文件，可在 `sync_tool` 目录下使用：

```powershell
pyinstaller --noconfirm --windowed --name NewApiPriceSync --add-data "app\styles\dark.qss;app\styles" main.py
```

生成文件位于：

```text
dist\NewApiPriceSync\
```

## 注意事项

- 写入 `/api/option/` 需要 NewAPI Root 权限。
- 读取 `/api/channel/models_enabled` 需要管理权限。
- 同步前请先测试目标站连接。
- 如果目标站存在旧计费模式残留，本工具会阻止跨模式同步，避免删除旧键。
- 本工具不会自动备份目标站配置。建议在 NewAPI 后台或数据库层面自行备份重要配置。

## 开发说明

后端核心逻辑集中在 `sync_tool/app/core`：

- `pricing.py`：负责价格模型与 NewAPI option maps 的转换。
- `sync.py`：负责生成同步预览、检测删除风险、执行合并写入。
- `client.py`：负责 NewAPI HTTP 请求、登录和接口封装。
- `store.py`：负责站点配置与凭据保存。

GUI 通过 `app/api_bridge.py` 调用后端服务。前端组件不直接访问 NewAPI 接口。
