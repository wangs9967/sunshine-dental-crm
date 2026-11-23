import { entryRoute, workspacePath } from '../../config/navigation';
import { errorMessage, memberState, RequestError, submitRegistration } from '../../services/member-session';

function businessDate(): string {
  return new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);
}

Page({
  data: { name: '', birthday: '', phone: '', today: '', submitting: false, error: '' },
  onLoad() {
    if (memberState() !== 'registration') {
      wx.reLaunch({ url: memberState() === 'member' ? workspacePath('member') : entryRoute });
      return;
    }
    this.setData({ today: businessDate() });
  },
  updateName(event: WechatMiniprogram.Input) {
    this.setData({ name: event.detail.value });
  },
  updateBirthday(event: WechatMiniprogram.PickerChange) {
    if (typeof event.detail.value === 'string') this.setData({ birthday: event.detail.value });
  },
  updatePhone(event: WechatMiniprogram.Input) {
    this.setData({ phone: event.detail.value });
  },
  async submit() {
    if (this.data.submitting) return;
    const form = { name: this.data.name.trim(), birthday: this.data.birthday, phone: this.data.phone.trim() };
    const date = new Date(form.birthday);
    if (!form.name || form.name.length > 80 || /[\x00-\x1f\x7f]/.test(form.name)) {
      this.setData({ error: '请输入姓名（最多 80 字）。' });
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.birthday) || form.birthday.startsWith('0000') || !Number.isFinite(date.getTime())
      || date.toISOString().slice(0, 10) !== form.birthday || form.birthday > businessDate()) {
      this.setData({ error: '请选择有效的出生日期。' });
      return;
    }
    if (!/^1[3-9][0-9]{9}$/.test(form.phone)) {
      this.setData({ error: '请输入 11 位大陆手机号。' });
      return;
    }
    this.setData({ submitting: true, error: '' });
    try {
      const source = await submitRegistration(form);
      this.setData({ name: '', birthday: '', phone: '' });
      if (source === 'invalid') {
        wx.showModal({
          title: '注册成功',
          content: '员工来源码无效或已过期，本次未关联员工。',
          showCancel: false,
          complete: () => wx.reLaunch({ url: workspacePath('member') }),
        });
      } else {
        wx.reLaunch({
          url: workspacePath('member'),
          success: () => wx.showToast({ title: source === 'bound' ? '注册成功，已关联员工' : '注册成功', icon: 'none' }),
        });
      }
    } catch (error) {
      if (error instanceof RequestError && (error.status === 401 || error.code === 'MEMBER_ALREADY_REGISTERED')) {
        wx.showModal({
          title: '请重新微信登录', content: errorMessage(error), showCancel: false,
          complete: () => wx.reLaunch({ url: entryRoute }),
        });
      } else {
        this.setData({ error: errorMessage(error) });
      }
    } finally {
      this.setData({ submitting: false });
    }
  },
});
