export function idleState(lastActivity, now, timeout=120000, warning=30000) {
  const remaining=Math.max(0,timeout-(now-lastActivity))
  return {expired:remaining===0,warning:remaining>0&&remaining<=warning,seconds:Math.ceil(remaining/1000)}
}
