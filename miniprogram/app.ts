import { entryRoute, workspacePath } from './config/navigation';
import { getDemoRole } from './services/demo-session';
import { memberState, rememberScene } from './services/member-session';
import { employeeSignedIn } from './services/staff-session';

App({
  onShow({ query }) {
    rememberScene(query.scene_token ?? query.scene);
  },
  onPageNotFound() {
    const role = employeeSignedIn() ? 'employee' : memberState() === 'member' ? 'member' : getDemoRole();
    wx.reLaunch({
      url: role ? workspacePath(role) : entryRoute,
      success: () => wx.showToast({ title: '页面不存在，已返回入口', icon: 'none' }),
    });
  },
});
