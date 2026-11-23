import { entryRoute, navigation, routes, routeUrl, workspaceLinks, workspacePath } from '../../config/navigation';
import { endDemoSession, getDemoRole } from '../../services/demo-session';

Component({
  options: { styleIsolation: 'apply-shared' },
  data: {
    permitted: false,
    path: '',
    title: '',
    roleLabel: '',
    emptyText: '',
    backUrl: '',
    links: [] as ReturnType<typeof workspaceLinks>,
    tabs: [] as ReadonlyArray<{ path: string; label: string }>,
  },
  pageLifetimes: {
    show() {
      const pages = getCurrentPages();
      const page = pages[pages.length - 1];
      const path = `/${page.route}`;
      const route = routes[path];
      if (!route || getDemoRole() !== route.role) {
        this.setData({ permitted: false });
        return;
      }
      const id = page.options?.id;
      const missingId = Boolean(route.id && routeUrl(path, id) === path);
      const parent = route.back && missingId && routes[route.back].id
        ? (routes[route.back].back ?? workspacePath(route.role))
        : route.back;
      this.setData({
        permitted: true,
        path,
        title: route.title,
        roleLabel: navigation[route.role].label,
        emptyText: missingId ? '缺少有效标识，请返回列表选择演示记录。' : (route.empty ?? ''),
        backUrl: parent ? routeUrl(parent, routes[parent].id ? id : undefined) : '',
        links: missingId ? [] : workspaceLinks(path, id),
        tabs: route.back ? [] : navigation[route.role].tabs,
      });
    },
    hide() {
      this.setData({ permitted: false });
    },
  },
  methods: {
    returnToParent() {
      const fallback = this.data.backUrl;
      if (!fallback) return;
      if (getCurrentPages().length > 1) {
        wx.navigateBack({ fail: () => wx.redirectTo({ url: fallback }) });
      } else {
        wx.redirectTo({ url: fallback });
      }
    },
    returnToEntry() {
      endDemoSession();
      wx.reLaunch({
        url: entryRoute,
        fail: () => wx.showToast({ title: '页面打开失败，请重试', icon: 'none' }),
      });
    },
  },
});
