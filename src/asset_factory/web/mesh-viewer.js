import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {FBXLoader} from 'three/addons/loaders/FBXLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';

// A local inspection renderer. Display modes never modify exported model files.
class MeshInspector extends HTMLElement {
 static observedAttributes=['src','camera-orbit'];
 connectedCallback(){
  if(this.renderer)return;
  this.scene=new THREE.Scene();this.scene.background=new THREE.Color('#27313b');
  this.camera=new THREE.PerspectiveCamera(38,1,.01,1000);
  this.renderer=new THREE.WebGLRenderer({antialias:true});this.renderer.setPixelRatio(Math.min(devicePixelRatio,2));
  this.renderer.toneMapping=THREE.ACESFilmicToneMapping;this.renderer.toneMappingExposure=1;
  this.append(this.renderer.domElement);this.renderer.domElement.setAttribute('aria-label','3D inspection canvas');
  this.controls=new OrbitControls(this.camera,this.renderer.domElement);this.controls.enableDamping=true;this.controls.enabled=!this.hasAttribute('thumbnail');this.controls.enableRotate=true;this.controls.enableZoom=true;this.controls.enablePan=true;this.controls.mouseButtons={LEFT:THREE.MOUSE.ROTATE,MIDDLE:THREE.MOUSE.DOLLY,RIGHT:THREE.MOUSE.PAN};
  this.scene.add(new THREE.HemisphereLight(0xe6f0ff,0x39404a,.5));
  const key=new THREE.DirectionalLight(0xfff0db,1.8);key.position.set(3,4,5);this.scene.add(key);
  const rim=new THREE.DirectionalLight(0xa7cbff,1.4);rim.position.set(-4,2,-3);this.scene.add(rim);
  const generator=new THREE.PMREMGenerator(this.renderer),room=new RoomEnvironment();
  this.env=generator.fromScene(room);this.scene.environment=this.env.texture;room.dispose();generator.dispose();
  this.mode='clay';this.doubleSided=true;this.meshes=[];this.serial=0;
  this.observer=new ResizeObserver(()=>this.resize());this.observer.observe(this);this.resize();
  if(!this.hasAttribute('thumbnail'))this.renderer.setAnimationLoop(()=>{if(!this.hidden&&this.getClientRects().length){this.controls.update();this.renderer.render(this.scene,this.camera);}});
  if(this.getAttribute('src'))this.load(this.getAttribute('src'));
 }
 set src(value){this.setAttribute('src',value);}
 attributeChangedCallback(name,old,value){if(old===value||!this.renderer)return;if(name==='src'){if(value)this.load(value);else{this.serial++;this.clear();}}else this.jumpCameraToGoal();}
 resize(){const w=this.clientWidth,h=this.clientHeight;if(!w||!h)return;this.renderer.setSize(w,h);this.camera.aspect=w/h;this.camera.updateProjectionMatrix();}
 disposeModel(root){root.traverse(o=>{if(o.geometry)o.geometry.dispose();for(const m of [].concat(o.material||[])){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}});}
 clear(){if(!this.root)return;this.scene.remove(this.root);for(const entry of this.meshes){entry.mesh.remove(entry.overlay);entry.overlay.material.dispose();entry.clay.dispose();entry.mesh.material=entry.original;}this.disposeModel(this.root);this.root=null;this.meshes=[];}
 async load(url){
  const serial=++this.serial;this.clear();
  try{
   const manager=new THREE.LoadingManager();
   let texturesFailed=false;
   const resourcesReady=new Promise(resolve=>{manager.onLoad=resolve;});
   manager.onError=()=>{texturesFailed=true;};
   const loaded=this.getAttribute('model-format')==='fbx'?await new FBXLoader(manager).loadAsync(url):await new GLTFLoader(manager).loadAsync(url);
   await resourcesReady;
   if(texturesFailed)throw new Error('Model texture failed to load');
   const gltf={scene:loaded.scene||loaded};
   if(serial!==this.serial){this.disposeModel(gltf.scene);return;}
   this.root=gltf.scene;this.scene.add(this.root);
   const box=new THREE.Box3().setFromObject(this.root),size=box.getSize(new THREE.Vector3());
   if(box.isEmpty()||!Number.isFinite(size.length()))throw new Error('Empty model');
   this.center=box.getCenter(new THREE.Vector3());this.radius=Math.max(size.length()/2,.001);
   this.distance=this.radius/Math.sin(THREE.MathUtils.degToRad(19))*1.12;
   this.camera.near=this.radius/1000;this.camera.far=this.radius*100;this.camera.updateProjectionMatrix();
   this.controls.minDistance=this.radius*.08;this.controls.maxDistance=this.radius*20;
   this.root.traverse(mesh=>{
    if(!mesh.isMesh)return;
    const original=mesh.material;
    const clay=new THREE.MeshStandardMaterial({color:0xc7ced7,metalness:0,roughness:.78,envMapIntensity:.18,polygonOffset:true,polygonOffsetFactor:1,polygonOffsetUnits:1});
    const wire=new THREE.MeshBasicMaterial({color:0x14202b,wireframe:true,transparent:true,opacity:.85,depthWrite:false});
    const overlay=mesh.isSkinnedMesh?new THREE.SkinnedMesh(mesh.geometry,wire):new THREE.Mesh(mesh.geometry,wire);
    if(mesh.isSkinnedMesh){overlay.bindMode=mesh.bindMode;overlay.bind(mesh.skeleton,mesh.bindMatrix);}
    overlay.name='inspection-wire';overlay.visible=false;overlay.renderOrder=2;
    this.meshes.push({mesh,original,clay,overlay});
   });
   for(const e of this.meshes)e.mesh.add(e.overlay);
   this.setDoubleSided(this.doubleSided);this.setMode(this.mode);this.jumpCameraToGoal();this.resize();this.dispatchEvent(new Event('load'));
  }catch(error){if(serial===this.serial){this.clear();this.dispatchEvent(new Event('error'));}}
 }
 setMode(mode){
  this.mode=mode;
  for(const e of this.meshes){
   e.mesh.material=mode==='material'?e.original:e.clay;
   e.clay.visible=mode!=='xray';e.overlay.visible=!!this.wireEnabled||mode==='xray';
   e.overlay.material.depthTest=mode!=='xray';e.overlay.material.color.set(mode==='xray'?0x80dcff:0x14202b);e.overlay.material.opacity=mode==='xray'?.28:.45;
  }
 }
 setDoubleSided(enabled){
  this.doubleSided=enabled;
  const side=enabled?THREE.DoubleSide:THREE.FrontSide;
  for(const e of this.meshes)for(const material of [e.clay,e.overlay.material,...[].concat(e.original)]){
   material.side=side;material.needsUpdate=true;
  }
 }
 captureThumbnail(){this.resize();this.renderer.render(this.scene,this.camera);return this.renderer.domElement.toDataURL('image/jpeg',.86);}
 setWireEnabled(enabled){this.wireEnabled=enabled;this.setMode(this.mode);}
 jumpCameraToGoal(){
  if(!this.center)return;
  const [theta,phi]=(this.getAttribute('camera-orbit')||'0deg 75deg auto').split(' ').map(parseFloat);
  const t=THREE.MathUtils.degToRad(theta||0),p=THREE.MathUtils.degToRad(phi||75);
  this.controls.target.copy(this.center);this.camera.position.copy(this.center).add(new THREE.Vector3(this.distance*Math.sin(p)*Math.sin(t),this.distance*Math.cos(p),this.distance*Math.sin(p)*Math.cos(t)));this.controls.update();
 }
 disconnectedCallback(){this.serial++;this.clear();this.observer?.disconnect();this.controls?.dispose();this.env?.dispose();this.renderer?.setAnimationLoop(null);this.renderer?.dispose();this.renderer?.domElement.remove();this.renderer=null;}
}
customElements.define('mesh-inspector',MeshInspector);
