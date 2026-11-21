import { allowsDemoSession } from '../../config/environment';
import { isDemoRole, navigation } from '../../config/navigation';
import { endDemoSession, startDemoSession } from '../../services/demo-session';

Page({
  data: { demoAvailable: false, opening: false },
  onShow() {
    this.setData({ demoAvailable: allowsDemoSession() });
  },
  openWorkspace(event: WechatMiniprogram.TouchEvent) {
    const role: unknown = event.currentTarget.dataset.role;
    if (this.data.opening || !isDemoRole(role) || !startDemoSession(role)) return;

    this.setData({ opening: true });
    wx.reLaunch({
      url: navigation[role].links[0].url,
      fail: () => {
        endDemoSession();
        this.setData({ opening: false });
        wx.showToast({ title: '页面打开失败，请重试', icon: 'none' });
      },
    });
  },
});
