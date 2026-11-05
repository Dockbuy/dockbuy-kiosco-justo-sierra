export function trapFocus(event) {
  if(event.key!=='Tab')return
  const elements=[...event.currentTarget.querySelectorAll('button:not([disabled]),input:not([disabled])')].filter(el=>el.offsetParent!==null)
  const first=elements[0],last=elements.at(-1)
  if(!first)return
  if(!elements.includes(document.activeElement)){event.preventDefault();first.focus()}
  else if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
}
