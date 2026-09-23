import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createTapTracker } from './tap.js';
import { createSceneLifecycle } from './lifecycle.js';

const LAYOUT = {
  saryarka: [-5.8, -3.3], baikonur: [0, -3.3], almaty: [5.8, -3.3],
  nura: [-3, 2.8], esil: [3, 2.8],
};
const HOME = [17, 20, 23];

// Building shapes and positions are schematic; only bars encode data.
export function createScene(viewport, state, indicator, selectedId, onSelect, onError, savedCamera, onCameraChange) {
  const lifecycle = createSceneLifecycle(onError);
  let renderer;
  let scene;
  let controls;
  let observer;
  let disposed = false;
  try {
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch {
    const error = new Error('WebGL is unavailable');
    error.code = 'WEBGL_UNAVAILABLE';
    throw error;
  }
  lifecycle.addCleanup(() => {
    try { renderer.forceContextLoss(); } finally {
      try { renderer.dispose(); } finally { renderer.domElement.remove(); }
    }
  });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
  renderer.setClearColor(0xe9eee7, 1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.setAttribute('aria-label', '3D-макет. Выбор района также доступен кнопками под сценой.');
  viewport.prepend(renderer.domElement);
  scene = new THREE.Scene();
  const geometries = new Set();
  const allMaterials = new Set();
  lifecycle.addCleanup(() => {
    scene.traverse(object => {
      if (object.geometry) geometries.add(object.geometry);
      if (object.material) allMaterials.add(object.material);
    });
    geometries.forEach(item => item.dispose());
    allMaterials.forEach(item => item.dispose());
  });
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 140);
  camera.position.fromArray(HOME);
  controls = new OrbitControls(camera, renderer.domElement);
  lifecycle.addCleanup(() => {
    try { controls.removeEventListener('change', controlsChanged); }
    finally { controls.dispose(); }
  });
  controls.target.set(0, 0, 0);
  controls.minDistance = 15;
  controls.maxDistance = 50;
  controls.minPolarAngle = 0.12;
  controls.maxPolarAngle = Math.PI / 2.25;
  controls.enablePan = false;
  controls.enableDamping = false;
  function controlsChanged() { lifecycle.run(render); }
  if (savedCamera?.position?.length === 3 && savedCamera?.target?.length === 3) {
    camera.position.fromArray(savedCamera.position);
    controls.target.fromArray(savedCamera.target);
  }
  controls.update();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x648172, 2.6));
  const sunlight = new THREE.DirectionalLight(0xfff7e8, 3.5);
  sunlight.position.set(-9, 20, 11);
  sunlight.castShadow = true;
  sunlight.shadow.mapSize.set(1024, 1024);
  Object.assign(sunlight.shadow.camera, { left: -17, right: 17, top: 15, bottom: -15, far: 60 });
  sunlight.shadow.normalBias = 0.04;
  scene.add(sunlight);
  const geometry = new THREE.BoxGeometry(1, 1, 1);
  geometries.add(geometry);
  const materials = new Map();
  function material(color) {
    if (!materials.has(color)) {
      const value = new THREE.MeshStandardMaterial({ color, roughness: 0.83 });
      materials.set(color, value);
      allMaterials.add(value);
    }
    return materials.get(color);
  }
  function box(parent, x, y, z, width, height, depth, color) {
    const mesh = new THREE.Mesh(geometry, material(color));
    mesh.position.set(x, y, z);
    mesh.scale.set(width, height, depth);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    parent.add(mesh);
    return mesh;
  }
  box(scene, 0, -0.45, 0, 18.5, 0.55, 13.2, 0xd7dfd6);
  box(scene, 0, -0.12, -0.1, 17.9, 0.08, 0.7, 0xb7c4bc);
  for (let x = -8; x < 9; x += 1.1) box(scene, x, -0.065, -0.1, 0.45, 0.015, 0.04, 0xf9fbf6);
  const treeGeometry = new THREE.IcosahedronGeometry(0.36, 0);
  geometries.add(treeGeometry);
  const districts = [];
  const labels = [];
  for (const district of state.districts) {
    const [x, z] = LAYOUT[district.id] || [0, 0];
    const group = new THREE.Group();
    group.position.set(x, 0, z);
    group.userData.districtId = district.id;
    scene.add(group);
    const value = district.indicators[indicator];
    const color = value < 40 ? 0xc46c3d : new THREE.Color(0x91c5ae).lerp(new THREE.Color(0x246856), value / 100).getHex();
    const slab = box(group, 0, 0, 0, 5.15, 0.28, 4.7, 0xf4f3e9);
    const borderBoxGeometry = new THREE.BoxGeometry(5.25, 0.32, 4.8);
    geometries.add(borderBoxGeometry);
    const borderGeometry = new THREE.EdgesGeometry(borderBoxGeometry);
    geometries.add(borderGeometry);
    const borderMaterial = new THREE.LineBasicMaterial({ color: 0xb1c5b7 });
    allMaterials.add(borderMaterial);
    const border = new THREE.LineSegments(borderGeometry, borderMaterial);
    group.add(border);
    // A fixed cluster per district, not a claim about actual building counts.
    [[-0.6, -0.7, 1.2], [0.55, -0.8, 1.8], [1.5, -0.7, 0.9], [-0.7, 0.8, 0.7], [0.5, 0.75, 1.15]].forEach(([bx, bz, h], i) => {
      box(group, bx, h / 2 + 0.16, bz, 0.72, h, 0.85, i % 2 ? 0xe9e7db : 0xd5e0d8);
      box(group, bx, h + 0.2, bz, 0.78, 0.09, 0.91, 0xfcfaf0);
      for (let level = 0.45; level < h; level += 0.4) box(group, bx, level + 0.17, bz + 0.433, 0.5, 0.12, 0.012, 0x829d96);
    });
    for (const [tx, tz] of [[1.8, 1], [1.8, 1.75], [-1.1, 1.75]]) {
      box(group, tx, 0.35, tz, 0.07, 0.45, 0.07, 0x899779);
      const crown = new THREE.Mesh(treeGeometry, material(0x709b7d));
      crown.position.set(tx, 0.76, tz);
      crown.castShadow = true;
      group.add(crown);
    }
    const barHeight = value / 100 * 3;
    box(group, -1.9, 1.68, -0.75, 0.1, 3, 0.1, 0xc9d4cd);
    box(group, -1.9, barHeight / 2 + 0.18, -0.75, 0.48, barHeight || 0.015, 0.48, color);
    // The marker is always at 40 on the same 0–100 scale.
    box(group, -1.9, 0.18 + 1.2, -0.75, 0.72, 0.04, 0.72, 0x334f46);
    const label = document.createElement('button');
    label.className = 'district-label';
    label.type = 'button';
    label.dataset.district = district.id;
    label.setAttribute('aria-label', `${district.name}: ${indicator} — ${value}. Выбрать район`);
    const name = document.createElement('span');
    name.textContent = district.name;
    const number = document.createElement('strong');
    number.textContent = String(value);
    label.append(name, number);
    label.onclick = () => lifecycle.run(onSelect, district.id);
    viewport.append(label);
    lifecycle.addCleanup(() => label.remove());
    labels.push({ element: label, position: new THREE.Vector3(x, 0.2, z + 2.15) });
    districts.push({ id: district.id, group, border, slab, label });
  }
  const raycaster = new THREE.Raycaster();
  const tap = createTapTracker();
  function render() {
    if (disposed) return;
    renderer.render(scene, camera);
    onCameraChange({ position: camera.position.toArray(), target: controls.target.toArray() });
    for (const { element, position } of labels) {
      const projected = position.clone().project(camera);
      const px = (projected.x * 0.5 + 0.5) * viewport.clientWidth;
      const py = (-projected.y * 0.5 + 0.5) * viewport.clientHeight;
      element.style.left = `${px}px`;
      element.style.top = `${py}px`;
      element.hidden = projected.z > 1 || px < 0 || px > viewport.clientWidth || py < 0 || py > viewport.clientHeight;
    }
  }
  function select(id) {
    if (disposed) return;
    for (const district of districts) {
      const selected = district.id === id;
      district.border.material.color.setHex(selected ? 0x133f38 : 0xb1c5b7);
      district.label.classList.toggle('selected', selected);
      district.label.setAttribute('aria-pressed', String(selected));
    }
    render();
  }
  function resize() {
    if (disposed) return;
    const width = viewport.clientWidth;
    const height = viewport.clientHeight;
    if (!width || !height) return;
    camera.aspect = width / height;
    renderer.setSize(width, height, false);
    // Keep the whole model visible in portrait; preserve the user's orbit.
    camera.fov = width < 500 ? 57 : 42;
    camera.updateProjectionMatrix();
    render();
  }
  function pointerDown(event) { tap.start(event); }
  function pointerMove(event) { tap.move(event); }
  function pointerCancel(event) { tap.cancel(event); }
  function pointerUp(event) {
    if (!tap.end(event)) return;
    const rect = renderer.domElement.getBoundingClientRect();
    raycaster.setFromCamera(new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1), camera);
    const hit = raycaster.intersectObjects(districts.map(d => d.group), true)[0];
    if (!hit) return;
    let object = hit.object;
    while (object && !object.userData.districtId) object = object.parent;
    if (object) onSelect(object.userData.districtId);
  }
  function contextLost(event) {
    event.preventDefault();
    lifecycle.report('context_lost');
  }
  const guardedPointerDown = event => lifecycle.run(pointerDown, event);
  const guardedPointerMove = event => lifecycle.run(pointerMove, event);
  const guardedPointerCancel = event => lifecycle.run(pointerCancel, event);
  const guardedPointerUp = event => lifecycle.run(pointerUp, event);
  const guardedContextLost = event => lifecycle.run(contextLost, event);
  lifecycle.addCleanup(() => {
    renderer.domElement.removeEventListener('pointerdown', guardedPointerDown);
    renderer.domElement.removeEventListener('pointermove', guardedPointerMove);
    renderer.domElement.removeEventListener('pointercancel', guardedPointerCancel);
    renderer.domElement.removeEventListener('pointerup', guardedPointerUp);
    renderer.domElement.removeEventListener('webglcontextlost', guardedContextLost);
  });
  renderer.domElement.addEventListener('pointerdown', guardedPointerDown);
  renderer.domElement.addEventListener('pointermove', guardedPointerMove);
  renderer.domElement.addEventListener('pointercancel', guardedPointerCancel);
  renderer.domElement.addEventListener('pointerup', guardedPointerUp);
  renderer.domElement.addEventListener('webglcontextlost', guardedContextLost);
  controls.addEventListener('change', controlsChanged);
  observer = new ResizeObserver(() => lifecycle.run(resize));
  lifecycle.addCleanup(() => observer.disconnect());
  observer.observe(viewport);
  lifecycle.run(resize);
  lifecycle.run(select, selectedId);
  viewport.dataset.renderReady = 'true';
  return {
    select(id) { lifecycle.run(select, id); },
    reset(top = false) {
      lifecycle.run(() => {
        controls.target.set(0, 0, 0);
        camera.position.fromArray(top ? [0, 29, 0.1] : HOME);
        controls.update();
        render();
      });
    },
    zoom(factor) {
      lifecycle.run(() => {
        const offset = camera.position.clone().sub(controls.target);
        offset.setLength(THREE.MathUtils.clamp(offset.length() * factor, 15, 50));
        camera.position.copy(controls.target).add(offset);
        controls.update();
        render();
      });
    },
    getCamera() { return lifecycle.run(() => ({ position: camera.position.toArray(), target: controls.target.toArray() })); },
    dispose() {
      if (disposed) return;
      disposed = true;
      lifecycle.dispose();
    },
  };
  } catch (error) {
    disposed = true;
    lifecycle.dispose();
    throw error;
  }
}
