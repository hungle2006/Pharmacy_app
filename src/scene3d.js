import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const cover = document.getElementById('cover');
const canvas = document.getElementById('scene');
const reduced = matchMedia('(prefers-reduced-motion:reduce)');
let renderer, model, frame = 0, previous = 0, running = false, elapsed = 0;
const pointer = {x:0,y:0};
const eased = {x:0,y:0};

function fallback() {
  running = false;
  cover.dataset.fallback = 'true';
  cancelAnimationFrame(frame);
  renderer?.dispose();
  const replacement = document.createElement('canvas');
  replacement.id = 'scene';
  replacement.setAttribute('aria-hidden', 'true');
  canvas.replaceWith(replacement);
  const script = document.createElement('script');
  script.src = '/assets/scene.js';
  document.body.append(script);
}

try {
  renderer = new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 1.5));
  renderer.setClearColor(0x000000, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(35, 1, .1, 100);
  camera.position.z = 9;
  const pmrem = new THREE.PMREMGenerator(renderer);
  const room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, .04);
  scene.environment = environment.texture;
  room.dispose();
  pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xe4fff0, 0x16382b, 2));
  const key = new THREE.DirectionalLight(0xffffff, 4);
  key.position.set(-3, 4, 5);scene.add(key);
  const group = new THREE.Group();scene.add(group);
  const orbit = new THREE.Group();group.add(orbit);
  for (let i=0;i<3;i++) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(2.05+i*.23,.006,6,120),new THREE.MeshBasicMaterial({color:0x86d3b0,transparent:true,opacity:.32}));
    ring.rotation.set(.7+i*.42,i*.6,-.3+i*.3);
    orbit.add(ring);
    const sphere = new THREE.Mesh(new THREE.SphereGeometry(i===0?.14:.095,24,16),new THREE.MeshStandardMaterial({color:i===1?0xf1eacb:0xa7efc7,metalness:.3,roughness:.22}));
    sphere.position.set(Math.cos(i*2)*2.3,Math.sin(i*2)*1.7,i*.25);orbit.add(sphere);
  }
  function theme() {const dark=document.documentElement.dataset.theme==='dark';key.intensity=dark?4:3;renderer.toneMappingExposure=dark?1.2:1.05;draw();}
  function size() {
    const w=cover.clientWidth,h=cover.clientHeight;if(!w||!h)return;
    renderer.setSize(w,h,false);camera.aspect=w/h;camera.updateProjectionMatrix();
    const halfHeight=Math.tan(THREE.MathUtils.degToRad(17.5))*camera.position.z;
    group.position.set((w<760?.38:.60)*halfHeight*camera.aspect,0,0);
    group.scale.setScalar(w<760?.68:Math.min(1.08,h/850));draw();
  }
  function draw() {
    if(model){model.rotation.set(.18+eased.y*.15,elapsed*.13+eased.x*.22,-.38);model.position.y=Math.sin(elapsed*.7)*.09;}
    orbit.rotation.y=elapsed*.045;renderer.render(scene,camera);
  }
  function tick(now) {
    if(!running)return;
    const dt=Math.min((now-previous)/1000,.05);previous=now;
    elapsed+=dt;eased.x+=(pointer.x-eased.x)*.055;eased.y+=(pointer.y-eased.y)*.055;draw();
    frame=requestAnimationFrame(tick);
  }
  function stop(){running=false;cancelAnimationFrame(frame);}
  function start(){if(running||cover.hidden||document.hidden)return;if(reduced.matches){draw();return;}running=true;previous=performance.now();frame=requestAnimationFrame(tick);}
  new GLTFLoader().load('/assets/models/pharmabiz-capsule.glb',gltf=>{
    model=gltf.scene;group.add(model);canvas.dataset.renderer='blender-webgl';size();start();
  },undefined,fallback);
  cover.addEventListener('pointermove',e=>{pointer.x=e.clientX/innerWidth-.5;pointer.y=e.clientY/innerHeight-.5;});
  cover.addEventListener('pointerleave',()=>{pointer.x=0;pointer.y=0;});
  window.addEventListener('resize',size,{passive:true});
  document.addEventListener('visibilitychange',()=>document.hidden?stop():start());
  new MutationObserver(()=>{if(cover.hidden)stop();else{size();start();}}).observe(cover,{attributes:true,attributeFilter:['hidden']});
  new MutationObserver(theme).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
  reduced.addEventListener('change',()=>{stop();start();});
  canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();stop();});
  canvas.addEventListener('webglcontextrestored',()=>{size();start();});
  size();
} catch { fallback(); }
