import test from 'node:test';
import assert from 'node:assert/strict';
import { getActiveState, validatePayload } from './protocol.js';

const codes = ['T1','T2','E1','E2','S1','S2','B1','B2','C1','C2'];
function payload() {
  const ids = ['esil','almaty','saryarka','baikonur','nura'];
  return {schema_version:1, selected_indicator:'S1', selected_district:null, diff_only:false,
    states:[{id:'baseline',label:'Исходное состояние',is_baseline:true,decisions:[],cost:0,remaining_budget:100,score:52.55768,
      district_scores:Object.fromEntries(ids.map(id=>[id,49.18])),
      districts:ids.map(id=>({id,name:id,indicators:Object.fromEntries(codes.map(code=>[code,38]))}))}]};
}
test('only schema 1 is accepted and unsupported versions are reported safely',()=>{
  for (const data of [null,{}, {schema_version:2}, {schema_version:'1'}]) assert.equal(validatePayload(data),'unsupported_schema');
});
test('baseline and a saved plan allow null selection and keep fractional numbers',()=>{
  const data=payload(); assert.equal(validatePayload(data),null);
  const state=data.states[0]; state.id='A'; state.label='Сохранённый план A'; state.is_baseline=false;
  state.decisions=Array.from({length:5},(_,i)=>({measure_id:`M${i+1}`,district_id:null}));
  state.districts[4].indicators.S2=43.75;
  assert.equal(validatePayload(data),null); assert.equal(state.districts[4].indicators.S2,43.75);
});
test('malformed selectors and nonfinite data are rejected before WebGL',()=>{
  for (const mutate of [d=>d.selected_indicator='bad',d=>d.selected_district='bad',d=>d.states=[],d=>d.states[0].score=NaN,
    d=>d.states[0].districts[0].indicators.S1=101,d=>d.states[0].districts[0].indicators.S1=Infinity,
    d=>delete d.states[0].districts[0].indicators.S1,d=>d.states[0].district_scores.esil='49',
    d=>d.states[0].districts[0].id='unknown',d=>d.diff_only='false']) {
    const data=payload(); mutate(data); assert.equal(validatePayload(data),'render_failed');
  }
});
test('state identity and ordering cannot label a scenario baseline or invent B',()=>{
  for (const mutate of [d=>d.states[0].is_baseline=false,d=>d.states[0].id='B',d=>d.states.push(structuredClone(d.states[0])),
    d=>d.diff_only=true]) {
    const data=payload(); mutate(data); assert.equal(validatePayload(data),'render_failed');
  }
});
test('the bridge may select any included state and omission selects the first state',()=>{
  const data=payload();
  assert.equal(getActiveState(data).id,'baseline');
  data.states.push({...structuredClone(data.states[0]),id:'A',label:'План A',is_baseline:false,
    decisions:Array.from({length:5},(_,i)=>({measure_id:`M${i+1}`,district_id:null}))});
  data.active_state='A';
  assert.equal(validatePayload(data),null);
  assert.equal(getActiveState(data).id,'A');
});
test('unknown bridge active state fails payload validation',()=>{
  const data=payload(); data.active_state='C';
  assert.equal(validatePayload(data),'render_failed');
});
