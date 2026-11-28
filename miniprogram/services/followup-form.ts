import { contacts, contactNames, failure, followup, validMemberId } from './followups';

export function registerFollowupPage(home: boolean) {
  Page({
    data: {
      home, id: '', types: contactNames.slice(0, 4), typeIndex: 0, content: '', busy: false, error: '', available: false,
    },
    onLoad(options) {
      const id = options.id ?? '';
      const available = validMemberId(id);
      this.setData({ id, available, error: available ? '' : '客户不存在，请返回客户列表。' });
    },
    changeType(event: WechatMiniprogram.PickerChange) {
      this.setData({ typeIndex: Number(event.detail.value) });
    },
    changeContent(event: WechatMiniprogram.Input) {
      this.setData({ content: event.detail.value });
    },
    async submit() {
      const { id, content, typeIndex, busy, available } = this.data;
      if (!available || busy) return;
      if (!content.trim()) {
        this.setData({ error: '请填写沟通内容。' });
        return;
      }
      this.setData({ busy: true, error: '' });
      try {
        await followup(id, home ? 'home_visit' : contacts[typeIndex], content.trim());
        wx.redirectTo({ url: '/pages/staff/followup-history?id=' + encodeURIComponent(id) + (home ? '&home=1' : '') });
        wx.showToast({ title: '记录已保存' });
      } catch (error) {
        this.setData({ error: failure(error) });
      } finally {
        this.setData({ busy: false });
      }
    },
  });
}
