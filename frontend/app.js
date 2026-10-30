/**
 * AI Vision Assistant 2026 - Ultra-Accessible Audio & UI Controller
 * Engineered specifically for Elderly and Visually Impaired Users (WCAG AAA)
 * Unlocks AudioContext & SpeechSynthesis on 1st tap, provides spatial sonar beeps,
 * prevents TTS queue corruption, and supports English/Urdu bilingual guidance.
 */

// ============================================================================
// 1. ROBUST AUDIO CONTROLLER
// ============================================================================
class AudioController {
  constructor() {
    this.audioCtx = null;
    this.unlocked = false;
    this.speechSynth = window.speechSynthesis;
    this.currentLang = 'en'; // 'en' or 'ur'
    this.speechRate = 0.95; // Slower, highly legible pace for elderly ears
    
    // Cooldown management to prevent stuttering/queue jamming
    this.lastHazardSpoken = {};
    this.lastSpokenText = '';
    this.hazardCooldownMs = 3500; // 3.5-second strict cooldown per hazard type
    this.isSpeaking = false;
    this.fallbackPlayer = document.getElementById('fallbackAudioPlayer');
    
    this.voices = [];
    if (this.speechSynth) {
      this.voices = this.speechSynth.getVoices();
      if (this.speechSynth.onvoiceschanged !== undefined) {
        this.speechSynth.onvoiceschanged = () => {
          this.voices = this.speechSynth.getVoices();
        };
      }
    }
  }

  /**
   * Unlock Web Audio API context and SpeechSynthesis on first user touch.
   * Completely resolves browser autoplay policy blocks.
   */
  unlock() {
    if (this.unlocked) return;

    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass && !this.audioCtx) {
        this.audioCtx = new AudioContextClass();
      }
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      // Unlock SpeechSynthesis with an empty utterance
      if (this.speechSynth) {
        const dummyUtterance = new SpeechSynthesisUtterance(' ');
        dummyUtterance.volume = 0.01;
        this.speechSynth.speak(dummyUtterance);
      }

      this.unlocked = true;
      console.log("[AudioController] AudioContext and SpeechSynthesis unlocked successfully.");

      // Play pleasant startup chime
      this.playTone(523.25, 100, 'sine'); // C5
      setTimeout(() => this.playTone(659.25, 120, 'sine'), 110); // E5

      // Dismiss overlay
      const overlay = document.getElementById('unlockOverlay');
      if (overlay) overlay.classList.add('dismissed');

      // Announce initial status
      const welcome = this.currentLang === 'ur' 
        ? "ویژن اسسٹنٹ فعال ہے۔ کیمرہ اور آواز آن ہیں۔"
        : "Vision Assistant active. Camera and sound are ready.";
      this.speak(welcome, true);

    } catch (err) {
      console.error("[AudioController] Unlock error:", err);
    }
  }

  /**
   * Synthesize immediate hardware audio beeps using Web Audio API oscillator.
   * Guaranteed to produce audio even if OS voices are unavailable.
   */
  playTone(frequency, durationMs, type = 'sine', volume = 0.35) {
    if (!this.audioCtx) {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass) this.audioCtx = new AudioContextClass();
    }
    if (!this.audioCtx) return;

    if (this.audioCtx.state === 'suspended') {
      this.audioCtx.resume();
    }

    try {
      const osc = this.audioCtx.createOscillator();
      const gain = this.audioCtx.createGain();

      osc.type = type;
      osc.frequency.setValueAtTime(frequency, this.audioCtx.currentTime);

      gain.gain.setValueAtTime(volume, this.audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + (durationMs / 1000));

      osc.connect(gain);
      gain.connect(this.audioCtx.destination);

      osc.start();
      osc.stop(this.audioCtx.currentTime + (durationMs / 1000));
    } catch (e) {
      console.warn("[AudioController] Tone playback error:", e);
    }
  }

  // Touch confirmation chime
  playTouchChime() {
    this.playTone(587.33, 80, 'sine', 0.25); // D5
    if (navigator.vibrate) navigator.vibrate(50);
  }

  // Critical danger sonar (high-pitch dual chirp)
  playDangerChirp() {
    this.playTone(880, 140, 'square', 0.4); // A5
    setTimeout(() => this.playTone(1200, 180, 'square', 0.4), 150);
    if (navigator.vibrate) navigator.vibrate([200, 90, 200]);
  }

  // Caution ping (medium warm tone)
  playCautionPing() {
    this.playTone(440, 160, 'sine', 0.3); // A4
    if (navigator.vibrate) navigator.vibrate(100);
  }

  /**
   * Robust speech output with strict queue safety, cooldowns, and server fallback.
   */
  speak(text, isPriority = false, hazardKey = null) {
    if (!text || !text.trim()) return;

    const now = Date.now();

    // 1. Strict Hazard Cooldown (3.5s per hazard key)
    if (hazardKey) {
      const lastTime = this.lastHazardSpoken[hazardKey] || 0;
      if (now - lastTime < this.hazardCooldownMs) {
        return; // Suppress repetitive chatter
      }
      this.lastHazardSpoken[hazardKey] = now;
    }

    // 2. Prevent repeating identical text too quickly
    if (!isPriority && text === this.lastSpokenText && now - (this.lastHazardSpoken['generic'] || 0) < 4000) {
      return;
    }
    this.lastHazardSpoken['generic'] = now;
    this.lastSpokenText = text;

    // Update UI text bubble
    const bubbleText = document.getElementById('bubbleText');
    if (bubbleText) bubbleText.textContent = text;

    // 3. Audio Sonar Chimes
    if (isPriority) {
      this.playDangerChirp();
    }

    // 4. Client-side SpeechSynthesis Execution
    if (this.speechSynth) {
      // Safe interruption for priority alerts
      if (isPriority && this.speechSynth.speaking) {
        this.speechSynth.cancel();
      }

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = this.speechRate;
      utterance.pitch = 1.0;

      // Select voice based on language
      if (this.voices.length > 0) {
        if (this.currentLang === 'ur') {
          const urVoice = this.voices.find(v => v.lang.includes('ur') || v.lang.includes('hi'));
          if (urVoice) utterance.voice = urVoice;
        } else {
          const enVoice = this.voices.find(v => v.lang.includes('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
          if (enVoice) utterance.voice = enVoice;
        }
      }

      // Watchdog timeout to prevent frozen speech synthesis
      let hasEnded = false;
      const speechTimeout = setTimeout(() => {
        if (!hasEnded && this.speechSynth.speaking) {
          this.speechSynth.cancel();
        }
      }, 7000);

      utterance.onend = () => {
        hasEnded = true;
        clearTimeout(speechTimeout);
        this.isSpeaking = false;
      };

      utterance.onerror = (e) => {
        hasEnded = true;
        clearTimeout(speechTimeout);
        this.isSpeaking = false;
        console.warn("[SpeechSynthesis] Error encountered. Invoking server TTS fallback.", e);
        this._speakServerFallback(text);
      };

      try {
        this.isSpeaking = true;
        this.speechSynth.speak(utterance);
        return;
      } catch (err) {
        console.warn("[SpeechSynthesis] Speak call failed:", err);
      }
    }

    // 5. Server-side TTS Fallback (gTTS MP3 Stream)
    this._speakServerFallback(text);
  }

  _speakServerFallback(text) {
    if (!this.fallbackPlayer) return;
    try {
      fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text, lang: this.currentLang })
      })
      .then(res => {
        if (!res.ok) throw new Error("Server TTS unavailable");
        return res.blob();
      })
      .then(blob => {
        const url = URL.createObjectURL(blob);
        this.fallbackPlayer.src = url;
        this.fallbackPlayer.play().catch(e => console.warn("Fallback player blocked:", e));
      })
      .catch(e => console.warn("Fallback TTS error:", e));
    } catch (e) {
      console.warn("Server fallback failed:", e);
    }
  }
}

// Global Audio Instance
const audioCtrl = new AudioController();

// ============================================================================
// 2. BILINGUAL DICTIONARY & UI STRINGS
// ============================================================================
const STRINGS = {
  en: {
    lang_btn: "ENGLISH",
    safe_headline: "SAFE PATH",
    safe_sub: "Forward corridor is clear to walk",
    danger_headline: "DANGER AHEAD",
    danger_sub: "Obstacle or hazard in your walking path",
    middle_title: "TAP TO SPEAK OR ASK",
    middle_sub: "Touch anywhere here. I will listen and describe what is in front of you.",
    ocr_title: "READ TEXT",
    ocr_sub: "Street signs, bills, medicines",
    repeat_title: "REPEAT SOUND",
    repeat_sub: "Hear last message or check audio",
    listening: "Listening for your question. Speak now...",
    scanning: "Scanning text in front of you...",
    speech_init: "Vision Assistant active. Path is clear.",
    repeat_confirm: "Repeating last alert: "
  },
  ur: {
    lang_btn: "اردو (URDU)",
    safe_headline: "راستہ صاف ہے",
    safe_sub: "سامنے کوئی رکاوٹ نہیں ہے",
    danger_headline: "سامنے خطرہ ہے!",
    danger_sub: "سامنے کھڈا یا رکاوٹ موجود ہے",
    middle_title: "بولنے کے لیے دبائیں",
    middle_sub: "یہاں ہاتھ لگائیں اور بولیں، میں سامنے کا منظر بتاؤں گا۔",
    ocr_title: "تحریر پڑھیں",
    ocr_sub: "بورڈ، کاغذ یا دوائی پڑھیں",
    repeat_title: "آواز سنیں",
    repeat_sub: "آخری پیغام دوبارہ سنیں",
    listening: "میں سن رہا ہوں، اپنا سوال پوچھیں۔",
    scanning: "سامنے موجود تحریر پڑھی جا رہی ہے...",
    speech_init: "ویژن اسسٹنٹ آن ہے۔ راستہ صاف ہے۔",
    repeat_confirm: "آخری پیغام: "
  }
};

// ============================================================================
// 3. APPLICATION STATE & DOM REFERENCES
// ============================================================================
const appState = {
  isCloudMode: window.location.hostname.includes('vercel.app') || window.location.port === '',
  ws: null,
  wsConnected: false,
  cameraStream: null,
  facingMode: 'environment', // Rear camera by default
  isListening: false,
  isProcessingOCR: false,
  recognition: null,
  isAwaitingReply: false,
  lastHazardStatus: 'SAFE'
};

const video = document.getElementById('cameraFeed');
const overlayCanvas = document.getElementById('overlayCanvas');
const ctx = overlayCanvas.getContext('2d');
const hiddenCanvas = document.getElementById('hiddenCanvas');
const hiddenCtx = hiddenCanvas.getContext('2d');

const statusBanner = document.getElementById('statusBanner');
const statusSymbol = document.getElementById('statusSymbol');
const statusHeadline = document.getElementById('statusHeadline');
const statusSubline = document.getElementById('statusSubline');

const langToggleBtn = document.getElementById('langToggleBtn');
const langLabel = document.getElementById('langLabel');
const modePill = document.getElementById('modePill');
const engineBadge = document.getElementById('engineBadge');
const flipCamBtn = document.getElementById('flipCamBtn');

const zoneMiddle = document.getElementById('zoneMiddle');
const middleCard = document.getElementById('middleCard');
const middleTitle = document.getElementById('middleTitle');
const middleSubtext = document.getElementById('middleSubtext');

const btnOcr = document.getElementById('btnOcr');
const ocrTitle = document.getElementById('ocrTitle');
const ocrSub = document.getElementById('ocrSub');

const btnRepeat = document.getElementById('btnRepeat');
const repeatTitle = document.getElementById('repeatTitle');
const repeatSub = document.getElementById('repeatSub');

// ============================================================================
// 4. CAMERA INITIALIZATION (WebRTC)
// ============================================================================
async function initCamera() {
  if (appState.cameraStream) {
    appState.cameraStream.getTracks().forEach(t => t.stop());
  }

  const constraints = {
    audio: false,
    video: {
      facingMode: appState.facingMode,
      width: { ideal: 640 },
      height: { ideal: 480 }
    }
  };

  try {
    appState.cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    video.srcObject = appState.cameraStream;
    video.onloadedmetadata = () => {
      overlayCanvas.width = video.videoWidth;
      overlayCanvas.height = video.videoHeight;
      hiddenCanvas.width = video.videoWidth;
      hiddenCanvas.height = video.videoHeight;
    };
  } catch (err) {
    console.warn("[Camera] Camera access error:", err);
    updateStatus('DANGER', "Camera access required", "Please allow camera access.");
  }
}

flipCamBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  audioCtrl.unlock();
  audioCtrl.playTouchChime();
  appState.facingMode = appState.facingMode === 'environment' ? 'user' : 'environment';
  initCamera();
  audioCtrl.speak(audioCtrl.currentLang === 'ur' ? "کیمرہ تبدیل کر دیا گیا۔" : "Camera flipped.", true);
});

// ============================================================================
// 5. HYBRID BACKEND CONNECTION (Local WebSocket vs Cloud Vercel REST)
// ============================================================================
function initBackendConnection() {
  if (appState.isCloudMode) {
    setupCloudEdgeMode();
  } else {
    setupLocalWebSocketMode();
  }
}

function setupLocalWebSocketMode() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws/stream`;

  engineBadge.textContent = "⚡ LOCAL OPENVINO (92 FPS)";

  try {
    appState.ws = new WebSocket(wsUrl);

    appState.ws.onopen = () => {
      appState.wsConnected = true;
      console.log("[WebSocket] Connected to local OpenVINO backend.");
      startLocalStreamingLoop();
    };

    appState.ws.onmessage = (event) => {
      appState.isAwaitingReply = false;
      try {
        const data = JSON.parse(event.data);
        handleDetectionResults(data);
      } catch (e) {
        console.error("WS Parse error:", e);
      }
    };

    appState.ws.onerror = () => {
      console.warn("[WebSocket] Local connection failed. Falling back to Cloud Edge mode.");
      appState.wsConnected = false;
      setupCloudEdgeMode();
    };

    appState.ws.onclose = () => {
      appState.wsConnected = false;
    };
  } catch (e) {
    setupCloudEdgeMode();
  }
}

function startLocalStreamingLoop() {
  function streamFrame() {
    if (appState.wsConnected && video.readyState === 4 && !appState.isAwaitingReply) {
      hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
      const b64 = hiddenCanvas.toDataURL('image/jpeg', 0.65);
      appState.isAwaitingReply = true;
      appState.ws.send(JSON.stringify({
        frame: b64,
        mode: 'navigation',
        conf_thresh: 0.35,
        include_depth: true
      }));
    }
    setTimeout(() => requestAnimationFrame(streamFrame), 65);
  }
  streamFrame();
}

function setupCloudEdgeMode() {
  engineBadge.textContent = "☁️ CLOUD EDGE (VERCEL + GROQ)";
  console.log("[CloudMode] Running on Vercel Serverless Architecture.");

  // Periodic REST frame analysis every 1.6s
  setInterval(async () => {
    if (video.readyState !== 4 || appState.isProcessingOCR || appState.isListening) return;

    hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
    const b64 = hiddenCanvas.toDataURL('image/jpeg', 0.6);

    try {
      const res = await fetch('/api/analyze-scene', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          image_b64: b64,
          lang: audioCtrl.currentLang
        })
      });
      if (res.ok) {
        const data = await res.json();
        handleCloudResults(data);
      }
    } catch (e) {
      console.warn("Cloud analyze error:", e);
    }
  }, 1600);
}

// ============================================================================
// 6. DETECTION & HAZARD HANDLING
// ============================================================================
function handleDetectionResults(data) {
  const isDanger = data.has_critical_hazard || Boolean(data.priority_alert);
  const statusType = isDanger ? 'DANGER' : 'SAFE';

  if (isDanger) {
    const alertMsg = data.priority_alert || "Obstacle detected ahead!";
    updateStatus('DANGER', STRINGS[audioCtrl.currentLang].danger_headline, alertMsg);
    
    // Announce with strict 3.5s cooldown
    const hazardWord = extractHazardKeyword(alertMsg);
    audioCtrl.speak(translateHazardAlert(alertMsg), true, hazardWord);
  } else {
    updateStatus('SAFE', STRINGS[audioCtrl.currentLang].safe_headline, STRINGS[audioCtrl.currentLang].safe_sub);
  }

  // Draw overlay bounding boxes
  drawBoundingBoxes(data.detections || []);
}

function handleCloudResults(data) {
  const isDanger = data.status === 'DANGER' || Boolean(data.priority_alert);
  if (isDanger) {
    updateStatus('DANGER', STRINGS[audioCtrl.currentLang].danger_headline, data.priority_alert || "Hazard ahead");
    audioCtrl.speak(data.speech_text || data.priority_alert, true, 'cloud_hazard');
  } else {
    updateStatus('SAFE', STRINGS[audioCtrl.currentLang].safe_headline, data.speech_text || STRINGS[audioCtrl.currentLang].safe_sub);
  }
}

function updateStatus(type, headline, subline) {
  appState.lastHazardStatus = type;
  if (type === 'DANGER') {
    statusBanner.className = 'giant-status-banner danger';
    statusSymbol.textContent = '⚠️';
  } else {
    statusBanner.className = 'giant-status-banner safe';
    statusSymbol.textContent = '✓';
  }
  statusHeadline.textContent = headline;
  statusSubline.textContent = subline;
}

function extractHazardKeyword(alertText) {
  const lower = alertText.toLowerCase();
  for (const k of ['pothole', 'manhole', 'ditch', 'wire', 'step', 'motorcycle', 'car', 'chair']) {
    if (lower.includes(k)) return k;
  }
  return 'obstacle';
}

function translateHazardAlert(alertText) {
  if (audioCtrl.currentLang !== 'ur') return alertText;

  const lower = alertText.toLowerCase();
  if (lower.includes('pothole') || lower.includes('ditch')) {
    return "خبردار! آگے کھڈا یا گڑھا ہے۔ رک جائیں۔";
  } else if (lower.includes('wire')) {
    return "دھیان دیجیے! سامنے تار ہے۔";
  } else if (lower.includes('motorcycle')) {
    return "خبردار! موٹر سائیکل آ رہی ہے۔";
  } else if (lower.includes('step') || lower.includes('stairs')) {
    return "احتیاط! آگے سیڑھیاں یا اونچ نیچ ہے۔";
  } else {
    return "خبردار! سامنے رکاوٹ ہے۔ رک جائیں۔";
  }
}

function drawBoundingBoxes(detections) {
  ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  detections.forEach(det => {
    const [x1, y1, x2, y2] = det.bbox;
    const isCrit = det.is_critical || det.proximity === 'very close';
    ctx.lineWidth = isCrit ? 6 : 3;
    ctx.strokeStyle = isCrit ? '#FF0033' : '#00E676';
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
  });
}

// ============================================================================
// 7. TOUCH ZONES INTERACTIONS (WCAG AAA - Huge Tap Targets)
// ============================================================================

// Global screen unlock on ANY initial interaction
document.addEventListener('pointerdown', () => audioCtrl.unlock(), { once: true });

// ZONE 2: MIDDLE ZONE (Tap to speak / ask question)
zoneMiddle.addEventListener('click', () => {
  audioCtrl.unlock();
  audioCtrl.playTouchChime();

  if (appState.isListening) {
    stopListening();
  } else {
    startListening();
  }
});

// ZONE 3 LEFT: READ DOCUMENT / SIGN (Instant OCR Snapshot)
btnOcr.addEventListener('click', async () => {
  audioCtrl.unlock();
  audioCtrl.playTouchChime();

  const scanMsg = STRINGS[audioCtrl.currentLang].scanning;
  audioCtrl.speak(scanMsg, true);

  appState.isProcessingOCR = true;
  hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  const snapshotB64 = hiddenCanvas.toDataURL('image/jpeg', 0.85);

  try {
    const res = await fetch('/api/ocr/frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_b64: snapshotB64, lang: audioCtrl.currentLang })
    });
    const data = await res.json();
    appState.isProcessingOCR = false;

    const speechResult = data.summary || data.text || "No text visible in front of camera.";
    audioCtrl.speak(speechResult, true);
  } catch (e) {
    appState.isProcessingOCR = false;
    audioCtrl.speak(audioCtrl.currentLang === 'ur' ? "تحریر پڑھنے میں رکاوٹ آئی ہے۔ دوبارہ کوشش کریں۔" : "Could not read text. Please hold steady and try again.", true);
  }
});

// ZONE 3 RIGHT: REPEAT LAST ALERT / TEST SOUND
btnRepeat.addEventListener('click', () => {
  audioCtrl.unlock();
  audioCtrl.playTouchChime();

  if (audioCtrl.lastSpokenText) {
    const prefix = STRINGS[audioCtrl.currentLang].repeat_confirm;
    audioCtrl.speak(prefix + audioCtrl.lastSpokenText, true);
  } else {
    audioCtrl.playDangerChirp();
    const testMsg = audioCtrl.currentLang === 'ur' ? "آڈیو سسٹم بالکل ٹھیک کام کر رہا ہے۔" : "Sound system is working perfectly.";
    audioCtrl.speak(testMsg, true);
  }
});

// ============================================================================
// 8. BILINGUAL SUPPORT TOGGLE (English / Urdu)
// ============================================================================
langToggleBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  audioCtrl.unlock();
  audioCtrl.playTouchChime();

  audioCtrl.currentLang = audioCtrl.currentLang === 'en' ? 'ur' : 'en';
  applyLanguage(audioCtrl.currentLang);
});

function applyLanguage(lang) {
  const s = STRINGS[lang];
  langLabel.textContent = s.lang_btn;
  middleTitle.textContent = s.middle_title;
  middleSubtext.textContent = s.middle_sub;
  ocrTitle.textContent = s.ocr_title;
  ocrSub.textContent = s.ocr_sub;
  repeatTitle.textContent = s.repeat_title;
  repeatSub.textContent = s.repeat_sub;

  if (appState.lastHazardStatus === 'SAFE') {
    statusHeadline.textContent = s.safe_headline;
    statusSubline.textContent = s.safe_sub;
  } else {
    statusHeadline.textContent = s.danger_headline;
  }

  const switchMsg = lang === 'ur' ? "اردو آواز منتخب ہو چکی ہے۔" : "English voice activated.";
  audioCtrl.speak(switchMsg, true);
}

// ============================================================================
// 9. SPEECH RECOGNITION (Voice Command & Multimodal Groq Vision)
// ============================================================================
function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Speech recognition not natively supported on this browser.");
    return;
  }

  appState.recognition = new SpeechRecognition();
  appState.recognition.continuous = false;
  appState.recognition.interimResults = false;
  appState.recognition.lang = audioCtrl.currentLang === 'ur' ? 'ur-PK' : 'en-US';

  appState.recognition.onstart = () => {
    appState.isListening = true;
    middleCard.classList.add('listening');
    middleTitle.textContent = audioCtrl.currentLang === 'ur' ? "سن رہا ہوں..." : "LISTENING...";
    if (navigator.vibrate) navigator.vibrate(60);
  };

  appState.recognition.onresult = async (event) => {
    const transcript = event.results[0][0].transcript.trim();
    stopListening();
    console.log("[STT Heard]:", transcript);

    // Multimodal Query to Groq Vision
    audioCtrl.speak(audioCtrl.currentLang === 'ur' ? "منظر کا جائزہ لیا جا رہا ہے..." : "Checking the scene for you...", true);

    hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
    const frameSnapshot = hiddenCanvas.toDataURL('image/jpeg', 0.85);

    try {
      const res = await fetch('/api/chat/multimodal', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: transcript,
          image_b64: frameSnapshot,
          lang: audioCtrl.currentLang
        })
      });
      const data = await res.json();
      audioCtrl.speak(data.reply, true);
    } catch (e) {
      audioCtrl.speak(audioCtrl.currentLang === 'ur' ? "سروس سے رابطہ نہیں ہو سکا۔ راستہ صاف ہے۔" : "Could not connect to vision assistant. Path is clear.", true);
    }
  };

  appState.recognition.onerror = () => stopListening();
  appState.recognition.onend = () => stopListening();
}

function startListening() {
  if (appState.recognition && !appState.isListening) {
    try {
      appState.recognition.lang = audioCtrl.currentLang === 'ur' ? 'ur-PK' : 'en-US';
      appState.recognition.start();
    } catch (e) {
      console.warn("Recognition error:", e);
    }
  }
}

function stopListening() {
  appState.isListening = false;
  middleCard.classList.remove('listening');
  middleTitle.textContent = STRINGS[audioCtrl.currentLang].middle_title;
}

// ============================================================================
// 10. SYSTEM BOOTSTRAP
// ============================================================================
window.addEventListener('DOMContentLoaded', () => {
  initCamera();
  initBackendConnection();
  initSpeechRecognition();
});
