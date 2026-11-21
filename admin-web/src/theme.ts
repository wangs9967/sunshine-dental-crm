import type { ThemeConfig } from 'antd';

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#2878D8',
    colorBgLayout: '#F4F7FB',
    colorBgContainer: '#FFFFFF',
    colorText: '#1B2D40',
    colorTextSecondary: '#65788C',
    colorBorder: '#DDE6F0',
    colorLink: '#155AA8',
    fontFamily: '"Noto Sans SC", "Microsoft YaHei", sans-serif',
    borderRadius: 8,
    controlHeight: 38,
  },
  components: {
    Card: { paddingLG: 24 },
    Menu: {
      itemHeight: 38,
      itemSelectedBg: '#EAF3FF',
      itemSelectedColor: '#155AA8',
      itemMarginInline: 0,
      groupTitleFontSize: 12,
    },
    Table: { headerBg: '#F4F7FB', cellPaddingBlock: 14 },
  },
};
