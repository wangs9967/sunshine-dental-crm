import { entryRoute, navigation } from '../../config/navigation';
import { getDemoRole } from '../../services/demo-session';
import { RequestError, errorMessage } from '../../services/request';
import { customerStatuses, loadCustomers, presentCustomer } from '../../services/staff-customers';

Page({
  requestVersion: 0,
  data: {
    customers: [] as ReturnType<typeof presentCustomer>[],
    tabs: navigation.employee.tabs,
    statuses: customerStatuses,
    selections: [0, 0, 0],
    keyword: '',
    query: '',
    page: 1,
    hasNext: false,
    loading: true,
    loginRequired: false,
    error: '',
  },
  onShow() {
    return this.load();
  },
  onHide() {
    this.requestVersion++;
    this.setData({ customers: [], loading: true });
  },
  onUnload() {
    this.requestVersion++;
  },
  changeKeyword(event: WechatMiniprogram.Input) {
    this.setData({ keyword: event.detail.value });
  },
  changeStatus(event: WechatMiniprogram.PickerChange) {
    const selections = [...this.data.selections];
    selections[Number(event.currentTarget.dataset.index)] = Number(event.detail.value);
    this.setData({ selections, query: this.data.keyword.trim(), page: 1 });
    return this.load();
  },
  search() {
    this.setData({ query: this.data.keyword.trim(), page: 1 });
    return this.load();
  },
  previous() {
    if (this.data.page > 1) {
      this.setData({ page: this.data.page - 1 });
      return this.load();
    }
  },
  next() {
    if (this.data.hasNext) {
      this.setData({ page: this.data.page + 1 });
      return this.load();
    }
  },
  async load() {
    const version = ++this.requestVersion;
    const { query, selections, page } = this.data;
    this.setData({ loading: true, loginRequired: false, error: '', customers: [], hasNext: false });
    try {
      const result = await loadCustomers(query, selections, page);
      if (version !== this.requestVersion) return;
      if (!result.items.length && page > 1) {
        this.setData({ page: Math.max(1, Math.min(page - 1, Math.ceil(result.total / result.page_size))) });
        await this.load();
        return;
      }
      this.setData({ customers: result.items.map(presentCustomer), hasNext: result.page * result.page_size < result.total });
    } catch (error) {
      if (version !== this.requestVersion) return;
      const loginRequired = error instanceof RequestError && error.status === 401;
      this.setData({
        loginRequired,
        error: loginRequired && getDemoRole() === 'employee' ? '演示身份无法读取客户资料。' : errorMessage(error),
      });
    } finally {
      if (version === this.requestVersion) this.setData({ loading: false });
    }
  },
  returnToLogin() {
    wx.reLaunch({ url: entryRoute });
  },
});
