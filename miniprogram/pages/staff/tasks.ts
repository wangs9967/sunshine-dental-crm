import { changeTask, defaultDate, failure, tasks } from '../../services/followups';

const actions: Record<string, string> = { complete: '完成', postpone: '延期', ignore: '忽略' };

Page({
  data: {
    items: [] as Awaited<ReturnType<typeof tasks>>['items'], page: 1, total: 0, loading: true, error: '',
    taskId: '', action: '', actionName: '', result: '', date: '', time: '09:00', saving: false, actionError: '',
  },
  onShow() { void this.load(this.data.page); },
  async load(page: number) {
    this.setData({ loading: true, error: '', items: [] });
    try {
      const data = await tasks(page);
      if (page > 1 && data.items.length === 0) {
        await this.load(1);
        return;
      }
      this.setData({ ...data, page });
    } catch (error) {
      this.setData({ error: failure(error) });
    } finally {
      this.setData({ loading: false });
    }
  },
  retry() { void this.load(this.data.page); },
  previous() { void this.load(this.data.page - 1); },
  next() { void this.load(this.data.page + 1); },
  choose(event: WechatMiniprogram.TouchEvent) {
    const { id, action } = event.currentTarget.dataset as { id: string; action: string };
    if (!actions[action] || this.data.saving) return;
    this.setData({ taskId: id, action, actionName: actions[action], result: '', date: defaultDate(), time: '09:00', actionError: '' });
  },
  cancel() { if (!this.data.saving) this.setData({ taskId: '', actionError: '' }); },
  changeDate(event: WechatMiniprogram.PickerChange) { this.setData({ date: String(event.detail.value) }); },
  changeTime(event: WechatMiniprogram.PickerChange) { this.setData({ time: String(event.detail.value) }); },
  changeResult(event: WechatMiniprogram.Input) { this.setData({ result: event.detail.value }); },
  async submit() {
    const { taskId, action, result, date, time, saving } = this.data;
    if (!taskId || saving) return;
    if (action !== 'postpone' && !result.trim()) {
      this.setData({ actionError: '请填写处理结果。' });
      return;
    }
    this.setData({ saving: true, actionError: '' });
    try {
      await changeTask(taskId, action, result, date, time);
      this.setData({ taskId: '' });
      await this.load(this.data.page);
    } catch (error) {
      this.setData({ actionError: failure(error) });
      await this.load(this.data.page);
    } finally {
      this.setData({ saving: false });
    }
  },
});
