// Validate the render boundary, not the municipal model. Python owns all maths.
const INDICATORS = ['T1','T2','E1','E2','S1','S2','B1','B2','C1','C2'];
const DISTRICTS = ['esil','almaty','saryarka','baikonur','nura'];
const ORDER = ['baseline','A','B'];
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const number = value => typeof value === 'number' && Number.isFinite(value);

export function validatePayload(data) {
  if (!object(data) || data.schema_version !== 1) return 'unsupported_schema';
  if (!Array.isArray(data.states) || !data.states.length || typeof data.diff_only !== 'boolean'
      || !INDICATORS.includes(data.selected_indicator)
      || (data.selected_district !== null && !DISTRICTS.includes(data.selected_district))) return 'render_failed';
  let previous = -1;
  const ids = [];
  for (const state of data.states) {
    if (!object(state)) return 'render_failed';
    const order = ORDER.indexOf(state.id);
    if (order <= previous || order < 0 || typeof state.label !== 'string'
        || state.is_baseline !== (state.id === 'baseline') || !number(state.score)
        || !Number.isInteger(state.cost) || state.cost < 0
        || !Number.isInteger(state.remaining_budget) || state.remaining_budget < 0
        || !Array.isArray(state.decisions) || state.decisions.length !== (state.is_baseline ? 0 : 5)
        || !Array.isArray(state.districts) || state.districts.length !== 5 || !object(state.district_scores)) return 'render_failed';
    const districtIds = new Set();
    for (const district of state.districts) {
      if (!object(district) || !DISTRICTS.includes(district.id) || districtIds.has(district.id)
          || typeof district.name !== 'string' || !object(district.indicators)
          || Object.keys(district.indicators).length !== 10 || !number(state.district_scores[district.id])
          || INDICATORS.some(code => !number(district.indicators[code]) || district.indicators[code] < 0 || district.indicators[code] > 100)) return 'render_failed';
      districtIds.add(district.id);
    }
    const measures = new Set();
    for (const decision of state.decisions) {
      if (!object(decision) || typeof decision.measure_id !== 'string' || !decision.measure_id
          || measures.has(decision.measure_id)
          || (decision.district_id !== null && !DISTRICTS.includes(decision.district_id))) return 'render_failed';
      measures.add(decision.measure_id);
    }
    previous = order;
    ids.push(state.id);
  }
  if ((ids.includes('B') && !ids.includes('A')) || (data.diff_only && !(ids.includes('A') && ids.includes('B')))) return 'render_failed';
  return null;
}
