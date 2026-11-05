export function orderedCharges(charges) {
  return [...charges].sort((a, b) => a.fechaVencimiento.localeCompare(b.fechaVencimiento) || a.id - b.id)
}
export function addNext(charges, selected, id) {
  const ordered = orderedCharges(charges)
  return ordered[selected.length]?.id === id ? [...selected, id] : selected
}
export function removeLast(selected, id) {
  return selected.at(-1) === id ? selected.slice(0, -1) : selected
}
