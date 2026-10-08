(() => {
  const canvas = document.getElementById('scene'), ctx = canvas.getContext('2d');
  if (!ctx) return;
  const cover = document.getElementById('cover');
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  let width=0,height=0,dpr=1,frame=0,running=false,time=0,last=0;
  const pointer={x:0,y:0},smooth={x:0,y:0};
  function resize(){width=cover.clientWidth;height=cover.clientHeight;dpr=Math.min(devicePixelRatio||1,1.5);canvas.width=width*dpr;canvas.height=height*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);if(!running)render(time);}
  function rotate(p,a,b,c){let [x,y,z]=p;let ny=y*Math.cos(a)-z*Math.sin(a),nz=y*Math.sin(a)+z*Math.cos(a);y=ny;z=nz;let nx=x*Math.cos(b)+z*Math.sin(b);nz=-x*Math.sin(b)+z*Math.cos(b);x=nx;z=nz;nx=x*Math.cos(c)-y*Math.sin(c);ny=x*Math.sin(c)+y*Math.cos(c);return [nx,ny,z];}
  function project(p){const scale=Math.min(width*.17,height*.21),f=7.7/(7.7+p[2]);return [width*(width<760?.85:.76)+p[0]*scale*f,height*.49+p[1]*scale*f,f];}
  const mesh=[];
  const point=(v,u)=>{let y,r;if(v<Math.PI/2){y=-1.05-Math.cos(v)*.65;r=Math.sin(v)*.65;}else{y=1.05-Math.cos(v)*.65;r=Math.sin(v)*.65;}return [Math.cos(u)*r,y,Math.sin(u)*r];};
  const rings=[];
  for(let i=0;i<13;i++){let v=i/12*Math.PI/2;rings.push({v,y:-1.05-Math.cos(v)*.65,r:Math.sin(v)*.65});}
  for(let i=1;i<9;i++)rings.push({v:Math.PI/2,y:-1.05+i/8*2.1,r:.65});
  for(let i=1;i<=12;i++){let v=Math.PI/2+i/12*Math.PI/2;rings.push({v,y:1.05-Math.cos(v)*.65,r:Math.sin(v)*.65});}
  const rp=(r,u)=>[Math.cos(u)*r.r,r.y,Math.sin(u)*r.r];
  for(let j=0;j<rings.length-1;j++)for(let i=0;i<40;i++){let u=i/40*2*Math.PI,v=(i+1)/40*2*Math.PI;mesh.push({points:[rp(rings[j],u),rp(rings[j],v),rp(rings[j+1],v),rp(rings[j+1],u)],mint:(rings[j].y+rings[j+1].y)/2<0});}
  const dust=Array.from({length:65},(_,i)=>({x:((i*79)%100)/100,y:((i*53)%100)/100,r:i%4===0?1.4:.7,s:.3+i%5*.15}));
  function render(t){
    ctx.clearRect(0,0,width,height);ctx.fillStyle='#0b211f';ctx.fillRect(0,0,width,height);
    const bg=ctx.createRadialGradient(width*.76,height*.48,0,width*.76,height*.48,height*.8);bg.addColorStop(0,'#204d3e');bg.addColorStop(.5,'#123a2c');bg.addColorStop(1,'#0b211f');ctx.fillStyle=bg;ctx.fillRect(0,0,width,height);
    dust.forEach((p,i)=>{ctx.fillStyle=`rgba(158,219,183,${.12+.08*Math.sin(t*p.s+i)})`;ctx.beginPath();ctx.arc(p.x*width,((p.y*height-t*p.s*2)%height+height)%height,p.r,0,Math.PI*2);ctx.fill();});
    const a=.25+smooth.y*.16,b=t*.13+smooth.x*.2,c=-.48+Math.sin(t*.35)*.11;
    const objects=[];
    for(let ring=0;ring<3;ring++){
      let pts=[];
      for(let j=0;j<=120;j++){let u=j/120*Math.PI*2;let p=rotate([Math.cos(u)*(1.8+ring*.26),Math.sin(u)*(1.8+ring*.26),0],.8+ring*.52,t*.05+ring*.8,-.25+ring*.4);pts.push(p);}
      for(let j=0;j<120;j++)objects.push({z:(pts[j][2]+pts[j+1][2])/2,kind:'line',p:pts[j],q:pts[j+1],ring});
      for(let j=0;j<4;j++){let u=t*(.2+ring*.04)+j*Math.PI/2+ring;let p=rotate([Math.cos(u)*(1.8+ring*.26),Math.sin(u)*(1.8+ring*.26),0],.8+ring*.52,t*.05+ring*.8,-.25+ring*.4);objects.push({z:p[2],kind:'sphere',p,r:.036+(j===0?.025:0),mint:ring!==1});}
    }
    mesh.forEach(face=>{const pts=face.points.map(p=>rotate(p,a,b,c)),p=pts[0],q=pts[1],r=pts[2];let ax=q[0]-p[0],ay=q[1]-p[1],az=q[2]-p[2],bx=r[0]-p[0],by=r[1]-p[1],bz=r[2]-p[2];let normal=[ay*bz-az*by,az*bx-ax*bz,ax*by-ay*bx];let len=Math.hypot(...normal)||1;normal=normal.map(v=>-v/len);if(normal[0]*-p[0]+normal[1]*-p[1]+normal[2]*(-7.7-p[2])<=0)return;let light=Math.max(0,-normal[0]*.45-normal[1]*.65-normal[2]*.6),shine=Math.pow(Math.max(0,-normal[2]),14)*.13;objects.push({kind:'face',z:pts.reduce((n,p)=>n+p[2],0)/4,pts,light:Math.min(1,.24+light*.69+shine),mint:face.mint});});
    const satellite=[[-1.73,-1.0,.5],[1.55,.92,-.45],[1.3,-1.37,-.8],[-1.4,1.2,.3]];
    satellite.forEach((p,i)=>{p=rotate(p,.05,t*.09+i*.14,0);objects.push({kind:'sphere',z:p[2],p,r:i===0?.21:.14,mint:i%2===0});});
    objects.sort((a,b)=>b.z-a.z).forEach(o=>{
      if(o.kind==='line'){const p=project(o.p),q=project(o.q);ctx.strokeStyle=`rgba(136,207,166,${o.z>0?.12:.29})`;ctx.lineWidth=.7;ctx.beginPath();ctx.moveTo(p[0],p[1]);ctx.lineTo(q[0],q[1]);ctx.stroke();}
      else if(o.kind==='face'){let pts=o.pts.map(project),l=o.light;const rgb=o.mint?[90+l*83,145+l*95,111+l*84]:[90+l*140,120+l*123,110+l*126];ctx.fillStyle=`rgb(${rgb.map(Math.round).join(',')})`;ctx.strokeStyle=ctx.fillStyle;ctx.lineWidth=.6;ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p[0],p[1]):ctx.moveTo(p[0],p[1]));ctx.closePath();ctx.fill();ctx.stroke();}
      else{let [x,y,f]=project(o.p),r=o.r*Math.min(width*.17,height*.21)*f;const g=ctx.createRadialGradient(x-r*.35,y-r*.4,r*.05,x,y,r);g.addColorStop(0,o.mint?'#c5f6d1':'#dcece0');g.addColorStop(.35,o.mint?'#9adfb0':'#a9c5b3');g.addColorStop(1,o.mint?'#236344':'#41664d');ctx.fillStyle=g;ctx.shadowColor='#7beba227';ctx.shadowBlur=r*.8;ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.fill();ctx.shadowBlur=0;}
    });
    const shade=ctx.createLinearGradient(0,0,width,0);shade.addColorStop(0,'#0b211ff2');shade.addColorStop(width<760?.4:.32,'#0b211fcc');shade.addColorStop(width<760?.85:.6,'#0b211f00');ctx.fillStyle=shade;ctx.fillRect(0,0,width,height);
  }
  function tick(now){if(!running)return;if(now-last>32){time=now*.001;smooth.x+=(pointer.x-smooth.x)*.04;smooth.y+=(pointer.y-smooth.y)*.04;render(time);last=now;}frame=requestAnimationFrame(tick);}
  function start(){if(running||cover.hidden||document.hidden)return;if(reduced.matches){render(0);return;}running=true;frame=requestAnimationFrame(tick);}
  function stop(){running=false;cancelAnimationFrame(frame);}
  cover.addEventListener('pointermove',e=>{pointer.x=(e.clientX/width-.5)*2;pointer.y=(e.clientY/height-.5)*2;});
  cover.addEventListener('pointerleave',()=>{pointer.x=0;pointer.y=0;});
  window.addEventListener('resize',resize,{passive:true});document.addEventListener('visibilitychange',()=>document.hidden?stop():start());
  new MutationObserver(()=>cover.hidden?stop():start()).observe(cover,{attributes:true,attributeFilter:['hidden']});
  reduced.addEventListener('change',()=>{stop();start();});resize();start();
})();
