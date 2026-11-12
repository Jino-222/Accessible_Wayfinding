import * as THREE from './vendor/three/three.module.min.js';

// A lightweight browser reconstruction of the authored Unity corridor.
export function createScene(canvas,config){
  const renderer=new THREE.WebGLRenderer({canvas,antialias:true,alpha:false,powerPreference:'low-power'});
  renderer.setPixelRatio(Math.min(devicePixelRatio||1,1.75));
  renderer.outputColorSpace=THREE.SRGBColorSpace;
  const scene=new THREE.Scene();scene.background=new THREE.Color('#dadfd9');
  scene.fog=new THREE.Fog('#dadfd9',18,43);
  scene.add(new THREE.HemisphereLight('#ffffff','#a0aa9c',2.1));
  const sun=new THREE.DirectionalLight('#fff8e7',1.5);sun.position.set(2,6,2);scene.add(sun);
  const camera=new THREE.PerspectiveCamera(63,1,.06,70);
  const mats={};
  const material=color=>mats[color]??=new THREE.MeshLambertMaterial({color});
  function box(x,y,z,w,h,d,color){
    const mesh=new THREE.Mesh(new THREE.BoxGeometry(w,h,d),typeof color==='string'?material(color):color);
    mesh.position.set(x,y,z);scene.add(mesh);return mesh;
  }
  function textureCanvas(w,h,draw){
    const el=document.createElement('canvas');el.width=w;el.height=h;draw(el.getContext('2d'),w,h);
    const texture=new THREE.CanvasTexture(el);texture.colorSpace=THREE.SRGBColorSpace;return texture;
  }
  function plane(texture,x,y,z,w,h,rotation=0){
    const mesh=new THREE.Mesh(new THREE.PlaneGeometry(w,h),new THREE.MeshBasicMaterial({map:texture}));
    mesh.position.set(x,y,z);mesh.rotation.y=rotation;scene.add(mesh);return mesh;
  }
  function sign(title,subtitle){return textureCanvas(1024,256,(ctx,w,h)=>{
    ctx.fillStyle='#173d35';ctx.fillRect(0,0,w,h);ctx.fillStyle='#fff';
    ctx.font='600 74px "Malgun Gothic",sans-serif';ctx.fillText(title,44,114);
    ctx.fillStyle='#c2d6c9';ctx.font='34px "Malgun Gothic",sans-serif';ctx.fillText(subtitle,48,193);
    ctx.fillStyle='#b9d66a';ctx.fillRect(0,h-12,w,12);
  });}
  const w=config.halfWidth,h=config.ceilingHeight,end=config.length+1.3;
  const tiles=textureCanvas(256,256,(ctx)=>{
    ctx.fillStyle='#c6cbc2';ctx.fillRect(0,0,256,256);ctx.fillStyle='#b9c1b8';ctx.fillRect(0,0,128,128);ctx.fillRect(128,128,128,128);
    ctx.strokeStyle='#a4aea5';ctx.lineWidth=2;for(const p of [0,128,255]){ctx.beginPath();ctx.moveTo(p,0);ctx.lineTo(p,256);ctx.stroke();ctx.beginPath();ctx.moveTo(0,p);ctx.lineTo(256,p);ctx.stroke();}
  });
  tiles.wrapS=tiles.wrapT=THREE.RepeatWrapping;tiles.repeat.set(w,(end+5)/2);tiles.anisotropy=4;
  const floor=new THREE.Mesh(new THREE.PlaneGeometry(w*2,end+5),new THREE.MeshLambertMaterial({map:tiles}));
  floor.rotation.x=-Math.PI/2;floor.position.set(0,0,-end/2+1);scene.add(floor);
  box(0,h+.05,-end/2,w*2,.1,end+5,'#e6e9e2');
  for(const side of [-1,1]){
    box(side*w,h/2,-end/2,.14,h,end+5,'#e5e8e0');
    box(side*(w-.08),.15,-end/2,.06,.3,end+5,'#9aa99f');
    box(side*(w-.08),2.7,-end/2,.06,.15,end+5,'#25483d');
    for(let i=0;i<5;i++)box(side*(w-.22),h/2,-2.4-i*5,.45,h,.4,'#b7c1b5');
    for(let i=0;i<9;i++){
      const id=String(i+(side>0?9:0)).padStart(2,'0');
      const texture=new THREE.TextureLoader().load(new URL(`assets/explorer/poster-${id}.png`,import.meta.url).href);
      texture.colorSpace=THREE.SRGBColorSpace;
      plane(texture,side*(w-.09),1.65,-1-i*2.5,1.05,1.31,side<0?Math.PI/2:-Math.PI/2);
    }
  }
  for(let z=0;z<end;z+=3)for(const side of [-1,1])box(side*1.4,h-.035,-z,.19,.04,1.7,'#fffff2');
  box(0,h/2,-end-.05,w*2,h,.1,'#dce2d8');
  box(0,1.2,-end+.04,2.45,2.4,.16,'#25483d');
  box(-.55,1.14,-end+.14,1.08,2.25,.1,'#bdcac6');
  box(.55,1.14,-end+.14,1.08,2.25,.1,'#a5b6b2');
  box(0,1.14,-end+.2,.025,2.22,.02,'#617c72');
  box(1.42,1.05,-end+.13,.18,.42,.08,'#6b8278');
  box(1.42,1.1,-end+.18,.06,.06,.02,'#e7f0ce');
  plane(sign('엘리베이터  01','B1 대합실  ↕  B2 승강장'),0,2.8,-end+.17,3,.75);
  const liftInfo=textureCanvas(512,640,(ctx,w,h)=>{
    ctx.fillStyle='#f5f4e9';ctx.fillRect(0,0,w,h);ctx.fillStyle='#25483d';
    ctx.fillRect(24,24,w-48,8);ctx.font='bold 50px "Malgun Gothic",sans-serif';ctx.fillText('엘리베이터',42,114);
    ctx.font='38px "Malgun Gothic",sans-serif';ctx.fillText('B1 · B2',42,190);ctx.font='120px sans-serif';ctx.fillText('↕',165,370);
    ctx.font='28px "Malgun Gothic",sans-serif';ctx.fillText('가상 역사 / 안내 체험',42,530);
  });plane(liftInfo,-1.9,1.55,-end+.17,.95,1.19);
  for(const z of [5,14]){
    box(0,2.8,-z-.03,2.5,.625,.08,'#25483d');
    plane(sign('엘리베이터  ↑','ELEVATOR / B1 · B2'),0,2.8,-z+.02,2.5,.625);
  }
  const arrowGroup=new THREE.Group(),shape=new THREE.Shape();
  shape.moveTo(0,.55);shape.lineTo(.36,.06);shape.lineTo(.13,.06);shape.lineTo(.13,-.5);shape.lineTo(-.13,-.5);shape.lineTo(-.13,.06);shape.lineTo(-.36,.06);shape.closePath();
  const arrow=new THREE.Mesh(new THREE.ShapeGeometry(shape),new THREE.MeshBasicMaterial({color:'#00a986',side:THREE.DoubleSide,depthTest:true}));
  arrow.rotation.x=-Math.PI/2;arrowGroup.add(arrow);scene.add(arrowGroup);
  const line=new THREE.Line(new THREE.BufferGeometry(),new THREE.LineDashedMaterial({color:'#209f80',dashSize:.3,gapSize:.22,transparent:true,opacity:.8}));scene.add(line);
  const marker=new THREE.Mesh(new THREE.RingGeometry(.6,.66,48),new THREE.MeshBasicMaterial({color:'#10785e',side:THREE.DoubleSide}));
  marker.rotation.x=-Math.PI/2;marker.position.set(config.path.at(-1).x,.018,-config.path.at(-1).z);scene.add(marker);
  const stopSign=plane(sign('접근 중단','체험용 설정 · 등록된 대체 경로 없음'),0,1.45,-end+.24,2.1,.525);stopSign.visible=false;
  let lastLine='';
  const resize=()=>{const rect=canvas.parentElement.getBoundingClientRect();if(!rect.width||!rect.height)return;renderer.setSize(rect.width,rect.height,false);camera.aspect=rect.width/rect.height;camera.updateProjectionMatrix();};
  const observer=new ResizeObserver(resize);observer.observe(canvas.parentElement);resize();
  return {
    render(pose,view){
      camera.position.set(pose.x,config.cameraHeight,-pose.z);camera.rotation.set(-.12,-pose.yaw,0,'YXZ');
      arrowGroup.visible=line.visible=view.arrowVisible;marker.visible=!view.closed;stopSign.visible=view.closed;
      if(view.arrowVisible){
        const p=view.observation,t=view.target,dx=t.x-p.x,dz=t.z-p.z,len=Math.hypot(dx,dz)||1;
        arrowGroup.position.set(p.x+dx/len*Math.min(len,2.4),.035,-p.z-dz/len*Math.min(len,2.4));
        arrowGroup.rotation.y=-Math.atan2(dx,dz);
        const key=`${p.x},${p.z}`;
        if(key!==lastLine){
          lastLine=key;const pts=[new THREE.Vector3(p.x,.022,-p.z),new THREE.Vector3(t.x,.022,-t.z),...config.path.filter(q=>q.z>t.z).map(q=>new THREE.Vector3(q.x,.022,-q.z))];
          line.geometry.dispose();line.geometry=new THREE.BufferGeometry().setFromPoints(pts);line.computeLineDistances();
        }
      }
      renderer.render(scene,camera);
    },resize,
    dispose(){observer.disconnect();scene.traverse(o=>{o.geometry?.dispose();if(o.material){o.material.map?.dispose();o.material.dispose();}});renderer.dispose();}
  };
}
