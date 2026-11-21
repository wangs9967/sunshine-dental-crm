import { entryRoute } from '../../config/navigation';

Page({
  onLoad() {
    wx.redirectTo({ url: entryRoute });
  },
  retry() {
    wx.redirectTo({ url: entryRoute });
  },
});
