export function allowsDemoSession(
  version = wx.getAccountInfoSync().miniProgram.envVersion,
): boolean {
  return version === 'develop' || version === 'trial';
}

// Public API origins only. Deployment supplies the clinic's HTTPS API domain.
const developmentApiOrigin = 'http://127.0.0.1:18081';
const deployedApiOrigin = '';

export function apiOrigin(version = wx.getAccountInfoSync().miniProgram.envVersion): string {
  return deployedApiOrigin || (version === 'develop' ? developmentApiOrigin : '');
}
