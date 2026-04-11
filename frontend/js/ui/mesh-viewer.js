import * as THREE from "three";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { STLLoader } from "three/addons/loaders/STLLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const BG = 0xc0c0c0;
const MESH_COLOR = 0x305090;

/**
 * Three.js OBJ preview with Win32-gray client background.
 */
export class MeshViewer {
  /**
   * @param {HTMLElement} container
   * @param {{ onStatus?: (left: string | null, right?: string | null) => void }} [opts]
   */
  constructor(container, opts = {}) {
    this.container = container;
    this.onStatus = opts.onStatus || (() => {});
    /** @type {{ scene: THREE.Scene; camera: THREE.PerspectiveCamera; renderer: THREE.WebGLRenderer; controls: import("three/addons/controls/OrbitControls.js").OrbitControls } | null} */
    this._viewer = null;
    /** @type {THREE.Group | null} */
    this._meshRoot = null;
  }

  ensure() {
    if (this._viewer) return this._viewer;
    const container = this.container;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(BG);

    const camera = new THREE.PerspectiveCamera(45, 1, 0.01, 5000);
    camera.position.set(2, 1.5, 2);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dir = new THREE.DirectionalLight(0xffffff, 0.75);
    dir.position.set(2, 4, 3);
    scene.add(dir);

    const group = new THREE.Group();
    scene.add(group);
    this._meshRoot = group;

    const resize = () => {
      const w = container.clientWidth || 1;
      const h = container.clientHeight || 1;
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h, false);
    };
    resize();
    new ResizeObserver(resize).observe(container);

    const tick = () => {
      requestAnimationFrame(tick);
      controls.update();
      renderer.render(scene, camera);
    };
    tick();

    this._viewer = { scene, camera, renderer, controls };
    return this._viewer;
  }

  clear() {
    const root = this._meshRoot;
    if (!root) return;
    while (root.children.length) {
      const o = root.children[0];
      root.remove(o);
      o.traverse((c) => {
        if (c.geometry) c.geometry.dispose();
        if (c.material) {
          const m = c.material;
          if (Array.isArray(m)) m.forEach((x) => x.dispose?.());
          else m.dispose?.();
        }
      });
    }
  }

  /**
   * @param {THREE.Object3D} object
   * @param {THREE.PerspectiveCamera} camera
   * @param {import("three/addons/controls/OrbitControls.js").OrbitControls} controls
   */
  _fitCamera(object, camera, controls) {
    const box = new THREE.Box3().setFromObject(object);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z, 0.001);
    const dist = maxDim * 1.8;
    camera.position.set(center.x + dist * 0.7, center.y + dist * 0.5, center.z + dist * 0.7);
    camera.near = Math.max(dist / 2000, 0.001);
    camera.far = dist * 50;
    camera.updateProjectionMatrix();
    controls.target.copy(center);
    controls.update();
  }

  /**
   * @param {string} url
   */
  loadUrl(url) {
    const v = this.ensure();
    if (!v || !this._meshRoot) return;

    this.onStatus("Loading mesh…", null);
    this.clear();

    const loader = new OBJLoader();
    loader.load(
      url,
      (obj) => {
        obj.traverse((child) => {
          if (child.isMesh) {
            child.material = new THREE.MeshStandardMaterial({
              color: MESH_COLOR,
              metalness: 0.12,
              roughness: 0.5,
              flatShading: false,
            });
          }
        });
        this._meshRoot.add(obj);
        this._fitCamera(this._meshRoot, v.camera, v.controls);
        this.onStatus("Ready", null);
      },
      undefined,
      (err) => {
        console.error(err);
        this.onStatus("Failed to load mesh", String(err));
      }
    );
  }

  /**
   * @param {string} url
   */
  loadStlUrl(url) {
    const v = this.ensure();
    if (!v || !this._meshRoot) return;

    this.onStatus("Loading STL…", null);
    this.clear();

    const loader = new STLLoader();
    fetch(url, { credentials: "same-origin" })
      .then((res) => {
        if (!res.ok) return res.text().then((t) => Promise.reject(new Error(t || res.statusText)));
        return res.arrayBuffer();
      })
      .then((buf) => {
        const geometry = loader.parse(buf);
        geometry.computeVertexNormals();
        const mesh = new THREE.Mesh(
          geometry,
          new THREE.MeshStandardMaterial({
            color: MESH_COLOR,
            metalness: 0.12,
            roughness: 0.5,
            flatShading: false,
          })
        );
        this._meshRoot.add(mesh);
        this._fitCamera(this._meshRoot, v.camera, v.controls);
        this.onStatus("Ready", null);
      })
      .catch((err) => {
        console.error(err);
        this.onStatus("Failed to load STL", String(err));
      });
  }
}
