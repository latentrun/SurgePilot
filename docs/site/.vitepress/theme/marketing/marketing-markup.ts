const publicMarketingMarkup = `
<div class="fixed-glow-1"></div>
<nav class="sticky top-0 z-50 w-full h-16 flex items-center justify-between px-4 md:px-8 bg-[#0a0e1a]/80 backdrop-blur-md border-b border-white/5">
  <div class="flex items-center gap-4 min-w-0">
    <div class="flex items-center gap-3">
      <img alt="SurgePilot Logo" class="w-8 h-8 object-contain" src="__SURGEPILOT_LOGO__"/>
      <span class="text-xl font-bold text-on-surface tracking-tight font-display">SurgePilot</span>
    </div>
    <div class="hidden xl:flex items-center px-2 py-0.5 rounded-full bg-primary/10 border border-primary/20 shadow-[0_0_10px_rgba(34,211,238,0.1)]">
      <span class="font-technical text-[10px] text-primary">✦ 100% AI-built</span>
    </div>
  </div>
  <div class="hidden md:flex items-center gap-8">
    <a class="text-sm text-on-surface-variant hover:text-primary transition-colors" href="#product">Product</a>
    <a class="text-sm text-on-surface-variant hover:text-primary transition-colors" href="#how-it-works">How it works</a>
    <a class="text-sm text-on-surface-variant hover:text-primary transition-colors" href="__SURGEPILOT_DOCS__">Docs</a>
    <a class="text-sm text-on-surface-variant hover:text-primary transition-colors flex items-center gap-1" href="__SURGEPILOT_REPOSITORY__">
      <svg class="w-4 h-4 fill-current" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 .5a12 12 0 0 0-3.79 23.39c.6.11.82-.26.82-.58v-2.1c-3.34.72-4.04-1.42-4.04-1.42-.55-1.38-1.33-1.75-1.33-1.75-1.09-.75.08-.73.08-.73 1.2.08 1.84 1.24 1.84 1.24 1.07 1.83 2.81 1.3 3.49 1 .11-.78.42-1.3.76-1.6-2.66-.31-5.46-1.34-5.46-5.94 0-1.31.47-2.38 1.24-3.22-.13-.31-.54-1.53.12-3.18 0 0 1.01-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.29-1.55 3.3-1.23 3.3-1.23.65 1.65.24 2.87.12 3.18.77.84 1.23 1.91 1.23 3.22 0 4.61-2.8 5.63-5.48 5.93.43.37.82 1.1.82 2.22v3.3c0 .32.19.69.82.58A12 12 0 0 0 12 .5Z"></path></svg>
      GitHub
    </a>
  </div>
  <div class="flex items-center gap-3 md:gap-4">
    <div class="hidden xl:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
      <div class="w-2 h-2 rounded-full bg-primary shadow-[0_0_8px_rgba(34,211,238,0.6)]"></div>
      <span class="font-technical text-[10px] text-on-surface-variant uppercase tracking-wider">OPEN SOURCE · SELF-HOSTED</span>
    </div>
    <a class="text-sm bg-primary text-[#00363e] px-4 md:px-5 py-2 rounded font-bold primary-glow-btn transition-all" href="__SURGEPILOT_REPOSITORY__">★ Star on GitHub</a>
  </div>
</nav>

<header class="relative min-h-[90vh] flex flex-col items-center justify-start pt-16 px-6">
  <div class="max-w-4xl text-center z-10 mb-16">
    <div class="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-white/10 bg-white/5 backdrop-blur-md mb-8 animate-pulse">
      <span class="text-xs font-technical text-on-surface-variant">Original public baseline · produced by AI agents</span>
    </div>
    <h1 aria-label="A distributed load-testing platform built 100% by AI agents." class="text-5xl md:text-7xl font-bold text-on-surface mb-6 leading-[1.1] tracking-tight font-display">
      A distributed load-testing platform <span class="text-transparent bg-clip-text bg-gradient-to-r from-primary via-secondary to-primary bg-[length:200%_auto] animate-gradient">built 100% by AI agents.</span>
    </h1>
    <p class="text-lg md:text-xl text-on-surface-variant mb-10 max-w-3xl mx-auto leading-relaxed">
      Turn API &amp; business flows into reusable load tests.<br class="hidden sm:block"/> A self-hosted distributed API load-testing platform—and an inspectable experiment in AI-agent software delivery.
    </p>
    <div class="flex flex-col sm:flex-row items-center justify-center gap-4">
      <a class="w-full sm:w-auto bg-primary text-[#00363e] px-8 py-4 rounded-lg font-bold primary-glow-btn text-lg" href="__SURGEPILOT_REPOSITORY__">★ Star on GitHub</a>
      <a class="w-full sm:w-auto border border-white/10 text-on-surface-variant px-8 py-4 rounded-lg flex items-center justify-center gap-2 backdrop-blur-md hover:border-primary/40 hover:text-primary transition-colors" href="__SURGEPILOT_REPOSITORY__#built-100-by-ai">
        <svg class="w-5 h-5 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 20l4-16m4 4 4 4-4 4M6 16l-4-4 4-4" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
        Inspect the evidence
      </a>
    </div>
  </div>
  <div class="relative w-full max-w-6xl mx-auto">
    <div class="glass-card rounded-xl p-4 md:p-6 shadow-2xl overflow-hidden border border-white/10">
      <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between mb-6 border-b border-white/5 pb-4">
        <div class="flex items-center gap-2">
          <div class="w-3 h-3 rounded-full bg-red-500/30"></div><div class="w-3 h-3 rounded-full bg-yellow-500/30"></div><div class="w-3 h-3 rounded-full bg-[#22c55e]/30"></div>
          <div class="ml-4 font-technical text-[11px] text-on-surface-variant/40">ANALYTICS_DASHBOARD_LIVE · UI DEMONSTRATION · NOT BENCHMARK DATA · EXAMPLE DATA · NOT A LIVE SERVICE</div>
        </div>
        <div class="flex gap-4">
          <div class="flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-primary"></div><span class="font-technical text-[10px] text-on-surface-variant uppercase">/checkout</span></div>
          <div class="flex items-center gap-2"><div class="w-2 h-2 rounded-full bg-secondary"></div><span class="font-technical text-[10px] text-on-surface-variant uppercase">/search</span></div>
        </div>
      </div>
      <div class="grid grid-cols-1 md:grid-cols-12 gap-6 min-h-[400px]">
        <div class="md:col-span-9 bg-black/40 rounded-lg border border-white/5 p-8 relative overflow-hidden flex flex-col justify-between">
          <div class="relative z-10">
            <div class="font-technical text-primary text-[10px] uppercase mb-1 tracking-widest">Live Combined Throughput</div>
            <div class="flex items-baseline gap-2">
              <span class="font-technical text-5xl text-on-surface counter" data-target="8600">0</span>
              <span class="text-xs opacity-50 font-technical">REQ/SEC</span>
            </div>
          </div>
          <div class="absolute inset-x-0 bottom-0 h-64 overflow-hidden pointer-events-none px-0">
            <svg class="w-[200%] h-full stream-bg" preserveAspectRatio="none" viewBox="0 0 2000 100" aria-hidden="true">
              <defs>
                <linearGradient id="grad-cyan" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#22d3ee" stop-opacity="0.3"></stop><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"></stop></linearGradient>
                <linearGradient id="grad-magenta" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#ec4899" stop-opacity="0.2"></stop><stop offset="100%" stop-color="#ec4899" stop-opacity="0"></stop></linearGradient>
              </defs>
              <path d="M0,50 C100,20 200,80 300,40 C400,10 500,90 600,50 C700,20 800,80 900,40 C1000,10 1100,90 1200,50 C1300,20 1400,80 1500,40 C1600,10 1700,90 1800,50 C1900,20 2000,80 2000,50" fill="none" stroke="#22d3ee" stroke-width="2.5"></path>
              <path d="M0,50 C100,20 200,80 300,40 C400,10 500,90 600,50 C700,20 800,80 900,40 C1000,10 1100,90 1200,50 C1300,20 1400,80 1500,40 C1600,10 1700,90 1800,50 C1900,20 2000,80 2000,50 L2000,100 L0,100 Z" fill="url(#grad-cyan)"></path>
              <path d="M0,70 C100,40 200,90 300,60 C400,30 500,70 600,70 C700,40 800,90 900,60 C1000,30 1100,70 1200,70 C1300,40 1400,90 1500,60 C1600,30 1700,70 1800,70 C1900,40 2000,90 2000,70" fill="none" stroke="#ec4899" stroke-dasharray="4 2" stroke-width="2"></path>
              <path d="M0,70 C100,40 200,90 300,60 C400,30 500,70 600,70 C700,40 800,90 900,60 C1000,30 1100,70 1200,70 C1300,40 1400,90 1500,60 C1600,30 1700,70 1800,70 C1900,40 2000,90 2000,70 L2000,100 L0,100 Z" fill="url(#grad-magenta)"></path>
            </svg>
          </div>
        </div>
        <div class="md:col-span-3 flex flex-col gap-6">
          <div class="flex-1 bg-black/40 rounded-lg border border-white/5 p-6"><div class="font-technical text-primary text-[10px] uppercase mb-1 tracking-widest">Active VUs</div><div class="font-technical text-3xl text-on-surface counter-fast">1,245</div></div>
          <div class="flex-1 bg-black/40 rounded-lg border border-white/5 p-6"><div class="flex justify-between items-start mb-2"><div class="font-technical text-secondary text-[10px] uppercase tracking-widest">Global Error Rate</div><svg class="w-4 h-4 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v2m0 4h.01M5.07 19h13.86c1.54 0 2.5-1.67 1.73-3L13.73 4c-.77-1.33-2.69-1.33-3.46 0L3.34 16c-.77 1.33.19 3 1.73 3Z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg></div><span class="font-technical text-3xl text-on-surface">0.02<span class="text-sm opacity-50">%</span></span><div class="mt-4 h-1 w-full bg-white/5 rounded-full overflow-hidden"><div class="h-full bg-secondary w-[2%]"></div></div></div>
        </div>
      </div>
    </div>
  </div>
</header>



<section id="how-it-works" class="py-24 px-6 max-w-7xl mx-auto">
  <div class="text-center mb-16"><h2 class="text-4xl md:text-5xl font-bold font-display mb-4 tracking-tight">How it was built.</h2><p class="text-lg text-on-surface-variant max-w-2xl mx-auto">From intent to running platform — orchestrated by AI agents.</p></div>
  <div class="relative"><div class="hidden lg:block absolute top-6 left-0 w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent z-0"></div>
    <div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-12 lg:gap-6 relative z-10">
      <div class="flex flex-col items-center text-center"><div class="icon-tile mb-6 glass-card border-white/10 text-on-surface-variant hover:text-primary transition-colors"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><span class="font-technical text-[10px] text-primary uppercase tracking-widest mb-2">Stage 01</span><h3 class="font-bold text-lg mb-2 font-display">Product Intent</h3><p class="text-sm text-on-surface-variant px-4">Product intent and requirements discussed with a human through text.</p></div>
      <div class="flex flex-col items-center text-center"><div class="icon-tile mb-6 glass-card border-white/10 text-on-surface-variant hover:text-primary transition-colors"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.691.387a2 2 0 01-2.179 0l-.691-.387a6 6 0 00-3.86-.517l-2.387.477a2 2 0 00-1.022.547l-.34.34a2 2 0 000 2.828l1.246 1.246a2 2 0 002.828 0l.34-.34a2 2 0 00.547-1.022l.477-2.387a6 6 0 01.517-3.86l.387-.691a2 2 0 000-2.179l-.387-.691a6 6 0 01-.517-3.86l.477-2.387a2 2 0 00-.547-1.022l-.34-.34a2 2 0 00-2.828 0l-1.246 1.246a2 2 0 000 2.828l.34.34a2 2 0 001.022.547l2.387.477a6 6 0 003.86-.517l.691-.387a2 2 0 012.179 0l.691.387a6 6 0 003.86.517l2.387-.477a2 2 0 001.022-.547l.34-.34a2 2 0 000-2.828l-1.246-1.246a2 2 0 00-2.828 0l-.34.34z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><span class="font-technical text-[10px] text-primary uppercase tracking-widest mb-2">Stage 02</span><h3 class="font-bold text-lg mb-2 font-display">AI Product Design</h3><p class="text-sm text-on-surface-variant px-4">AI agents define product design, governance, quality gates, and specifications.</p></div>
      <div class="flex flex-col items-center text-center"><div class="icon-tile mb-6 glass-card border-white/10 text-on-surface-variant hover:text-primary transition-colors"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5a1 1 0 011-1h14a1 1 0 011 1v2a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM4 13a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H5a1 1 0 01-1-1v-6zM16 13a1 1 0 011-1h2a1 1 0 011 1v6a1 1 0 01-1 1h-2a1 1 0 01-1-1v-6z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><span class="font-technical text-[10px] text-primary uppercase tracking-widest mb-2">Stage 03</span><h3 class="font-bold text-lg mb-2 font-display">AI Architecture</h3><p class="text-sm text-on-surface-variant px-4">AI agents define architecture, contracts, and the interface system.</p></div>
      <div class="flex flex-col items-center text-center"><div class="icon-tile mb-6 glass-card border-white/10 text-on-surface-variant hover:text-primary transition-colors"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><span class="font-technical text-[10px] text-primary uppercase tracking-widest mb-2">Stage 04</span><h3 class="font-bold text-lg mb-2 font-display">AI Implementation</h3><p class="text-sm text-on-surface-variant px-4">AI agents author application code, tests, and verification repairs.</p></div>
      <div class="flex flex-col items-center text-center"><div class="icon-tile mb-6 glass-card border-white/10 text-on-surface-variant hover:text-primary transition-colors"><svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><span class="font-technical text-[10px] text-primary uppercase tracking-widest mb-2">Stage 05</span><h3 class="font-bold text-lg mb-2 font-display">AI Verification &amp; Release</h3><p class="text-sm text-on-surface-variant px-4">AI agents execute quality gates and produce deployment and release assets.</p></div>
    </div>
  </div>
</section>

<section class="py-24 px-6 max-w-7xl mx-auto">
  <div class="glass-card rounded-[2.5rem] border border-white/10 overflow-hidden relative">
    <div class="grid lg:grid-cols-2 gap-0 items-stretch min-h-[600px]">
      <div class="p-12 md:p-16 flex flex-col justify-center relative z-10">
        <div class="inline-flex items-center gap-2 mb-6 text-primary">
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M13 10V3L4 14h7v7l9-11h-7Z" stroke-linecap="round" stroke-linejoin="round" stroke-width="2"></path></svg>
          <span class="font-technical text-[10px] uppercase tracking-widest">AI Engineering Prototype</span>
        </div>
        <h2 class="text-4xl md:text-5xl font-bold font-display mb-6 tracking-tight text-on-surface">The original baseline — <span class="text-primary">produced by AI agents.</span></h2>
        <p class="text-lg text-on-surface-variant mb-10 leading-relaxed">Human participation is explicit: product intent, requirements discussion, product use, usage feedback, and result acceptance. AI agents handled product and process design, governance, quality gates, specifications, architecture, implementation, tests, verification repair, deployment, and release assets.</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="p-4 rounded-xl border border-white/5 bg-white/[0.02]"><div class="font-technical text-primary text-[10px] mb-2 uppercase tracking-wider">Human</div><div class="text-sm text-on-surface-variant leading-relaxed">Intent · requirements · product use · feedback · acceptance</div></div>
          <div class="p-4 rounded-xl border border-white/5 bg-white/[0.02]"><div class="font-technical text-secondary text-[10px] mb-2 uppercase tracking-wider">AI agents</div><div class="text-sm text-on-surface-variant leading-relaxed">Design · gates · specs · code · tests · deployment</div></div>
        </div>
      </div>
      <div class="bg-black/40 border-l border-white/5 flex flex-col items-center justify-center p-8 relative overflow-hidden">
        <div class="relative z-10 w-full max-w-md mx-auto">
          <div class="mb-6 flex items-center justify-center gap-3">
            <span class="w-2.5 h-2.5 rounded-full bg-primary running-pulse"></span>
            <span class="font-technical text-base md:text-lg uppercase tracking-widest text-primary">Loop Engineering</span>
          </div>
          <div class="relative mx-auto aspect-square w-full max-w-[400px]">
            <svg class="absolute inset-0 h-full w-full overflow-visible" fill="none" viewbox="0 0 340 340" aria-hidden="true">
              <defs>
                <lineargradient id="orbitGrad" x1="30" x2="310" y1="30" y2="310" gradientUnits="userSpaceOnUse"><stop offset="0%" stop-color="#22d3ee"></stop><stop offset="100%" stop-color="#ec4899"></stop></lineargradient>
                <radialgradient id="orbitVeil" cx="50%" cy="50%" r="50%"><stop offset="0%" stop-color="#22d3ee" stop-opacity="0.10"></stop><stop offset="100%" stop-color="#22d3ee" stop-opacity="0"></stop></radialgradient>
                <filter id="packet-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="4" result="blur"></feGaussianBlur><feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
              </defs>
              <circle cx="170" cy="170" r="150" fill="url(#orbitVeil)"></circle>
              <g class="orbit-ring">
                <circle cx="170" cy="170" r="140" stroke="url(#orbitGrad)" stroke-dasharray="2 10" stroke-opacity="0.6" stroke-width="1.5"></circle>
                <circle cx="170" cy="30" r="9" fill="#22d3ee" fill-opacity="0.15"></circle>
                <circle cx="170" cy="30" r="4.5" fill="#22d3ee" filter="url(#packet-glow)"></circle>
              </g>
              <g class="orbit-ring-rev">
                <circle cx="170" cy="170" r="108" stroke="#ec4899" stroke-dasharray="1 9" stroke-opacity="0.30" stroke-width="1"></circle>
                <circle cx="170" cy="62" r="3.5" fill="#ec4899" filter="url(#packet-glow)"></circle>
              </g>
              <g class="orbit-core-cw">
                <path d="M170 118 A52 52 0 0 1 222 170" stroke="#22d3ee" stroke-width="2.5" stroke-linecap="round"></path>
                <path d="M118 170 A52 52 0 0 1 170 118" stroke="#22d3ee" stroke-width="2.5" stroke-linecap="round" opacity="0.35"></path>
              </g>
              <g class="orbit-core-ccw">
                <path d="M170 222 A52 52 0 0 1 118 170" stroke="#ec4899" stroke-width="2.5" stroke-linecap="round"></path>
                <path d="M222 170 A52 52 0 0 1 170 222" stroke="#ec4899" stroke-width="2.5" stroke-linecap="round" opacity="0.35"></path>
              </g>
              <circle cx="170" cy="170" r="34" fill="#0a0e1a" stroke="#22d3ee" stroke-opacity="0.25"></circle>
            </svg>
            <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div class="core-throb text-center">
                <div class="font-technical text-[13px] uppercase tracking-wider text-on-surface leading-tight">Review <span class="text-primary">⇄</span> Fix</div>
                <div class="font-technical text-[9px] uppercase tracking-widest text-on-surface-variant/70 mt-1">until clean</div>
              </div>
            </div>
            <div class="orbit-node absolute glass-card rounded-full border border-white/10 px-3 py-1.5 flex items-center gap-1.5" style="top:8.8%;left:50%;transform:translate(-50%,-50%);">
              <svg class="w-3.5 h-3.5 text-primary shrink-0" fill="none" stroke="currentColor" viewbox="0 0 24 24" aria-hidden="true"><path d="M11 5H6a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="m18.5 2.5 3 3L12 15H9v-3l9.5-9.5Z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span class="font-technical text-[10px] whitespace-nowrap">Design</span>
            </div>
            <div class="orbit-node absolute glass-card rounded-full border border-white/10 px-3 py-1.5 flex items-center gap-1.5" style="top:50%;left:91.2%;transform:translate(-50%,-50%);">
              <svg class="w-3.5 h-3.5 text-primary shrink-0" fill="none" stroke="currentColor" viewbox="0 0 24 24" aria-hidden="true"><path d="M12 3 20 7v5c0 5-3.4 8.5-8 9-4.6-.5-8-4-8-9V7l8-4Z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="m9 12 2 2 4-4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span class="font-technical text-[10px] whitespace-nowrap">Cross-Review</span>
            </div>
            <div class="orbit-node absolute glass-card rounded-full border border-white/10 px-3 py-1.5 flex items-center gap-1.5" style="top:91.2%;left:50%;transform:translate(-50%,-50%);">
              <svg class="w-3.5 h-3.5 text-primary shrink-0" fill="none" stroke="currentColor" viewbox="0 0 24 24" aria-hidden="true"><path d="m10 20 4-16M18 8l4 4-4 4M6 16l-4-4 4-4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>
              <span class="font-technical text-[10px] whitespace-nowrap">Code</span>
            </div>
            <div class="frozen-node absolute rounded-full border-2 border-primary/60 bg-primary/10 px-3 py-1.5 flex items-center gap-1.5" style="top:50%;left:8.8%;transform:translate(-50%,-50%);">
              <svg class="w-3.5 h-3.5 text-primary shrink-0" fill="none" stroke="currentColor" viewbox="0 0 24 24" aria-hidden="true"><path d="M7 11V8a5 5 0 0 1 10 0v3" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><rect x="5" y="11" width="14" height="10" rx="2" stroke-width="2"></rect><path d="M12 15v2" stroke-width="2" stroke-linecap="round"></path></svg>
              <span class="font-technical text-[10px] text-primary whitespace-nowrap">Frozen</span>
            </div>
          </div>
          <p class="mt-8 font-technical text-[9px] text-on-surface-variant/60 text-center leading-relaxed">design → cross-review → code → review ⇄ fix → frozen ↺ re-iterate</p>
        </div>
        <div class="absolute inset-0 pointer-events-none"><div class="absolute top-1/4 left-1/4 w-64 h-64 bg-primary/5 rounded-full blur-[100px]"></div><div class="absolute bottom-1/4 right-1/4 w-64 h-64 bg-secondary/5 rounded-full blur-[100px]"></div></div>
      </div>
    </div>
  </div>
</section>

<section id="product" class="py-24 max-w-7xl mx-auto px-6 relative">
  <div class="text-center mb-16"><h2 class="text-4xl md:text-5xl font-bold font-display mb-4 tracking-tight">Command every request.</h2><p class="text-lg text-on-surface-variant max-w-3xl mx-auto">Scalable infrastructure that stays within your private network, giving you total control over data and execution.</p></div>
  <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6"><svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Visual Scenario Designer</h3><p class="text-sm text-on-surface-variant leading-relaxed">Design complex API flows visually. Capture requests, define headers, and set assertions without writing complex code.</p></div>
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6" style="background: rgba(236, 72, 153, 0.1); border-color: rgba(236, 72, 153, 0.2);"><svg class="w-6 h-6 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 11.5V14m0-2.5v-6a1.5 1.5 0 113 0m-3 6a1.5 1.5 0 00-3 0v2a7.5 7.5 0 0015 0v-5a1.5 1.5 0 00-3 0m-6-3V11m0-5.5v-1a1.5 1.5 0 013 0v1m0 0V11" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Test Plan Orchestration</h3><p class="text-sm text-on-surface-variant leading-relaxed">Chain multiple scenarios together. Control ramp-up, hold times, and failure criteria at a global level.</p></div>
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6"><svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Scalable Generator Mesh</h3><p class="text-sm text-on-surface-variant leading-relaxed">Deploy worker nodes as a distributed cluster. Orchestrate massive load from your own private infrastructure.</p></div>
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6"><svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Traceable Run Reports</h3><p class="text-sm text-on-surface-variant leading-relaxed">Trace every test run. Detailed interactive reports including performance artifacts, logs, and failure analysis.</p></div>
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6" style="background: rgba(236, 72, 153, 0.1); border-color: rgba(236, 72, 153, 0.2);"><svg class="w-6 h-6 text-secondary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Unified Asset Management</h3><p class="text-sm text-on-surface-variant leading-relaxed">Centralized storage for datasets, external scripts, and configuration files. Upload once, reuse across all plans.</p></div>
    <div class="glass-card p-8 rounded-xl flex flex-col items-start"><div class="icon-tile mb-6"><svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="font-display font-bold text-xl mb-3">Open Source &amp; Privacy First</h3><p class="text-sm text-on-surface-variant leading-relaxed">No proprietary lock-in. Host it on-premise or in your cloud. Built for privacy-conscious engineering teams.</p></div>
  </div>
</section>

<section class="py-12 max-w-6xl mx-auto px-6 relative">
  <div class="glass-card rounded-xl border border-white/10 overflow-hidden">
    <div class="px-6 py-4 border-b border-white/5 bg-white/5 flex flex-wrap items-center justify-between gap-3"><div class="flex flex-wrap items-center gap-3"><h2 class="font-technical text-xs uppercase tracking-widest text-primary">Recent Test Runs</h2><span class="font-technical text-[9px] uppercase tracking-wider text-on-surface-variant/60">UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA</span></div><span class="font-technical text-[10px] text-primary border border-primary/20 bg-primary/10 rounded-full px-3 py-1">LIVE_UPDATE: ON</span></div>
    <div class="overflow-x-auto"><table class="w-full text-left font-technical text-xs border-collapse"><thead><tr class="text-on-surface-variant/60 bg-white/[0.02]"><th class="px-6 py-3">RUN ID</th><th class="px-6 py-3">STATUS</th><th class="px-6 py-3">SLA RESULT</th><th class="px-6 py-3">P95 LATENCY</th><th class="px-6 py-3">ERROR %</th><th class="px-6 py-3">DURATION</th></tr></thead><tbody class="divide-y divide-white/5">
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9482</td><td class="px-6 py-4">FINISHED</td><td class="px-6 py-4 text-[#22c55e]">PASSED</td><td class="px-6 py-4">142ms</td><td class="px-6 py-4">0.00%</td><td class="px-6 py-4">15m 00s</td></tr>
      <tr data-run-row class="bg-primary/5 hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9481</td><td class="px-6 py-4">RUNNING</td><td class="px-6 py-4 text-on-surface-variant">PENDING</td><td class="px-6 py-4">218ms</td><td class="px-6 py-4">0.84%</td><td class="px-6 py-4">08m 42s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9480</td><td class="px-6 py-4">FAILED</td><td class="px-6 py-4 text-red-400">Critical</td><td class="px-6 py-4">1,240ms</td><td class="px-6 py-4">22.4%</td><td class="px-6 py-4">02m 14s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9479</td><td class="px-6 py-4">ABORTED</td><td class="px-6 py-4 text-on-surface-variant">N/A</td><td class="px-6 py-4">--</td><td class="px-6 py-4">0.00%</td><td class="px-6 py-4">00m 18s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9478</td><td class="px-6 py-4">FINISHED</td><td class="px-6 py-4 text-[#22c55e]">PASSED</td><td class="px-6 py-4">94ms</td><td class="px-6 py-4">0.01%</td><td class="px-6 py-4">10m 00s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9477</td><td class="px-6 py-4">FINISHED</td><td class="px-6 py-4 text-[#22c55e]">PASSED</td><td class="px-6 py-4">108ms</td><td class="px-6 py-4">0.00%</td><td class="px-6 py-4">12m 30s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9476</td><td class="px-6 py-4">FAILED</td><td class="px-6 py-4 text-secondary">Soft Fail</td><td class="px-6 py-4">356ms</td><td class="px-6 py-4">1.20%</td><td class="px-6 py-4">05m 00s</td></tr>
      <tr data-run-row class="hover:bg-white/[0.03] transition-colors"><td class="px-6 py-4 text-primary">#SP-9475</td><td class="px-6 py-4">FINISHED</td><td class="px-6 py-4 text-[#22c55e]">PASSED</td><td class="px-6 py-4">112ms</td><td class="px-6 py-4">0.00%</td><td class="px-6 py-4">15m 00s</td></tr>
    </tbody></table></div>
  </div>
</section>

<section class="py-24 px-6 max-w-7xl mx-auto overflow-hidden">
  <div class="text-center mb-12"><h2 class="text-4xl md:text-5xl font-bold font-display mb-4 tracking-tight">Distributed load mesh</h2><p class="text-lg text-on-surface-variant max-w-3xl mx-auto">High-scale orchestration across distributed clusters with complete visibility.<br/><span class="font-technical text-[10px] uppercase tracking-wider text-on-surface-variant/60">UI DEMONSTRATION · EXAMPLE DATA · NOT A LIVE SERVICE · NOT BENCHMARK DATA</span></p></div>
  <div class="mesh-visual relative min-h-[560px] glass-card rounded-[2.5rem] bg-black/20 overflow-hidden flex items-center justify-center mesh-dot-grid">
    <div class="radar-ring mesh-radar-ring mesh-radar-ring--inner"></div><div class="radar-ring mesh-radar-ring mesh-radar-ring--middle"></div><div class="radar-ring mesh-radar-ring mesh-radar-ring--outer"></div>
    <svg class="mesh-svg absolute hidden md:block" viewBox="-300 -300 600 600" preserveAspectRatio="xMidYMid meet" aria-hidden="true" style="left:50%;top:50%;width:600px;height:600px;transform:translate(-50%,-50%);">
      <defs>
        <filter id="mesh-link-glow" filterUnits="userSpaceOnUse" x="-300" y="-300" width="600" height="600"><feGaussianBlur stdDeviation="2.5" result="blur"></feGaussianBlur><feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
        <filter id="mesh-interface-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="2.5" result="blur"></feGaussianBlur><feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
        <filter id="mesh-packet-glow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="blur"></feGaussianBlur><feMerge><feMergeNode in="blur"></feMergeNode><feMergeNode in="SourceGraphic"></feMergeNode></feMerge></filter>
      </defs>
      <g class="mesh-links" fill="none">
        <path class="mesh-link mesh-link--busy" d="M60 0 L170 0"></path>
        <path class="mesh-link mesh-link--idle" d="M30 52 L101 175"></path>
        <path class="mesh-link mesh-link--busy" d="M-30 52 L-101 175"></path>
        <path class="mesh-link mesh-link--idle" d="M-60 0 L-170 0"></path>
        <path class="mesh-link mesh-link--busy" d="M-30 -52 L-101 -175"></path>
        <path class="mesh-link mesh-link--idle" d="M30 -52 L101 -175"></path>
      </g>
      <g class="mesh-interfaces" fill="#22d3ee" filter="url(#mesh-interface-glow)">
        <circle class="mesh-interface mesh-interface--busy" cx="170" cy="0" r="4"></circle>
        <circle class="mesh-interface mesh-interface--idle" cx="101" cy="175" r="4"></circle>
        <circle class="mesh-interface mesh-interface--busy" cx="-101" cy="175" r="4"></circle>
        <circle class="mesh-interface mesh-interface--idle" cx="-170" cy="0" r="4"></circle>
        <circle class="mesh-interface mesh-interface--busy" cx="-101" cy="-175" r="4"></circle>
        <circle class="mesh-interface mesh-interface--idle" cx="101" cy="-175" r="4"></circle>
      </g>
      <g class="mesh-packets" fill="#22d3ee" filter="url(#mesh-packet-glow)">
        <circle class="mesh-packet mesh-packet--01" r="3"><animateMotion begin="0s" dur="2.4s" path="M 60 0 L 170 0" repeatCount="indefinite"></animateMotion></circle>
        <circle class="mesh-packet mesh-packet--03" r="3"><animateMotion begin="0.7s" dur="2.9s" path="M -30 52 L -101 175" repeatCount="indefinite"></animateMotion></circle>
        <circle class="mesh-packet mesh-packet--05" r="3"><animateMotion begin="1.4s" dur="3.3s" path="M -30 -52 L -101 -175" repeatCount="indefinite"></animateMotion></circle>
      </g>
    </svg>
    <div class="mesh-orchestrator relative z-50 flex flex-col items-center">
      <div class="relative w-24 h-24 rounded-3xl border-2 border-primary/40 bg-primary/20 flex items-center justify-center backdrop-blur-3xl shadow-[0_0_60px_-10px_rgba(34,211,238,.5)] running-pulse"><div class="absolute -inset-2 border border-primary/10 rounded-full arc-rotate"></div><img alt="SurgePilot Logo" class="w-12 h-12 object-contain relative z-10" src="__SURGEPILOT_LOGO__"/></div>
      <span class="mt-4 font-technical text-[9px] uppercase tracking-[0.2em] text-primary bg-primary/10 px-3 py-1 rounded-full border border-primary/20">Orchestrator</span>
    </div>
    <div class="node-card mesh-node glass-card mesh-node--east mesh-node--busy mesh-node--pulse" style="--node-x:250px;--node-y:0px;--mesh-pulse-delay:0s;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-primary">node-01</span><span class="mesh-node__status mesh-node__status--busy">BUSY</span></div><div class="mesh-node__progress"><span style="width:82%"></span></div><div class="mesh-node__metrics"><span>CPU 82%</span><span>RAM 14.1G</span></div></div>
    <div class="node-card mesh-node glass-card mesh-node--southeast mesh-node--idle" style="--node-x:125px;--node-y:217px;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-on-surface-variant">node-02</span><span class="mesh-node__status mesh-node__status--idle">IDLE</span></div><div class="mesh-node__metrics"><span>CPU 2%</span><span>RAM 0.8G</span></div></div>
    <div class="node-card mesh-node glass-card mesh-node--southwest mesh-node--busy mesh-node--pulse" style="--node-x:-125px;--node-y:217px;--mesh-pulse-delay:-0.9s;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-primary">node-03</span><span class="mesh-node__status mesh-node__status--busy">BUSY</span></div><div class="mesh-node__progress"><span style="width:48%"></span></div><div class="mesh-node__metrics"><span>CPU 48%</span><span>RAM 6.2G</span></div></div>
    <div class="node-card mesh-node glass-card mesh-node--west mesh-node--idle" style="--node-x:-250px;--node-y:0px;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-on-surface-variant">node-04</span><span class="mesh-node__status mesh-node__status--idle">IDLE</span></div><div class="mesh-node__metrics"><span>CPU 5%</span><span>RAM 1.1G</span></div></div>
    <div class="node-card mesh-node glass-card mesh-node--northwest mesh-node--busy mesh-node--pulse" style="--node-x:-125px;--node-y:-217px;--mesh-pulse-delay:-1.8s;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-primary">node-05</span><span class="mesh-node__status mesh-node__status--busy">BUSY</span></div><div class="mesh-node__progress"><span style="width:64%"></span></div><div class="mesh-node__metrics"><span>CPU 64%</span><span>RAM 8.4G</span></div></div>
    <div class="node-card mesh-node glass-card mesh-node--northeast mesh-node--idle" style="--node-x:125px;--node-y:-217px;"><div class="mesh-node__top"><span class="font-technical text-[9px] text-on-surface-variant">node-06</span><span class="mesh-node__status mesh-node__status--idle">IDLE</span></div><div class="mesh-node__metrics"><span>CPU 1%</span><span>RAM 0.4G</span></div></div>
  </div>
</section>

<section class="py-24 px-6 max-w-6xl mx-auto text-center relative">
  <div class="mb-20"><h2 class="text-4xl md:text-5xl font-bold font-display mb-4 tracking-tight">Ready in four steps.</h2><p class="text-lg text-on-surface-variant max-w-2xl mx-auto">From concept to production-ready performance reports.</p></div>
  <div class="grid md:grid-cols-4 gap-12 relative z-10">
    <div class="group reveal-on-scroll" style="transition-delay: 100ms;"><div class="icon-tile w-12 h-12 mx-auto glass-card rounded-full mb-6 border-white/10 group-hover:border-primary/40 transition-all duration-500 group-hover:scale-110"><svg class="w-6 h-6 text-on-surface-variant group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="text-xl font-bold mb-3 font-display">1. Design</h3><p class="text-sm text-on-surface-variant leading-relaxed">Design a performance scenario visually or through configuration.</p></div>
    <div class="group reveal-on-scroll" style="transition-delay: 300ms;"><div class="icon-tile w-12 h-12 mx-auto glass-card rounded-full mb-6 border-white/10 group-hover:border-primary/40 transition-all duration-500 group-hover:scale-110"><svg class="w-6 h-6 text-on-surface-variant group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="text-xl font-bold mb-3 font-display">2. Orchestrate</h3><p class="text-sm text-on-surface-variant leading-relaxed">Combine scenarios into a robust, high-scale Test Plan.</p></div>
    <div class="group reveal-on-scroll" style="transition-delay: 500ms;"><div class="icon-tile w-12 h-12 mx-auto glass-card rounded-full mb-6 border-white/10 group-hover:border-primary/40 transition-all duration-500 group-hover:scale-110"><svg class="w-6 h-6 text-on-surface-variant group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path><path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="text-xl font-bold mb-3 font-display">3. Run</h3><p class="text-sm text-on-surface-variant leading-relaxed">Execute at scale from your distributed Load Nodes.</p></div>
    <div class="group reveal-on-scroll" style="transition-delay: 700ms;"><div class="icon-tile w-12 h-12 mx-auto glass-card rounded-full mb-6 border-white/10 group-hover:border-primary/40 transition-all duration-500 group-hover:scale-110"><svg class="w-6 h-6 text-on-surface-variant group-hover:text-primary transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg></div><h3 class="text-xl font-bold mb-3 font-display">4. Report</h3><p class="text-sm text-on-surface-variant leading-relaxed">Analyze deep-dive metrics with traceable run reports.</p></div>
  </div>
  <div class="absolute top-[48%] left-[12%] right-[12%] h-[2px] bg-white/5 hidden md:block z-0 overflow-hidden"><div class="packet-motion"></div></div>
</section>

<section class="py-24 px-6 mb-20">
  <div class="max-w-6xl mx-auto relative overflow-hidden glass-card rounded-[2.5rem] p-10 md:p-16 text-center border border-white/10">
    <div class="relative z-10"><h2 class="text-4xl md:text-6xl font-bold font-display mb-8 tracking-tight">Inspect the baseline. <br/><span class="text-primary">Then judge the claim.</span></h2><div class="flex flex-col sm:flex-row items-center justify-center gap-6"><a class="w-full sm:w-auto bg-primary text-[#00363e] px-12 py-5 rounded-xl font-bold primary-glow-btn text-xl" href="__SURGEPILOT_REPOSITORY__">★ Star on GitHub</a><a class="w-full sm:w-auto border border-white/10 text-on-surface-variant px-12 py-5 rounded-xl backdrop-blur-xl flex items-center justify-center gap-3 hover:border-primary/40 hover:text-primary transition-colors" href="__SURGEPILOT_DOCS__"><svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5a2 2 0 012-2h9l5 5v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5z" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path></svg>Read the docs</a></div><p class="mt-10 font-technical text-on-surface-variant/60 text-xs uppercase tracking-[0.3em]">Open Source • MIT License • Self-Hosted</p></div>
  </div>
</section>

<footer class="bg-[#0a0e1a] border-t border-white/5 pt-24 pb-12 px-6">
  <div class="max-w-7xl mx-auto"><div class="grid grid-cols-2 md:grid-cols-6 gap-12">
    <div class="col-span-2"><div class="flex items-center gap-3 mb-8"><img alt="" class="w-8 h-8 object-contain" src="__SURGEPILOT_LOGO__"/><span class="text-2xl font-bold text-on-surface font-display">SurgePilot</span></div><p class="text-on-surface-variant leading-relaxed mb-8 max-w-xs">Open source · Self-hosted · Original public baseline produced by AI agents.</p><a class="inline-flex items-center gap-2 text-primary font-technical text-xs uppercase tracking-wider" href="__SURGEPILOT_REPOSITORY__">★ Star on GitHub ↗</a></div>
    <div><h3 class="font-technical text-primary text-[10px] uppercase tracking-widest mb-6">Explore</h3><ul class="space-y-4 text-sm"><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="#product">Product</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="#how-it-works">How it was built</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_REPOSITORY__#built-100-by-ai">Evidence</a></li></ul></div>
    <div><h3 class="font-technical text-primary text-[10px] uppercase tracking-widest mb-6">Docs</h3><ul class="space-y-4 text-sm"><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_DOCS__">Getting Started</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_CONFIGURATION__">Configuration</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_QUICKSTART__">Quickstart</a></li></ul></div>
    <div><h3 class="font-technical text-primary text-[10px] uppercase tracking-widest mb-6">Project</h3><ul class="space-y-4 text-sm"><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_REPOSITORY__">GitHub</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_RELEASES__">Releases</a></li><li><a class="text-on-surface-variant hover:text-on-surface transition-colors" href="__SURGEPILOT_SECURITY__">Security</a></li></ul></div>
  </div></div>
</footer>

`;

export type PublicMarketingLinks = {
  logo: string;
  docs: string;
  quickstart: string;
  configuration: string;
  repository: string;
  releases: string;
};

export function getPublicMarketingMarkup(links: PublicMarketingLinks) {
  const repository = links.repository;
  return publicMarketingMarkup
    .replaceAll("__SURGEPILOT_LOGO__", links.logo)
    .replaceAll("__SURGEPILOT_DOCS__", links.docs)
    .replaceAll("__SURGEPILOT_QUICKSTART__", links.quickstart)
    .replaceAll("__SURGEPILOT_CONFIGURATION__", links.configuration)
    .replaceAll("__SURGEPILOT_REPOSITORY__", repository)
    .replaceAll("__SURGEPILOT_RELEASES__", links.releases)
    .replaceAll("__SURGEPILOT_SECURITY__", `${repository}/blob/main/SECURITY.md`);
}
