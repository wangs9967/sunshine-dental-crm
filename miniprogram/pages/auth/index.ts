import { allowsDemoSession } from '../../config/environment';
import { isDemoRole, workspacePath } from '../../config/navigation';
import { endDemoSession, startDemoSession } from '../../services/demo-session';
import { errorMessage, forgetMemberSession, loginWithWechat, memberState, rememberScene, shouldRestoreMember } from '../../services/member-session';
import { bindEmployee, employeeSignedIn, loginEmployee, scanStaffInvitation, setStaffCustomerSession, shouldRestoreEmployee } from '../../services/staff-session';

Page({
  data: { demoAvailable: false, opening: false, action: 'member', error: '', notice: '' },
  onLoad(query) {
    rememberScene(query.scene_token ?? query.scene);
    if (query.employeeExpired === '1') this.setData({ action: 'employee', error: '员工登录已失效，请重新登录。' });
    if (query.restore === 'employee' && shouldRestoreEmployee()) return this.staffLogin(true);
    if (query.restore === '1' && shouldRestoreMember()) return this.login();
  },
  onShow() {
    this.setData({ demoAvailable: allowsDemoSession() && !memberState() && !employeeSignedIn() });
  },
  async login() {
    if (this.data.opening) return;
    this.setData({ opening: true, action: 'member', error: '', notice: '' });
    try {
      const url = await loginWithWechat();
      setStaffCustomerSession();
      endDemoSession();
      wx.reLaunch({ url, fail: () => this.setData({ error: '页面打开失败，请重试。' }) });
    } catch (error) {
      this.setData({ error: errorMessage(error) });
    } finally {
      this.setData({ opening: false });
    }
  },
  async staffLogin(restoring: boolean | WechatMiniprogram.TouchEvent = false) {
    if (this.data.opening) return;
    this.setData({ opening: true, action: 'employee', error: '', notice: '' });
    try {
      await loginEmployee();
      forgetMemberSession();
      endDemoSession();
      wx.reLaunch({ url: workspacePath('employee'), fail: () => this.setData({ error: '页面打开失败，请重试。' }) });
    } catch (error) {
      if (restoring === true) setStaffCustomerSession();
      this.setData({ error: errorMessage(error) });
    } finally {
      this.setData({ opening: false });
    }
  },
  async staffBind() {
    if (this.data.opening) return;
    this.setData({ opening: true, action: 'bind', error: '', notice: '' });
    try {
      const invitation = await scanStaffInvitation();
      if (!invitation) return;
      await bindEmployee(invitation);
      this.setData({ notice: '员工微信已绑定，请点击员工微信登录。' });
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
