import { entryRoute } from '../../config/navigation';
import { shouldRestoreMember } from '../../services/member-session';

Page({
  onLoad() {
    this.openEntry();
  },
  retry() {
    this.openEntry();
  },
  openEntry() {
    wx.redirectTo({ url: shouldRestoreMember() ? `${entryRoute}?restore=1` : entryRoute });
  },
});
