import { createScene } from './scene.js';
import { getViewState } from './view-state.js';
import './style.css';

const TITLES = {
  T1: 'Разгрузка дорог', T2: 'Общественный транспорт', E1: 'Озеленение', E2: 'Качество воздуха',
  S1: 'Школы и детсады', S2: 'Первичная медпомощь', B1: 'Безопасность улиц',
  B2: 'Безопасность движения', C1: 'Надёжность ЖКХ', C2: 'Решение обращений',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export default function ({ parentElement, data, key, setStateValue }) {
  const host = parentElement.querySelector('.city-root');
  const view = getViewState(window, data.view_key || key);
  host.replaceChildren();
  const state = data.states[0];
  const indicator = data.selected_indicator;
  let selectedId = data.selected_district || state.districts[0].id;
  let scene = null;
  let failed = false;
  const title = element('header', 'city-header');
  const titleBlock = element('div', 'city-title-block');
  titleBlock.append(element('span', 'city-eyebrow', 'АСТАНА / ЛАБОРАТОРИЯ РЕШЕНИЙ'), element('h3', '', 'Город, который можно понять'));
  title.append(titleBlock, element('span', 'city-badge', 'Исходное состояние'));
  const layout = element('div', 'city-layout');
  const mapColumn = element('div', 'map-column');
  const viewport = element('div', 'city-viewport');
  const mapTag = element('div', 'map-tag', `${indicator} · ${TITLES[indicator]}`);
  viewport.append(mapTag);
  const cameraControls = element('div', 'camera-controls');
  const controls = [
    ['Общий вид', () => scene?.reset()], ['Сверху', () => scene?.reset(true)],
    ['+', () => scene?.zoom(0.82)], ['−', () => scene?.zoom(1.22)],
  ];
  const cameraButtons = [];
  for (const [label, action] of controls) {
    const button = element('button', '', label);
    button.type = 'button';
    if (label === '+') button.setAttribute('aria-label', 'Приблизить');
    if (label === '−') button.setAttribute('aria-label', 'Отдалить');
    button.onclick = action;
    cameraControls.append(button);
    cameraButtons.push(button);
  }
  viewport.append(cameraControls);
  const legend = element('div', 'city-legend');
  legend.append(element('span', 'legend-alert', '● Ниже 40'), element('span', 'legend-normal', '● 40–100'), element('span', 'legend-scale', 'Высота столбца: 0–100 · риска: 40'));
  const navigation = element('div', 'district-navigation');
  navigation.setAttribute('aria-label', 'Выбор района');
  const detail = element('aside', 'city-detail');
  detail.setAttribute('aria-live', 'polite');
  const buttons = new Map();

  function updateDetails() {
    const district = state.districts.find(item => item.id === selectedId);
    const value = district.indicators[indicator];
    detail.replaceChildren();
    detail.append(element('span', 'city-eyebrow', 'ВЫБРАННЫЙ РАЙОН'), element('h3', 'district-heading', district.name));
    detail.append(element('p', 'indicator-title', `${indicator} · ${TITLES[indicator]}`));
    const valueLine = element('div', `indicator-value ${value < 40 ? 'is-critical' : ''}`);
    valueLine.append(element('strong', '', String(value)), element('span', '', '/ 100'));
    detail.append(valueLine, element('p', `indicator-status ${value < 40 ? 'is-critical' : ''}`, value < 40 ? 'Ниже критического порога 40' : 'Не ниже критического порога 40'));
    const score = element('div', 'district-score');
    score.append(element('span', '', 'Районный балл'), element('strong', '', state.district_scores[district.id].toFixed(4)));
    detail.append(score, element('div', 'detail-label', 'Все показатели района'));
    const indicators = element('div', 'indicator-grid');
    for (const [id, number] of Object.entries(district.indicators)) {
      const cell = element('div', `indicator-cell ${number < 40 ? 'is-critical' : ''} ${id === indicator ? 'active' : ''}`);
      cell.title = TITLES[id];
      cell.append(element('span', '', id), element('strong', '', String(number)));
      indicators.append(cell);
    }
    detail.append(indicators, element('p', 'detail-footnote', 'Числа взяты из расчётной модели. Здания и расположение районов — условные.'));
    for (const [id, button] of buttons) button.setAttribute('aria-pressed', String(id === selectedId));
  }
  function select(id) {
    if (!state.districts.some(district => district.id === id)) return;
    const changed = selectedId !== id;
    selectedId = id;
    scene?.select(id);
    updateDetails();
    if (changed) setStateValue('district_selected', { district_id: id });
  }
  for (const district of state.districts) {
    const button = element('button', '', district.name);
    button.type = 'button';
    button.onclick = () => select(district.id);
    buttons.set(district.id, button);
    navigation.append(button);
  }
  mapColumn.append(viewport, legend, navigation);
  layout.append(mapColumn, detail);
  host.append(title, layout, element('p', 'city-caption', 'Условный 3D-макет · перетаскивайте для вращения, колесо или два пальца — масштаб. Это не географическая карта.'));
  updateDetails();

  function onError(code) {
    if (failed) return;
    failed = true;
    if (scene) view.camera = scene.getCamera();
    scene?.dispose();
    scene = null;
    viewport.dataset.renderReady = 'false';
    cameraButtons.forEach(button => { button.disabled = true; });
    const fallback = element('div', 'city-fallback');
    fallback.setAttribute('role', 'status');
    fallback.append(element('strong', '', '3D недоступно в этом браузере'), element('p', '', 'Выбор района и все показатели доступны ниже. Для повторной попытки перезагрузите страницу.'));
    viewport.append(fallback);
    if (!view.error) {
      view.error = code;
      setStateValue('render_error', { code });
    }
  }
  try {
    if (view.error) onError(view.error);
    else scene = createScene(viewport, state, indicator, selectedId, select, onError, view.camera,
      camera => { view.camera = camera; });
  } catch {
    onError('webgl_unavailable');
  }
  return () => {
    if (scene) view.camera = scene.getCamera();
    scene?.dispose();
    host.replaceChildren();
  };
}
