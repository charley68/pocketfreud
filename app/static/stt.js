/* PocketFreud STT (native-only, true hold-to-talk with race guard) */
(function () {
  const isNative = !!(window.Capacitor?.getPlatform && ['ios','android'].includes(window.Capacitor.getPlatform()));
  if (!isNative) return; // web keeps using your inline mic UI, no SR

  const SR    = window.Capacitor?.Plugins?.SpeechRecognition;
  const mic   = document.querySelector('#recordButton');
  const input = document.querySelector('#userInput');
  const send  = document.querySelector('#sendButton');
  if (!SR || !mic || !input || !send) return;

  let listening = false;
  let subs = [];
  let holdTimer = null;
  let pressed = false;
  let startNonce = 0;   // increments on every pointer/touch sequence
  const HOLD_MS = 250;  // tap < 250ms = ignore, no recording

  function killSubs() {
    subs.forEach(u => u?.remove && u.remove());
    subs = [];
  }

  async function requestPermsOnce() {
    try { await SR.requestPermissions(); } catch (e) { console.warn('requestPermissions error', e); }
  }

  async function actuallyStart(nonce) {
    // If the press was released before the threshold, abort starting.
    if (!pressed) return;

    // Clear old listeners every start
    killSubs();
    subs.push(
      SR.addListener('partialResults', ({ matches }) => { if (matches?.[0]) input.value = matches[0]; }),
      SR.addListener('result',         ({ matches }) => { if (matches?.[0]) input.value = matches[0]; })
    );

    try {
      await SR.start({ partialResults: true, popup: false, maxResults: 1 /*, language: 'en-GB'*/ });

      // If a newer press/release cycle happened, cancel this start immediately.
      if (nonce !== startNonce || !pressed) {
        try { await SR.stop(); } catch {}
        killSubs();
        return;
      }

      listening = true;
      mic.classList.add('active');
      mic.setAttribute('aria-pressed', 'true');
    } catch (e) {
      console.error('SR.start error', e);
      killSubs();
    }
  }

  async function stop(autoSend = true) {
    if (!listening) return;
    try { await SR.stop(); } catch {}
    listening = false;
    mic.classList.remove('active');
    mic.setAttribute('aria-pressed', 'false');
    killSubs();
    if (autoSend && input.value.trim()) send.click();
  }

  // ---- Event wiring (native owns the mic) ----

  // Block legacy click handlers bound elsewhere
  mic.addEventListener('click', (e) => {
    e.preventDefault(); e.stopPropagation(); e.stopImmediatePropagation();
  }, { capture: true });

  async function onPressDown(e) {
    e.preventDefault();
    pressed = true;
    const myNonce = ++startNonce;   // unique id for this press
    await requestPermsOnce();

    // Delay before actually starting recognition
    clearTimeout(holdTimer);
    holdTimer = setTimeout(() => {
      // If finger already lifted, don't start
      if (!pressed) return;
      // If something else started after this, ignore
      if (myNonce !== startNonce) return;
      actuallyStart(myNonce);
    }, HOLD_MS);
  }

  async function onPressUp(e, shouldAutoSend = true) {
    e.preventDefault();
    pressed = false;
    clearTimeout(holdTimer);

    // If we never made it past the HOLD_MS threshold, nothing to stop.
    if (!listening) return;

    // Invalidate this press cycle so any late SR.start bails out
    startNonce++;

    await stop(shouldAutoSend);
  }

  // Touch events
  mic.addEventListener('touchstart',  onPressDown,                          { passive: false });
  mic.addEventListener('touchend',    (e) => onPressUp(e, true),            { passive: false });
  mic.addEventListener('touchcancel', (e) => onPressUp(e, false),           { passive: false });

  // Pointer events (Android + iOS unified)
  mic.addEventListener('pointerdown', (e) => onPressDown(e));
  mic.addEventListener('pointerup',   (e) => onPressUp(e, true));
  mic.addEventListener('pointerleave',(e) => onPressUp(e, false));

  // Ask once soon after load (helps register in Settings)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', requestPermsOnce, { once: true });
  } else {
    requestPermsOnce();
  }
})();
