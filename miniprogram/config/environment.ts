export function allowsDemoSession(
  version = wx.getAccountInfoSync().miniProgram.envVersion,
): boolean {
  return version === 'develop' || version === 'trial';
}
