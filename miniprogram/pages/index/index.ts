import { entryRoute } from '../../config/navigation';
import { shouldRestoreMember } from '../../services/member-session';
import { shouldRestoreEmployee } from '../../services/staff-session';

Page({
  onLoad() {
    this.openEntry();
  },
  retry() {
    this.openEntry();
  },
  openEntry() {
    const restore = shouldRestoreEmployee() ? 'employee' : shouldRestoreMember() ? '1' : '';
    wx.redirectTo({ url: restore ? `${entryRoute}?restore=${restore}` : entryRoute });
  },
});
