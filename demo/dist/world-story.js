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
  const captions=[['01 / SIGNALS EMERGE','Illustrative signals emerge across all seven continents. Select a region to explore its context.'],['02 / DEMAND BUILDS','The signals strengthen. Historical data adds a longer view beyond today’s headlines.'],['03 / CONTEXT CONNECTS','The agent brings global demand, supply and climate signals together with historical context. Select the book to inspect its role.'],['04 / A POSSIBLE OUTLOOK','An illustrative forecast brings the context into focus. This is a product vision, not a live model output.']];
  const details={"usa": ["NORTH AMERICA / ILLUSTRATIVE SIGNAL", "Suppose US manufacturing demand rises. Investigate commodity use, reporting dates and contradictory evidence."], "south-america": ["SOUTH AMERICA / ILLUSTRATIVE SIGNAL", "Suppose a South American copper disruption reduces exports. Compare inventories, production reports and alternative suppliers."], "europe": ["EUROPE / ILLUSTRATIVE SIGNAL", "Suppose European energy demand increases. Compare weather, storage levels and industrial consumption before drawing conclusions."], "africa": ["AFRICA / ILLUSTRATIVE SIGNAL", "Suppose African mineral exports slow. Investigate transport constraints, production and the buyers affected."], "china": ["ASIA / ILLUSTRATIVE SIGNAL", "Suppose Asian infrastructure spending strengthens. Compare steel demand, trade flows and whether prices already reflect it."], "oceania": ["OCEANIA / ILLUSTRATIVE SIGNAL", "Suppose Australian iron ore shipments change. Compare port activity, weather and demand from importing countries."], "antarctica": ["ANTARCTICA / ILLUSTRATIVE SIGNAL", "Suppose Antarctic observations signal a changing climate pattern. Investigate evidence for indirect effects on weather and shipping; this is not local commodity demand."], "history": ["HISTORICAL DATA / CONTEXT", "Past prices and supply\u2013demand cycles provide a baseline. TimesFM currently uses price history separately; feeding researched news into that forecast is future work."]};
  function controls(){stage.classList.toggle('is-paused',paused);stage.classList.toggle('is-reduced',reduced.matches);play.disabled=reduced.matches;play.textContent=reduced.matches?'—':paused?'▷':'Ⅱ';play.setAttribute('aria-pressed',String(paused));play.setAttribute('aria-label',reduced.matches?'Reduced motion enabled; use chapter buttons':paused?'Play product animation':'Pause product animation');}
  function chapter(index,reset=true){step=index;stage.dataset.step=String(index);if(reset)elapsed=index*duration;chapters.forEach((button,i)=>button.setAttribute('aria-pressed',String(i===index)));label.textContent=captions[index][0];copy.textContent=captions[index][1];
    for(const [selector,shown] of [['.history-book',index===1||index===2],['.world-news',index<3],['.world-agent',index===2],['.world-result',index===3]]){stage.querySelectorAll(selector).forEach(element=>{element.inert=!shown;element.setAttribute('aria-hidden',String(!shown));});}
    if(index===2)routes.forEach(({path,dot},i)=>{const point=path.getPointAtLength(path.getTotalLength()*((.35+i*.15)%1));dot.setAttribute('cx',point.x);dot.setAttribute('cy',point.y);});
  }
  function inspect(region){paused=true;const index=region==='history'?2:1;chapter(index);label.textContent=details[region][0];copy.textContent=details[region][1];controls();document.querySelectorAll('.map-country.featured').forEach(p=>p.classList.toggle('selected',p.dataset.region===region));}
  document.querySelectorAll('[data-region]').forEach(button=>{button.addEventListener('click',()=>inspect(button.dataset.region));button.addEventListener('keydown',event=>{if(button.tagName.toLowerCase()==='g'&&['Enter',' '].includes(event.key)){event.preventDefault();inspect(button.dataset.region);}});});
  document.getElementById('history-book').onclick=()=>inspect('history');
  chapters.forEach((button,i)=>button.onclick=()=>{paused=true;chapter(i);controls();});
  play.onclick=()=>{paused=!paused;controls();};
  const routes=['usa', 'south-america', 'europe', 'africa', 'china', 'oceania', 'antarctica', 'history'].map(name=>({path:document.getElementById('route-'+name),dot:document.getElementById('dot-'+name)}));
  let animationFrame=0;
  function tick(now){const delta=last?Math.min(now-last,100):0;last=now;if(visible&&!document.hidden&&!paused&&!reduced.matches){elapsed=(elapsed+delta)%(duration*4);const next=Math.floor(elapsed/duration);if(next!==step)chapter(next,false);}
    if(visible&&step===2&&!paused&&!reduced.matches){routes.forEach(({path,dot},i)=>{const phase=((elapsed-duration*2)/2400+i*.23)%1;const point=path.getPointAtLength(path.getTotalLength()*phase);dot.setAttribute('cx',point.x);dot.setAttribute('cy',point.y);});}
    animationFrame=requestAnimationFrame(tick);
  }
  new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;},{threshold:.15}).observe(stage);
  reduced.addEventListener('change',()=>{paused=reduced.matches;companyPaused=reduced.matches;companyState();controls();});
  fetch('world-map.json').then(response=>{if(!response.ok)throw new Error('Map unavailable');return response.json();}).then(features=>{
    const fragment=document.createDocumentFragment();
    for(const feature of features){const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',feature.path);path.setAttribute('class','map-country');
      const region=({'United States of America':'usa','China':'china','Brazil':'south-america','Germany':'europe','Democratic Republic of the Congo':'africa','Australia':'oceania'})[feature.name]||null;
      if(region){path.classList.add('featured');path.dataset.region=region;path.setAttribute('role','button');path.setAttribute('tabindex','0');path.setAttribute('aria-label','Explore '+feature.name+' demand signal');path.addEventListener('click',()=>inspect(region));path.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();inspect(region);}});}
      else path.setAttribute('aria-hidden','true');fragment.append(path);
    }countries.append(fragment);
  }).catch(()=>{label.textContent='MAP UNAVAILABLE';copy.textContent='Country outlines could not load. The continent controls still let you explore the concept.';});
  // A static, inspectable first chapter is also the reduced-motion experience.
  controls();chapter(0);animationFrame=requestAnimationFrame(tick);
  window.addEventListener('pagehide',()=>cancelAnimationFrame(animationFrame));
  window.addEventListener('pageshow',event=>{if(event.persisted){last=0;animationFrame=requestAnimationFrame(tick);}});
})();
