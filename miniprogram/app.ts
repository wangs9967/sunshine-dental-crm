import { entryRoute, workspacePath } from './config/navigation';
import { getDemoRole } from './services/demo-session';

App({
  onPageNotFound() {
    const role = getDemoRole();
    wx.reLaunch({
      url: role ? workspacePath(role) : entryRoute,
      success: () => wx.showToast({ title: '页面不存在，已返回入口', icon: 'none' }),
    });
  },
});
