'use strict';
/* FaceStudio v4: offline, browser-only color grading and playful face warps.
   The source video never leaves the browser except for explicit local AI calls.
   These are artistic distortions, NOT age progression or realistic face swapping. */
(() => {
  const looks = [
    {id:'natural',name:'Natural',icon:'◯',css:'none',tone:'#eef0f6'},
    {id:'glow',name:'Glow',icon:'✧',css:'brightness(1.12) contrast(1.03) saturate(1.14)',tone:'#f8dfec'},
    {id:'noir',name:'Noir',icon:'◑',css:'grayscale(1) contrast(1.3)',tone:'#d3d4e0'},
    {id:'vintage',name:'Vintage',icon:'☼',css:'sepia(.56) saturate(.92) contrast(.96)',tone:'#f7dfb9'},
    {id:'pop',name:'Color Pop',icon:'●',css:'saturate(1.85) contrast(1.12)',tone:'#f8bfcd'},
    {id:'cool',name:'Cool',icon:'❆',css:'hue-rotate(13deg) saturate(.85) brightness(1.05)',tone:'#cef2f6'},
    {id:'warm',name:'Golden',icon:'☀',css:'sepia(.26) saturate(1.25) hue-rotate(-10deg)',tone:'#fae2a4'},
    {id:'dream',name:'Dreamy',icon:'✳',css:'brightness(1.13) contrast(.88) saturate(.93)',tone:'#e7d9fd'},
    {id:'neon',name:'Neon',icon:'⚡',css:'saturate(2) contrast(1.42) hue-rotate(30deg)',tone:'#d5c4fd'},
    {id:'comic',name:'Comic',icon:'★',css:'contrast(1.48) saturate(1.95)',tone:'#b8f0d5'},
  ];
  const morphs=[
    {id:'off',name:'Normal'}, {id:'eyes',name:'Big eyes'},
    {id:'grin',name:'Big smile'}, {id:'funhouse',name:'Funhouse'}
  ];
  let mirror = document.createElement('canvas');
  let mirrorCtx = mirror.getContext('2d', {willReadFrequently:true});
  const byId = id => looks.find(v=>v.id===id) || looks[0];
  const clamp=(a,min,max)=>Math.max(min,Math.min(max,a));

  // Radial, edge-feathered inverse deformation. Runs only on small image patches
  // rather than filtering the entire webcam frame at every animation tick.
  function warpPatch(ctx, source, cx, cy, rx, ry, amount, direction='both') {
    const W=source.canvas.width,H=source.canvas.height;
    let x0=clamp(Math.floor(cx-rx),0,W-1),y0=clamp(Math.floor(cy-ry),0,H-1);
    let x1=clamp(Math.ceil(cx+rx),x0+1,W),y1=clamp(Math.ceil(cy+ry),y0+1,H);
    const ww=x1-x0,hh=y1-y0;
    if(ww*hh>125000 || ww<6 || hh<6)return;
    let inp;try{inp=source.getImageData(x0,y0,ww,hh);}catch{return;}
    const out=ctx.createImageData(ww,hh),a=inp.data,b=out.data;
    for(let yy=0;yy<hh;yy++)for(let xx=0;xx<ww;xx++){
      const dx=(x0+xx-cx),dy=(y0+yy-cy);
      const r=Math.sqrt((dx*dx)/(rx*rx)+(dy*dy)/(ry*ry));
      if(r>=1)continue;
      const m=1+amount*Math.pow(1-r,1.35);
      // Inverse coordinate mapping keeps the outer edge fixed and creates a
      // continuous image warp instead of scaling a hard-edged photo sticker.
      const sx=(direction==='y'?dx:dx/m)+(cx-x0);
      const sy=(direction==='x'?dy:dy/m)+(cy-y0);
      const ix=clamp(Math.round(sx),0,ww-1),iy=clamp(Math.round(sy),0,hh-1);
      const src=4*(iy*ww+ix),dst=4*(yy*ww+xx);
      b[dst]=a[src];b[dst+1]=a[src+1];b[dst+2]=a[src+2];
      b[dst+3]=Math.round(255*clamp((1-r)*9,0,1));
    }
    ctx.putImageData(out,x0,y0);
  }
  function landmarks(face,w,h,sx,sy){
    const [x,y,bw,bh]=face.bbox;
    const box={x:(w-x-bw)*sx,y:y*sy,w:bw*sx,h:bh*sy};
    const pts=(face.landmarks||[]).map(p=>({x:(w-p[0])*sx,y:p[1]*sy}));
    return {box,pts};
  }
  function frame(video, canvas, result, config,now) {
    if(!video.videoWidth || !result)return;
    const w=video.videoWidth,h=video.videoHeight;
    if(canvas.width!==w)canvas.width=w;
    if(canvas.height!==h)canvas.height=h;
    const c=canvas.getContext('2d');c.clearRect(0,0,w,h);
    const sx=w/result.width,sy=h/result.height;
    const appearances=(result.faces||[]).slice(0,4).map(face=>({face,...landmarks(face,result.width,result.height,sx,sy)}));
    if(config.morph!=='off' && appearances.length){
      if(mirror.width!==w)mirror.width=w;
      if(mirror.height!==h)mirror.height=h;
      mirrorCtx.save();mirrorCtx.clearRect(0,0,w,h);
      mirrorCtx.filter=byId(config.filter).css;
      mirrorCtx.translate(w,0);mirrorCtx.scale(-1,1);mirrorCtx.drawImage(video,0,0,w,h);mirrorCtx.restore();
      for(const {box,pts} of appearances){
        const {x,y,w:bw,h:bh}=box;
        const t=1+.075*Math.sin(now/330);
        if(config.morph==='eyes'){
          const eyes=pts.length>=2?pts.slice(0,2):[{x:x+bw*.36,y:y+bh*.37},{x:x+bw*.64,y:y+bh*.37}];
          for(const p of eyes)warpPatch(c,mirrorCtx,p.x,p.y,bw*.18,bh*.18,.90*t);
        }else if(config.morph==='grin'){
          const p=pts.length>=5?{x:(pts[3].x+pts[4].x)/2,y:(pts[3].y+pts[4].y)/2}:{x:x+bw*.5,y:y+bh*.73};
          warpPatch(c,mirrorCtx,p.x,p.y,bw*.33,bh*.19,.85*t,'x');
        }else if(config.morph==='funhouse'){
          warpPatch(c,mirrorCtx,x+bw*.5,y+bh*.50,bw*.48,bh*.49,-.44*t,'x');
        }
      }
    }
    for(const {face,box,pts} of appearances){
      const {x,y,w:bw,h:bh}=box;
      if(config.mode==='vision'){
        for(const p of pts){c.beginPath();c.arc(p.x,p.y,Math.max(3,bw*.018),0,Math.PI*2);c.fillStyle='#6bf8cf';c.fill();}
      }
      if(config.mode==='party'){
        c.save();c.textAlign='center';c.shadowColor='#402887';c.shadowBlur=8;
        c.font=`${Math.max(32,bw*.47)}px system-ui`;
        const bob=Math.sin(now/360+face.index)*8;
        c.fillText('👑',x+bw/2,Math.max(36,y+bh*.08+bob));
        c.font=`${Math.max(25,bw*.37)}px system-ui`;
        c.fillText('😎',x+bw/2,y+bh*.51);
        c.font=`${Math.max(13,bw*.14)}px system-ui`;
        for(let i=0;i<4;i++){
          const angle=now/760+i*1.57+face.index;
          c.fillText(i%2?'✦':'♥',x+bw/2+Math.sin(angle)*(bw*.62),y+bh*.48+Math.cos(angle)*(bh*.6));
        }
        c.restore();
      }
      // Minimal face corners instead of a distracting full bounding rectangle.
      if(config.mode==='studio'||config.mode==='celebrity'||config.mode==='vision'){
        const r=Math.max(12,Math.min(bw,bh)*.12);c.save();c.strokeStyle='#c8b9ff';c.lineWidth=Math.max(2,Math.min(4,w/300));c.lineCap='round';c.shadowColor='#6441d9';c.shadowBlur=10;
        c.beginPath();c.moveTo(x+r,y);c.lineTo(x,y);c.lineTo(x,y+r);
        c.moveTo(x+bw-r,y);c.lineTo(x+bw,y);c.lineTo(x+bw,y+r);
        c.moveTo(x+r,y+bh);c.lineTo(x,y+bh);c.lineTo(x,y+bh-r);
        c.moveTo(x+bw-r,y+bh);c.lineTo(x+bw,y+bh);c.lineTo(x+bw,y+bh-r);c.stroke();c.restore();
        let label=face.identity?.name || `Face ${face.index}`;
        if(config.mode==='celebrity' && face.celebrity_lookalikes?.length)label=`★ ${face.celebrity_lookalikes[0].name}`;
        else if(face.age_estimate?.range)label+=` · ~${face.age_estimate.range}`;
        c.save();c.font=`700 ${Math.max(14,Math.round(w/49))}px system-ui`;
        const tw=Math.min(w-8,c.measureText(label).width+22),tx=clamp(x,4,w-tw-4),ty=Math.max(4,y-31);
        c.fillStyle='#17192be8';c.beginPath();c.roundRect(tx,ty,tw,27,8);c.fill();c.fillStyle='#fff';c.fillText(label,tx+9,ty+19,tw-14);c.restore();
      }
    }
  }
  window.FaceEffects={looks,morphs,byId,frame};
})();
