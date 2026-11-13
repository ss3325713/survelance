/**
 * Wheat Watch Dashboard Client Logic.
 * Event-based surveillance dashboard with Night Mode, Event Deduplication Timeline,
 * Storage Retention, Force Push Alerts, and Real-time Telemetry.
 */

let currentToken = localStorage.getItem('wheat_watch_token') || '';
let currentCsrfToken = localStorage.getItem('wheat_watch_csrf') || '';
let isMonitoring = true;
let currentFilter = 'all';
let currentViewMode = localStorage.getItem('wheat_watch_view_mode') || 'timeline'; // 'timeline' or 'gallery'
let currentSelectedEventId = null;
let latestEventCache = null;
let latestDiagnosticsData = null;

// Force Push Messages State
let pushEnabled = localStorage.getItem('wheat_watch_push_enabled') !== 'false';
let pushDesktop = localStorage.getItem('wheat_watch_push_desktop') !== 'false';
let pushAudio = localStorage.getItem('wheat_watch_push_audio') !== 'false';
let pushEventSource = null;

// DOM Elements: Top Bar & Status
const navSurveillanceBtn = document.getElementById('navSurveillanceBtn');
const navSurveillanceText = document.getElementById('navSurveillanceText');
const btnNightDay = document.getElementById('btnNightDay');
const btnNightNight = document.getElementById('btnNightNight');
const btnNightAuto = document.getElementById('btnNightAuto');
const nightActiveIndicator = document.getElementById('nightActiveIndicator');
const uptimeText = document.getElementById('uptimeText');
const cameraPill = document.getElementById('cameraPill');
const cameraPillText = document.getElementById('cameraPillText');
const micPill = document.getElementById('micPill');
const micPillText = document.getElementById('micPillText');
const dbPill = document.getElementById('dbPill');
const dbStatusText = document.getElementById('dbStatusText');
const sleepPill = document.getElementById('sleepPill');

const cameraDisconnectBanner = document.getElementById('cameraDisconnectBanner');
const bannerRetryCamBtn = document.getElementById('bannerRetryCamBtn');

const togglePushNavBtn = document.getElementById('togglePushNavBtn');
const pushNavLabel = document.getElementById('pushNavLabel');
const testPushBtn = document.getElementById('testPushBtn');
const cfgTestPushBtn = document.getElementById('cfgTestPushBtn');
const diagnosticsBtn = document.getElementById('diagnosticsBtn');

const laptopLanIp = document.getElementById('laptopLanIp');
const phoneUrlText = document.getElementById('phoneUrlText');
const phoneUrlLink = document.getElementById('phoneUrlLink');

const telemetryFps = document.getElementById('telemetryFps');
const telemetryProcFps = document.getElementById('telemetryProcFps');
const telemetryLatency = document.getElementById('telemetryLatency');

const toggleMonitoringBtn = document.getElementById('toggleMonitoringBtn');
const testAlarmBtn = document.getElementById('testAlarmBtn');
const testCamBtn = document.getElementById('testCamBtn');
const snapshotBtn = document.getElementById('snapshotBtn');

// Diagnostics & Metrics Cards
const todayEventsBadge = document.getElementById('todayEventsBadge');
const todayEventsCount = document.getElementById('todayEventsCount');
const lastDetectionTimeText = document.getElementById('lastDetectionTimeText');

const storagePercentBadge = document.getElementById('storagePercentBadge');
const storageUsedMbText = document.getElementById('storageUsedMbText');
const storageBar = document.getElementById('storageBar');
const storageImageCount = document.getElementById('storageImageCount');
const purgeStorageBtn = document.getElementById('purgeStorageBtn');

const metricCpu = document.getElementById('metricCpu');
const metricCpuBar = document.getElementById('metricCpuBar');
const metricCpuBadge = document.getElementById('metricCpuBadge');
const throttleStatus = document.getElementById('throttleStatus');

const metricRam = document.getElementById('metricRam');
const metricRamBar = document.getElementById('metricRamBar');
const metricRamMb = document.getElementById('metricRamMb');

// Flashlight & Audio Diagnostics
const flashlightStatusPill = document.getElementById('flashlightStatusPill');
const btnFlashlightAuto = document.getElementById('btnFlashlightAuto');
const btnFlashlightManual = document.getElementById('btnFlashlightManual');
const btnFlashlightOff = document.getElementById('btnFlashlightOff');
const flashlightTriggerText = document.getElementById('flashlightTriggerText');
const flashlightRequestedText = document.getElementById('flashlightRequestedText');
const flashlightLightingText = document.getElementById('flashlightLightingText');
const flashlightMotionText = document.getElementById('flashlightMotionText');
const flashlightCountdownText = document.getElementById('flashlightCountdownText');
const flashlightCountdownFill = document.getElementById('flashlightCountdownFill');
const flashlightResultText = document.getElementById('flashlightResultText');
const toggleFlashlightLogBtn = document.getElementById('toggleFlashlightLogBtn');
const flashlightLogContainer = document.getElementById('flashlightLogContainer');
const flashlightLogTableBody = document.getElementById('flashlightLogTableBody');

// Audio elements
const audioStateBadge = document.getElementById('audioStateBadge');
const audioStatusText = document.getElementById('audioStatusText');
const audioMeterFill = document.getElementById('audioMeterFill');
const audioRmsText = document.getElementById('audioRmsText');
const audioNoiseFloorText = document.getElementById('audioNoiseFloorText');
const audioSnrText = document.getElementById('audioSnrText');
const audioFormatText = document.getElementById('audioFormatText');
const audioStreamUrlText = document.getElementById('audioStreamUrlText');
const testAudioBtn = document.getElementById('testAudioBtn');

const metricAudioBadge = document.getElementById('metricAudioBadge');
const metricAudioVal = document.getElementById('metricAudioVal');
const metricAudioBar = document.getElementById('metricAudioBar');
const metricAudioSub = document.getElementById('metricAudioSub');

// Latest Event Showcase
const latestEventTitle = document.getElementById('latestEventTitle');
const latestEventTimeBadge = document.getElementById('latestEventTimeBadge');
const latestEventThumbBox = document.getElementById('latestEventThumbBox');
const latestEventImg = document.getElementById('latestEventImg');
const latestEventTagBadge = document.getElementById('latestEventTagBadge');
const latestEventCategoryBadge = document.getElementById('latestEventCategoryBadge');
const latestEventNightBadge = document.getElementById('latestEventNightBadge');
const latestEventLabelText = document.getElementById('latestEventLabelText');
const latestEventConfidence = document.getElementById('latestEventConfidence');
const latestEventAgeText = document.getElementById('latestEventAgeText');
const viewLatestEventBtn = document.getElementById('viewLatestEventBtn');

// View Mode Tabs & Category Filters
const viewTabTimeline = document.getElementById('viewTabTimeline');
const viewTabGallery = document.getElementById('viewTabGallery');
const eventsList = document.getElementById('eventsList');
const pinStatusText = document.getElementById('pinStatusText');

const countAll = document.getElementById('countAll');
const countPerson = document.getElementById('countPerson');
const countBird = document.getElementById('countBird');
const countAnimal = document.getElementById('countAnimal');
const countMonkey = document.getElementById('countMonkey');
const countMotion = document.getElementById('countMotion');

// Modals
const qrModal = document.getElementById('qrModal');
const pinModal = document.getElementById('pinModal');
const settingsModal = document.getElementById('settingsModal');
const eventDetailModal = document.getElementById('eventDetailModal');
const diagnosticsModal = document.getElementById('diagnosticsModal');

// Helper: Authenticated Fetch with CSRF support
async function apiFetch(url, options = {}) {
  options.headers = options.headers || {};
  if (currentToken) {
    options.headers['X-Dashboard-Token'] = currentToken;
  }
  if (currentCsrfToken && options.method && options.method !== 'GET') {
    options.headers['X-CSRF-Token'] = currentCsrfToken;
  }
  const res = await fetch(url, options);
  if (res.status === 401) {
    currentToken = '';
    localStorage.removeItem('wheat_watch_token');
    if (pinStatusText) pinStatusText.textContent = '(Locked)';
    openModal(pinModal);
  }
  return res;
}

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// Relative Time Formatter
function formatRelativeTime(timestamp) {
  if (!timestamp) return 'None';
  try {
    const t = typeof timestamp === 'number' ? timestamp * 1000 : new Date(timestamp).getTime();
    const diffSec = Math.floor((Date.now() - t) / 1000);
    if (diffSec < 5) return 'Just now';
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return new Date(t).toLocaleDateString();
  } catch (e) {
    return 'Recently';
  }
}

// Status Poller
async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Surveillance Monitoring Mode
    isMonitoring = data.monitoring.is_monitoring;
    if (navSurveillanceBtn && navSurveillanceText) {
      if (isMonitoring) {
        navSurveillanceBtn.className = 'btn btn-surveillance-toggle active';
        navSurveillanceText.textContent = 'SURVEILLANCE: ON';
      } else {
        navSurveillanceBtn.className = 'btn btn-surveillance-toggle inactive';
        navSurveillanceText.textContent = 'SURVEILLANCE: OFF';
      }
    }
    if (toggleMonitoringBtn) {
      if (isMonitoring) {
        toggleMonitoringBtn.className = 'btn btn-danger';
        toggleMonitoringBtn.textContent = '🛑 Stop Surveillance';
      } else {
        toggleMonitoringBtn.className = 'btn btn-primary';
        toggleMonitoringBtn.textContent = '▶️ Start Surveillance';
      }
    }

    // 2. Monitoring Uptime
    if (uptimeText) {
      uptimeText.textContent = data.monitoring.monitoring_uptime_str || '00:00:00';
    }

    // 3. Night Mode Status
    const nm = data.night_mode || {};
    updateNightModeButtons(nm.mode || 'auto');
    if (nightActiveIndicator) {
      const isNight = nm.is_night || (nm.active_mode === 'night');
      const luxVal = nm.measured_brightness !== undefined ? `${Math.round(nm.measured_brightness)} lux` : '';
      if (isNight) {
        nightActiveIndicator.className = 'night-indicator-badge night-active';
        nightActiveIndicator.textContent = `🌙 Night (${luxVal})`;
      } else {
        nightActiveIndicator.className = 'night-indicator-badge';
        nightActiveIndicator.textContent = `☀️ Day (${luxVal})`;
      }
    }

    // 4. Camera Status & Disconnection Warning
    const cam = data.camera;
    updatePhoneStreamLink(cam.stream_url);
    const dcBannerText = document.getElementById('cameraDisconnectText');
    const isReconfig = (cam.state === 'RECONFIGURING');

    // Prevent repeated commands while reconfiguring
    document.querySelectorAll('.btn-toggle-option, #resetControlsBtn').forEach(b => {
      b.disabled = isReconfig;
      if (isReconfig) b.classList.add('btn-disabled');
      else b.classList.remove('btn-disabled');
    });

    if (cam.state === 'ONLINE' || cam.state === 'CONNECTED') {
      cameraPill.className = 'status-pill pill-active';
      cameraPillText.textContent = `CAM: ONLINE (${cam.fps} FPS)`;
      if (cameraDisconnectBanner) cameraDisconnectBanner.style.display = 'none';
    } else if (cam.state === 'RECONFIGURING') {
      cameraPill.className = 'status-pill pill-warning';
      cameraPillText.textContent = `CAM: RECONFIGURING...`;
      if (cameraDisconnectBanner) cameraDisconnectBanner.style.display = 'none';
    } else if (cam.state === 'RECONNECTING') {
      cameraPill.className = 'status-pill pill-warning';
      cameraPillText.textContent = `CAM: RECONNECTING (Try #${cam.reconnect_attempts})`;
      if (cameraDisconnectBanner) {
        cameraDisconnectBanner.style.display = 'block';
        if (dcBannerText) {
          dcBannerText.innerHTML = `<strong>CAMERA RECONNECTING:</strong> Stream lost (${cam.disconnect_reason || 'reconnecting'}). Attempt #${cam.reconnect_attempts}...`;
        }
      }
    } else if (cam.state === 'OFFLINE' || cam.state === 'DISCONNECTED') {
      cameraPill.className = 'status-pill pill-danger';
      cameraPillText.textContent = `CAM: OFFLINE`;
      if (cameraDisconnectBanner) {
        cameraDisconnectBanner.style.display = 'block';
        if (dcBannerText) {
          dcBannerText.innerHTML = `<strong>CAMERA OFFLINE:</strong> IP camera server unreachable at ${cam.stream_url}. Background recovery active.`;
        }
      }
    } else {
      cameraPill.className = 'status-pill pill-danger';
      cameraPillText.textContent = `CAM: ERROR`;
      if (cameraDisconnectBanner) {
        cameraDisconnectBanner.style.display = 'block';
        if (dcBannerText) {
          dcBannerText.innerHTML = `<strong>CAMERA ERROR:</strong> ${cam.last_error || 'Stream error occurred.'}`;
        }
      }
    }

    // 5. Telemetry
    telemetryFps.textContent = `Cam: ${cam.fps} FPS`;
    telemetryProcFps.textContent = `Proc: ${data.metrics.processing_fps} FPS`;
    telemetryLatency.textContent = `Ping: ${cam.latency_ms} ms`;

    // 6. Power
    if (data.monitoring.power_inhibited) {
      sleepPill.style.display = 'inline-flex';
    } else {
      sleepPill.style.display = 'none';
    }

    // 7. Network Banner
    const net = data.network;
    laptopLanIp.textContent = net.laptop_lan_ip;
    phoneUrlText.textContent = net.phone_access_url;
    phoneUrlLink.href = net.phone_access_url;

    // 8. Today's Incidents & Last Detection
    const todayCount = data.today_events_count !== undefined ? data.today_events_count : (data.summary.today_count || 0);
    if (todayEventsCount) todayEventsCount.textContent = todayCount;
    if (todayEventsBadge) todayEventsBadge.textContent = `${todayCount} Today`;

    if (lastDetectionTimeText) {
      if (data.monitoring.last_detection_timestamp) {
        lastDetectionTimeText.textContent = formatRelativeTime(data.monitoring.last_detection_timestamp);
      } else if (data.summary.latest_event) {
        lastDetectionTimeText.textContent = formatRelativeTime(data.summary.latest_event.timestamp);
      } else {
        lastDetectionTimeText.textContent = 'None';
      }
    }

    // 9. Storage Usage & Retention
    const st = data.storage || {};
    if (storageUsedMbText) storageUsedMbText.textContent = `${st.used_mb || 0} MB`;
    if (storagePercentBadge) storagePercentBadge.textContent = `${st.storage_percent || 0}% Used`;
    if (storageBar) storageBar.style.width = `${Math.min(100, st.storage_percent || 0)}%`;
    if (storageImageCount) storageImageCount.textContent = st.image_count || 0;

    // 10. Metrics (CPU & RAM)
    const m = data.metrics;
    metricCpu.textContent = `${m.cpu_percent}%`;
    metricCpuBar.style.width = `${Math.min(100, m.cpu_percent)}%`;
    if (m.cpu_percent >= 85) {
      metricCpuBar.style.backgroundColor = 'var(--color-danger)';
      metricCpuBadge.textContent = 'HIGH';
      metricCpuBadge.className = 'badge text-danger';
    } else {
      metricCpuBar.style.backgroundColor = 'var(--color-brand)';
      metricCpuBadge.textContent = 'Normal';
      metricCpuBadge.className = 'badge';
    }

    if (m.is_throttled) {
      throttleStatus.textContent = '⚠️ Auto-throttle: ACTIVE (Pacing)';
      throttleStatus.style.color = 'var(--color-warning)';
    } else {
      throttleStatus.textContent = 'Auto-throttle: Idle';
      throttleStatus.style.color = 'var(--text-sub)';
    }

    metricRam.textContent = `${m.ram_percent}%`;
    metricRamBar.style.width = `${m.ram_percent}%`;
    metricRamMb.textContent = `${m.ram_used_mb} MB used / ${m.ram_total_mb} MB`;

    // 11. Category Breakdown on Tabs
    const sum = data.summary;
    const counts = sum.category_counts || {};
    if (countAll) countAll.textContent = sum.total_events || 0;
    if (countPerson) countPerson.textContent = counts['Person'] || 0;
    if (countBird) countBird.textContent = counts['Bird'] || 0;
    if (countAnimal) countAnimal.textContent = (counts['Animal detected — species unconfirmed'] || 0) + (counts['Other recognized animal'] || 0);
    if (countMonkey) countMonkey.textContent = counts['Possible monkey'] || 0;
    if (countMotion) countMotion.textContent = counts['General motion'] || 0;

    // 12. Latest Event Showcase Card
    if (sum.latest_event) {
      updateLatestEventShowcase(sum.latest_event);
    }

    // 13. Flashlight & Microphone Telemetry
    const fl = data.flashlight || {};
    updateFlashlightUI(fl);

    const mic = data.microphone || {};
    updateMicrophoneUI(mic, fl);

  } catch (err) {
    console.debug('Status poll error:', err);
  }
}

// Flashlight UI Updater
function updateFlashlightUI(fl) {
  if (!fl) return;
  const mode = (fl.mode || 'auto').toLowerCase();
  if (btnFlashlightAuto) btnFlashlightAuto.classList.toggle('active', mode === 'auto');
  if (btnFlashlightManual) btnFlashlightManual.classList.toggle('active', mode === 'manual');
  if (btnFlashlightOff) btnFlashlightOff.classList.toggle('active', mode === 'off');

  if (flashlightStatusPill) {
    if (fl.is_on) {
      const trig = fl.active_trigger ? ` (${fl.active_trigger})` : '';
      flashlightStatusPill.className = 'badge';
      flashlightStatusPill.style.background = 'rgba(234, 179, 8, 0.25)';
      flashlightStatusPill.style.color = '#fbbf24';
      flashlightStatusPill.style.border = '1px solid #eab308';
      flashlightStatusPill.textContent = `💡 ${mode.toUpperCase()} [ON${trig}]`;
    } else {
      flashlightStatusPill.className = 'badge';
      flashlightStatusPill.style.background = '';
      flashlightStatusPill.style.color = '';
      flashlightStatusPill.style.border = '';
      flashlightStatusPill.textContent = `⚫ ${mode.toUpperCase()} [OFF]`;
    }
  }

  if (flashlightRequestedText) {
    flashlightRequestedText.textContent = fl.requested_state ? 'ON' : 'OFF';
  }
  if (flashlightLightingText) {
    flashlightLightingText.textContent = fl.lighting_condition || 'UNKNOWN';
  }
  if (flashlightMotionText) {
    flashlightMotionText.textContent = fl.motion_detected ? 'DETECTED' : 'CLEAR';
    flashlightMotionText.style.color = fl.motion_detected ? 'var(--color-danger)' : 'inherit';
  }
  if (flashlightCountdownText) {
    const cd = fl.inactivity_countdown_sec !== undefined ? fl.inactivity_countdown_sec : (fl.is_on ? 15.0 : 0.0);
    flashlightCountdownText.textContent = `${Number(cd).toFixed(1)}s`;
  }
  if (flashlightCountdownFill) {
    const cd = fl.inactivity_countdown_sec !== undefined ? fl.inactivity_countdown_sec : (fl.is_on ? 15.0 : 0.0);
    const limit = fl.inactivity_timeout_sec || 15.0;
    const pct = Math.min(100, Math.max(0, Math.round((Number(cd) / limit) * 100)));
    flashlightCountdownFill.style.width = `${pct}%`;
  }
  if (flashlightTriggerText) {
    flashlightTriggerText.textContent = fl.active_trigger || fl.last_trigger || 'None';
  }
  if (flashlightResultText) {
    flashlightResultText.textContent = fl.last_command_result || 'IDLE';
    flashlightResultText.style.color = (fl.last_command_result && fl.last_command_result.startsWith('FAILED')) ? 'var(--color-danger)' : 'inherit';
  }

  // Update Event Log Table if available
  if (flashlightLogTableBody && fl.event_log && Array.isArray(fl.event_log)) {
    if (fl.event_log.length === 0) {
      flashlightLogTableBody.innerHTML = '<tr><td colspan="4" class="text-sub" style="text-align: center;">No automation events recorded yet.</td></tr>';
    } else {
      flashlightLogTableBody.innerHTML = fl.event_log.slice().reverse().slice(0, 10).map(entry => {
        const timeStr = entry.timestamp ? entry.timestamp.split(' ')[1] : '--';
        const resColor = entry.result === 'SUCCESS' || entry.result === 'OK' ? '#34d399' : '#f87171';
        return `<tr>
          <td>${timeStr}</td>
          <td>${entry.action || '--'}</td>
          <td>${entry.details || entry.mode || '--'}</td>
          <td style="color: ${resColor};">${entry.result || 'OK'}</td>
        </tr>`;
      }).join('');
    }
  }

  // Preserve existing toggleTorchBtn display
  if (toggleTorchBtn) {
    toggleTorchBtn.classList.toggle('active', !!fl.is_on);
    toggleTorchBtn.textContent = `🔦 Torch: ${fl.is_on ? 'ON' : 'OFF'}`;
  }
}

// Microphone Audio Activity UI Updater
function updateMicrophoneUI(mic, fl) {
  if (!mic) return;
  const active = !!mic.has_activity;
  const rms = mic.current_rms || 0;
  const snr = mic.snr || 1.0;
  const pct = Math.min(100, Math.round((rms / 5000.0) * 100));

  if (micPill && micPillText) {
    if (mic.is_connected) {
      micPill.className = 'status-pill pill-active';
      micPillText.textContent = 'PHONE AUDIO: CONNECTED';
    } else {
      micPill.className = 'status-pill pill-danger';
      micPillText.textContent = 'PHONE AUDIO: DISCONNECTED';
    }
  }

  if (audioStateBadge) {
    if (!mic.is_connected) {
      audioStateBadge.className = 'badge badge-danger';
      audioStateBadge.textContent = 'DISCONNECTED';
    } else if (active) {
      audioStateBadge.className = 'badge text-danger';
      audioStateBadge.textContent = 'AUDIO ACTIVE';
    } else {
      audioStateBadge.className = 'badge badge-success';
      audioStateBadge.textContent = 'SILENT (ONLINE)';
    }
  }

  if (audioMeterFill) {
    audioMeterFill.style.width = `${pct}%`;
  }

  if (audioRmsText) {
    audioRmsText.textContent = `${Number(rms).toFixed(1)} RMS`;
  }

  if (audioNoiseFloorText) {
    audioNoiseFloorText.textContent = `${Number(mic.noise_floor || 1200).toFixed(1)}`;
  }

  if (audioSnrText) {
    audioSnrText.textContent = `${Number(snr).toFixed(2)}x`;
  }

  if (audioFormatText && mic.sample_rate) {
    audioFormatText.textContent = `${mic.sample_rate / 1000}kHz ${mic.channels === 1 ? 'Mono' : 'Stereo'}`;
  }

  if (audioStreamUrlText && mic.stream_url) {
    audioStreamUrlText.textContent = mic.stream_url;
  }

  if (metricAudioVal) metricAudioVal.textContent = `${pct}%`;
  if (metricAudioBar) {
    metricAudioBar.style.width = `${pct}%`;
    metricAudioBar.style.backgroundColor = active ? 'var(--color-danger)' : (rms > 2000 ? '#f59e0b' : '#38bdf8');
  }

  if (metricAudioBadge) {
    if (active) {
      metricAudioBadge.className = 'badge text-danger';
      metricAudioBadge.textContent = '🔊 SOUND DETECTED';
    } else if (!mic.is_connected) {
      metricAudioBadge.className = 'badge text-sub';
      metricAudioBadge.textContent = 'Disconnected';
    } else {
      metricAudioBadge.className = 'badge';
      metricAudioBadge.textContent = 'Ambient / Silent';
    }
  }

  if (metricAudioSub) {
    const flState = fl && fl.is_on ? `Torch ON (${fl.active_trigger || 'Active'})` : `Torch Auto`;
    metricAudioSub.textContent = `Floor: ${mic.noise_floor || '--'} | SNR: ${snr}x | ${flState}`;
  }

  if (audioStatusText) {
    audioStatusText.textContent = active ? '🔊 SOUND DETECTED' : (rms > 1800 ? 'Moderate' : 'Silent');
    audioStatusText.style.color = active ? 'var(--color-danger)' : 'inherit';
  }
}

async function setFlashlightMode(mode) {
  try {
    const res = await apiFetch('/api/flashlight/mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    const data = await res.json();
    if (res.ok) {
      updateFlashlightUI(data);
      showToast(`Flashlight Mode: ${mode.toUpperCase()}`, 'info');
      fetchStatus();
    } else {
      showToast(data.detail || 'Failed to update flashlight mode', 'danger');
    }
  } catch (err) {
    showToast('Network error setting flashlight mode', 'danger');
  }
}

// Helper: Format Image URL for date-organized paths
function formatImageUrl(imagePath) {
  if (!imagePath) return '/api/stream/snapshot';
  const norm = imagePath.replace(/\\/g, '/');
  const parts = norm.split('storage/events/');
  if (parts.length > 1) {
    return `/api/storage/${parts[1]}`;
  }
  return `/api/storage/${norm.split('/').pop()}`;
}

// Night Mode UI Button Switcher
function updateNightModeButtons(mode) {
  if (btnNightDay) btnNightDay.classList.toggle('active', mode === 'off');
  if (btnNightNight) btnNightNight.classList.toggle('active', mode === 'on');
  if (btnNightAuto) btnNightAuto.classList.toggle('active', mode === 'auto');
}

// Update Latest Event Showcase Card
function updateLatestEventShowcase(evt) {
  if (!evt) return;
  latestEventCache = evt;

  if (latestEventTitle) latestEventTitle.textContent = evt.label || evt.category;
  if (latestEventTimeBadge) latestEventTimeBadge.textContent = new Date(evt.timestamp).toLocaleTimeString();
  if (latestEventImg) {
    latestEventImg.src = formatImageUrl(evt.image_path);
  }

  const cat = (evt.category || 'General motion').toLowerCase();
  let badgeClass = 'cat-motion';
  if (cat.includes('person')) badgeClass = 'cat-person';
  else if (cat.includes('monkey')) badgeClass = 'cat-monkey';
  else if (cat.includes('bird')) badgeClass = 'cat-bird';
  else if (cat.includes('animal')) badgeClass = 'cat-animal';

  if (latestEventCategoryBadge) {
    latestEventCategoryBadge.className = `badge ${badgeClass}`;
    latestEventCategoryBadge.textContent = evt.category;
  }

  const isNight = evt.details && evt.details.night_mode && evt.details.night_mode.is_night;
  if (latestEventNightBadge) {
    latestEventNightBadge.textContent = isNight ? '🌙 Night Mode' : '☀️ Day Mode';
    latestEventNightBadge.className = isNight ? 'badge badge-night-tag' : 'badge';
  }

  if (latestEventLabelText) latestEventLabelText.textContent = evt.label || evt.category;
  if (latestEventConfidence) {
    const conf = Math.round((evt.confidence || 0) * 100);
    latestEventConfidence.textContent = `${conf}%`;
  }
  if (latestEventAgeText) {
    latestEventAgeText.textContent = formatRelativeTime(evt.timestamp);
  }

  const tags = (evt.details && evt.details.tags) || ['INITIAL'];
  const lastTag = tags[tags.length - 1] || 'INITIAL';
  if (latestEventTagBadge) {
    latestEventTagBadge.textContent = lastTag.toUpperCase();
  }

  if (viewLatestEventBtn) {
    viewLatestEventBtn.onclick = () => openEventDetail(evt.id);
  }
}

// Event List Fetcher
async function fetchEvents() {
  try {
    const url = currentFilter === 'all' ? '/api/events?limit=40' : `/api/events?category=${encodeURIComponent(currentFilter)}&limit=40`;
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();
    renderEvents(data.events || []);
  } catch (err) {
    console.debug('Event poll error:', err);
  }
}

function renderEvents(events) {
  if (events.length === 0) {
    eventsList.innerHTML = '<div class="empty-state">No incidents recorded for this filter. Field is peaceful.</div>';
    return;
  }

  if (currentViewMode === 'timeline') {
    renderTimelineView(events);
  } else {
    renderGalleryView(events);
  }
}

// ── TIMELINE VIEW: Grouped Events with Initial / Change / Final Thumbnails ──
function renderTimelineView(events) {
  eventsList.className = 'events-timeline-container';
  eventsList.innerHTML = events.map(evt => {
    let catClass = 'cat-motion';
    const c = evt.category.toLowerCase();
    if (c.includes('person')) catClass = 'cat-person';
    else if (c.includes('bird')) catClass = 'cat-bird';
    else if (c.includes('animal')) catClass = 'cat-animal';
    else if (c.includes('monkey')) catClass = 'cat-monkey';

    const timeFormatted = new Date(evt.timestamp).toLocaleTimeString();
    const relativeTime = formatRelativeTime(evt.timestamp);
    const confPercent = Math.round((evt.confidence || 0) * 100);
    const duration = evt.details && evt.details.session_duration_sec !== undefined ? `${evt.details.session_duration_sec}s` : 'Active';

    // Collect all thumbnails in this grouped event session
    const images = (evt.details && evt.details.images) || [
      { path: evt.image_path, tag: 'initial', label: evt.label }
    ];

    const thumbsHtml = images.map(img => {
      const src = formatImageUrl(img.path);
      const tag = img.tag || 'initial';
      return `
        <div class="timeline-thumb-box" onclick="event.stopPropagation(); openImagePreview('${src}', '${escapeHtml(img.label || evt.label)}', '${tag}')" title="${tag.toUpperCase()} frame">
          <img src="${src}" alt="${tag}" loading="lazy" onerror="this.src='/api/stream/snapshot'">
          <span class="timeline-tag-pill tag-${tag}">${tag.toUpperCase()}</span>
        </div>
      `;
    }).join('');

    const statusBadge = evt.status === 'active'
      ? '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #10b981;">● IN PROGRESS</span>'
      : `<span class="timeline-duration-badge">⏱️ ${duration}</span>`;

    return `
      <div class="timeline-card" onclick="openEventDetail(${evt.id})">
        <div class="timeline-card-header">
          <div class="timeline-title-row">
            <span class="event-cat-badge ${catClass}">${evt.category}</span>
            <strong class="timeline-title">${escapeHtml(evt.label)}</strong>
          </div>
          <div style="display: flex; align-items: center; gap: 0.5rem;">
            ${statusBadge}
            <span class="timeline-session-badge">#${evt.id}</span>
          </div>
        </div>

        <!-- Thumbnails Strip: Initial, Change, Final -->
        <div class="timeline-thumbs-strip">
          ${thumbsHtml}
        </div>

        <div class="timeline-footer">
          <span>🕒 ${timeFormatted} (${relativeTime})</span>
          <span>Conf: <strong>${confPercent}%</strong> • ${images.length} frame(s)</span>
        </div>
      </div>
    `;
  }).join('');
}

// ── GALLERY VIEW: Grid of Images ──
function renderGalleryView(events) {
  eventsList.className = 'events-grid';
  eventsList.innerHTML = events.map(evt => {
    let catClass = 'cat-motion';
    const c = evt.category.toLowerCase();
    if (c.includes('person')) catClass = 'cat-person';
    else if (c.includes('bird')) catClass = 'cat-bird';
    else if (c.includes('animal')) catClass = 'cat-animal';
    else if (c.includes('monkey')) catClass = 'cat-monkey';

    const imgSrc = formatImageUrl(evt.image_path);
    const timeFormatted = new Date(evt.timestamp).toLocaleTimeString();

    return `
      <div class="event-item" onclick="openEventDetail(${evt.id})">
        <img class="event-thumb" src="${imgSrc}" alt="${evt.label}" loading="lazy" onerror="this.src='/api/stream/snapshot'">
        <div class="event-meta">
          <span class="event-cat-badge ${catClass}">${evt.category}</span>
          <div class="event-title">${escapeHtml(evt.label)}</div>
          <div class="event-time">${timeFormatted}</div>
        </div>
      </div>
    `;
  }).join('');
}

// Modal Helpers
function openModal(modal) {
  modal.classList.add('active');
}
function closeModal(modal) {
  modal.classList.remove('active');
}

document.querySelectorAll('.modal-close').forEach(btn => {
  btn.addEventListener('click', (e) => {
    const targetId = btn.getAttribute('data-close');
    const modal = document.getElementById(targetId);
    if (modal) closeModal(modal);
  });
});

window.addEventListener('click', (e) => {
  if (e.target.classList.contains('modal')) {
    closeModal(e.target);
  }
});

// Image Preview Helper (for Timeline Thumbnails)
function openImagePreview(src, label, tag) {
  document.getElementById('eventDetailTitle').textContent = `Snapshot: ${tag ? tag.toUpperCase() : 'FRAME'}`;
  document.getElementById('eventDetailImg').src = src;
  document.getElementById('eventDetailCategory').textContent = tag ? tag.toUpperCase() : 'Snapshot';
  document.getElementById('eventDetailTimestamp').textContent = new Date().toLocaleString();
  document.getElementById('eventDetailConfidence').textContent = '--';
  document.getElementById('eventDetailLabel').textContent = label || 'Surveillance Frame';
  document.getElementById('eventDetailJson').textContent = JSON.stringify({ snapshot_type: tag, image_url: src }, null, 2);
  const dlBtn = document.getElementById('downloadEventImgBtn');
  if (dlBtn) {
    dlBtn.href = src;
    dlBtn.download = src.split('/').pop() || 'snapshot.jpg';
  }
  openModal(eventDetailModal);
}

// Event Detail Modal
async function openEventDetail(eventId) {
  currentSelectedEventId = eventId;
  try {
    const res = await fetch(`/api/events/${eventId}`);
    if (!res.ok) return;
    const evt = await res.json();

    const imgUrl = formatImageUrl(evt.image_path);
    document.getElementById('eventDetailTitle').textContent = `Incident Record #${evt.id}`;
    document.getElementById('eventDetailImg').src = imgUrl;
    document.getElementById('eventDetailCategory').textContent = evt.category;
    document.getElementById('eventDetailTimestamp').textContent = new Date(evt.timestamp).toLocaleString();
    document.getElementById('eventDetailConfidence').textContent = `${(evt.confidence * 100).toFixed(1)}%`;
    document.getElementById('eventDetailLabel').textContent = evt.label;
    document.getElementById('eventDetailJson').textContent = JSON.stringify(evt.details || {}, null, 2);

    const dlBtn = document.getElementById('downloadEventImgBtn');
    if (dlBtn) {
      dlBtn.href = imgUrl;
      const filename = evt.image_path ? evt.image_path.split('/').pop() : 'event.jpg';
      dlBtn.download = filename;
    }

    openModal(eventDetailModal);
  } catch (err) {
    showToast('Failed to load event details', 'danger');
  }
}

// Delete Event
document.getElementById('deleteEventBtn').addEventListener('click', async () => {
  if (!currentSelectedEventId) return;
  if (!confirm(`Are you sure you want to delete incident #${currentSelectedEventId}?`)) return;

  try {
    const res = await apiFetch(`/api/events/${currentSelectedEventId}`, { method: 'DELETE' });
    if (res.ok) {
      showToast('Incident deleted', 'info');
      closeModal(eventDetailModal);
      fetchEvents();
      fetchStatus();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Delete failed', 'danger');
    }
  } catch (err) {
    showToast('Error deleting event', 'danger');
  }
});

// --- HTML Escaping Helper ---
function escapeHtml(text) {
  if (!text) return '';
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// --- Force Push Messages Management ---
function updatePushUI() {
  if (togglePushNavBtn) {
    togglePushNavBtn.classList.toggle('active', pushEnabled);
    togglePushNavBtn.classList.toggle('muted', !pushEnabled);
  }
  if (pushNavLabel) {
    pushNavLabel.textContent = pushEnabled ? 'Push: ON' : 'Push: OFF';
  }
  const cfgEnabled = document.getElementById('cfgPushEnabled');
  if (cfgEnabled) cfgEnabled.checked = pushEnabled;
  const cfgDesktop = document.getElementById('cfgPushDesktop');
  if (cfgDesktop) cfgDesktop.checked = pushDesktop;
  const cfgAudio = document.getElementById('cfgPushAudio');
  if (cfgAudio) cfgAudio.checked = pushAudio;
}

async function togglePush(enable = null) {
  if (enable === null) {
    pushEnabled = !pushEnabled;
  } else {
    pushEnabled = !!enable;
  }

  localStorage.setItem('wheat_watch_push_enabled', pushEnabled ? 'true' : 'false');
  updatePushUI();

  if (pushEnabled) {
    // Request Desktop Notification permission if supported
    if ('Notification' in window && Notification.permission === 'default') {
      try {
        await Notification.requestPermission();
      } catch (e) {
        console.debug('Notification permission request error:', e);
      }
    }
    showToast('🔔 Force push messages ENABLED for this browser', 'info');
  } else {
    showToast('🔕 Force push messages DISABLED for this browser', 'info');
  }

  // Synchronize state with backend
  try {
    await fetch('/api/push/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: pushEnabled }),
    });
  } catch (e) {
    console.debug('Failed to sync push toggle with server:', e);
  }
}

// Web Audio API Synthesizer (Works on all mobile & desktop browsers)
function playBrowserChime(category) {
  if (!pushAudio) return;
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    if (ctx.state === 'suspended') {
      ctx.resume();
    }
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';

    const isUrgent = category === 'Person' || (category && category.toLowerCase().includes('monkey'));
    const startFreq = isUrgent ? 880 : 587.33;  // A5 or D5
    const endFreq = isUrgent ? 1174.66 : 880;    // D6 or A5

    osc.frequency.setValueAtTime(startFreq, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(endFreq, ctx.currentTime + 0.15);

    gain.gain.setValueAtTime(0.25, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.45);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.45);
  } catch (e) {
    console.debug('Browser audio chime error:', e);
  }
}

// Native Desktop / OS Notification
function triggerDesktopNotification(event) {
  if (!pushEnabled || !pushDesktop) return;
  if (!('Notification' in window)) return;
  if (Notification.permission !== 'granted') return;

  const cat = event.category || 'Surveillance Alert';
  const label = event.label || cat;
  const conf = Math.round((event.confidence || 0) * 100);
  const timeStr = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

  try {
    const notif = new Notification(`🌾 PySURVEILLANCE: ${cat}`, {
      body: `${label}\nConfidence: ${conf}% • ${timeStr}`,
      tag: `pysurveillance-${event.id || Date.now()}`,
      requireInteraction: cat === 'Person' || cat.toLowerCase().includes('monkey'),
    });

    notif.onclick = () => {
      window.focus();
      if (event.id) openEventDetail(event.id);
      notif.close();
    };
  } catch (e) {
    console.debug('Desktop notification error:', e);
  }
}

// In-App Force Push Floating Sliding Banner
function showPushBanner(event) {
  if (!pushEnabled) return;
  const container = document.getElementById('pushBannerContainer');
  if (!container) return;

  // Limit visible stack to 3 items
  while (container.children.length >= 3) {
    container.firstChild.remove();
  }

  const cat = (event.category || 'General motion').toLowerCase();
  let catClass = 'push-banner-motion';
  let badgeClass = 'cat-motion';
  let catIcon = '🏃';

  if (cat.includes('person')) {
    catClass = 'push-banner-person';
    badgeClass = 'cat-person';
    catIcon = '🚨';
  } else if (cat.includes('monkey')) {
    catClass = 'push-banner-monkey';
    badgeClass = 'cat-monkey';
    catIcon = '⚠️';
  } else if (cat.includes('bird')) {
    catClass = 'push-banner-bird';
    badgeClass = 'cat-bird';
    catIcon = '🦅';
  } else if (cat.includes('animal')) {
    catClass = 'push-banner-animal';
    badgeClass = 'cat-animal';
    catIcon = '🐾';
  }

  const banner = document.createElement('div');
  banner.className = `push-banner ${catClass}`;

  const imgSrc = formatImageUrl(event.image_path);
  const timeStr = event.timestamp ? new Date(event.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
  const confPercent = Math.round((event.confidence || 0) * 100);

  banner.innerHTML = `
    <div class="push-banner-thumb-box">
      <img src="${imgSrc}" class="push-banner-thumb" alt="Incident Snapshot" onerror="this.src='/api/stream/snapshot'">
    </div>
    <div class="push-banner-content">
      <div class="push-banner-top">
        <span class="badge ${badgeClass} push-banner-badge">${catIcon} ${escapeHtml(event.category)}</span>
        <span class="push-banner-time">${timeStr}</span>
        <button class="push-banner-close" title="Dismiss">&times;</button>
      </div>
      <div class="push-banner-title">${escapeHtml(event.label || event.category)}</div>
      <div class="push-banner-meta">Confidence: <strong>${confPercent}%</strong></div>
      <div class="push-banner-actions">
        ${event.id ? `<button class="push-banner-btn-view" data-event-id="${event.id}">🔍 View Incident</button>` : ''}
      </div>
    </div>
    <div class="push-banner-progress" style="animation-duration: 8s;"></div>
  `;

  const closeBtn = banner.querySelector('.push-banner-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dismissBanner(banner);
    });
  }

  const viewBtn = banner.querySelector('.push-banner-btn-view');
  if (viewBtn && event.id) {
    viewBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      openEventDetail(event.id);
      dismissBanner(banner);
    });
  }

  container.appendChild(banner);

  const timer = setTimeout(() => {
    dismissBanner(banner);
  }, 8000);
  banner._dismissTimer = timer;
}

function dismissBanner(banner) {
  if (banner._dismissed) return;
  banner._dismissed = true;
  clearTimeout(banner._dismissTimer);
  banner.classList.add('dismissing');
  setTimeout(() => banner.remove(), 300);
}

// Prepend event card into gallery dynamically
function prependEventCard(evt) {
  if (!eventsList) return;
  const empty = eventsList.querySelector('.empty-state');
  if (empty) empty.remove();

  if (document.getElementById(`evt-card-${evt.id}`)) return;

  let catClass = 'cat-unknown';
  const c = (evt.category || '').toLowerCase();
  if (c.includes('person')) catClass = 'cat-person';
  else if (c.includes('bird')) catClass = 'cat-bird';
  else if (c.includes('animal')) catClass = 'cat-animal';
  else if (c.includes('monkey')) catClass = 'cat-monkey';
  else if (c.includes('motion')) catClass = 'cat-motion';

  const filename = (evt.image_path || '').split('/').pop();
  const timeFormatted = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

  const card = document.createElement('div');
  card.id = `evt-card-${evt.id}`;
  card.className = 'event-item';
  card.onclick = () => openEventDetail(evt.id);
  card.innerHTML = `
    <img class="event-thumb" src="/api/storage/${filename}" alt="${escapeHtml(evt.label)}" loading="lazy" onerror="this.src='/api/stream/snapshot'">
    <div class="event-meta">
      <span class="event-cat-badge ${catClass}">${escapeHtml(evt.category)}</span>
      <div class="event-title">${escapeHtml(evt.label)}</div>
      <div class="event-time">${timeFormatted}</div>
    </div>
  `;
  eventsList.prepend(card);
}

// Handle incoming real-time push detection
function handlePushDetection(event) {
  if (currentFilter === 'all' || currentFilter === event.category) {
    prependEventCard(event);
  }

  if (pushEnabled) {
    showPushBanner(event);
    triggerDesktopNotification(event);
    playBrowserChime(event.category);
  }
}

// Send test push message
async function sendTestPush() {
  try {
    showToast('Dispatching test push message...', 'info');
    const res = await fetch('/api/push/test', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast('✓ Test push dispatched to all connected browsers!', 'info');
    } else {
      showToast(data.message || 'Test push failed', 'warning');
    }
  } catch (err) {
    showToast('Failed to trigger test push', 'danger');
  }
}

// SSE Connection Listener
function initPushStream() {
  if (pushEventSource) {
    try { pushEventSource.close(); } catch (e) {}
  }

  pushEventSource = new EventSource('/api/push/stream');

  pushEventSource.addEventListener('handshake', (e) => {
    console.log('SSE Push stream connected:', e.data);
  });

  pushEventSource.addEventListener('detection', (e) => {
    try {
      const data = JSON.parse(e.data);
      handlePushDetection(data);
      updateLatestEventShowcase(data);
      fetchEvents();
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing push detection event:', err);
    }
  });

  pushEventSource.addEventListener('detection_update', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateLatestEventShowcase(data);
      fetchEvents();
    } catch (err) {
      console.debug('Error parsing detection_update event:', err);
    }
  });

  pushEventSource.addEventListener('event_completed', (e) => {
    try {
      fetchEvents();
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing event_completed event:', err);
    }
  });

  pushEventSource.addEventListener('camera_disconnected', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (cameraDisconnectBanner) cameraDisconnectBanner.style.display = 'block';
      showToast('⚠️ Camera disconnected! Real-time stream lost. Auto-reconnecting...', 'danger');
      playBrowserChime('Camera');
    } catch (err) {
      console.debug('Error parsing camera_disconnected event:', err);
    }
  });

  pushEventSource.addEventListener('camera_connected', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (cameraDisconnectBanner) cameraDisconnectBanner.style.display = 'none';
      showToast('✓ Camera online! Surveillance active.', 'info');
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing camera_connected event:', err);
    }
  });

  pushEventSource.addEventListener('camera_reconfiguring', (e) => {
    try {
      const data = JSON.parse(e.data);
      cameraPill.className = 'status-pill pill-warning';
      cameraPillText.textContent = 'CAM: RECONFIGURING...';
      if (cameraDisconnectBanner) cameraDisconnectBanner.style.display = 'none';
      showToast('Camera reconfiguring... Applying settings safely.', 'info');
    } catch (err) {
      console.debug('Error parsing camera_reconfiguring event:', err);
    }
  });

  pushEventSource.addEventListener('camera_rollback', (e) => {
    try {
      const data = JSON.parse(e.data);
      showToast(`⚠️ Reconfiguration failed. Rolled back to ${data.restored_resolution || 'previous resolution'}`, 'warning');
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing camera_rollback event:', err);
    }
  });

  pushEventSource.addEventListener('night_mode', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateNightModeButtons(data.mode);
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing night_mode event:', err);
    }
  });

  pushEventSource.addEventListener('surveillance_mode', (e) => {
    try {
      const data = JSON.parse(e.data);
      isMonitoring = !!data.active;
      fetchStatus();
    } catch (err) {
      console.debug('Error parsing surveillance_mode event:', err);
    }
  });

  pushEventSource.addEventListener('flashlight', (e) => {
    try {
      const data = JSON.parse(e.data);
      updateFlashlightUI(data);
    } catch (err) {
      console.debug('Error parsing flashlight event:', err);
    }
  });

  pushEventSource.addEventListener('alarm', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (pushEnabled) {
        showToast(`🔊 Laptop Alarm Sounded: ${data.category}`, 'warning');
      }
    } catch (err) {
      console.debug('Error parsing push alarm event:', err);
    }
  });

  pushEventSource.addEventListener('push_config', (e) => {
    try {
      const data = JSON.parse(e.data);
      if (data.enabled !== undefined) {
        pushEnabled = !!data.enabled;
        localStorage.setItem('wheat_watch_push_enabled', pushEnabled ? 'true' : 'false');
      }
      if (data.desktop_notifications !== undefined) {
        pushDesktop = !!data.desktop_notifications;
        localStorage.setItem('wheat_watch_push_desktop', pushDesktop ? 'true' : 'false');
      }
      if (data.browser_audio !== undefined) {
        pushAudio = !!data.browser_audio;
        localStorage.setItem('wheat_watch_push_audio', pushAudio ? 'true' : 'false');
      }
      updatePushUI();
    } catch (err) {
      console.debug('Error updating push config:', err);
    }
  });

  pushEventSource.onerror = (err) => {
    console.debug('SSE Push stream reconnecting...', err);
  };
}

// Wire push toggle buttons
if (togglePushNavBtn) {
  togglePushNavBtn.addEventListener('click', () => togglePush());
}
if (testPushBtn) {
  testPushBtn.addEventListener('click', sendTestPush);
}
if (cfgTestPushBtn) {
  cfgTestPushBtn.addEventListener('click', sendTestPush);
}

const cfgPushEnabledElem = document.getElementById('cfgPushEnabled');
if (cfgPushEnabledElem) {
  cfgPushEnabledElem.addEventListener('change', (e) => {
    pushEnabled = e.target.checked;
    localStorage.setItem('wheat_watch_push_enabled', pushEnabled ? 'true' : 'false');
    updatePushUI();
  });
}
const cfgPushDesktopElem = document.getElementById('cfgPushDesktop');
if (cfgPushDesktopElem) {
  cfgPushDesktopElem.addEventListener('change', (e) => {
    pushDesktop = e.target.checked;
    localStorage.setItem('wheat_watch_push_desktop', pushDesktop ? 'true' : 'false');
  });
}
const cfgPushAudioElem = document.getElementById('cfgPushAudio');
if (cfgPushAudioElem) {
  cfgPushAudioElem.addEventListener('change', (e) => {
    pushAudio = e.target.checked;
    localStorage.setItem('wheat_watch_push_audio', pushAudio ? 'true' : 'false');
  });
}

// --- Live Image Quality & Exposure Controls ---
const sliderQuality = document.getElementById('sliderQuality');
const sliderQualityVal = document.getElementById('sliderQualityVal');
const sliderGamma = document.getElementById('sliderGamma');
const sliderGammaVal = document.getElementById('sliderGammaVal');
const sliderBrightness = document.getElementById('sliderBrightness');
const sliderBrightnessVal = document.getElementById('sliderBrightnessVal');
const sliderContrast = document.getElementById('sliderContrast');
const sliderContrastVal = document.getElementById('sliderContrastVal');
const liveResBadge = document.getElementById('liveResBadge');

const toggleHdrBtn = document.getElementById('toggleHdrBtn');
const toggleTorchBtn = document.getElementById('toggleTorchBtn');
const toggleNightBtn = document.getElementById('toggleNightBtn');
const resetControlsBtn = document.getElementById('resetControlsBtn');

let activeHdr = false;
let activeTorch = false;
let activeNight = false;
let controlDebounceTimer = null;

async function sendControlUpdate(updates, immediate = false) {
  clearTimeout(controlDebounceTimer);
  const doSend = async () => {
    try {
      const res = await fetch('/api/camera/controls', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(updates),
      });
      return await res.json();
    } catch (e) {
      console.debug('Failed to update controls:', e);
      return null;
    }
  };

  if (immediate) {
    return await doSend();
  } else {
    controlDebounceTimer = setTimeout(doSend, 120);
    return null;
  }
}

async function loadImageControls() {
  try {
    const res = await fetch('/api/camera/controls');
    if (!res.ok) return;
    const data = await res.json();
    const ctrl = data.controls || {};

    if (sliderQuality) {
      sliderQuality.value = ctrl.quality || 95;
      sliderQualityVal.textContent = `${sliderQuality.value}%`;
    }
    if (sliderGamma) {
      sliderGamma.value = ctrl.gamma || 0.75;
      sliderGammaVal.textContent = `${sliderGamma.value}x`;
    }
    if (sliderBrightness) {
      sliderBrightness.value = ctrl.brightness !== undefined ? ctrl.brightness : -15;
      sliderBrightnessVal.textContent = sliderBrightness.value;
    }
    if (sliderContrast) {
      sliderContrast.value = ctrl.contrast || 1.15;
      sliderContrastVal.textContent = `${sliderContrast.value}x`;
    }

    const curRes = ctrl.resolution || '1280x720';
    if (liveResBadge) liveResBadge.textContent = curRes.includes('1080') ? '1080p FHD' : (curRes.includes('720') ? '720p HD' : '480p SD');
    document.querySelectorAll('.btn-toggle-option').forEach(btn => {
      btn.classList.toggle('active', btn.getAttribute('data-res') === curRes);
    });

    activeHdr = !!ctrl.auto_hdr;
    if (toggleHdrBtn) {
      toggleHdrBtn.classList.toggle('active', activeHdr);
      toggleHdrBtn.textContent = `Auto-HDR: ${activeHdr ? 'ON' : 'OFF'}`;
    }

    activeTorch = !!ctrl.torch;
    if (toggleTorchBtn) {
      toggleTorchBtn.classList.toggle('active', activeTorch);
      toggleTorchBtn.textContent = `🔦 Torch: ${activeTorch ? 'ON' : 'OFF'}`;
    }

    activeNight = !!ctrl.night_vision;
    if (toggleNightBtn) {
      toggleNightBtn.classList.toggle('active', activeNight);
      toggleNightBtn.textContent = `🌙 Night Vision: ${activeNight ? 'ON' : 'OFF'}`;
    }
  } catch (err) {
    console.debug('Error loading image controls:', err);
  }
}

// Slider Event Listeners
if (sliderQuality) {
  sliderQuality.addEventListener('input', () => {
    sliderQualityVal.textContent = `${sliderQuality.value}%`;
  });
  sliderQuality.addEventListener('change', () => {
    sendControlUpdate({ quality: parseInt(sliderQuality.value, 10) }, true);
    showToast(`Camera Quality set to ${sliderQuality.value}%`, 'info');
  });
}

if (sliderGamma) {
  sliderGamma.addEventListener('input', () => {
    sliderGammaVal.textContent = `${sliderGamma.value}x`;
    sendControlUpdate({ gamma: parseFloat(sliderGamma.value) });
  });
}

if (sliderBrightness) {
  sliderBrightness.addEventListener('input', () => {
    sliderBrightnessVal.textContent = sliderBrightness.value;
    sendControlUpdate({ brightness: parseInt(sliderBrightness.value, 10) });
  });
}

if (sliderContrast) {
  sliderContrast.addEventListener('input', () => {
    sliderContrastVal.textContent = `${sliderContrast.value}x`;
    sendControlUpdate({ contrast: parseFloat(sliderContrast.value) });
  });
}

// Resolution Switcher Buttons
document.querySelectorAll('.btn-toggle-option').forEach(btn => {
  btn.addEventListener('click', async () => {
    const res = btn.getAttribute('data-res');
    document.querySelectorAll('.btn-toggle-option').forEach(b => {
      b.classList.remove('active');
      b.disabled = true;
    });
    btn.classList.add('active');
    if (liveResBadge) liveResBadge.textContent = res.includes('1080') ? '1080p FHD' : (res.includes('720') ? '720p HD' : '480p SD');
    showToast(`Reconfiguring camera resolution to ${res}...`, 'info');
    try {
      const resp = await sendControlUpdate({ resolution: res }, true);
      if (resp && resp.success) {
        showToast(`✓ Camera resolution set to ${res} (stream verified)`, 'info');
      } else if (resp && resp.message) {
        showToast(resp.message, 'warning');
      }
    } catch (err) {
      console.debug('Resolution update failed:', err);
    } finally {
      document.querySelectorAll('.btn-toggle-option').forEach(b => b.disabled = false);
      loadImageControls();
      fetchStatus();
    }
  });
});

// Hardware Toggles
if (toggleHdrBtn) {
  toggleHdrBtn.addEventListener('click', () => {
    activeHdr = !activeHdr;
    toggleHdrBtn.classList.toggle('active', activeHdr);
    toggleHdrBtn.textContent = `Auto-HDR: ${activeHdr ? 'ON' : 'OFF'}`;
    sendControlUpdate({ auto_hdr: activeHdr }, true);
    showToast(`Auto-HDR Tone Mapping: ${activeHdr ? 'ENABLED' : 'DISABLED'}`, 'info');
  });
}

if (toggleTorchBtn) {
  toggleTorchBtn.addEventListener('click', () => {
    activeTorch = !activeTorch;
    toggleTorchBtn.classList.toggle('active', activeTorch);
    toggleTorchBtn.textContent = `🔦 Torch: ${activeTorch ? 'ON' : 'OFF'}`;
    sendControlUpdate({ torch: activeTorch }, true);
    showToast(`Phone Flashlight: ${activeTorch ? 'ON' : 'OFF'}`, 'info');
  });
}

if (toggleNightBtn) {
  toggleNightBtn.addEventListener('click', () => {
    activeNight = !activeNight;
    toggleNightBtn.classList.toggle('active', activeNight);
    toggleNightBtn.textContent = `🌙 Night Vision: ${activeNight ? 'ON' : 'OFF'}`;
    sendControlUpdate({ night_vision: activeNight }, true);
    showToast(`Night Vision Mode: ${activeNight ? 'ON' : 'OFF'}`, 'info');
  });
}

if (resetControlsBtn) {
  resetControlsBtn.addEventListener('click', async () => {
    resetControlsBtn.disabled = true;
    showToast('Resetting camera settings to defaults and verifying stream...', 'info');
    try {
      const res = await fetch('/api/camera/reset', {
        method: 'POST',
        headers: authHeader(),
      });
      const data = await res.json();
      if (data && data.success) {
        showToast('✓ Controls reset and stream verified at 1280x720', 'info');
      } else {
        showToast(`Reset notice: ${(data && data.message) || 'Stream check completed'}`, 'warning');
      }
    } catch (err) {
      console.debug('Reset controls failed:', err);
      showToast('Error resetting camera controls.', 'danger');
    } finally {
      resetControlsBtn.disabled = false;
      loadImageControls();
      fetchStatus();
    }
  });
}

// Load controls on startup
loadImageControls();

// Filter Tabs
document.querySelectorAll('.filter-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    currentFilter = tab.getAttribute('data-filter');
    fetchEvents();
  });
});

// --- Surveillance & Night Mode Handlers ---
async function toggleSurveillance(targetState = null) {
  try {
    const payload = targetState !== null ? { active: targetState } : { active: !isMonitoring };
    const res = await apiFetch('/api/surveillance/toggle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      isMonitoring = data.is_monitoring;
      showToast(data.message, 'info');
      fetchStatus();
    } else {
      showToast(data.detail || 'Failed to toggle surveillance', 'danger');
    }
  } catch (err) {
    showToast('Connection error toggling surveillance', 'danger');
  }
}

async function setNightMode(mode) {
  try {
    const res = await apiFetch('/api/night_mode', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode }),
    });
    const data = await res.json();
    if (res.ok) {
      updateNightModeButtons(data.mode);
      const modeLabel = data.mode === 'auto' ? 'AUTO (Adaptive Lux)' : (data.mode === 'on' ? 'NIGHT (High Noise Tolerance)' : 'DAY (Normal)');
      showToast(`🌙 Night Mode set to: ${modeLabel}`, 'info');
      fetchStatus();
    } else {
      showToast(data.detail || 'Failed to update night mode', 'danger');
    }
  } catch (err) {
    showToast('Failed to switch night mode', 'danger');
  }
}

function setViewMode(mode) {
  currentViewMode = mode;
  localStorage.setItem('wheat_watch_view_mode', mode);
  if (viewTabTimeline) viewTabTimeline.classList.toggle('active', mode === 'timeline');
  if (viewTabGallery) viewTabGallery.classList.toggle('active', mode === 'gallery');
  fetchEvents();
}

async function purgeStorage() {
  if (!confirm('Run storage cleanup now? Expired snapshots exceeding 14-day retention will be deleted. Active event snapshots are permanently protected.')) return;
  try {
    showToast('Enforcing storage retention cleanup...', 'info');
    const res = await apiFetch('/api/storage/cleanup', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      const del = (data.cleanup && data.cleanup.deleted_count) || 0;
      showToast(`✓ Storage Cleanup: ${del} expired snapshot(s) deleted. Disk usage: ${data.stats.used_mb} MB`, 'info');
      fetchStatus();
      fetchEvents();
    } else {
      showToast(data.detail || 'Storage cleanup failed', 'danger');
    }
  } catch (err) {
    showToast('Error during storage retention cleanup', 'danger');
  }
}

// Controls
if (navSurveillanceBtn) {
  navSurveillanceBtn.addEventListener('click', () => toggleSurveillance());
}
if (toggleMonitoringBtn) {
  toggleMonitoringBtn.addEventListener('click', () => toggleSurveillance());
}
if (btnNightDay) {
  btnNightDay.addEventListener('click', () => setNightMode('off'));
}
if (btnNightNight) {
  btnNightNight.addEventListener('click', () => setNightMode('on'));
}
if (btnNightAuto) {
  btnNightAuto.addEventListener('click', () => setNightMode('auto'));
}
if (btnFlashlightAuto) {
  btnFlashlightAuto.addEventListener('click', () => setFlashlightMode('auto'));
}
if (btnFlashlightManual) {
  btnFlashlightManual.addEventListener('click', () => setFlashlightMode('manual'));
}
if (btnFlashlightOff) {
  btnFlashlightOff.addEventListener('click', () => setFlashlightMode('off'));
}
if (viewTabTimeline) {
  viewTabTimeline.addEventListener('click', () => setViewMode('timeline'));
}
if (viewTabGallery) {
  viewTabGallery.addEventListener('click', () => setViewMode('gallery'));
}
if (purgeStorageBtn) {
  purgeStorageBtn.addEventListener('click', purgeStorage);
}
if (bannerRetryCamBtn) {
  bannerRetryCamBtn.addEventListener('click', async () => {
    showToast('Re-initializing camera connection...', 'info');
    try {
      await fetch('/api/camera/reconnect', { method: 'POST' });
      fetchStatus();
      showToast('Camera reconnection signal sent.', 'info');
    } catch (e) {
      showToast('Camera check failed', 'danger');
    }
  });
}

testAlarmBtn.addEventListener('click', async () => {
  try {
    const res = await apiFetch('/api/alarm/test', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast('🔊 Laptop alarm sounded successfully!', 'info');
    } else {
      showToast(data.message || 'Alarm test failed', 'warning');
    }
  } catch (err) {
    showToast('Error triggering test alarm', 'danger');
  }
});

snapshotBtn.addEventListener('click', () => {
  const win = window.open('/api/stream/snapshot', '_blank');
});

// QR Modal
document.getElementById('qrBtn').addEventListener('click', async () => {
  try {
    const res = await fetch('/api/qr');
    const svgText = await res.text();
    document.getElementById('qrCodeContainer').innerHTML = svgText;
    document.getElementById('qrUrlDisplay').textContent = phoneUrlLink.href;
    openModal(qrModal);
  } catch (err) {
    showToast('Failed to load QR code', 'danger');
  }
});

// Copy URL
document.getElementById('copyUrlBtn').addEventListener('click', () => {
  navigator.clipboard.writeText(phoneUrlLink.href).then(() => {
    showToast('Phone URL copied to clipboard!', 'info');
  });
});

// PIN Form
document.getElementById('pinBtn').addEventListener('click', () => openModal(pinModal));
document.getElementById('pinForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const pin = document.getElementById('pinInput').value.trim();
  const errDiv = document.getElementById('pinError');
  errDiv.textContent = '';

  try {
    const res = await fetch('/api/auth/verify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pin }),
    });
    const data = await res.json();
    if (res.ok && data.success) {
      currentToken = data.token;
      currentCsrfToken = data.csrf_token || '';
      localStorage.setItem('wheat_watch_token', currentToken);
      if (currentCsrfToken) {
        localStorage.setItem('wheat_watch_csrf', currentCsrfToken);
      }
      pinStatusText.textContent = '(Unlocked)';
      closeModal(pinModal);
      showToast('Dashboard unlocked with PIN!', 'info');
    } else {
      errDiv.textContent = data.message || 'Invalid PIN';
    }
  } catch (err) {
    errDiv.textContent = 'Server verification error';
  }
});

// Settings Modal & Loading
document.getElementById('settingsBtn').addEventListener('click', async () => {
  try {
    const res = await fetch('/api/config');
    const cfg = await res.json();

    document.getElementById('cfgPhoneIp').value = cfg.camera.phone_ip;
    document.getElementById('cfgPhonePort').value = cfg.camera.phone_port;
    document.getElementById('cfgVideoEp').value = cfg.camera.video_endpoint;
    document.getElementById('cfgSnapshotEp').value = cfg.camera.snapshot_endpoint;

    document.getElementById('cfgMotionFps').value = cfg.pipeline.motion_fps;
    document.getElementById('cfgAiFps').value = cfg.pipeline.ai_fps;
    document.getElementById('cfgMotionThresh').value = cfg.pipeline.motion_threshold;
    document.getElementById('cfgConfidence').value = cfg.pipeline.detection_confidence;
    document.getElementById('cfgAutoThrottle').checked = cfg.pipeline.auto_throttle_cpu;

    document.getElementById('cfgSoundEnabled').checked = cfg.alarm.sound_enabled;
    if (document.getElementById('cfgAlarmMotion')) {
      document.getElementById('cfgAlarmMotion').checked = !!cfg.alarm.alarm_on_general_motion;
    }
    if (document.getElementById('cfgAlarmUnknown')) {
      document.getElementById('cfgAlarmUnknown').checked = !!cfg.alarm.alarm_on_unknown_objects;
    }
    document.getElementById('cfgCdPerson').value = cfg.alarm.cooldowns['Person'] || 30;
    document.getElementById('cfgCdAnimal').value = cfg.alarm.cooldowns['Animal detected — species unconfirmed'] || 25;
    document.getElementById('cfgCdMotion').value = cfg.alarm.cooldowns['General motion'] || 15;

    const pushCfg = cfg.push || {};
    if (document.getElementById('cfgPushEnabled')) {
      document.getElementById('cfgPushEnabled').checked = pushCfg.enabled !== undefined ? pushCfg.enabled : pushEnabled;
    }
    if (document.getElementById('cfgPushDesktop')) {
      document.getElementById('cfgPushDesktop').checked = pushCfg.desktop_notifications !== undefined ? pushCfg.desktop_notifications : pushDesktop;
    }
    if (document.getElementById('cfgPushAudio')) {
      document.getElementById('cfgPushAudio').checked = pushCfg.browser_audio !== undefined ? pushCfg.browser_audio : pushAudio;
    }
    if (document.getElementById('cfgPushMotion')) {
      document.getElementById('cfgPushMotion').checked = !!pushCfg.push_on_general_motion;
    }
    if (document.getElementById('cfgPushUnknown')) {
      document.getElementById('cfgPushUnknown').checked = !!pushCfg.push_on_unknown_objects;
    }

    // Dedicated Night Surveillance Config
    const nm = cfg.night_mode || {};
    if (document.getElementById('cfgNightModeSelect')) {
      document.getElementById('cfgNightModeSelect').value = nm.mode || 'auto';
    }
    if (document.getElementById('cfgNightAutoThresh')) {
      document.getElementById('cfgNightAutoThresh').value = nm.auto_night_lux_threshold || 45;
    }
    const dayProf = (nm.profiles && nm.profiles.day) || {};
    const nightProf = (nm.profiles && nm.profiles.night) || {};
    if (document.getElementById('cfgDayThresh')) {
      document.getElementById('cfgDayThresh').value = dayProf.threshold || 25;
    }
    if (document.getElementById('cfgNightThresh')) {
      document.getElementById('cfgNightThresh').value = nightProf.threshold || 34;
    }
    if (document.getElementById('cfgDayMinArea')) {
      document.getElementById('cfgDayMinArea').value = dayProf.min_motion_area || 250;
    }
    if (document.getElementById('cfgNightMinArea')) {
      document.getElementById('cfgNightMinArea').value = nightProf.min_motion_area || 350;
    }

    // Storage Retention Config
    const stor = cfg.storage || {};
    if (document.getElementById('cfgRetentionDays')) {
      document.getElementById('cfgRetentionDays').value = stor.retention_days || 14;
    }
    if (document.getElementById('cfgMaxStorageMb')) {
      document.getElementById('cfgMaxStorageMb').value = stor.max_storage_mb || 2048;
    }

    // Event Grouping Deduplication Config
    const grp = cfg.event_grouping || {};
    if (document.getElementById('cfgSessionTimeout')) {
      document.getElementById('cfgSessionTimeout').value = grp.session_timeout_sec || 4;
    }
    if (document.getElementById('cfgCapChange')) {
      document.getElementById('cfgCapChange').checked = grp.capture_change !== false;
    }
    if (document.getElementById('cfgCapFinal')) {
      document.getElementById('cfgCapFinal').checked = grp.capture_final !== false;
    }

    // Flashlight & Audio Detection Config
    const flCfg = cfg.flashlight || {};
    if (document.getElementById('cfgFlashlightMode')) {
      document.getElementById('cfgFlashlightMode').value = flCfg.mode || 'auto';
    }
    if (document.getElementById('cfgFlashlightLux')) {
      document.getElementById('cfgFlashlightLux').value = flCfg.lux_threshold || 45;
    }
    if (document.getElementById('cfgFlashlightMinOn')) {
      document.getElementById('cfgFlashlightMinOn').value = flCfg.min_on_time_sec || 10;
    }
    if (document.getElementById('cfgFlashlightMaxOn')) {
      document.getElementById('cfgFlashlightMaxOn').value = flCfg.max_on_time_sec || 120;
    }
    if (document.getElementById('cfgFlashlightInactivity')) {
      document.getElementById('cfgFlashlightInactivity').value = flCfg.inactivity_timeout_sec || 15;
    }

    const audCfg = cfg.audio_detection || {};
    if (document.getElementById('cfgAudioEnabled')) {
      document.getElementById('cfgAudioEnabled').checked = audCfg.enabled !== false;
    }
    if (document.getElementById('cfgAudioSpike')) {
      document.getElementById('cfgAudioSpike').value = audCfg.spike_multiplier || 3.0;
    }
    if (document.getElementById('cfgAudioSustained')) {
      document.getElementById('cfgAudioSustained').value = audCfg.sustained_threshold_rms || 2500;
    }

    document.getElementById('cfgPreventSleep').checked = cfg.power.prevent_sleep;

    openModal(settingsModal);
  } catch (err) {
    showToast('Failed to load settings', 'danger');
  }
});

// Camera Test inside Settings
document.getElementById('cfgTestCamBtn').addEventListener('click', async () => {
  const statusSpan = document.getElementById('cfgCamTestStatus');
  statusSpan.textContent = 'Testing connection...';
  statusSpan.style.color = '#38bdf8';

  const payload = {
    phone_ip: document.getElementById('cfgPhoneIp').value.trim(),
    phone_port: parseInt(document.getElementById('cfgPhonePort').value, 10),
    video_endpoint: document.getElementById('cfgVideoEp').value.trim(),
    snapshot_endpoint: document.getElementById('cfgSnapshotEp').value.trim(),
  };

  try {
    const res = await fetch('/api/camera/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await res.json();
    if (result.success) {
      statusSpan.textContent = `✓ ${result.message}`;
      statusSpan.style.color = '#34d399';
    } else {
      statusSpan.textContent = `✗ ${result.message}`;
      statusSpan.style.color = '#f87171';
    }
  } catch (err) {
    statusSpan.textContent = `✗ Request failed: ${err.message}`;
    statusSpan.style.color = '#f87171';
  }
});

// Quick Test Camera button on main view
testCamBtn.addEventListener('click', async () => {
  showToast('Testing camera connection...', 'info');
  const ip = document.getElementById('cfgPhoneIp').value.trim() || '192.168.31.211';
  const port = parseInt(document.getElementById('cfgPhonePort').value, 10) || 8080;
  try {
    const res = await fetch('/api/camera/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ phone_ip: ip, phone_port: port }),
    });
    const r = await res.json();
    if (r.success) {
      showToast(`Camera OK: ${r.resolution} (${r.http_latency_ms}ms)`, 'info');
    } else {
      showToast(`Camera check: ${r.message}`, 'warning');
    }
  } catch (err) {
    showToast('Camera check failed', 'danger');
  }
});

// Save Settings
document.getElementById('saveSettingsBtn').addEventListener('click', async () => {
  const updates = {
    camera: {
      phone_ip: document.getElementById('cfgPhoneIp').value.trim(),
      phone_port: parseInt(document.getElementById('cfgPhonePort').value, 10),
      video_endpoint: document.getElementById('cfgVideoEp').value.trim(),
      snapshot_endpoint: document.getElementById('cfgSnapshotEp').value.trim(),
    },
    pipeline: {
      motion_fps: parseFloat(document.getElementById('cfgMotionFps').value),
      ai_fps: parseFloat(document.getElementById('cfgAiFps').value),
      motion_threshold: parseInt(document.getElementById('cfgMotionThresh').value, 10),
      detection_confidence: parseFloat(document.getElementById('cfgConfidence').value),
      auto_throttle_cpu: document.getElementById('cfgAutoThrottle').checked,
    },
    alarm: {
      sound_enabled: document.getElementById('cfgSoundEnabled').checked,
      alarm_on_general_motion: document.getElementById('cfgAlarmMotion') ? document.getElementById('cfgAlarmMotion').checked : false,
      alarm_on_unknown_objects: document.getElementById('cfgAlarmUnknown') ? document.getElementById('cfgAlarmUnknown').checked : false,
      cooldowns: {
        'Person': parseInt(document.getElementById('cfgCdPerson').value, 10),
        'Animal detected — species unconfirmed': parseInt(document.getElementById('cfgCdAnimal').value, 10),
        'Other recognized animal': parseInt(document.getElementById('cfgCdAnimal').value, 10),
        'Possible monkey': parseInt(document.getElementById('cfgCdAnimal').value, 10),
        'General motion': parseInt(document.getElementById('cfgCdMotion').value, 10),
      },
    },
    power: {
      prevent_sleep: document.getElementById('cfgPreventSleep').checked,
    },
    push: {
      enabled: document.getElementById('cfgPushEnabled').checked,
      desktop_notifications: document.getElementById('cfgPushDesktop').checked,
      browser_audio: document.getElementById('cfgPushAudio').checked,
      push_on_general_motion: document.getElementById('cfgPushMotion') ? document.getElementById('cfgPushMotion').checked : false,
      push_on_unknown_objects: document.getElementById('cfgPushUnknown') ? document.getElementById('cfgPushUnknown').checked : false,
    },
    night_mode: {
      mode: document.getElementById('cfgNightModeSelect') ? document.getElementById('cfgNightModeSelect').value : 'auto',
      auto_night_lux_threshold: parseFloat(document.getElementById('cfgNightAutoThresh').value) || 45,
      profiles: {
        day: {
          threshold: parseInt(document.getElementById('cfgDayThresh').value, 10) || 25,
          min_motion_area: parseInt(document.getElementById('cfgDayMinArea').value, 10) || 250,
        },
        night: {
          threshold: parseInt(document.getElementById('cfgNightThresh').value, 10) || 34,
          min_motion_area: parseInt(document.getElementById('cfgNightMinArea').value, 10) || 350,
        }
      }
    },
    storage: {
      retention_days: parseInt(document.getElementById('cfgRetentionDays').value, 10) || 14,
      max_storage_mb: parseInt(document.getElementById('cfgMaxStorageMb').value, 10) || 2048,
    },
    event_grouping: {
      session_timeout_sec: parseFloat(document.getElementById('cfgSessionTimeout').value) || 4.0,
      capture_initial: true,
      capture_change: document.getElementById('cfgCapChange') ? document.getElementById('cfgCapChange').checked : true,
      capture_final: document.getElementById('cfgCapFinal') ? document.getElementById('cfgCapFinal').checked : true,
    },
    flashlight: {
      mode: document.getElementById('cfgFlashlightMode') ? document.getElementById('cfgFlashlightMode').value : 'auto',
      lux_threshold: parseFloat(document.getElementById('cfgFlashlightLux').value) || 45.0,
      min_on_time_sec: parseFloat(document.getElementById('cfgFlashlightMinOn').value) || 10.0,
      max_on_time_sec: parseFloat(document.getElementById('cfgFlashlightMaxOn').value) || 120.0,
      inactivity_timeout_sec: parseFloat(document.getElementById('cfgFlashlightInactivity').value) || 15.0,
    },
    audio_detection: {
      enabled: document.getElementById('cfgAudioEnabled') ? document.getElementById('cfgAudioEnabled').checked : true,
      spike_multiplier: parseFloat(document.getElementById('cfgAudioSpike').value) || 3.0,
      sustained_threshold_rms: parseFloat(document.getElementById('cfgAudioSustained').value) || 2500.0,
    },
  };

  const newPin = document.getElementById('cfgNewPin').value.trim();
  if (newPin) {
    updates.server = { dashboard_pin: newPin };
  }

  try {
    const res = await apiFetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (res.ok) {
      pushEnabled = document.getElementById('cfgPushEnabled').checked;
      pushDesktop = document.getElementById('cfgPushDesktop').checked;
      pushAudio = document.getElementById('cfgPushAudio').checked;
      localStorage.setItem('wheat_watch_push_enabled', pushEnabled ? 'true' : 'false');
      localStorage.setItem('wheat_watch_push_desktop', pushDesktop ? 'true' : 'false');
      localStorage.setItem('wheat_watch_push_audio', pushAudio ? 'true' : 'false');
      updatePushUI();

      showToast('Settings saved successfully!', 'info');
      closeModal(settingsModal);
      fetchStatus();
    } else {
      const err = await res.json();
      showToast(err.detail || 'Failed to save settings', 'danger');
    }
  } catch (err) {
    showToast('Error saving settings', 'danger');
  }
});

// --- Dual-Mode Live Video Player (MJPEG + Canvas Fallback) ---
const liveStreamImg = document.getElementById('liveStreamImg');
const liveCanvas = document.getElementById('liveCanvas');
const modeMjpegBtn = document.getElementById('modeMjpegBtn');
const modeCanvasBtn = document.getElementById('modeCanvasBtn');
const modeDirectPhoneLink = document.getElementById('modeDirectPhoneLink');

let currentStreamMode = 'mjpeg'; // 'mjpeg' or 'canvas'
let canvasLoopRunning = false;
let canvasReqId = null;
const canvasCtx = liveCanvas ? liveCanvas.getContext('2d') : null;

function setStreamMode(mode) {
  currentStreamMode = mode;
  if (mode === 'mjpeg') {
    modeMjpegBtn.classList.add('active');
    modeCanvasBtn.classList.remove('active');
    liveStreamImg.style.display = 'block';
    liveCanvas.style.display = 'none';
    stopCanvasLoop();
    liveStreamImg.src = `/api/stream/live?t=${Date.now()}`;
    showToast('Switched to Live MJPEG Stream', 'info');
  } else {
    modeCanvasBtn.classList.add('active');
    modeMjpegBtn.classList.remove('active');
    liveStreamImg.style.display = 'none';
    liveCanvas.style.display = 'block';
    startCanvasLoop();
    showToast('Switched to Direct Fast Refresh (Safe Mode)', 'info');
  }
}

if (modeMjpegBtn) modeMjpegBtn.addEventListener('click', () => setStreamMode('mjpeg'));
if (modeCanvasBtn) modeCanvasBtn.addEventListener('click', () => setStreamMode('canvas'));

function startCanvasLoop() {
  if (canvasLoopRunning) return;
  canvasLoopRunning = true;

  let isFetching = false;
  const offscreenImg = new Image();

  offscreenImg.onload = () => {
    if (liveCanvas.width !== offscreenImg.naturalWidth) {
      liveCanvas.width = offscreenImg.naturalWidth;
      liveCanvas.height = offscreenImg.naturalHeight;
    }
    if (canvasCtx) {
      canvasCtx.drawImage(offscreenImg, 0, 0);
    }
    isFetching = false;
  };

  offscreenImg.onerror = () => {
    isFetching = false;
  };

  function renderFrame() {
    if (!canvasLoopRunning) return;
    if (!isFetching) {
      isFetching = true;
      offscreenImg.src = `/api/stream/snapshot?t=${Date.now()}`;
    }
    // Schedule next frame (~15 FPS)
    setTimeout(() => {
      canvasReqId = requestAnimationFrame(renderFrame);
    }, 65);
  }

  canvasReqId = requestAnimationFrame(renderFrame);
}

function stopCanvasLoop() {
  canvasLoopRunning = false;
  if (canvasReqId) {
    cancelAnimationFrame(canvasReqId);
    canvasReqId = null;
  }
}

// Auto-Detection: If MJPEG image fails to load or naturalWidth is 0 after 2 seconds
// (Common in Brave browser with shields / tracker blocking), auto-switch to Fast Refresh!
setTimeout(() => {
  if (currentStreamMode === 'mjpeg' && (!liveStreamImg.complete || liveStreamImg.naturalWidth === 0)) {
    console.warn('MJPEG stream not rendering (Brave Shields or browser security). Auto-switching to Fast Refresh mode.');
    setStreamMode('canvas');
  }
}, 2500);

liveStreamImg.onerror = () => {
  console.warn('liveStreamImg error detected.');
  if (currentStreamMode === 'mjpeg') {
    setStreamMode('canvas');
  }
};

// Update Direct Phone link with actual IP from config
function updatePhoneStreamLink(camUrl) {
  if (modeDirectPhoneLink && camUrl) {
    modeDirectPhoneLink.href = camUrl;
  }
}

// Flashlight History Toggle Listener
if (toggleFlashlightLogBtn && flashlightLogContainer) {
  toggleFlashlightLogBtn.addEventListener('click', () => {
    const isHidden = flashlightLogContainer.style.display === 'none';
    flashlightLogContainer.style.display = isHidden ? 'block' : 'none';
    toggleFlashlightLogBtn.textContent = isHidden ? '🔼 Hide History' : '📜 Toggle History';
  });
}

// Test Audio Trigger Listener
if (testAudioBtn) {
  testAudioBtn.addEventListener('click', async () => {
    try {
      const res = await apiFetch('/api/microphone/test', { method: 'POST' });
      if (res.ok) {
        showToast('Synthetic Phone Microphone Activity Triggered (2.0s)!', 'info');
        fetchStatus();
      } else {
        const data = await res.json();
        showToast(data.detail || 'Failed to trigger audio test', 'danger');
      }
    } catch (e) {
      showToast('Audio test request failed', 'danger');
    }
  });
}

// Diagnostics Modal Opener & Population
if (diagnosticsBtn && diagnosticsModal) {
  diagnosticsBtn.addEventListener('click', () => {
    populateDiagnosticsModal(latestDiagnosticsData);
    openModal(diagnosticsModal);
  });
}

function populateDiagnosticsModal(data) {
  if (!data) return;
  const cam = data.camera || {};
  const mic = data.microphone || {};
  const fl = data.flashlight || {};
  const metrics = data.metrics || {};
  const storage = data.storage || {};

  // Camera Subsystem
  const diagCamState = document.getElementById('diagCamState');
  if (diagCamState) {
    diagCamState.textContent = cam.state || 'OFFLINE';
    diagCamState.style.color = cam.is_connected ? '#34d399' : '#f87171';
  }
  const diagCamUrl = document.getElementById('diagCamUrl');
  if (diagCamUrl) diagCamUrl.textContent = cam.video_url || '--';
  const diagCamRes = document.getElementById('diagCamRes');
  if (diagCamRes) diagCamRes.textContent = cam.resolution ? `${cam.resolution[0]}x${cam.resolution[1]}` : '--';
  const diagCamFps = document.getElementById('diagCamFps');
  if (diagCamFps) diagCamFps.textContent = `${cam.fps || 0} FPS`;
  const diagCamLatency = document.getElementById('diagCamLatency');
  if (diagCamLatency) diagCamLatency.textContent = `${cam.latency_ms || 0} ms`;
  const diagCamReconnects = document.getElementById('diagCamReconnects');
  if (diagCamReconnects) diagCamReconnects.textContent = cam.reconnect_attempts || 0;

  // Phone Mic Subsystem
  const diagMicState = document.getElementById('diagMicState');
  if (diagMicState) {
    diagMicState.textContent = mic.is_connected ? 'CONNECTED' : 'DISCONNECTED';
    diagMicState.style.color = mic.is_connected ? '#34d399' : '#f87171';
  }
  const diagMicUrl = document.getElementById('diagMicUrl');
  if (diagMicUrl) diagMicUrl.textContent = mic.stream_url || '--';
  const diagMicFormat = document.getElementById('diagMicFormat');
  if (diagMicFormat) diagMicFormat.textContent = `${(mic.sample_rate || 16000)/1000}kHz 16-bit ${mic.channels === 1 ? 'Mono' : 'Stereo'} PCM`;
  const diagMicRms = document.getElementById('diagMicRms');
  if (diagMicRms) diagMicRms.textContent = `${mic.current_rms || 0} RMS`;
  const diagMicFloor = document.getElementById('diagMicFloor');
  if (diagMicFloor) diagMicFloor.textContent = `${mic.noise_floor || 1200} (SNR: ${mic.snr || 1.0}x)`;

  // Flashlight Subsystem
  const diagFlashMode = document.getElementById('diagFlashMode');
  if (diagFlashMode) diagFlashMode.textContent = (fl.mode || 'auto').toUpperCase();
  const diagFlashHw = document.getElementById('diagFlashHw');
  if (diagFlashHw) {
    diagFlashHw.textContent = fl.is_on ? 'ON' : 'OFF';
    diagFlashHw.style.color = fl.is_on ? '#fbbf24' : 'inherit';
  }
  const diagFlashReq = document.getElementById('diagFlashReq');
  if (diagFlashReq) diagFlashReq.textContent = fl.requested_state ? 'ON' : 'OFF';
  const diagFlashLight = document.getElementById('diagFlashLight');
  if (diagFlashLight) diagFlashLight.textContent = fl.lighting_condition || 'UNKNOWN';
  const diagFlashResult = document.getElementById('diagFlashResult');
  if (diagFlashResult) diagFlashResult.textContent = fl.last_command_result || 'IDLE';

  // Host Resources
  const diagCpuPct = document.getElementById('diagCpuPct');
  if (diagCpuPct) diagCpuPct.textContent = `${metrics.cpu_percent || 0}%`;
  const diagRamPct = document.getElementById('diagRamPct');
  if (diagRamPct) diagRamPct.textContent = `${metrics.ram_used_mb || 0} MB (${metrics.ram_percent || 0}%)`;
  const diagProcFps = document.getElementById('diagProcFps');
  if (diagProcFps) diagProcFps.textContent = `${metrics.processing_fps || 0} FPS`;
  const diagThrottle = document.getElementById('diagThrottle');
  if (diagThrottle) diagThrottle.textContent = metrics.is_throttling ? 'YES (High CPU)' : 'No';

  // Storage
  const diagDbRows = document.getElementById('diagDbRows');
  if (diagDbRows) diagDbRows.textContent = `${data.summary ? data.summary.total_events : (storage.events_count || 14)} records`;
  const diagStorageCount = document.getElementById('diagStorageCount');
  if (diagStorageCount) diagStorageCount.textContent = `${storage.image_count || 0} snapshots`;
  const diagStorageMb = document.getElementById('diagStorageMb');
  if (diagStorageMb) diagStorageMb.textContent = `${storage.total_size_mb || 0} MB / ${storage.max_storage_mb || 2048} MB (${storage.percent_used || 0}%)`;

  const diagPushClients = document.getElementById('diagPushClients');
  if (diagPushClients) diagPushClients.textContent = 'Active';
}

// Initializations
updatePushUI();
initPushStream();
setViewMode(currentViewMode);

// Polling loops
fetchStatus();
fetchEvents();
setInterval(fetchStatus, 1500);
setInterval(fetchEvents, 3000);
