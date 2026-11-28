import { failure, history, presentFollowup, validMemberId } from '../../services/followups';

Page({
  data: { id: '', home: false, items: [] as ReturnType<typeof presentFollowup>[], page: 1, total: 0, loading: true, error: '' },
  onLoad(options) {
    this.setData({ id: options.id ?? '', home: options.home === '1' });
  },
  onShow() { void this.load(1); },
  async load(page: number) {
    const { id, home } = this.data;
    if (!validMemberId(id)) {
      this.setData({ loading: false, error: '客户不存在。' });
      return;
    }
    this.setData({ loading: true, error: '', items: [] });
    try {
      const result = await history(id, page, home);
      this.setData({ items: result.items.map(presentFollowup), total: result.total, page });
    } catch (error) {
      this.setData({ error: failure(error) });
    } finally {
      this.setData({ loading: false });
    }
  },
  retry() { void this.load(this.data.page); },
  previous() { void this.load(this.data.page - 1); },
  next() { void this.load(this.data.page + 1); },
});
