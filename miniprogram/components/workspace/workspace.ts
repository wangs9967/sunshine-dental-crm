import { entryRoute, navigation, routes, routeUrl, workspaceLinks, workspacePath } from '../../config/navigation';
import { endDemoSession, getDemoRole } from '../../services/demo-session';
import { errorMessage, loadPoints, logoutMember, memberState } from '../../services/member-session';

Component({
  options: { styleIsolation: 'apply-shared' },
  data: {
    permitted: false,
    realMember: false,
    points: '',
    logoutPending: false,
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
      const realMember = memberState() === 'member' && route?.role === 'member';
      if (!route || (!realMember && getDemoRole() !== route.role)) {
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
        realMember,
        path,
        title: route.title,
        roleLabel: navigation[route.role].label,
        emptyText: realMember && path === '/pages/points/index' ? '正在读取积分…'
          : missingId ? '缺少有效标识，请返回列表。' : (route.empty ?? ''),
        points: '',
        backUrl: parent ? routeUrl(parent, routes[parent].id ? id : undefined) : '',
        links: missingId ? [] : workspaceLinks(path, id),
        tabs: route.back ? [] : navigation[route.role].tabs,
      });
      if (realMember && path === '/pages/points/index') this.fetchPoints();
    },
    hide() {
      this.setData({ permitted: false });
    },
  },
  methods: {
    async fetchPoints() {
      try {
        const points = await loadPoints();
        if (this.data.permitted) this.setData({ points, emptyText: '' });
      } catch (error) {
        if (this.data.permitted) this.setData({ emptyText: errorMessage(error) });
      }
    },
    returnToParent() {
      const fallback = this.data.backUrl;
      if (!fallback) return;
      if (getCurrentPages().length > 1) {
        wx.navigateBack({ fail: () => wx.redirectTo({ url: fallback }) });
      } else {
        wx.redirectTo({ url: fallback });
      }
    },
    async returnToEntry() {
      if (this.data.logoutPending) return;
      if (this.data.realMember) {
        this.setData({ logoutPending: true });
        try {
          await logoutMember();
        } catch (error) {
          wx.showToast({ title: errorMessage(error), icon: 'none' });
          return;
        } finally {
          this.setData({ logoutPending: false });
        }
      }
      endDemoSession();
      wx.reLaunch({
        url: entryRoute,
        fail: () => wx.showToast({ title: '页面打开失败，请重试', icon: 'none' }),
      });
    },
  },
});
