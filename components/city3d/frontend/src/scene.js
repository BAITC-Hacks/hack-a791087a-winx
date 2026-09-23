import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { createTapTracker } from './tap.js';

const LAYOUT = {
  saryarka: [-5.8, -3.3], baikonur: [0, -3.3], almaty: [5.8, -3.3],
  nura: [-3, 2.8], esil: [3, 2.8],
};
const HOME = [17, 20, 23];

// Building shapes and positions are schematic; only bars encode data.
export function createScene(viewport, state, indicator, selectedId, onSelect, onError, savedCamera, onCameraChange) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.7));
  renderer.setClearColor(0xe9eee7, 1);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.domElement.setAttribute('aria-label', '3D-макет. Выбор района также доступен кнопками под сценой.');
  viewport.prepend(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 140);
  camera.position.fromArray(HOME);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 0, 0);
  controls.minDistance = 15;
  controls.maxDistance = 50;
  controls.minPolarAngle = 0.12;
  controls.maxPolarAngle = Math.PI / 2.25;
  controls.enablePan = false;
  controls.enableDamping = false;
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
  const materials = new Map();
  function material(color) {
    if (!materials.has(color)) materials.set(color, new THREE.MeshStandardMaterial({ color, roughness: 0.83 }));
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
    const border = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(5.25, 0.32, 4.8)),
      new THREE.LineBasicMaterial({ color: 0xb1c5b7 }),
    );
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
    label.onclick = () => onSelect(district.id);
    viewport.append(label);
    labels.push({ element: label, position: new THREE.Vector3(x, 0.2, z + 2.15) });
    districts.push({ id: district.id, group, border, slab, label });
  }
  let disposed = false;
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
    for (const district of districts) {
      const selected = district.id === id;
      district.border.material.color.setHex(selected ? 0x133f38 : 0xb1c5b7);
      district.label.classList.toggle('selected', selected);
      district.label.setAttribute('aria-pressed', String(selected));
    }
    render();
  }
  function resize() {
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
    onError('context_lost');
  }
  renderer.domElement.addEventListener('pointerdown', pointerDown);
  renderer.domElement.addEventListener('pointermove', pointerMove);
  renderer.domElement.addEventListener('pointercancel', pointerCancel);
  renderer.domElement.addEventListener('pointerup', pointerUp);
  renderer.domElement.addEventListener('webglcontextlost', contextLost);
  controls.addEventListener('change', render);
  const observer = new ResizeObserver(resize);
  observer.observe(viewport);
  resize();
  select(selectedId);
  viewport.dataset.renderReady = 'true';
  return {
    select,
    reset(top = false) {
      controls.target.set(0, 0, 0);
      camera.position.fromArray(top ? [0, 29, 0.1] : HOME);
      controls.update();
      render();
    },
    zoom(factor) {
      const offset = camera.position.clone().sub(controls.target);
      offset.setLength(THREE.MathUtils.clamp(offset.length() * factor, 15, 50));
      camera.position.copy(controls.target).add(offset);
      controls.update();
      render();
    },
    getCamera() { return { position: camera.position.toArray(), target: controls.target.toArray() }; },
    dispose() {
      disposed = true;
      observer.disconnect();
      controls.removeEventListener('change', render);
      controls.dispose();
      renderer.domElement.removeEventListener('pointerdown', pointerDown);
      renderer.domElement.removeEventListener('pointermove', pointerMove);
      renderer.domElement.removeEventListener('pointercancel', pointerCancel);
      renderer.domElement.removeEventListener('pointerup', pointerUp);
      renderer.domElement.removeEventListener('webglcontextlost', contextLost);
      const geometries = new Set();
      const allMaterials = new Set();
      scene.traverse(object => {
        if (object.geometry) geometries.add(object.geometry);
        if (object.material) allMaterials.add(object.material);
      });
      geometries.forEach(item => item.dispose());
      allMaterials.forEach(item => item.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
      labels.forEach(({ element }) => element.remove());
    },
  };
}
