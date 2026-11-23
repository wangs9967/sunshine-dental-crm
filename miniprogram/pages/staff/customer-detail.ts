import { entryRoute } from '../../config/navigation';
import { RequestError, errorMessage } from '../../services/request';
import { loadCustomer, presentCustomer } from '../../services/staff-customers';

const listUrl = '/pages/staff/customers';

Page({
  requestVersion: 0,
  data: {
    id: '',
    customer: null as ReturnType<typeof presentCustomer> | null,
    loading: true,
    loginRequired: false,
    unavailable: false,
    error: '',
  },
  onLoad(options) {
    this.setData({ id: options.id ?? '' });
  },
  onShow() {
    return this.load();
  },
  onHide() {
    this.requestVersion++;
    this.setData({ customer: null, loading: true });
  },
  onUnload() {
    this.requestVersion++;
  },
  async load() {
    const version = ++this.requestVersion;
    const { id } = this.data;
    if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(id)) {
      this.setData({ loading: false, unavailable: true, error: '客户不存在。' });
      return;
    }
    this.setData({ loading: true, customer: null, loginRequired: false, unavailable: false, error: '' });
    try {
      const customer = await loadCustomer(id);
      if (version === this.requestVersion) this.setData({ customer: presentCustomer(customer) });
    } catch (error) {
      if (version !== this.requestVersion) return;
      const status = error instanceof RequestError ? error.status : 0;
      this.setData({ error: errorMessage(error), loginRequired: status === 401, unavailable: status === 404 });
    } finally {
      if (version === this.requestVersion) this.setData({ loading: false });
    }
  },
  returnToList() {
    if (getCurrentPages().length > 1) {
      wx.navigateBack({ fail: () => wx.redirectTo({ url: listUrl }) });
    } else {
      wx.redirectTo({ url: listUrl });
    }
  },
  returnToLogin() {
    wx.reLaunch({ url: entryRoute });
  },
});
