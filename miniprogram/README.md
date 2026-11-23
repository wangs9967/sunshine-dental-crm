会员与员工共用的微信原生小程序骨架，含 TypeScript 和 TDesign 依赖。导入微信开发者工具及预览步骤见[本地开发与验证](../docs/local-development.md#微信原生小程序)。

导入项目并安装锁定依赖后，在微信开发者工具执行「工具 → 构建 npm」，再点击「编译」。开发版和体验版可以切换演示身份，正式版关闭演示会话。

沿用已有本地项目配置时，确认 `setting.es6` 为 `true`、`setting.useCompilerPlugins` 包含 `typescript`。ES6 转译用于处理 TDesign 包中的模块导出。项目模板已包含这两项设置。

会员端已经接入微信登录、注册、积分余额与退出。测试 AppID、后端配置和真机条件见 [2.5.4 手动测试指南](../docs/manual-test-2.5.4.md)。员工工作台继续通过开发版和体验版的演示入口访问。真实会话与演示身份分别只保存在当前进程。其余导航见[页面清单](../docs/navigation.md)。
