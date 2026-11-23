import { entryRoute } from '../../config/navigation';
import { errorMessage, loadMemberProfile, memberState, RequestError } from '../../services/member-session';
import type { MemberProfile } from '../../services/member-session';

Page({
  data: {
    loading: false,
    expired: false,
    error: '',
    profile: null as MemberProfile | null,
  },
  onLoad() {
    return this.loadProfile();
  },
  async loadProfile() {
    if (this.data.loading) return;
    if (memberState() !== 'member') {
      this.setData({ profile: null, expired: true, error: '' });
      return;
    }
    this.setData({ loading: true, expired: false, error: '', profile: null });
    try {
      const profile = await loadMemberProfile();
      this.setData({ profile });
    } catch (error) {
      if (error instanceof RequestError && error.status === 401) {
        this.setData({ expired: true });
      } else {
        this.setData({ error: errorMessage(error) });
      }
    } finally {
      this.setData({ loading: false });
    }
  },
  returnToLogin() {
    wx.reLaunch({ url: entryRoute });
  },
});
