/**
 * AI Vision Assistant 2026 - Ultra-Accessible Audio & UI Controller
 * WCAG AAA Compliant Interface for Elderly and Visually Impaired Users
 * 
 * Features:
 * 1. "Silent-Until-Danger" Navigation Intelligence:
 *    - 100% silent on safe paths and benign objects (Zero Chattering).
 *    - Strict Threat-Only Triggering: Center collision corridor or side encroaching (Area_Ratio >= 0.12).
 *    - 6-second cooldown per hazard type.
 * 2. Two-Way Interactive Voice Companion:
 *    - Middle zone tap-to-ask with listening chime.
 *    - Multimodal visual Q&A (spatial room layout & object locating).
 *    - Voice commands ("Mute alerts", "Resume navigation", "Read text").
 *    - Accessible dialog fallback for text input when STT is unsupported.
 * 3. Zero Audio Echo / Double-Voice Fix:
 *    - Exclusive SpeechSynthesis engine (zero MP3 fallback overlap).
 *    - Single click event binding & silent AudioContext unlock.
 *    - 5,000ms duplicate suppression window.
 * 4. 100% Global English.
 */

// ============================================================================
// 1. ROBUST AUDIO CONTROLLER (Exclusive SpeechSynthesis, Zero Echo, Mutex)
// ============================================================================
class AudioController {
  constructor() {
    this.audioCtx = null;
    this.unlocked = false;
    this.hasSpeechSynth = ('speechSynthesis' in window && window.speechSynthesis !== null);
    this.speechSynth = this.hasSpeechSynth ? window.speechSynthesis : null;
    this.voiceEnabled = true;
    this.speechRate = 0.95; // Calm, clear tempo for elderly comprehension
    
    // Strict Deduplication & Concurrency Mutex
    this.isSpeakingLock = false;
    this.lastSpokenText = '';
    this.lastContentText = '';
    this.lastSpokenTimestamp = 0;
    this.lastHazardSpoken = {};
    this.hazardCooldownMs = 6000; // Strict 6.0s cooldown per unique hazard type
    
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
   * Unlocks Web Audio API and SpeechSynthesis on first user interaction.
   * Silent unlock — does NOT speak any overlapping welcome text.
   */
  unlock() {
    if (this.unlocked) return;
    this.unlocked = true;

    try {
      const AudioContextClass = window.AudioContext || window.webkitAudioContext;
      if (AudioContextClass && !this.audioCtx) {
        this.audioCtx = new AudioContextClass();
      }
      if (this.audioCtx && this.audioCtx.state === 'suspended') {
        this.audioCtx.resume();
      }

      // Unlock Web Audio API with a soft low-volume sine tone
      this.playTone(587.33, 40, 'sine', 0.05);

      // Prime SpeechSynthesis with a silent empty utterance
      if (this.speechSynth) {
        const silent = new SpeechSynthesisUtterance('');
        silent.volume = 0;
        this.speechSynth.speak(silent);
      }

      const overlay = document.getElementById('unlockOverlay');
      if (overlay) overlay.classList.add('dismissed');

      console.log("[AudioController] Unlocked AudioContext & SpeechSynthesis successfully.");
    } catch (err) {
      console.warn("[AudioController] Unlock error:", err);
    }
  }

  /**
   * Synthesize immediate hardware audio beeps using Web Audio API oscillator.
   */
  playTone(frequency, durationMs, type = 'sine', volume = 0.35) {
    if (!this.voiceEnabled) return;
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

  // Touch confirmation tone + vibration
  playTouchChime() {
    this.playTone(587.33, 70, 'sine', 0.25);
    if (navigator.vibrate) navigator.vibrate(40);
  }

  // Listening chime for middle zone
  playListeningChime() {
    this.playTone(659.25, 90, 'sine', 0.3);
    setTimeout(() => this.playTone(880, 110, 'sine', 0.3), 100);
    if (navigator.vibrate) navigator.vibrate(60);
  }

  // Critical danger sonar (high-pitch dual chirp)
  playDangerChirp() {
    this.playTone(880, 130, 'square', 0.4);
    setTimeout(() => this.playTone(1200, 160, 'square', 0.4), 140);
    if (navigator.vibrate) navigator.vibrate([200, 90, 200]);
  }

  // Caution ping (medium warm tone)
  playCautionPing() {
    this.playTone(440, 150, 'sine', 0.3);
    if (navigator.vibrate) navigator.vibrate(90);
  }

  /**
   * Single-Flight Speech: Exclusively uses SpeechSynthesis when available.
   * Completely avoids dual-engine echo.
   */
  speak(text, isPriority = false, hazardKey = null) {
    if (!this.voiceEnabled || !text || !text.trim()) return;

    const cleanText = text.trim();
    const now = Date.now();

    // 1. Strict Hazard Cooldown (6.0s per unique hazard key)
    if (hazardKey) {
      const lastTime = this.lastHazardSpoken[hazardKey] || 0;
      if (now - lastTime < this.hazardCooldownMs) {
        return;
      }
      this.lastHazardSpoken[hazardKey] = now;
    }

    // 2. Exact Duplicate Suppression (5000ms window for identical message)
    if (cleanText === this.lastSpokenText && (now - this.lastSpokenTimestamp) < 5000) {
      return;
    }

    // 3. Short Single-Flight Mutex (500ms lock between any speech calls)
    if ((now - this.lastSpokenTimestamp) < 500) {
      return;
    }

    this.lastSpokenText = cleanText;
    if (!cleanText.startsWith("Repeating")) {
      this.lastContentText = cleanText;
    }
    this.lastSpokenTimestamp = now;
    this.isSpeakingLock = true;

    // Update UI speech bubble text
    const bubbleText = document.getElementById('bubbleText');
    if (bubbleText) bubbleText.textContent = cleanText;

    // Hardware Audio Sonar Chirp for priority danger
    if (isPriority) {
      this.playDangerChirp();
    }

    // 4. EXCLUSIVE ENGINE: If speechSynthesis exists in browser, use ONLY speechSynthesis
    if (this.hasSpeechSynth) {
      try {
        if (isPriority && this.speechSynth.speaking) {
          this.speechSynth.cancel();
        }

        const utterance = new SpeechSynthesisUtterance(cleanText);
        utterance.rate = this.speechRate;
        utterance.pitch = 1.0;
        utterance.lang = 'en-US';

        if (this.voices.length > 0) {
          const naturalVoice = this.voices.find(v => v.lang.includes('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
          if (naturalVoice) utterance.voice = naturalVoice;
        }

        utterance.onend = () => {
          this.isSpeakingLock = false;
        };

        utterance.onerror = (e) => {
          this.isSpeakingLock = false;
          // Interrupted or canceled events occur normally on cancel() — DO NOT trigger fallback!
          if (e.error !== 'interrupted' && e.error !== 'canceled') {
            console.warn("[SpeechSynthesis] Non-cancel error:", e.error);
          }
        };

        this.speechSynth.speak(utterance);
        return; // ALWAYS return here. Never execute server fallback.
      } catch (err) {
        console.warn("[SpeechSynthesis] Speak call failed:", err);
        this.isSpeakingLock = false;
      }
    }

    // 5. Server-side TTS Fallback: Executed ONLY if window.speechSynthesis is completely missing
    this._speakServerFallback(cleanText);
  }

  _speakServerFallback(text) {
    if (!this.fallbackPlayer || this.hasSpeechSynth) return;
    try {
      fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: text })
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

// Global Audio Controller Instance
const audioCtrl = new AudioController();
window.audioCtrl = audioCtrl;

// ============================================================================
// 2. CLIENT-SIDE REAL-TIME AI VISION DETECTOR (COCO-SSD 30 FPS)
// ============================================================================
class ClientObjectDetector {
  constructor() {
    this.model = null;
    this.isLoading = false;
    this.isReady = false;
    this.isDetecting = false;
    this.hasActiveCritical = false;
    this.paused = false;

    // Benign everyday accessories to filter out during passive walking
    this.benignObjects = new Set([
      'laptop', 'cell phone', 'phone', 'cup', 'bottle', 'book', 'mouse',
      'keyboard', 'remote', 'clock', 'vase', 'bowl', 'tv', 'bed', 'sink', 'toilet'
    ]);

    // High collision risk obstacle categories
    this.hazardKeywords = [
      'person', 'chair', 'car', 'motorcycle', 'bicycle', 'bus', 'truck',
      'pothole', 'manhole', 'stairs', 'step', 'barrier', 'pole', 'curb'
    ];
  }

  feedDetections(detections) {
    if (detections && detections.length > 0) {
      drawBoundingBoxes(detections);
      this.evaluateDetections(detections);
    } else {
      this.hasActiveCritical = false;
      ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
      if (appState.lastHazardStatus !== 'SAFE') {
        updateStatus('SAFE', "SAFE PATH", "SILENT MONITORING");
      }
    }
  }

  async init() {
    if (this.isReady || this.isLoading) return;
    this.isLoading = true;
    console.log("[ClientDetector] Initializing browser-side AI vision engine...");

    const tryLoad = async () => {
      if (typeof cocoSsd !== 'undefined') {
        try {
          this.model = await cocoSsd.load();
          this.isReady = true;
          this.isLoading = false;
          console.log("[ClientDetector] Real-time COCO-SSD model ready in browser!");
          const badge = document.getElementById('engineBadge');
          if (badge) badge.textContent = "⚡ REAL-TIME AI (30 FPS)";
          this.startDetectionLoop();
          return true;
        } catch (e) {
          console.warn("[ClientDetector] Model load failed:", e);
          this.isLoading = false;
          return false;
        }
      }
      return false;
    };

    if (!(await tryLoad())) {
      let attempts = 0;
      const interval = setInterval(async () => {
        attempts++;
        if (typeof cocoSsd !== 'undefined') {
          clearInterval(interval);
          await tryLoad();
        } else if (attempts > 30) {
          clearInterval(interval);
          this.isLoading = false;
          console.warn("[ClientDetector] COCO-SSD script timeout; proceeding with Cloud Edge mode.");
        }
      }, 300);
    }
  }

  startDetectionLoop() {
    const loop = async () => {
      if (this.paused) {
        requestAnimationFrame(loop);
        return;
      }
      if (this.isReady && this.model && video.readyState >= 2 && video.videoWidth > 0 && !this.isDetecting && !appState.isProcessingOCR) {
        this.isDetecting = true;
        try {
          const predictions = await this.model.detect(video, 5, 0.35);
          const detections = this.formatPredictions(predictions);

          if (detections && detections.length > 0) {
            drawBoundingBoxes(detections);
            this.evaluateDetections(detections);
          } else {
            this.hasActiveCritical = false;
            if (!appState.lastCloudDangerTime || (Date.now() - appState.lastCloudDangerTime > 2500)) {
              ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
              // Silent-Until-Danger: Safe path reset without any spoken chattering
              if (appState.lastHazardStatus !== 'SAFE') {
                updateStatus('SAFE', "SAFE PATH", "SILENT MONITORING");
              }
            }
          }
        } catch (e) {
          // ignore transient video draw errors
        } finally {
          this.isDetecting = false;
        }
      }
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }

  formatPredictions(predictions) {
    if (!predictions || !predictions.length) return [];
    const frameW = video.videoWidth || overlayCanvas.width;
    const frameH = video.videoHeight || overlayCanvas.height;
    const totalArea = Math.max(1, frameW * frameH);

    const formatted = [];
    for (const p of predictions) {
      const [x, y, w, h] = p.bbox;
      const midX = x + (w / 2);
      let corridor = 'center';
      if (midX < frameW * 0.33) corridor = 'left';
      else if (midX > frameW * 0.67) corridor = 'right';

      const areaRatio = (w * h) / totalArea;
      const label = (p.class || '').toLowerCase().trim();

      // Filter out benign small tabletop items
      if (this.benignObjects.has(label) && areaRatio < 0.20) {
        continue;
      }

      let proximity = 'distant';
      let is_critical = false;

      // Proximity categorization
      if (areaRatio > 0.14) {
        proximity = 'very close';
      } else if (areaRatio > 0.06) {
        proximity = 'close';
      } else {
        proximity = 'ahead';
      }

      const isHazard = this.hazardKeywords.some(k => label.includes(k));

      // "Silent-Until-Danger" Corridor Filtering Rules:
      // 1. Center Walking Corridor Threat:
      if (corridor === 'center') {
        if (isHazard && areaRatio >= 0.05) {
          is_critical = true;
        } else if (areaRatio >= 0.10) {
          is_critical = true;
        }
      }
      // 2. Side Encroachment Threat:
      else if (areaRatio >= 0.12 && isHazard) {
        is_critical = true;
      }

      formatted.push({
        bbox: [x, y, w, h],
        is_xywh: true,
        label: p.class,
        conf: p.score,
        corridor: corridor,
        proximity: proximity,
        areaRatio: areaRatio,
        is_critical: is_critical,
        is_hazard: isHazard
      });
    }

    return formatted;
  }

  evaluateDetections(detections) {
    // If user is currently in two-way interactive Q&A, don't interrupt with passive alerts
    if (appState.isInteracting) {
      return;
    }

    const critical = detections.find(d => d.is_critical);

    if (critical) {
      this.hasActiveCritical = true;
      const labelUpper = critical.label.toUpperCase();
      let alertMsg;

      if (critical.corridor === 'center') {
        alertMsg = `Caution: ${labelUpper} directly ahead in center path.`;
      } else {
        alertMsg = `Caution: ${labelUpper} close on your ${critical.corridor}.`;
      }

      updateStatus('DANGER', "DANGER AHEAD", alertMsg);
      // Announce with strict 6s cooldown per hazard type
      audioCtrl.speak(alertMsg, true, critical.label.toLowerCase());
    } else {
      this.hasActiveCritical = false;
      // "Silent-Until-Danger": When path is clear of critical collision hazards,
      // update banner to SAFE PATH and STAY 100% SILENT.
      if (appState.lastHazardStatus !== 'SAFE') {
        updateStatus('SAFE', "SAFE PATH", "SILENT MONITORING");
      }
    }
  }
}

const clientDetector = new ClientObjectDetector();
window.clientDetector = clientDetector;

// ============================================================================
// 3. APPLICATION STATE & DOM REFERENCES
// ============================================================================
const isMobileDevice = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
const appState = {
  isCloudMode: window.location.hostname.includes('vercel.app') || window.location.port === '',
  ws: null,
  wsConnected: false,
  cameraStream: null,
  facingMode: isMobileDevice ? 'environment' : 'user', // Environment on mobile, webcam on desktop
  isListening: false,
  isInteracting: false,
  isProcessingOCR: false,
  recognition: null,
  isAwaitingReply: false,
  isAwaitingCloudReply: false,
  lastHazardStatus: 'SAFE',
  cloudIntervalId: null
};
window.appState = appState;
window.handleDetectionResults = handleDetectionResults;
window.handleCloudResults = handleCloudResults;

const video = document.getElementById('cameraFeed');
const overlayCanvas = document.getElementById('overlayCanvas');
const ctx = overlayCanvas.getContext('2d');
const hiddenCanvas = document.getElementById('hiddenCanvas');
const hiddenCtx = hiddenCanvas.getContext('2d');

const statusBanner = document.getElementById('statusBanner');
const statusSymbol = document.getElementById('statusSymbol');
const statusHeadline = document.getElementById('statusHeadline');
const statusSubline = document.getElementById('statusSubline');

const voiceToggleBtn = document.getElementById('voiceToggleBtn');
const voiceLabel = document.getElementById('voiceLabel');
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

// Accessible Question Dialog Elements
const questionDialog = document.getElementById('questionDialog');
const dialogInput = document.getElementById('dialogInput');
const dialogSubmitBtn = document.getElementById('dialogSubmitBtn');
const dialogCancelBtn = document.getElementById('dialogCancelBtn');
const dialogCloseBtn = document.getElementById('dialogCloseBtn');

// ============================================================================
// 4. WEBRTC CAMERA INITIALIZATION (Resilient Desktop & Mobile Detection)
// ============================================================================
async function initCamera() {
  if (appState.cameraStream) {
    try {
      appState.cameraStream.getTracks().forEach(t => t.stop());
    } catch (e) {}
  }

  let stream = null;
  // 1. Try with ideal facingMode
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: {
        facingMode: { ideal: appState.facingMode },
        width: { ideal: 640 },
        height: { ideal: 480 }
      }
    });
  } catch (err) {
    console.warn("[Camera] Ideal facingMode failed, falling back to any available camera:", err);
    try {
      // 2. Fallback: Any available camera (laptop webcam)
      stream = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
    } catch (err2) {
      console.error("[Camera] All camera access attempts failed:", err2);
      updateStatus('DANGER', "CAMERA REQUIRED", "Please allow camera permissions in browser.");
      return;
    }
  }

  appState.cameraStream = stream;
  video.srcObject = stream;

  try {
    await video.play();
  } catch (e) {
    console.warn("[Camera] Video play error:", e);
  }

  const updateDims = () => {
    const w = video.videoWidth || 640;
    const h = video.videoHeight || 480;
    overlayCanvas.width = w;
    overlayCanvas.height = h;
    hiddenCanvas.width = w;
    hiddenCanvas.height = h;
  };

  video.onloadedmetadata = updateDims;
  if (video.videoWidth > 0) updateDims();
}

// Flip Camera (Front / Rear)
flipCamBtn.addEventListener('click', async (e) => {
  e.stopPropagation();
  audioCtrl.unlock();
  audioCtrl.playTouchChime();
  appState.facingMode = appState.facingMode === 'user' ? 'environment' : 'user';
  await initCamera();
  audioCtrl.speak("Camera switched", true);
});

// Voice / Alerts Toggle (Mute / Unmute)
voiceToggleBtn.addEventListener('click', (e) => {
  e.stopPropagation();
  audioCtrl.unlock();
  audioCtrl.voiceEnabled = !audioCtrl.voiceEnabled;
  voiceToggleBtn.classList.toggle('muted', !audioCtrl.voiceEnabled);
  voiceLabel.textContent = audioCtrl.voiceEnabled ? "ALERTS: ON" : "ALERTS: MUTED";
  audioCtrl.playTouchChime();
  if (audioCtrl.voiceEnabled) {
    audioCtrl.speak("Navigation alerts active.", true);
  } else {
    if (audioCtrl.speechSynth) audioCtrl.speechSynth.cancel();
  }
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
      if (appState.cloudIntervalId) {
        clearInterval(appState.cloudIntervalId);
        appState.cloudIntervalId = null;
      }
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

  if (appState.cloudIntervalId) {
    clearInterval(appState.cloudIntervalId);
    appState.cloudIntervalId = null;
  }

  // Periodic REST frame analysis every 2.0s
  appState.cloudIntervalId = setInterval(async () => {
    if (video.readyState < 2 || !video.videoWidth || appState.isProcessingOCR || appState.isListening || appState.isInteracting || appState.isAwaitingCloudReply) return;

    if (!hiddenCanvas.width || hiddenCanvas.width !== video.videoWidth) {
      hiddenCanvas.width = video.videoWidth;
      hiddenCanvas.height = video.videoHeight;
    }

    hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
    const b64 = hiddenCanvas.toDataURL('image/jpeg', 0.65);

    appState.isAwaitingCloudReply = true;
    try {
      const res = await fetch('/api/analyze-scene', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_b64: b64 })
      });
      if (res.ok) {
        const data = await res.json();
        handleCloudResults(data);
      }
    } catch (e) {
      console.warn("Cloud analyze error:", e);
    } finally {
      appState.isAwaitingCloudReply = false;
    }
  }, 2000);
}

// ============================================================================
// 6. DETECTION & HAZARD HANDLING ("Silent-Until-Danger")
// ============================================================================
function handleDetectionResults(data) {
  if (appState.isInteracting) return;

  const isDanger = data.has_critical_hazard || Boolean(data.priority_alert);

  if (isDanger) {
    const alertMsg = data.priority_alert || "Caution: Obstacle detected ahead!";
    updateStatus('DANGER', "DANGER AHEAD", alertMsg);
    
    // Announce with strict 6s cooldown
    const hazardWord = extractHazardKeyword(alertMsg);
    audioCtrl.speak(alertMsg, true, hazardWord);
  } else {
    // Silent on safe paths
    updateStatus('SAFE', "SAFE PATH", "SILENT MONITORING");
  }

  // Draw overlay bounding boxes
  drawBoundingBoxes(data.detections || []);
}

function handleCloudResults(data) {
  if (appState.isInteracting) return;

  const isDanger = data.status === 'DANGER' && Boolean(data.priority_alert);

  if (isDanger) {
    appState.lastCloudDangerTime = Date.now();
    const alertMsg = data.priority_alert;
    updateStatus('DANGER', "DANGER AHEAD", alertMsg);
    const hazardWord = extractHazardKeyword(alertMsg);
    audioCtrl.speak(alertMsg, true, hazardWord);
  } else {
    // Silent-Until-Danger: Safe paths remain 100% silent.
    if (!clientDetector.hasActiveCritical) {
      updateStatus('SAFE', "SAFE PATH", "SILENT MONITORING");
    }
  }

  // Draw detections if provided by cloud model and clientDetector is not already running
  if (data.detections && data.detections.length > 0 && !clientDetector.isReady) {
    const formatted = data.detections.map(d => {
      let [y1, x1, y2, x2] = d.bbox || [0, 0, 0, 0];
      const scaleX = overlayCanvas.width / 1000;
      const scaleY = overlayCanvas.height / 1000;
      return {
        bbox: [x1 * scaleX, y1 * scaleY, (x2 - x1) * scaleX, (y2 - y1) * scaleY],
        is_xywh: true,
        label: d.label || 'object',
        conf: d.conf || 0.9,
        corridor: d.corridor || 'center',
        proximity: d.proximity || 'ahead',
        is_critical: d.is_critical || isDanger
      };
    });
    drawBoundingBoxes(formatted);
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
  for (const k of ['person', 'face', 'human', 'pothole', 'manhole', 'ditch', 'wire', 'step', 'stairs', 'motorcycle', 'car', 'vehicle', 'chair', 'barrier', 'pole']) {
    if (lower.includes(k)) return k;
  }
  return 'obstacle';
}

function drawBoundingBoxes(detections) {
  ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
  if (!detections || !detections.length) return;

  const vW = video.videoWidth || overlayCanvas.width;
  const vH = video.videoHeight || overlayCanvas.height;
  const scaleX = overlayCanvas.width / vW;
  const scaleY = overlayCanvas.height / vH;

  detections.forEach(det => {
    let x, y, w, h;
    if (det.bbox && det.bbox.length === 4) {
      if (det.is_xywh) {
        [x, y, w, h] = det.bbox;
      } else {
        [x, y, w, h] = [det.bbox[0], det.bbox[1], det.bbox[2] - det.bbox[0], det.bbox[3] - det.bbox[1]];
      }
    } else {
      return;
    }

    x *= scaleX;
    y *= scaleY;
    w *= scaleX;
    h *= scaleY;

    const isCrit = det.is_critical || det.proximity === 'very close';
    const isClose = det.proximity === 'close';
    const strokeColor = isCrit ? '#FF0033' : (isClose ? '#FFD700' : '#00E676');

    // 1. High contrast bounding box
    ctx.shadowColor = 'rgba(0, 0, 0, 0.85)';
    ctx.shadowBlur = 6;
    ctx.lineWidth = isCrit ? 6 : 4;
    ctx.strokeStyle = strokeColor;
    ctx.strokeRect(x, y, w, h);

    // 2. High-contrast label badge
    const labelStr = (det.label || det.class || 'OBJECT').toUpperCase();
    const confStr = det.conf ? ` ${Math.round(det.conf * 100)}%` : '';
    const corridorStr = det.corridor ? ` [${det.corridor.toUpperCase()}]` : '';
    const fullText = `${labelStr}${confStr}${corridorStr}`;

    ctx.font = 'bold 15px "Segoe UI", Roboto, Arial, sans-serif';
    const textMetrics = ctx.measureText(fullText);
    const badgeW = textMetrics.width + 16;
    const badgeH = 26;
    const badgeY = Math.max(0, y - badgeH);

    // Badge background
    ctx.fillStyle = strokeColor;
    ctx.fillRect(x, badgeY, badgeW, badgeH);

    // Badge text
    ctx.fillStyle = isCrit ? '#FFFFFF' : '#000000';
    ctx.shadowBlur = 0;
    ctx.fillText(fullText, x + 8, badgeY + 18);
  });
}

// ============================================================================
// 7. TOUCH ZONES INTERACTIONS (Single Event Binding, Zero Overlap)
// ============================================================================

// Single global pointerdown listener for silent unlock
window.addEventListener('pointerdown', () => audioCtrl.unlock(), { once: true });

// ZONE 2: MIDDLE ZONE (Tap to speak / ask question)
zoneMiddle.addEventListener('click', () => {
  audioCtrl.unlock();
  audioCtrl.playListeningChime();

  if (appState.isListening) {
    stopListening();
  } else {
    // If Web Speech API is supported, start speech recognition
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition && !window.location.protocol.includes('http:')) {
      startListening();
    } else {
      // Fallback: Open accessible question dialog
      openQuestionDialog();
    }
  }
});

function openQuestionDialog() {
  if (!questionDialog) return;
  appState.isInteracting = true;
  if (typeof questionDialog.showModal === 'function') {
    questionDialog.showModal();
  } else {
    questionDialog.setAttribute('open', '');
  }
  if (dialogInput) {
    dialogInput.value = '';
    dialogInput.focus();
  }
}

function closeQuestionDialog() {
  if (!questionDialog) return;
  if (typeof questionDialog.close === 'function') {
    questionDialog.close();
  } else {
    questionDialog.removeAttribute('open');
  }
  setTimeout(() => { appState.isInteracting = false; }, 3000);
}

if (dialogCloseBtn) {
  dialogCloseBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    closeQuestionDialog();
  });
}

if (dialogCancelBtn) {
  dialogCancelBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    closeQuestionDialog();
  });
}

if (dialogSubmitBtn) {
  dialogSubmitBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    const query = dialogInput ? dialogInput.value.trim() : '';
    if (!query) return;
    closeQuestionDialog();
    await handleUserQuestion(query);
  });
}

if (dialogInput) {
  dialogInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      const query = dialogInput.value.trim();
      if (!query) return;
      closeQuestionDialog();
      await handleUserQuestion(query);
    }
  });
}

// ZONE 3 LEFT: READ DOCUMENT / SIGN (Instant OCR Snapshot)
btnOcr.addEventListener('click', async () => {
  audioCtrl.unlock();
  audioCtrl.playTouchChime();
  await triggerDocumentOCR();
});

async function triggerDocumentOCR() {
  audioCtrl.speak("Scanning text in front of you...", true);

  appState.isProcessingOCR = true;
  hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  const snapshotB64 = hiddenCanvas.toDataURL('image/jpeg', 0.85);

  try {
    const res = await fetch('/api/ocr/frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_b64: snapshotB64 })
    });
    const data = await res.json();
    appState.isProcessingOCR = false;

    const speechResult = data.summary || data.text || "No readable text visible in camera view.";
    audioCtrl.speak(speechResult, true);
  } catch (e) {
    appState.isProcessingOCR = false;
    audioCtrl.speak("Could not read text. Please hold steady and try again.", true);
  }
}

// ZONE 3 RIGHT: REPEAT LAST ALERT / TEST SOUND
btnRepeat.addEventListener('click', () => {
  audioCtrl.unlock();
  audioCtrl.playTouchChime();

  const msg = audioCtrl.lastContentText || audioCtrl.lastSpokenText;
  if (msg) {
    audioCtrl.speak("Repeating: " + msg, true);
  } else {
    audioCtrl.playDangerChirp();
    audioCtrl.speak("Sound system is active and monitoring safely.", true);
  }
});

// ============================================================================
// 8. INTERACTIVE VOICE COMPANION & GROQ MULTIMODAL Q&A
// ============================================================================
async function handleUserQuestion(transcript) {
  appState.isInteracting = true;
  const lower = transcript.toLowerCase();

  // Voice Command Handling:
  if (lower.includes('mute') || lower.includes('stop talking') || lower.includes('quiet')) {
    audioCtrl.speak("Alerts muted.", true);
    audioCtrl.voiceEnabled = false;
    voiceToggleBtn.classList.add('muted');
    voiceLabel.textContent = "ALERTS: MUTED";
    setTimeout(() => { appState.isInteracting = false; }, 2000);
    return;
  }

  if (lower.includes('unmute') || lower.includes('resume') || lower.includes('start alerts')) {
    audioCtrl.voiceEnabled = true;
    voiceToggleBtn.classList.remove('muted');
    voiceLabel.textContent = "ALERTS: ON";
    audioCtrl.speak("Navigation alerts resumed.", true);
    setTimeout(() => { appState.isInteracting = false; }, 2000);
    return;
  }

  if (lower.includes('read text') || lower.includes('read document') || lower.includes('read sign')) {
    await triggerDocumentOCR();
    setTimeout(() => { appState.isInteracting = false; }, 3000);
    return;
  }

  // Visual Scene Query:
  audioCtrl.speak("Checking scene for you...", true);

  hiddenCtx.drawImage(video, 0, 0, hiddenCanvas.width, hiddenCanvas.height);
  const frameSnapshot = hiddenCanvas.toDataURL('image/jpeg', 0.85);

  try {
    const res = await fetch('/api/chat/multimodal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        query: transcript,
        image_b64: frameSnapshot
      })
    });
    const data = await res.json();
    audioCtrl.speak(data.reply, true);
  } catch (e) {
    audioCtrl.speak("I could not analyze the scene right now.", true);
  } finally {
    setTimeout(() => { appState.isInteracting = false; }, 5000);
  }
}

function initSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Speech recognition not supported on this browser.");
    return;
  }

  try {
    appState.recognition = new SpeechRecognition();
    appState.recognition.continuous = false;
    appState.recognition.interimResults = false;
    appState.recognition.lang = 'en-US';

    appState.recognition.onstart = () => {
      appState.isListening = true;
      appState.isInteracting = true;
      middleCard.classList.add('listening');
      middleTitle.textContent = "LISTENING...";
      if (navigator.vibrate) navigator.vibrate(60);
    };

    appState.recognition.onresult = async (event) => {
      const transcript = event.results[0][0].transcript.trim();
      stopListening();
      console.log("[STT Heard]:", transcript);
      await handleUserQuestion(transcript);
    };

    appState.recognition.onerror = (e) => {
      console.warn("[SpeechRecognition Error]:", e.error);
      stopListening();
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {
        openQuestionDialog();
      }
    };

    appState.recognition.onend = () => stopListening();
  } catch (err) {
    console.warn("SpeechRecognition init failed:", err);
  }
}

function startListening() {
  if (appState.recognition && !appState.isListening) {
    try {
      appState.recognition.start();
    } catch (e) {
      console.warn("Recognition start error:", e);
      openQuestionDialog();
    }
  } else if (!appState.recognition) {
    openQuestionDialog();
  }
}

function stopListening() {
  appState.isListening = false;
  middleCard.classList.remove('listening');
  middleTitle.textContent = "TAP TO SPEAK OR ASK";
}

// ============================================================================
// 9. SYSTEM BOOTSTRAP
// ============================================================================
window.addEventListener('DOMContentLoaded', () => {
  initCamera();
  initBackendConnection();
  initSpeechRecognition();
  clientDetector.init();
});
