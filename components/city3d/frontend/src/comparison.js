const INDICATORS = ['T1','T2','E1','E2','S1','S2','B1','B2','C1','C2'];

// Match by stable district id so Python may return districts in any order.
export function compareStates(stateA, stateB) {
  if (!stateA || !stateB) return {};
  const byIdB = new Map(stateB.districts.map(district => [district.id, district]));
  const result = {};
  for (const districtA of stateA.districts) {
    const districtB = byIdB.get(districtA.id);
    if (!districtB) continue;
    const indicators = {};
    for (const code of INDICATORS) {
      const a = districtA.indicators[code];
      const b = districtB.indicators[code];
      indicators[code] = { a, b, delta: b - a };
    }
    result[districtA.id] = { indicators };
  }
  return result;
}

export function getChangedDistrictIds(comparison, indicator) {
  return Object.keys(comparison).filter(id => comparison[id].indicators[indicator]?.delta !== 0);
}
