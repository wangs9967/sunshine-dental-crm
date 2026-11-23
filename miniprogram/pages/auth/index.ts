import { allowsDemoSession } from '../../config/environment';
import { isDemoRole, workspacePath } from '../../config/navigation';
import { endDemoSession, startDemoSession } from '../../services/demo-session';
import { errorMessage, loginWithWechat, memberState, rememberScene, shouldRestoreMember } from '../../services/member-session';

Page({
  data: { demoAvailable: false, opening: false, error: '' },
  onLoad(query) {
    rememberScene(query.scene_token ?? query.scene);
    if (query.restore === '1' && shouldRestoreMember()) return this.login();
  },
  onShow() {
    this.setData({ demoAvailable: allowsDemoSession() && !memberState() });
  },
  async login() {
    if (this.data.opening) return;
    this.setData({ opening: true, error: '' });
    try {
      const url = await loginWithWechat();
      endDemoSession();
      wx.reLaunch({ url, fail: () => this.setData({ error: '页面打开失败，请重试。' }) });
    } catch (error) {
      this.setData({ error: errorMessage(error) });
    } finally {
      this.setData({ opening: false });
    }
  },
  openWorkspace(event: WechatMiniprogram.TouchEvent) {
    const role: unknown = event.currentTarget.dataset.role;
    if (!this.data.demoAvailable || this.data.opening || !isDemoRole(role) || !startDemoSession(role)) return;

    this.setData({ opening: true });
    wx.reLaunch({
      url: workspacePath(role),
      fail: () => {
        endDemoSession();
        this.setData({ opening: false });
        wx.showToast({ title: '页面打开失败，请重试', icon: 'none' });
      },
    });
  },
});
