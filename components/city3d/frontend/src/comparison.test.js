import test from 'node:test';
import assert from 'node:assert/strict';
import { compareStates, getChangedDistrictIds } from './comparison.js';

const codes=['T1','T2','E1','E2','S1','S2','B1','B2','C1','C2'];
function state(entries) {
  return {districts:entries.map(([id,values])=>({id,indicators:Object.fromEntries(codes.map(code=>[code,values[code] ?? 0]))}))};
}
test('comparison keeps exact fractional B minus A values',()=>{
  const result=compareStates(state([['esil',{T1:40.1}]]),state([['esil',{T1:43.35}]]));
  assert.equal(result.esil.indicators.T1.delta,3.25);
});
test('identical plans have no changed districts',()=>{
  const a=state([['esil',{T1:42}],['nura',{T1:58}]]);
  const result=compareStates(a,structuredClone(a));
  assert.deepEqual(getChangedDistrictIds(result,'T1'),[]);
});
test('comparison matches districts by id and filters changes by selected indicator',()=>{
  const a=state([['esil',{T1:20,T2:50}],['nura',{T1:30,T2:60}]]);
  const b=state([['nura',{T1:30,T2:61}],['esil',{T1:21,T2:50}]]);
  const result=compareStates(a,b);
  assert.equal(result.esil.indicators.T1.delta,1);
  assert.equal(result.nura.indicators.T2.delta,1);
  assert.deepEqual(getChangedDistrictIds(result,'T1'),['esil']);
});
