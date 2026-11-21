React + TypeScript + Vite + Ant Design 5 骨架。安装、构建、类型检查和测试命令见[本地开发与验证](../docs/local-development.md#react-管理后台)。

## 演示后台

在 `admin-web/` 执行 `npm ci`、`npm run typecheck`、`npm test` 和 `npm run build`。用 `npm exec -- vite preview --host 127.0.0.1` 查看本地生产构建。登录页可选择店长或管理员演示身份，会话仅保存于当前浏览器会话。页面使用占位内容，搜索只演示本地交互。部署静态包时将后台页面路径回退至 `index.html`，以支持刷新和直接打开页面。

基础导航与二级占位路径见[后台路由规范](../docs/navigation.md#管理后台)。共用组件包括 `PageHeader`、`PageContainer`、`SearchPanel`、`StatusTag`、`EmptyState`、`LoadingState`、`ErrorState`、`ConfirmDialog`。当前视觉以仓库记录的[视觉基线](../docs/ui-freeze.md)为参考，Figma 逐页对照待完成。

## 2.3 依赖审计

保留现有 React 18、Vite 5 和 Ant Design 5 版本及锁文件。`npm audit --package-lock-only --omit=dev` 报告 0 项。全量审计涉及以下 5 个开发或测试依赖包。

| 包 | 审计相关风险与适用场景 |
|---|---|
| `vite` | 开发服务器资源访问、跨源脚本及 Windows 编辑器集成问题。风险与开发服务器可达性及编辑器集成功能相关。 |
| `esbuild` | 开发服务器响应可被第三方网页读取。本项目使用 Vite 构建静态产物，未单独启动 esbuild 服务。 |
| `@vitest/mocker` | 测试 mock 服务中的文件读取和代码注入风险，是否暴露取决于运行模式。本项目现有脚本使用单次 `vitest run`。 |
| `tinypool` | 工作线程运行参数相关的代码执行风险。与不可信测试配置、测试代码或可影响工作线程参数的输入有关。 |
| `vitest` | 自身及传递依赖涉及 mock 文件读取和工作线程风险。仅在受信任的代码和配置下运行测试。 |

开发工具链告警需要单独验证兼容升级。当前验收使用绑定环回地址的生产构建预览，运行产物是静态页面。
