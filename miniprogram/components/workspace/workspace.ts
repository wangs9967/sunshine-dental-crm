import { entryRoute, isDemoRole, navigation } from '../../config/navigation';
import { endDemoSession, getDemoRole } from '../../services/demo-session';

Component({
  options: { styleIsolation: 'apply-shared' },
  properties: {
    role: String,
    current: Number,
    emptyText: String,
  },
  data: {
    permitted: false,
    title: '',
    roleLabel: '',
    links: [] as ReadonlyArray<{ url: string; label: string; description: string }>,
  },
  pageLifetimes: {
    show() {
      const { role, current } = this.properties;
      if (!isDemoRole(role) || getDemoRole() !== role) {
        this.setData({ permitted: false });
        return;
      }
      const workspace = navigation[role];
      this.setData({
        permitted: true,
        title: workspace.links[current]?.label ?? workspace.label,
        roleLabel: workspace.label,
        links: workspace.links,
      });
    },
    hide() {
      this.setData({ permitted: false });
    },
  },
  methods: {
    returnToEntry() {
      endDemoSession();
      wx.reLaunch({
        url: entryRoute,
        fail: () => wx.showToast({ title: '页面打开失败，请重试', icon: 'none' }),
      });
    },
  },
});
