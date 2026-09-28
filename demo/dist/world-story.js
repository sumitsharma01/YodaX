/* Illustrative product story: no API calls, fabricated live news, or real forecast claims. */
(() => {
  const marquee=document.querySelector('.company-marquee');
  const companyButton=document.getElementById('company-motion');
  const reduced=matchMedia('(prefers-reduced-motion: reduce)');
  let companyPaused=reduced.matches;
  function companyState(){marquee.classList.toggle('is-paused',companyPaused);companyButton.setAttribute('aria-pressed',String(companyPaused));companyButton.disabled=reduced.matches;companyButton.textContent=reduced.matches?'Reduced motion enabled':companyPaused?'Resume motion ▷':'Pause motion Ⅱ';}
  companyButton.onclick=()=>{companyPaused=!companyPaused;companyState();};companyState();
  const stage=document.getElementById('world-stage');
  const svg=document.getElementById('world-map');
  const countries=document.getElementById('world-countries');
  const play=document.getElementById('world-play');
  const label=document.getElementById('world-inspector-label');
  const copy=document.getElementById('world-inspector-copy');
  const chapters=[...document.querySelectorAll('[data-chapter]')];
  const duration=5000;
  let elapsed=0, step=0, paused=reduced.matches, visible=false, last=0;
  const captions=[['01 / SIGNALS EMERGE','Illustrative signals emerge from six major economies. Select a region to explore its context.'],['02 / DEMAND BUILDS','The signals strengthen. Historical data adds a longer view beyond today’s headlines.'],['03 / CONTEXT CONNECTS','The agent brings demand and supply signals together with historical context. Select the book to inspect its role.'],['04 / A POSSIBLE OUTLOOK','An illustrative forecast brings the context into focus. This is a product vision, not a live model output.']];
  const details={"usa": ["UNITED STATES / ILLUSTRATIVE SIGNAL", "Suppose US manufacturing demand rises. Investigate commodity use, reporting dates and contradictory evidence."], "china": ["CHINA / ILLUSTRATIVE SIGNAL", "Suppose Chinese infrastructure spending strengthens. Compare steel demand, trade flows and whether prices already reflect it."], "history": ["HISTORICAL DATA / CONTEXT", "Past prices and supply\u2013demand cycles provide a baseline. TimesFM currently uses price history separately; feeding researched news into that forecast is future work."], "germany": ["GERMANY / ILLUSTRATIVE SIGNAL", "Suppose German industrial energy demand increases. Compare manufacturing activity, storage levels and imports before inferring a price effect."], "uk": ["UNITED KINGDOM / ILLUSTRATIVE SIGNAL", "Suppose UK energy imports shift. Compare domestic supply, storage, weather and shipping costs against historical patterns."]};
  details.india=['INDIA / ILLUSTRATIVE SIGNAL','Suppose Indian energy imports rise. Compare refinery demand, inventories, industrial activity and shipping costs before inferring a price effect.'];
  details.japan=['JAPAN / ILLUSTRATIVE SIGNAL','Suppose Japanese industrial demand changes. Compare manufacturing orders, metal imports and energy use, including evidence that challenges the signal.'];
  function controls(){stage.classList.toggle('is-paused',paused);stage.classList.toggle('is-reduced',reduced.matches);play.disabled=reduced.matches;play.textContent=reduced.matches?'—':paused?'▷':'Ⅱ';play.setAttribute('aria-pressed',String(paused));play.setAttribute('aria-label',reduced.matches?'Reduced motion enabled; use chapter buttons':paused?'Play product animation':'Pause product animation');}
  function chapter(index,reset=true){step=index;stage.dataset.step=String(index);if(reset)elapsed=index*duration;chapters.forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));label.textContent=captions[index][0];copy.textContent=captions[index][1];
    for(const [selector,shown] of [['.history-book',index===1||index===2],['.world-news',index<3],['.world-agent',index===2],['.world-result',index===3]]){stage.querySelectorAll(selector).forEach(element=>{element.inert=!shown;element.setAttribute('aria-hidden',String(!shown));});}
    routes.forEach(({path,dot},i)=>{const point=path.getPointAtLength(0);dot.setAttribute('cx',point.x);dot.setAttribute('cy',point.y);});
  }
  function inspect(region){paused=true;const index=region==='history'?2:1;chapter(index);label.textContent=details[region][0];copy.textContent=details[region][1];controls();document.querySelectorAll('.map-country.featured').forEach(p=>p.classList.toggle('selected',p.dataset.region===region));}
  document.querySelectorAll('[data-region]').forEach(button=>{button.addEventListener('click',()=>inspect(button.dataset.region));button.addEventListener('keydown',event=>{if(button.tagName.toLowerCase()==='g'&&['Enter',' '].includes(event.key)){event.preventDefault();inspect(button.dataset.region);}});});
  document.getElementById('history-book').onclick=()=>inspect('history');
  chapters.forEach((button,i)=>button.onclick=()=>{paused=true;chapter(i);controls();});
  play.onclick=()=>{paused=!paused;controls();};
  const routes=['usa','china','germany','japan','uk','india','history'].map(name=>({path:document.getElementById('route-'+name),dot:document.getElementById('dot-'+name)}));
  let animationFrame=0;
  function tick(now){const delta=last?Math.min(now-last,100):0;last=now;if(visible&&!document.hidden&&!paused&&!reduced.matches){elapsed=(elapsed+delta)%(duration*4);const next=Math.floor(elapsed/duration);if(next!==step)chapter(next,false);}
    if(visible&&!document.hidden&&step===2&&!paused&&!reduced.matches){routes.forEach(({path,dot},i)=>{const travel=elapsed-duration*2-800-i*90;const phase=travel<=0?0:(travel%2800)/2800;const point=path.getPointAtLength(path.getTotalLength()*phase);dot.setAttribute('cx',point.x);dot.setAttribute('cy',point.y);});}
    animationFrame=requestAnimationFrame(tick);
  }
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{threshold:.15}).observe(stage);
  reduced.addEventListener('change',()=>{paused=reduced.matches;companyPaused=reduced.matches;companyState();controls();});
  fetch('world-map.json?v=8').then(response=>{if(!response.ok)throw new Error('Map unavailable');return response.json();}).then(features=>{
    const fragment=document.createDocumentFragment();
    for(const feature of features){const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',feature.path);path.setAttribute('class','map-country');
      const continentDelays={'North America':0,'South America':.7,'Europe':1.4,'Africa':2.1,'Asia':2.8,'Oceania':3.5,'Seven seas (open ocean)':3.5};
      if(Object.hasOwn(continentDelays,feature.continent)){path.classList.add('continent-pulse');path.style.setProperty('--continent-delay',-continentDelays[feature.continent]+'s');}

      const region=({'United States of America':'usa','China':'china','India':'india','Germany':'germany','Japan':'japan','United Kingdom':'uk'})[feature.name]||null;
      if(region){path.classList.add('featured');path.dataset.region=region;path.setAttribute('role','button');path.setAttribute('tabindex','0');path.setAttribute('aria-label','Explore '+feature.name+' market signal');path.addEventListener('click',()=>inspect(region));path.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();inspect(region);}});}
      else path.setAttribute('aria-hidden','true');fragment.append(path);
    }countries.append(fragment);
  }).catch(()=>{label.textContent='MAP UNAVAILABLE';copy.textContent='Country outlines could not load. The country controls still let you explore the concept.';});
  // A static, inspectable first chapter is also the reduced-motion experience.
  controls();chapter(0);animationFrame=requestAnimationFrame(tick);
  window.addEventListener('pagehide',()=>cancelAnimationFrame(animationFrame));
  window.addEventListener('pageshow',event=>{if(event.persisted){last=0;animationFrame=requestAnimationFrame(tick);}});
})();
